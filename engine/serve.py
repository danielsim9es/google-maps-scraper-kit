#!/usr/bin/env python3
"""The kit's own engine: the Google Maps scraper's HTTP API and web UI, on this machine only.

    python3 engine/serve.py               # port from SCRAPER_PORT (environment, then .env), default 8080
    python3 engine/serve.py --port 8190

Normally started by `python3 scripts/engine.py start`, or by `docker compose up -d` (the Dockerfile). It speaks the API of the engine the kit used
before (POST/GET/DELETE /api/v1/jobs, /api/v1/jobs/{id}/download, the same job body and "Status"
values), so scripts/scrape.py, the skill and the slash commands work unchanged; jobs also carry Error
and Progress, resume after a restart, and download as CSV or JSON. It listens on
127.0.0.1 (and ::1) only, or on 0.0.0.0 inside the Docker image, where Docker publishes the port on
the host's 127.0.0.1 only. Either way it refuses a foreign Host (DNS rebinding, 421) or Origin (cross-site
posts, 403); with SCRAPER_API_KEY set it also wants that X-API-Key (401). No telemetry: it talks to
Google Maps, for email or socials jobs to the businesses' own websites, and for verify_emails jobs
to Google's public DNS (dns.google), nothing else.
Standard library only.
"""
import argparse, csv, gzip, hmac, html, io, json, os, re, secrets, signal, socket, socketserver, sqlite3, sys, threading, unicodedata, zlib
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser, jobs, dashboard_api  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # ✓ and accented names on a Windows cp1252 console
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

VERSION = "2.2.0"
MARK = f"gmskit-engine/{VERSION}"  # X-Engine header: tells scripts/engine.py this engine from others
REPO = "https://github.com/Mahanaicoach/google-maps-scraper-kit"
# The web UI's sponsor box: the browser reads this static file from GitHub (cached a day, no
# tracking), so the sponsors it lists change without anyone updating their copy of the kit.
SPONSORS = "https://raw.githubusercontent.com/Mahanaicoach/google-maps-scraper-kit/master/assets/sponsors/sponsors.json"
# The web UI's update notice: the browser asks GitHub for the kit's latest release once a day (a
# public JSON endpoint, nothing about the user in the request) and shows a line when it is newer
# than this copy. Nothing updates itself: the line says to run scripts/update.sh.
RELEASES = "https://api.github.com/repos/Mahanaicoach/google-maps-scraper-kit/releases/latest"
# The web UI's What and Where boxes offer only these, so nobody searches for a business type or a
# place that does not exist: presets/business-types.json (hand-picked; add a niche there) and
# presets/cities.tsv.gz (GeoNames cities1000, CC BY 4.0: name, region, country code, lat, lon, biggest first).
# What also offers Google Business Profile's category names (4,053, US English) from
# lobstrio/google-business-categories, pinned to one commit. The browser loads that list from GitHub,
# like the sponsor box; the kit ships no copy, because that repository has no licence file.
CATEGORIES = ("https://raw.githubusercontent.com/lobstrio/google-business-categories/"
              "4ee1c4788d07c812a32986177c2a51c28957062f/data/google-business-categories.txt")
PRESETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")


def load_types(folder=None):
    """The What list; [] with one warning when the file is missing or broken, so the API and the scripts
    still work (only the web UI's What box is empty)."""
    try:
        with open(os.path.join(folder or PRESETS, "business-types.json"), encoding="utf-8") as f:
            types = json.load(f)
        if not isinstance(types, list) or not all(isinstance(t, str) for t in types):
            raise ValueError("not a list of names")
        return types
    except (OSError, ValueError) as e:
        print(f"presets/business-types.json unusable ({e.__class__.__name__}): the What box will be empty", file=sys.stderr)
        return []


TYPES = load_types()
TYPES_JS = json.dumps(TYPES).replace("</", "<\\/")  # the What list, inlined in the page script
_cities, _cities_lock = None, threading.Lock()
ENV_KEYS = ("SCRAPER_PORT", "SCRAPER_API_KEY", "SCRAPER_HEADLESS")
MAX_BODY = 1 << 20
LOCAL = r"(localhost|127\.0\.0\.1|\[::1\])"
HOST_OK = re.compile(rf"^{LOCAL}(:\d{{1,5}})?$", re.I)
ORIGIN_OK = re.compile(rf"^https?://{LOCAL}(:\d{{1,5}})?$", re.I)
JOB_PATH = re.compile(r"^/api/v1/jobs/([0-9a-f-]{36})(/download)?$")
JOB_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_log_lock = threading.Lock()
_REPLIED = object()  # body() answered the request itself (a bad body)


def file_name(job, jid):
    """"bakery-in-portland-or-c063a815": the job's search, then the start of its id; the web UI names
    its downloads the same way (fileName in PAGE)."""
    s = unicodedata.normalize("NFKD", (job or {}).get("Name") or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return (re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "results") + "-" + jid[:8]


FOLD = str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ı": "i", "ß": "ss", "æ": "ae", "œ": "oe", "þ": "th"})


def fold(s):
    """"sao paulo sp br" for "São Paulo, SP, BR": accents dropped (also ł, ø, ı...), lower case, punctuation
    as single spaces."""
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower().translate(FOLD)) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[\W_]+", " ", s).split())


def cities():
    """Every city as one "folded label<TAB>label<TAB>lat<TAB>lon<TAB>country" line, biggest first. Read on the
    first lookup, then kept (about 35 MB)."""
    global _cities
    with _cities_lock:
        if _cities is None:
            rows = []
            try:
                with gzip.open(os.path.join(PRESETS, "cities.tsv.gz"), "rt", encoding="utf-8") as f:
                    for line in f:
                        name, admin, cc, lat, lon = line.rstrip("\n").split("\t")
                        label = ", ".join([name] + ([admin] if admin and admin != name else []) + [cc])
                        rows.append("\t".join((fold(label), label, lat, lon, cc)))
            except (OSError, EOFError, ValueError, zlib.error) as e:  # missing, truncated, corrupt or odd file: what was read, once
                log(f"presets/cities.tsv.gz unusable after {len(rows)} cities ({e.__class__.__name__})")
            _cities = rows
    return _cities


def find_cities(q, limit=20):
    """The biggest cities whose "name, region, country" starts with q; with no q, the biggest in the US."""
    raw, q, out = q.strip(), fold(q), []
    if raw and not q:  # punctuation only: nothing can start with it
        return out
    for row in cities():  # ponytail: a linear scan, about 30 ms; a prefix index if lookups ever lag
        if row.startswith(q) if q else row.endswith("\tUS"):
            _, label, lat, lon, cc = row.split("\t")
            out.append({"label": label, "lat": lat, "lon": lon, "country": cc})
            if len(out) == limit:
                break
    return out


def log(msg):
    """One line on stderr with a UTC timestamp and its offset. Counts only, never scraped values.
    A log that cannot be written (full disk, closed stderr) is dropped, never raised."""
    with _log_lock:
        try:
            print(f"{jobs.utc_now()} {msg}", file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass


def env_value(v):
    """A .env value: quotes stripped, a trailing " # comment" dropped unless it sits inside the quotes
    (then docker compose keeps it too). Same rule as scripts/scrape.py."""
    v = v.strip()
    if v[:1] in ("\"", "'") and v[0] in v[1:]:
        return v[1:v.index(v[0], 1)]
    return v.split(" #", 1)[0].strip()


def read_env():
    """SCRAPER_PORT, SCRAPER_API_KEY and SCRAPER_HEADLESS: the environment wins, then the kit's .env (last line wins,
    as in docker compose and scripts/scrape.py)."""
    found = {}
    try:
        with open(os.path.join(browser.KIT, ".env"), encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                k, sep, v = line.strip().removeprefix("export ").partition("=")
                if sep and k.strip() in ENV_KEYS:
                    found[k.strip()] = env_value(v)
    except OSError:
        pass
    return {k: os.environ.get(k, found.get(k, "")) for k in ENV_KEYS}


JOB_PROPS = {
    "name": {"type": "string", "description": "any label"},
    "keywords": {"type": "array", "items": {"type": "string"}, "description": "searches, run one after another"},
    "lang": {"type": "string", "description": "2-letter interface language, e.g. en (category names, hours text)"},
    "country": {"type": "string", "description": "2-letter country Google ranks and formats results for, e.g. us "
                                                 "(default: the country of this machine's IP)"},
    "lat": {"type": "string", "description": "the map's centre, e.g. \"30.2672\"; send lat and lon both, or neither "
                                             "(then Google places the search by the keyword, e.g. \"cafes in Austin TX\")"},
    "lon": {"type": "string", "description": "e.g. \"-97.7431\""},
    "max_time": {"type": "integer", "description": "seconds"},
    "depth": {"type": "integer", "description": "result batches per keyword, about 20 places each (default 1)"},
    "zoom": {"type": "integer", "description": "map zoom 1-21 (default 15)"},
    "email": {"type": "boolean", "description": "visit each website's homepage for emails"},
    "verify_emails": {"type": "boolean", "description": "with email: check each address's domain over DNS (dns.google), "
                                                       "drop domains that do not exist, add email_host"},
    "browser_sites": {"type": "boolean", "description": "optional Playwright retry when HTTP finds no email or social links; adds website_fetch_status"},
    "socials": {"type": "boolean", "description": "visit each website's homepage for Instagram, Facebook, LinkedIn, "
                                                 "TikTok, YouTube and X links"},
    "reviews_max": {"type": "integer", "description": "0-5 reviews per place from its panel, one page load per place (headless supported)"},
    "proxies": {"type": "array", "items": {"type": "string"},
                "description": "http(s)://[user:pass@]host:port or socks5://host:port; one per keyword in turn, "
                               "and the next one when Google refuses a keyword"},
    "radius": {"type": "integer", "description": "accepted, not used"},
    "fast_mode": {"type": "boolean", "description": "accepted, not used"},
}
OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Google Maps Scraper Kit engine", "version": VERSION,
             "description": "Local only. Create a job, poll its Status until ok or failed (Progress says how far "
                            "it is), download the CSV or JSON. A job the engine was stopped in the middle of "
                            f"resumes from its last finished keyword on the next start. Source and docs: {REPO}"},
    "paths": {
        "/api/v1/jobs": {
            "get": {"summary": "List jobs, newest first (null when there are none)"},
            "post": {"summary": "Create a job; returns 201 {\"id\": \"<uuid>\"}, or 422 {\"code\", \"message\"}",
                     "requestBody": {"content": {"application/json": {"schema": {
                         "type": "object", "required": ["name", "keywords", "lang", "max_time"],
                         "properties": JOB_PROPS}}}}}},
        "/api/v1/jobs/{id}": {
            "get": {"summary": "One job: ID, Name, Date, Status (pending, working, ok, failed), Data (proxy "
                               "passwords masked), Error, Progress (keywords_done, keywords_total, places, percent, "
                               "stage: queued, search, reviews, websites or done)"},
            "delete": {"summary": "Delete a job and its results (stops it if it is running)"}},
        "/api/v1/jobs/{id}/download": {"get": {"summary": "The job's CSV, the rows so far while it works; "
                                                          "?format=json for a JSON array of the same rows"}},
        "/api/v1/cities": {"get": {"summary": "Up to 20 cities for the web UI's Where box, each {label, lat, lon, "
                                              "country}: ?q=aus gives the biggest whose \"name, region, country\" "
                                              "starts with it, no q the biggest US cities (GeoNames, CC BY 4.0)"}},
        "/api/openapi.json": {"get": {"summary": "This description as OpenAPI JSON (the page at /api/docs shows it)"}},
    },
}


OPENAPI["paths"].update({
    "/api/v1/dashboard": {"get": {"summary": "Consolidated dashboard KPIs, paginated leads and map points. Reads existing local CSV jobs."}},
    "/api/v1/dashboard/summary": {"get": {"summary": "Filtered summary, categories, coverage and job counts."}},
    "/api/v1/dashboard/leads": {"get": {"summary": "Filtered, deduplicated and paginated collected businesses."}},
    "/api/v1/dashboard/geojson": {"get": {"summary": "GeoJSON feature collection, maximum 700 mapped businesses."}},
    "/api/v1/dashboard/export": {"get": {"summary": "Download filtered CSV or JSON; ?format=csv|json."}},
})


# Resumo de documentação em português; preserva IDs e contratos da API.
OPENAPI["info"]["title"] = "API do Google Maps Scraper Kit"
OPENAPI["info"]["description"] = ("API local. Crie coletas, acompanhe a situação e baixe resultados em CSV ou JSON. " "As tarefas interrompidas podem ser retomadas. Fonte: " + REPO)
OPENAPI["paths"]["/api/v1/jobs"]["get"]["summary"] = "Lista as coletas, da mais recente para a mais antiga (null quando vazia)."
OPENAPI["paths"]["/api/v1/jobs"]["post"]["summary"] = "Cria uma coleta: retorna 201 com id; erros de validação retornam 422."
OPENAPI["paths"]["/api/v1/jobs/{id}"]["get"]["summary"] = "Detalhes da coleta: ID, nome, data, situação, parâmetros, erros e progresso."
OPENAPI["paths"]["/api/v1/jobs/{id}"]["delete"]["summary"] = "Exclui a coleta e seus resultados e interrompe a execução, quando estiver em andamento."
OPENAPI["paths"]["/api/v1/jobs/{id}/download"]["get"]["summary"] = "Baixa o CSV da coleta, inclusive resultados parciais; use ?format=json para receber JSON."
OPENAPI["paths"]["/api/v1/cities"]["get"]["summary"] = "Consulta de cidades para a seleção de localidades: filtro por prefixo no parâmetro q."
OPENAPI["paths"]["/api/openapi.json"]["get"]["summary"] = "Especificação OpenAPI JSON da aplicação."
OPENAPI["paths"]["/api/v1/dashboard"]["get"]["summary"] = "Indicadores, empresas paginadas e pontos de mapa com base nas coletas locais."
OPENAPI["paths"]["/api/v1/dashboard/summary"]["get"]["summary"] = "Resumo filtrado, segmentos, cobertura de dados e total de coletas."
OPENAPI["paths"]["/api/v1/dashboard/leads"]["get"]["summary"] = "Empresas coletadas, deduplicadas, filtradas e paginadas."
OPENAPI["paths"]["/api/v1/dashboard/geojson"]["get"]["summary"] = "Pontos de empresas em GeoJSON, até 700 por visualização."
OPENAPI["paths"]["/api/v1/dashboard/export"]["get"]["summary"] = "Exporta registros filtrados como CSV ou JSON; ?format=csv|json."
JOB_PROPS["name"]["description"] = "Nome da coleta"
JOB_PROPS["keywords"]["description"] = "Lista de termos executados em sequência"
JOB_PROPS["lang"]["description"] = "Idioma da pesquisa com duas letras, por exemplo pt"
JOB_PROPS["country"]["description"] = "País com duas letras, por exemplo br"
JOB_PROPS["lat"]["description"] = "Latitude do centro da pesquisa"
JOB_PROPS["lon"]["description"] = "Longitude do centro da pesquisa"
JOB_PROPS["max_time"]["description"] = "Tempo máximo da tarefa, em segundos"
JOB_PROPS["depth"]["description"] = "Etapas de resultados por termo"
JOB_PROPS["zoom"]["description"] = "Nível de zoom do mapa (1 a 21)"
JOB_PROPS["email"]["description"] = "Pesquisar e-mails nos sites das empresas"
JOB_PROPS["verify_emails"]["description"] = "Verificar DNS/MX dos domínios de e-mail e incluir email_host"
JOB_PROPS["browser_sites"]["description"] = "Usar Playwright opcionalmente para sites com JavaScript"
JOB_PROPS["socials"]["description"] = "Pesquisar links de redes sociais nos sites"
JOB_PROPS["reviews_max"]["description"] = "Avaliações por empresa, de 0 a 5"
JOB_PROPS["proxies"]["description"] = "Lista de servidores proxy usados na pesquisa"
JOB_PROPS["radius"]["description"] = "Aceito, porém não utilizado"
JOB_PROPS["fast_mode"]["description"] = "Aceito, porém não utilizado"

def docs_page(nonce):
    """/api/docs: OPENAPI as a plain HTML page (no scripts, nothing loaded from elsewhere)."""
    e = html.escape
    out = [f"<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Documentação da API</title>"
           f"<style nonce=\"{nonce}\">:root {{ color-scheme: light dark; }} body {{ margin: 0 auto; max-width: 960px; "
           "padding: 16px; font: 15px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }} code {{ font-size: .95em; }} "
           "table {{ width: 100%; border-collapse: collapse; }} th, td {{ text-align: left; vertical-align: top; "
           "padding: 4px 6px; border-bottom: 1px solid #8884; }} .m {{ font-weight: 600; }}</style></head><body>",
           f"<h1>{e(OPENAPI['info']['title'])} {e(VERSION)}</h1><p>{e(OPENAPI['info']['description'])}</p>",
           "<p><a href=\"/\">Coletor</a> · <a href=\"/api/openapi.json\">OpenAPI JSON</a> · "
           "Quando SCRAPER_API_KEY estiver configurada, envie-a no cabeçalho <code>X-API-Key</code>.</p>"]
    for path, ops in OPENAPI["paths"].items():
        for method, op in ops.items():
            out.append(f"<h2><span class=\"m\">{e(method.upper())}</span> <code>{e(path)}</code></h2><p>{e(op['summary'])}</p>")
            schema = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            if schema:
                out.append("<table><tr><th>Campo</th><th>Tipo</th><th>Obrigatório</th><th>Descrição</th></tr>")
                for name, prop in schema["properties"].items():
                    out.append(f"<tr><td><code>{e(name)}</code></td><td>{e(prop['type'])}</td>"
                               f"<td>{'sim' if name in schema['required'] else ''}</td>"
                               f"<td>{e(prop.get('description', ''))}</td></tr>")
                out.append("</table>")
    out.append("</body></html>")
    return "".join(out)


PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Google Maps Scraper Kit — Coletor de empresas</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Cpath fill=%27%230b7a5b%27 d=%27M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z%27/%3E%3C/svg%3E">
<style nonce="{nonce}">
:root {{ color-scheme: light dark; --paper: #f5f3ee; --sheet: #fffdf8; --ink: #17191c; --soft: #5b5f66; --rule: #dcd8ce;
  --go: #0b7a5b; --go-ink: #fff; --ring: #2f8f73; --bad: #b42318; --tag: #8a5a00; --alt: #3d5a80; --star: #f1c21b; --heart: #ea4aaa;
  --serif: ui-serif, "New York", Charter, "Iowan Old Style", Georgia, serif;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}
@media (prefers-color-scheme: dark) {{ :root {{ --paper: #111312; --sheet: #181b19; --ink: #ebe8e1; --soft: #a3a69f;
  --rule: #2c312d; --go: #46c49a; --go-ink: #0b1410; --ring: #7fdcbc; --bad: #ff8a7a; --tag: #e7b45a; --alt: #8fb3de; --star: #9a6700; --heart: #bf3989; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.5 var(--sans); }}
main {{ max-width: 860px; margin: 0 auto; padding: 0 20px 64px; }}
a {{ color: inherit; text-underline-offset: 3px; }} a:hover {{ color: var(--go); }}
.top {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px 16px;
  padding: 28px 0 14px; border-bottom: 2px solid var(--ink); }}
h1 {{ margin: 0; font: 600 1.6rem/1.2 var(--serif); letter-spacing: -.01em; }}
.top nav {{ display: flex; gap: 16px; font-size: .9rem; color: var(--soft); }}
.mono {{ font-family: var(--mono); font-size: .85em; }} .soft {{ color: var(--soft); font-size: .875rem; }}
.update {{ margin-top: 14px; padding: 10px 14px; border: 1px solid var(--rule); border-radius: 10px; background: var(--sheet); font-size: .9rem; }}
.update code {{ font-size: .85rem; }}
.stars {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding-top: 16px; color: var(--soft); font-size: .9rem; }}
.gh {{ display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 8px 14px; border-radius: 8px;
  color: var(--paper); background: var(--ink); font-size: .9rem; font-weight: 600; text-decoration: none; transition: filter .15s; }}
.gh:hover {{ color: var(--paper); filter: brightness(1.3); }} .gh .star {{ color: var(--star); }} .gh .heart {{ color: var(--heart); }}
.sponsors {{ position: relative; margin-top: 16px; padding: 16px 16px 14px; background: var(--sheet);
  border: 1px solid var(--rule); border-radius: 12px; }}
.sp-close {{ position: absolute; top: 6px; right: 6px; min-height: 36px; width: 36px; padding: 0; border: 0;
  background: transparent; color: var(--soft); font-size: 1.3rem; line-height: 1; }}
.sp-close:hover {{ color: var(--ink); }}
.sp-head {{ margin: 0 40px 4px 0; color: var(--soft); font-size: .85rem; }}
.sp-ask {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin: 12px 0 0; padding-top: 12px;
  border-top: 1px solid var(--rule); color: var(--soft); font-size: .9rem; }}
.sp-grid[hidden] + .sp-ask {{ margin: 0; padding: 0 40px 0 0; border: 0; }}  /* no paid sponsor loaded: the ask alone */
.sp-grid {{ display: grid; gap: 4px 16px; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }}
.sp {{ display: flex; align-items: center; gap: 14px; min-height: 64px; padding: 10px; margin: 0 -10px; color: var(--ink);
  text-decoration: none; border-radius: 10px; transition: background-color .15s; }}
.sp:hover {{ color: var(--ink); background: var(--paper); }}
.sp-mark {{ flex: none; display: grid; place-items: center; width: 42px; height: 42px; border-radius: 10px;
  color: var(--sheet); background: var(--brand, var(--go)); font: 700 1.15rem/1 var(--serif); }}
.sp:nth-child(2) .sp-mark {{ background: var(--brand, var(--ink)); }} .sp:nth-child(3) .sp-mark {{ background: var(--brand, var(--tag)); }}
.sp:nth-child(4) .sp-mark {{ background: var(--brand, var(--alt)); }}  /* neutral per tile, never a guessed brand colour */
.sp-body {{ display: grid; gap: 2px; min-width: 0; }} .sp-body b {{ font: 600 1.02rem/1.25 var(--serif); }}
.sp-line {{ display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden;
  color: var(--soft); font-size: .85rem; line-height: 1.4; }}
.sp-go {{ flex: none; margin-left: auto; color: var(--soft); transition: transform .15s, color .15s; }}
.sp:hover .sp-go {{ color: var(--go); transform: translate(2px, -2px); }}
h2 {{ margin: 0 0 12px; font: 600 1.15rem/1.3 var(--serif); }}
section {{ padding: 28px 0 0; }}
form {{ display: grid; gap: 14px; }}
.sr {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
.ww {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
.pick {{ display: grid; gap: 6px; align-content: start; }}
.search {{ display: flex; align-items: center; gap: 10px; padding: 6px 14px; background: var(--sheet);
  border: 1.5px solid var(--ink); border-radius: 14px; box-shadow: 0 1px 0 var(--rule); }}
.search:focus-within {{ outline: 3px solid var(--ring); outline-offset: 2px; }}
.search svg {{ flex: none; color: var(--go); }}
.search input {{ flex: 1; padding: 0; border: 0; outline: 0; background: transparent; font-size: 1.05rem; }}
.box {{ position: relative; }}
.opts {{ position: absolute; z-index: 5; left: 0; right: 0; top: calc(100% + 4px); max-height: 280px; overflow-y: auto;
  margin: 0; padding: 4px; list-style: none; background: var(--sheet); border: 1px solid var(--rule); border-radius: 10px;
  box-shadow: 0 8px 24px rgb(0 0 0 / .14); }}
.opts li {{ padding: 9px 10px; border-radius: 6px; cursor: pointer; }}
.opts li:hover, .opts li[aria-selected=true] {{ background: color-mix(in srgb, var(--go) 12%, var(--sheet)); }}
.tags:empty {{ display: none; }}
.tag {{ min-height: 36px; padding: 6px 12px; border-color: var(--go); border-radius: 999px;
  background: color-mix(in srgb, var(--go) 10%, var(--sheet)); }}
.hint {{ margin: -6px 2px 0; }}
label {{ display: grid; gap: 6px; font-size: .9rem; font-weight: 600; }}
input {{ font: inherit; font-weight: 400; min-height: 44px; width: 100%; padding: 9px 12px; color: var(--ink);
  background: var(--sheet); border: 1px solid var(--rule); border-radius: 8px; }}
input:hover {{ border-color: var(--soft); }}
input[type=number] {{ font-family: var(--mono); font-size: .95rem; }}
textarea {{ font: inherit; }}
.collect {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; border: 0; }}
.collect legend {{ float: left; margin-right: 6px; padding: 12px 0; font-size: .9rem; color: var(--soft); }}
.chip {{ display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 14px; font-weight: 500;
  border: 1px solid var(--rule); border-radius: 999px; background: var(--sheet); cursor: pointer; transition: border-color .15s, background-color .15s; }}
.chip:hover {{ border-color: var(--soft); }}
.chip:has(input:checked) {{ border-color: var(--go); background: color-mix(in srgb, var(--go) 10%, var(--sheet)); }}
.chip input {{ width: 18px; height: 18px; min-height: 0; margin: 0; accent-color: var(--go); cursor: pointer; }}
details {{ border-top: 1px solid var(--rule); }} details:last-of-type {{ border-bottom: 1px solid var(--rule); }}
summary {{ list-style: none; display: flex; align-items: center; justify-content: space-between; min-height: 48px;
  font-weight: 600; cursor: pointer; }}
summary::-webkit-details-marker {{ display: none; }}
summary::after {{ content: "+"; font: 400 1.4rem/1 var(--mono); color: var(--soft); }}
details[open] summary::after {{ content: "\\2212"; }}
summary:hover {{ color: var(--go); }}
.body {{ display: grid; gap: 12px; align-items: start; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); padding: 2px 0 18px; }}
.body .soft {{ font-weight: 400; }} .wide {{ grid-column: 1 / -1; }}
.body .chip {{ border-radius: 10px; font-weight: 400; }}
.body textarea {{ min-height: 84px; padding: 9px 12px; color: var(--ink); background: var(--sheet); border: 1px solid var(--rule);
  border-radius: 8px; font: .9rem/1.5 var(--mono); resize: vertical; }}
.go {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding-top: 4px; }}
button {{ font: inherit; min-height: 40px; padding: 8px 14px; color: var(--ink); background: var(--sheet);
  border: 1px solid var(--rule); border-radius: 8px; cursor: pointer; transition: border-color .15s, filter .15s; }}
button:hover {{ border-color: var(--ink); }}
.collect-choice {{ display: flex; align-items: center; gap: 6px; }}
button.info-button {{ width: 40px; min-height: 40px; padding: 0; border-radius: 50%; font-weight: 700;
  color: var(--soft); }}
.info-note[popover] {{ width: min(360px, calc(100vw - 40px)); padding: 20px; border: 1px solid var(--rule);
  border-radius: 12px; background: var(--sheet); color: var(--ink); line-height: 1.6;
  box-shadow: 0 12px 40px #0003; }}
.info-note p {{ margin: 8px 0 0; }}

button.primary {{ min-height: 48px; padding: 10px 26px; color: var(--go-ink); background: var(--go); border-color: var(--go);
  font-weight: 650; letter-spacing: .01em; }}
button.primary:hover {{ filter: brightness(1.08); }} button:disabled {{ opacity: .6; cursor: progress; }}
:focus-visible {{ outline: 3px solid var(--ring); outline-offset: 2px; }}
#msg {{ margin: 0; min-height: 1.5em; font-size: .95rem; }} #msg.ok {{ color: var(--go); }} #msg.bad {{ color: var(--bad); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 12px 8px 12px 0; text-align: left; vertical-align: top; border-bottom: 1px solid var(--rule); }}
th {{ padding-top: 0; color: var(--soft); font: 600 .7rem/1.4 var(--mono); letter-spacing: .1em; text-transform: uppercase;
  border-bottom: 1.5px solid var(--ink); }}
td.when {{ font-family: var(--mono); font-size: .85rem; color: var(--soft); white-space: nowrap; }}
.state {{ display: flex; align-items: center; gap: 8px; font-weight: 600; }}
.state::before {{ content: ""; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--soft); }}
.state.ok::before {{ background: var(--go); }} .state.failed {{ color: var(--bad); }} .state.failed::before {{ background: var(--bad); }}
.state.working::before {{ background: var(--tag); }}
.count {{ font-family: var(--mono); font-size: .85rem; font-weight: 400; color: var(--soft); }}
progress {{ display: block; width: 100%; max-width: 200px; height: 6px; margin-top: 8px; accent-color: var(--go); }}
.note {{ margin-top: 4px; color: var(--soft); font-size: .85rem; }}
.row {{ display: flex; flex-wrap: wrap; gap: 6px; }} .scroll {{ overflow-x: auto; }} [hidden] {{ display: none !important; }}
@media (max-width: 560px) {{ h1 {{ font-size: 1.35rem; }} button.primary {{ width: 100%; }}
  thead {{ display: none; }} tr, td {{ display: block; }} tr {{ padding: 12px 0; border-bottom: 1px solid var(--rule); }}
  td {{ padding: 2px 0; border: 0; }} td.when {{ font-size: .8rem; }} td .row {{ margin-top: 8px; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style></head><body><main>
<header class="top"><h1>Google Maps Scraper Kit</h1>
<nav><span class="mono">v{version}</span><a href="/dashboard">Painel de prospecção</a> · <a href="/api/docs">Documentação da API</a></nav></header>
<div class="update" id="update" role="status" hidden><b>Kit v<span id="up-v"></span> está disponível</b> (versão atual: v{version}).
  <a id="up-link" href="{repo}/releases/latest" target="_blank" rel="noopener">Ver novidades</a> &middot;
  atualize com <code>bash scripts/update.sh</code>, ou <code>docker compose up -d --build</code> no Docker.</div>
<div class="stars"><a class="gh" href="{repo}" target="_blank" rel="noopener"><span class="star"><svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2.5l2.9 6 6.6.8-4.9 4.6 1.3 6.6L12 17.2l-5.9 3.3 1.3-6.6L2.5 9.3l6.6-.8z"/></svg></span>Dar estrela no GitHub</a>
  <span>Gostou? Uma estrela ajuda mais pessoas a encontrar esta ferramenta gratuita.</span></div>
<aside class="sponsors" id="sponsors" aria-label="Patrocinadores"><button type="button" class="sp-close" id="sp-close"
  aria-label="Ocultar patrocinadores">&times;</button>
  <div class="sp-head" id="sp-head" hidden>Apoiado por</div><div class="sp-grid" id="sp-grid" hidden></div>
  <p class="sp-ask"><span>Ajude a manter este projeto gratuito e de código aberto.</span>
    <a class="gh" href="https://github.com/sponsors/Mahanaicoach" target="_blank" rel="noopener"><span class="heart"><svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21s-7.5-4.6-9.6-9.2C1 8.6 2.9 5 6.6 5c2.1 0 3.5 1.2 5.4 3.2C13.9 6.2 15.3 5 17.4 5 21.1 5 23 8.6 21.6 11.8 19.5 16.4 12 21 12 21z"/></svg></span>Apoiar no GitHub</a></p>
</aside>
<section aria-labelledby="h-new"><h2 id="h-new">Nova pesquisa</h2>
<form id="f">
  <div class="ww">
    <div class="pick"><label for="what">Tipo de empresa</label><div class="box">
      <div class="search"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
        <input id="what" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="what-opts"
          autocomplete="off" placeholder="Ex.: Barbearias"></div>
      <ul class="opts" id="what-opts" role="listbox" aria-label="Tipos de empresas" hidden></ul></div>
      <div class="row tags" id="whats"></div></div>
    <div class="pick"><label for="where">Cidade ou região</label><div class="box">
      <div class="search"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/>
        <circle cx="12" cy="9.5" r="2.5"/></svg>
        <input id="where" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="where-opts"
          autocomplete="off" placeholder="Ex.: São Paulo"></div>
      <ul class="opts" id="where-opts" role="listbox" aria-label="Cidades" hidden></ul></div>
      <div class="row tags" id="wheres"></div></div>
  </div>
  <p class="hint soft">Escolha as opções nas listas. Você pode combinar vários segmentos e cidades; será criada uma coleta por cidade.</p>
  <fieldset class="collect"><legend>Coletar</legend>
    <label class="chip"><input type="checkbox" id="email" checked> E-mails</label>
    <div class="collect-choice">
      <label class="chip"><input type="checkbox" id="socials" checked> Redes sociais</label>
      <button type="button" class="info-button" popovertarget="socials-help"
        aria-label="Sobre a coleta de redes sociais e o tempo de execução"
        title="Procura redes sociais no site das empresas. Essa etapa pode aumentar a duração da coleta."><span aria-hidden="true">!</span></button>
    </div>
    <div class="collect-choice">
      <label class="chip"><input type="checkbox" id="browser-sites"> Renderizar sites (Playwright)</label>
      <button type="button" class="info-button" popovertarget="browser-help"
        aria-label="Sobre a renderização dos sites e a velocidade da pesquisa"
        title="Tenta novamente com um navegador. Ative apenas quando necessário."><span aria-hidden="true">!</span></button>
    </div>
    <div id="socials-help" class="info-note" popover role="note" aria-label="Coleta de redes sociais">
      <strong>Redes sociais</strong>
      <p>Procura links de Instagram, Facebook, LinkedIn, TikTok, YouTube e X nos sites das empresas.</p>
      <p>Verificar sites pode demorar mais do que coletar apenas dados do Maps. Páginas já acessadas para buscar e-mails são reaproveitadas.</p>
      <p>Desative esta opção quando não precisar dos links de redes sociais.</p>
    </div>
    <div id="browser-help" class="info-note" popover role="note" aria-label="Tempo de renderização dos sites">
      <strong>Renderizar sites</strong>
      <p>Tenta renderizar páginas quando a verificação rápida não encontra e-mails nem links de redes sociais.</p>
      <p>Esta etapa pode aumentar o tempo de coleta. As tentativas de renderização compartilham um limite de 30 segundos por tarefa, além da finalização. Deixe desativado para maior velocidade.</p>
    </div>
  </fieldset>
  <details><summary>Localização e idioma</summary><div class="body">
    <p class="wide soft">Cada pesquisa centraliza o mapa na cidade selecionada.</p>
    <label for="zoom">Zoom<input id="zoom" type="number" min="1" max="21" value="15"></label>
    <label for="lang">Idioma<input id="lang" value="pt" maxlength="2" pattern="[A-Za-z]{{2}}"></label>
    <label for="country"><span>País <span class="soft">opcional</span></span><input id="country" maxlength="2" pattern="[A-Za-z]{{2}}" placeholder="conforme a cidade"></label>
  </div></details>
  <details><summary>Opções avançadas</summary><div class="body">
    <label for="depth">Profundidade<input id="depth" type="number" min="1" max="1000" value="5">
      <span class="soft">Aproximadamente 20 estabelecimentos por etapa.</span></label>
    <label for="max_time">Limite de tempo (segundos)<input id="max_time" type="number" min="1" max="86400" value="600"></label>
    <label for="reviews">Avaliações por empresa<input id="reviews" type="number" min="0" max="5" value="0">
      <span class="soft">De 0 a 5; cerca de 2 a 4 segundos adicionais por empresa.</span></label>
    <label class="chip wide"><input type="checkbox" id="verify"> Verificar o domínio de cada e-mail (registro MX) e descartar domínios inexistentes</label>
  </div></details>
  <details><summary>Proxies</summary><div class="body">
    <label class="wide" for="proxies">Um endereço por linha
      <textarea id="proxies" rows="3" autocomplete="off" placeholder="Ex.: http://usuario:senha@proxy.example.com:8000"></textarea>
      <span class="soft">http:// ou https://, com ou sem usuário e senha; socks5:// sem autenticação. Os termos alternam entre os proxies,
      e uma pesquisa recusada pelo Google usa o próximo endereço. Senhas aparecem como ***.</span></label>
  </div></details>
  <div class="go"><button class="primary" id="go">Iniciar coleta</button><p id="msg" role="status" aria-live="polite"></p></div>
  <label id="keybox" for="key" hidden>Chave da API (SCRAPER_API_KEY)<input id="key" type="password" autocomplete="off"></label>
</form></section>
<section aria-labelledby="h-jobs"><h2 id="h-jobs">Coletas</h2>
<div class="scroll"><table><thead><tr><th>Pesquisa</th><th>Criada em</th><th>Situação</th><th>Resultados</th></tr></thead>
<tbody id="jobs"></tbody></table></div></section>
</main>
<script nonce="{nonce}">
const $ = id => document.getElementById(id);
let key = ''; try {{ key = localStorage.getItem('gmskit-key') || ''; }} catch (e) {{}}
$('key').value = key;
$('key').addEventListener('change', () => {{ key = $('key').value; try {{ localStorage.setItem('gmskit-key', key); }} catch (e) {{}} load(); }});
function api(method, path, body) {{
  const h = {{}}; if (key) h['X-API-Key'] = key; if (body) h['Content-Type'] = 'application/json';
  return fetch(path, {{method, headers: h, body: body ? JSON.stringify(body) : undefined}}).then(r => {{
    if (r.status === 401) {{ $('keybox').hidden = false; throw new Error('Este motor exige uma chave de API. Informe-a no campo abaixo.'); }}
    return r;
  }});
}}
function say(t, kind) {{ $('msg').textContent = t; $('msg').className = kind || ''; }}
function cell(tr, text, cls) {{ const td = document.createElement('td'); td.textContent = text; if (cls) td.className = cls; tr.appendChild(td); return td; }}
function button(td, label, fn) {{ const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', fn); td.appendChild(b); }}
async function download(j, fmt) {{
  const r = await api('GET', '/api/v1/jobs/' + j.ID + '/download' + (fmt === 'json' ? '?format=json' : ''));
  if (!r.ok) return say('Ainda não há resultados para esta coleta.', 'bad');
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob());
  a.download = fileName(j) + '.' + fmt; document.body.appendChild(a); a.click(); a.remove();
}}
function fileName(j) {{  // "bakery-in-portland-or-c063a815": after the search, plus the job id's start
  const s = (j.Name || '').normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);
  return (s || 'results') + '-' + j.ID.slice(0, 8);
}}
const LABEL = {{pending: 'aguardando', working: 'em andamento', ok: 'concluída', failed: 'falhou'}};
function progress(j) {{
  const p = j.Progress || {{}}, name = LABEL[j.Status] || j.Status;
  if (j.Status === 'pending') return p.keywords_done ? name + ' (retomará no termo ' + (p.keywords_done + 1) + ')' : name;
  if (j.Status !== 'working') return name + (p.places ? ' · ' + p.places + ' empresas' : '');
  const stage = {{search: 'termo ' + Math.min(p.keywords_done + 1, p.keywords_total) + ' de ' + p.keywords_total,
    reviews: 'lendo avaliações' + (p.reviews_total ? ' ' + p.reviews_done + ' de ' + p.reviews_total : ''),
    websites: 'verificando sites'}}[p.stage] || p.stage || '';
  return name + ' · ' + stage + ' · ' + (p.places || 0) + ' empresas';
}}
async function remove(j) {{
  if (!confirm('Excluir esta coleta e seus resultados?')) return;
  const r = await api('DELETE', '/api/v1/jobs/' + j.ID); say(r.ok ? 'Excluída.' : 'Não foi possível excluir.', r.ok ? 'ok' : 'bad'); load();
}}
async function load() {{
  try {{
    const list = await (await api('GET', '/api/v1/jobs')).json() || [];
    const tb = $('jobs'); tb.replaceChildren();
    for (const j of list) {{
      const tr = document.createElement('tr');
      const name = cell(tr, j.Name); if (j.Error) {{ const s = document.createElement('div'); s.className = 'note'; s.textContent = j.Error; name.appendChild(s); }}
      const when = new Date(j.Date);  // shown in this computer's time zone
      cell(tr, isNaN(when) ? j.Date : when.toLocaleString([], {{dateStyle: 'medium', timeStyle: 'short'}}), 'when');
      const st = cell(tr, ''), s = document.createElement('div');
      const [word, ...more] = progress(j).split(' · ');
      s.className = 'state ' + j.Status; s.textContent = word; st.appendChild(s);
      if (more.length) {{ const c = document.createElement('div'); c.className = 'count'; c.textContent = more.join(' · '); st.appendChild(c); }}
      if (j.Status === 'working') {{
        const bar = document.createElement('progress'); bar.max = 100; bar.value = (j.Progress || {{}}).percent || 0;
        bar.setAttribute('aria-label', 'Progresso de ' + j.Name); st.appendChild(bar);
      }}
      const act = cell(tr, ''), row = document.createElement('div'); row.className = 'row'; act.appendChild(row);
      if (j.Status !== 'pending' || (j.Progress || {{}}).places) {{ button(row, 'CSV', () => download(j, 'csv')); button(row, 'JSON', () => download(j, 'json')); }}
      button(row, 'Excluir', () => remove(j));
      tb.appendChild(tr);
    }}
    if (!list.length) {{ const tr = document.createElement('tr'); cell(tr, 'Ainda não há coletas. Inicie uma pesquisa acima.', 'soft').colSpan = 4; tb.appendChild(tr); }}
  }} catch (e) {{ say(e.message, 'bad'); }}
}}
const TYPES = {types};
// Sugestões brasileiras na interface; mantém intactas as categorias originais e o contrato da API.
const TIPOS_PT = ["Barbearias","Restaurantes","Padarias","Dentistas","Clínicas odontológicas","Salões de beleza","Cafeterias","Hotéis","Farmácias","Academias","Escritórios de contabilidade","Imobiliárias","Pet shops","Oficinas mecânicas","Empresas de limpeza","Supermercados","Pizzarias","Lojas de roupas","Advogados","Hospitais","Mercados","Eletricistas","Encanadores","Consultórios médicos","Escolas","Lanchonetes","Clínicas médicas","Agências de publicidade","Escritórios de advocacia","Transportadoras","Autopeças","Lava-rápidos","Óticas","Lavanderias","Construtoras","Lojas de móveis","Clínicas veterinárias"];
for (const nome of TIPOS_PT) if (!TYPES.some(t => t.toLocaleLowerCase('pt-BR') === nome.toLocaleLowerCase('pt-BR'))) TYPES.unshift(nome);
const whats = [], wheres = [];  // picked business types, picked cities {{label, lat, lon, country}}
function tags(box, list) {{  // each pick is a button; pressing it removes the pick
  box.replaceChildren();
  list.forEach((v, i) => {{
    const b = document.createElement('button'), text = v.label || v; b.type = 'button'; b.className = 'tag';
    b.textContent = text + ' ×'; b.setAttribute('aria-label', 'Remover ' + text);
    b.addEventListener('click', () => {{ list.splice(i, 1); tags(box, list); }}); box.appendChild(b);
  }});
}}
function combo(input, box, source, choose) {{  // a box that takes only picks from its own list: arrows move, Enter or a click picks
  let items = [], active = -1, stale = false;
  function show(list) {{
    items = list; active = list.length ? 0 : -1; stale = false; box.replaceChildren();
    list.forEach((it, i) => {{
      const li = document.createElement('li'); li.id = box.id + '-' + i; li.setAttribute('role', 'option'); li.textContent = it.label;
      li.addEventListener('mousedown', ev => {{ ev.preventDefault(); pick(i); }}); box.appendChild(li);
    }});
    mark(); box.hidden = !list.length; input.setAttribute('aria-expanded', String(!box.hidden));
  }}
  function mark() {{
    [...box.children].forEach((li, i) => li.setAttribute('aria-selected', String(i === active)));
    if (active < 0) return input.removeAttribute('aria-activedescendant');
    input.setAttribute('aria-activedescendant', box.id + '-' + active); box.children[active].scrollIntoView({{block: 'nearest'}});
  }}
  function pick(i) {{ choose(items[i]); input.value = ''; say('', ''); source('', show); }}
  input.addEventListener('input', () => {{  // the list shown belongs to the old text until the source answers
    items = []; active = -1; stale = true; mark(); if ($('msg').className === 'bad') say('', ''); source(input.value.trim(), show); }});
  input.addEventListener('focus', () => source(input.value.trim(), show));
  input.addEventListener('blur', () => show([]));
  input.addEventListener('keydown', ev => {{
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {{
      ev.preventDefault(); if (!items.length) return;
      active = (active + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; mark();
    }} else if (ev.key === 'Enter') {{  // never submits the form
      ev.preventDefault();
      if (active >= 0) pick(active);
      else if (input.value.trim() && !stale) say('"' + input.value.trim() + '" não aparece na lista. Digite algumas letras e selecione uma opção.', 'bad');
    }} else if (ev.key === 'Escape') show([]);
  }});
}}
combo($('what'), $('what-opts'), (q, show) => {{  // names that start with q first, then the rest; 50 at most
  q = q.toLowerCase();
  const hit = TYPES.filter(t => t.toLowerCase().includes(q)), first = hit.filter(t => t.toLowerCase().startsWith(q));
  show(first.concat(hit.filter(t => !first.includes(t))).slice(0, 50).map(t => ({{label: t}})));
}}, t => {{ if (!whats.includes(t.label)) whats.push(t.label); tags($('whats'), whats); }});
(function () {{  // What also offers Google's own category names, cached for 30 days, as text only
  const key = 'gmskit-categories', month = 30 * 86400000, base = s => s.toLowerCase().replace(/s$/, '');
  function add(names) {{  // after the kit's own list; "Dentist" is dropped when "Dentists" is there
    const have = new Set(TYPES.map(base));
    for (const n of names) if (!have.has(base(n))) {{ have.add(base(n)); TYPES.push(n); }}
  }}
  try {{
    const c = JSON.parse(localStorage.getItem(key) || 'null');
    if (c && Date.now() - c.t < month && Array.isArray(c.names)) return add(c.names);
  }} catch (e) {{}}
  fetch('{categories}', {{credentials: 'omit'}}).then(r => r.ok ? r.text() : '').then(t => {{
    const names = t.split('\\n').map(s => s.trim()).filter(s => s && s.length <= 80).slice(0, 5000);
    if (!names.length) return;
    add(names);
    try {{ localStorage.setItem(key, JSON.stringify({{t: Date.now(), names}})); }} catch (e) {{}}
  }}).catch(() => {{}});
}})();
let timer = 0;
combo($('where'), $('where-opts'), (q, show) => {{  // the biggest cities that start with q; nothing typed, the biggest US ones
  clearTimeout(timer);
  timer = setTimeout(async () => {{
    try {{
      const r = await api('GET', '/api/v1/cities?q=' + encodeURIComponent(q)); if (!r.ok) return;
      const found = await r.json();
      if (q === $('where').value.trim() && document.activeElement === $('where')) show(found);  // else a newer lookup is coming
    }} catch (e) {{ say(e.message, 'bad'); }}
  }}, 120);
}}, c => {{ if (!wheres.some(w => w.label === c.label)) wheres.push(c); tags($('wheres'), wheres); }});
$('f').addEventListener('submit', async ev => {{
  ev.preventDefault();
  for (const box of [$('what'), $('where')]) if (box.value.trim()) {{ box.focus();
    return say('"' + box.value.trim() + '" ainda não foi selecionado. Escolha na lista ou limpe o campo.', 'bad'); }}
  if (!whats.length || !wheres.length) {{ (whats.length ? $('where') : $('what')).focus();
    return say('Escolha pelo menos um tipo de empresa e uma cidade nas listas.', 'bad'); }}
  const proxies = $('proxies').value.split('\\n').map(s => s.trim()).filter(Boolean);
  const go = $('go'); go.disabled = true; go.textContent = 'Iniciando…';
  let started = 0;
  try {{
    for (const c of wheres) {{  // one job per city, its map centred on that city
      const keywords = whats.map(w => w + ' em ' + c.label);
      const body = {{name: Array.from(keywords[0] + (keywords.length > 1 ? ' +' + (keywords.length - 1) + ' adicionais' : '')).slice(0, 200).join(''),
        keywords, lang: $('lang').value.trim().toLowerCase(), country: $('country').value.trim().toLowerCase() || c.country.toLowerCase(),
        lat: c.lat, lon: c.lon, zoom: +$('zoom').value || 15, depth: +$('depth').value, max_time: +$('max_time').value,
        email: $('email').checked, socials: $('socials').checked, browser_sites: $('browser-sites').checked, verify_emails: $('verify').checked,
        reviews_max: +$('reviews').value || 0}};
      if (proxies.length) body.proxies = proxies;
      const r = await api('POST', '/api/v1/jobs', body), d = await r.json();
      if (!r.ok) return say('Não iniciada' + (started ? ' após ' + started + ' coleta(s)' : '') + ': ' + d.message, 'bad');
      started++;
    }}
    say(started === 1 ? 'Coleta iniciada. A lista abaixo será atualizada automaticamente.'
      : 'Iniciadas ' + started + ' coletas, uma por cidade. Elas serão executadas em sequência e a lista será atualizada automaticamente.', 'ok');
  }} catch (e) {{ say(e.message, 'bad'); }}
  finally {{ go.disabled = false; go.textContent = 'Iniciar coleta'; load(); }}
}});
load(); setInterval(load, 3000);
(function () {{  // update notice: GitHub's latest release once a day, shown only when it is newer than this copy
  const key = 'gmskit-update', day = 86400000, mine = '{version}';
  const num = v => (String(v).replace(/^v/, '').split('.').slice(0, 3).map(x => parseInt(x, 10) || 0));
  const newer = (a, b) => {{ const x = num(a), y = num(b); for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i]; return false; }};
  function show(tag) {{
    if (!/^v?\d+\.\d+\.\d+/.test(tag || '') || !newer(tag, mine)) return;
    $('up-v').textContent = String(tag).replace(/^v/, '').slice(0, 20);
    $('up-link').href = '{repo}/releases/tag/' + encodeURIComponent(tag);
    $('update').hidden = false;
  }}
  try {{
    const c = JSON.parse(localStorage.getItem(key) || 'null');
    if (c && Date.now() - c.t < day) return show(c.tag);
  }} catch (e) {{}}
  fetch('{releases}', {{cache: 'no-store', credentials: 'omit', headers: {{Accept: 'application/vnd.github+json'}}}})
    .then(r => r.ok ? r.json() : null).then(d => {{
      if (!d || typeof d.tag_name !== 'string') return;
      show(d.tag_name);
      try {{ localStorage.setItem(key, JSON.stringify({{t: Date.now(), tag: d.tag_name}})); }} catch (e) {{}}
    }}).catch(() => {{}});
}})();
(function () {{  // sponsor tiles: only the entries Mahan marks "ui": true in sponsors.json, as text, https links only
  const box = $('sponsors'), grid = $('sp-grid'), key = 'gmskit-sponsors', day = 86400000;
  $('sp-close').addEventListener('click', () => {{ box.hidden = true; }});  // as gosom: hidden until the page reloads
  const svg = (tag, attrs) => {{ const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }};
  function render(list) {{
    const shown = Array.isArray(list) ? list.filter(s => s && s.ui === true && typeof s.name === 'string' && s.name.trim()
      && typeof s.url === 'string' && s.url.startsWith('https://')).slice(0, 4) : [];
    if (!shown.length) return;
    grid.replaceChildren();
    for (const s of shown) {{
      const a = document.createElement('a'), mark = document.createElement('span'), body = document.createElement('span');
      a.className = 'sp'; a.href = s.url; a.target = '_blank'; a.rel = 'noopener noreferrer sponsored';
      mark.className = 'sp-mark'; mark.setAttribute('aria-hidden', 'true'); mark.textContent = s.name.trim()[0].toUpperCase();
      if (/^#[0-9a-f]{{6}}$/i.test(s.color || '')) {{  // the sponsor's own colour, with ink or white for contrast
        const n = parseInt(s.color.slice(1), 16), lum = (0.299 * (n >> 16) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255;
        mark.style.setProperty('--brand', s.color); mark.style.color = lum > .6 ? '#17191c' : '#fff';
      }}
      const b = document.createElement('b'); b.textContent = s.name.slice(0, 40);
      body.className = 'sp-body'; body.appendChild(b);
      if (typeof s.tagline === 'string' && s.tagline.trim()) {{
        const t = s.tagline.trim().slice(0, 120), line = document.createElement('span');
        line.className = 'sp-line'; line.textContent = t[0].toUpperCase() + t.slice(1); body.appendChild(line);
      }}
      const go = svg('svg', {{width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
        'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', class: 'sp-go', 'aria-hidden': 'true'}});
      go.appendChild(svg('path', {{d: 'M7 17L17 7M8 7h9v9'}}));
      a.append(mark, body, go); grid.appendChild(a);
    }}
    grid.hidden = $('sp-head').hidden = false;
  }}
  try {{
    const c = JSON.parse(localStorage.getItem(key) || 'null');
    if (c && Date.now() - c.t < day) return render(c.list);
  }} catch (e) {{}}
  fetch('{sponsors}', {{cache: 'no-store', credentials: 'omit'}}).then(r => r.ok ? r.json() : null).then(d => {{
    if (!d || !Array.isArray(d.sponsors)) return;
    render(d.sponsors);
    try {{ localStorage.setItem(key, JSON.stringify({{t: Date.now(), list: d.sponsors}})); }} catch (e) {{}}
  }}).catch(() => {{}});
}})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "gmskit-engine"
    sys_version = ""
    timeout = 30  # a client that stalls mid-body or idles on keep-alive would otherwise pin a thread for good

    def log_message(self, fmt, *args):  # errors are logged by reply(); polls would flood the log
        pass

    def reply(self, code, body=b"", ctype="application/json", headers=()):
        if ctype == "application/json":
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Engine", MARK)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        if self.close_connection:  # tell the client too, so it never reuses the socket
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        if code >= 400:
            log(f"{self.command} {self.path.split('?')[0]!r} -> {code}")  # repr: no control characters in the log

    def fail(self, code, message):
        if self.command != "GET":  # a refused POST or DELETE may leave its body unread on the socket
            self.close_connection = True
        self.reply(code, {"code": code, "message": message})

    def guard(self):
        """Host (DNS rebinding) and Origin (cross-site posts) checks, plus the optional key."""
        host = self.headers.get("Host", "")
        if not HOST_OK.match(host):
            self.close_connection = True
            self.fail(421, "this engine answers to localhost only")
            return False
        origin = self.headers.get("Origin")  # only this page: a dev server on another local port is another site
        if origin is not None and not (ORIGIN_OK.match(origin) and origin.split("://", 1)[1].lower() == host.lower()):
            self.close_connection = True
            self.fail(403, "requests from other websites are refused")
            return False
        key, path = self.server.api_key, self.path.split("?")[0]
        if key and path not in ("/", "/dashboard", "/dashboard/", "/dashboard/app.js", "/dashboard/styles.css", "/api/docs", "/api/openapi.json") and not hmac.compare_digest(
                self.headers.get("X-API-Key", "").encode("latin-1", "replace"), key.encode()):  # headers arrive as latin-1
            self.fail(401, "missing or wrong X-API-Key")
            return False
        return True

    def body(self):
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            self.close_connection = True
            self.fail(411, "send a Content-Length")
            return _REPLIED
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_BODY:
            self.close_connection = True
            self.fail(413 if n > MAX_BODY else 400, "the body must be 1 MB or less")
            return _REPLIED
        try:
            return json.loads(self.rfile.read(n) or b"null")
        except (ValueError, RecursionError):  # bad JSON, bad UTF-8, or nested too deep to parse
            self.fail(400, "the body is not valid JSON")
            return _REPLIED

    def download(self, jid, query=""):
        data = self.server.store.read_csv(jid) if JOB_ID.match(jid or "") else None
        name = file_name(self.server.store.get(jid) if data is not None else None, jid or "")
        if data is None:
            return self.fail(404, "no results for this job (yet)")
        fmt = urllib.parse.parse_qs(query).get("format", ["csv"])[0]
        if fmt == "json":  # the same rows, every value a string, as in the CSV
            rows = list(csv.DictReader(io.StringIO(data.decode("utf-8", "replace"))))
            return self.reply(200, json.dumps(rows, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                              [("Content-Disposition", f'attachment; filename="{name}.json"')])
        if fmt != "csv":
            return self.fail(400, "format must be csv or json")
        self.reply(200, jobs.guard_csv(data), "text/csv; charset=utf-8",  # a spreadsheet opens it: no formulas
                   [("Content-Disposition", f'attachment; filename="{name}.csv"')])

    def do_GET(self):
        if not self.guard():
            return
        path, _, query = self.path.partition("?")
        store = self.server.store
        if path == "/api/v1/dashboard" or path in (
                "/api/v1/dashboard/summary", "/api/v1/dashboard/leads",
                "/api/v1/dashboard/geojson", "/api/v1/dashboard/export"):
            try:
                code, data, ctype, headers = dashboard_api.handle(store, path, query)
            except dashboard_api.InvalidQuery as e:
                return self.fail(400, str(e))
            except (OSError, sqlite3.Error, csv.Error) as e:
                return self.fail(500, "dashboard data could not be read")
            return self.reply(code, data, ctype, headers)
        if path in ("/dashboard", "/dashboard/"):
            path_on_disk = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
            try:
                with open(path_on_disk, "rb") as f:
                    data = f.read()
            except OSError:
                return self.fail(404, "dashboard is not installed")
            csp = ("default-src 'none'; script-src 'self' https://unpkg.com; "
                   "style-src 'self' https://unpkg.com; connect-src 'self'; "
                   "img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com; "
                   "font-src 'self' https://unpkg.com; base-uri 'none'; "
                   "form-action 'self'; frame-ancestors 'none'")
            return self.reply(200, data, "text/html; charset=utf-8", [("Content-Security-Policy", csp)])
        if path in ("/dashboard/app.js", "/dashboard/styles.css"):
            name = path.rsplit("/", 1)[-1]
            file_path = os.path.join(os.path.dirname(__file__), "dashboard", name)
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
            except OSError:
                return self.fail(404, "dashboard asset not found")
            ctype = "application/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8"
            return self.reply(200, data, ctype)
        if path == "/api/v1/jobs":  # null when empty, as before: the docs' health check
            return self.reply(200, [jobs.public(j) for j in store.all()] or None)
        m = JOB_PATH.match(path)
        if m:
            if m.group(2):
                return self.download(m.group(1), query)
            job = store.get(m.group(1))
            return self.reply(200, jobs.public(job)) if job else self.fail(404, "job not found")
        if path == "/download":  # the old web UI's download link
            return self.download(urllib.parse.parse_qs(query).get("id", [""])[0], query)
        if path == "/api/docs":
            nonce = secrets.token_urlsafe(16)
            csp = f"default-src 'none'; style-src 'nonce-{nonce}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            return self.reply(200, docs_page(nonce).encode(), "text/html; charset=utf-8",
                              [("Content-Security-Policy", csp)])
        if path == "/api/v1/cities":
            return self.reply(200, find_cities(urllib.parse.parse_qs(query).get("q", [""])[0][:100]))
        if path == "/api/openapi.json":
            return self.reply(200, OPENAPI)
        if path == "/":
            nonce = secrets.token_urlsafe(16)
            csp = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                   "connect-src 'self' https://raw.githubusercontent.com https://api.github.com; img-src 'self' data:; "
                   "form-action 'self'; base-uri 'none'; "
                   "frame-ancestors 'none'")
            page = PAGE.format(nonce=nonce, version=VERSION, repo=REPO, sponsors=SPONSORS, releases=RELEASES, types=TYPES_JS,
                               categories=CATEGORIES).encode()
            return self.reply(200, page, "text/html; charset=utf-8", [("Content-Security-Policy", csp)])
        self.fail(404, "not found")

    do_HEAD = do_GET  # the same headers (X-Engine included), no body

    def do_POST(self):
        if not self.guard():
            return
        if self.path.split("?")[0] != "/api/v1/jobs":
            return self.fail(404, "not found")
        body = self.body()
        if body is _REPLIED:
            return
        try:
            name, data = jobs.validate(body)
        except ValueError as e:
            return self.fail(422, str(e))
        try:
            jid = self.server.store.create(name, data)
        except (UnicodeEncodeError, ValueError) as e:  # validate() keeps these out; a belt for the braces
            return self.fail(422, f"invalid body: {e}")
        except sqlite3.Error as e:  # a full disk or a locked database: answer, do not drop the connection
            return self.fail(500, f"could not store the job: {e}")
        self.server.worker.wake.set()
        log(f"job {jid} created: {len(data['keywords'])} keyword(s)")
        self.reply(201, {"id": jid})

    def do_DELETE(self):
        if not self.guard():
            return
        m = JOB_PATH.match(self.path.split("?")[0])
        if not m or m.group(2):
            return self.fail(404, "not found")
        if not self.server.store.delete(m.group(1)):  # delete first: a job claimed after the cancel sees it is gone
            return self.fail(404, "job not found")
        self.server.worker.cancel(m.group(1))
        log(f"job {m.group(1)} deleted")
        self.reply(200, {"message": "deleted"})


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"  # on Windows SO_REUSEADDR would let a second server share the port
    daemon_threads = True

    def server_bind(self):
        # HTTPServer.server_bind also calls socket.getfqdn(), a reverse DNS lookup that took over
        # 30 s on a macOS runner before the engine could answer. The name is never used here.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "localhost", self.server_address[1]


def port_taken(port):
    """True if something answers on 127.0.0.1:port. With SO_REUSEADDR, macOS lets a new server bind
    127.0.0.1:port while another listens on *:port (the Docker engine), and takes its traffic."""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False


class Server6(Server):
    address_family = socket.AF_INET6


def lock_data(folder):
    """An exclusive lock on <folder>/engine.lock, held for the engine's life: a second engine on the same
    data (serve.py --port N by hand) would flip the first one's job to pending and cut its CSV."""
    os.makedirs(folder, exist_ok=True)
    f = open(os.path.join(folder, "engine.lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise OSError("its engine.lock is held")
    return f


def in_container():
    """True inside a Docker or Podman container (each leaves its marker file at the root)."""
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def make_servers(port, store, worker, api_key="", host="127.0.0.1"):
    """The server on host:port. On 127.0.0.1 also one on [::1]:port when this machine has IPv6
    loopback (Windows tries ::1 first for "localhost" and waits ~2 s before falling back)."""
    if port and port_taken(port):
        raise OSError(f"something already listens on port {port}")
    servers = [Server((host, port), Handler)]
    if host == "127.0.0.1":
        try:
            servers.append(Server6(("::1", servers[0].server_address[1]), Handler))
        except OSError:
            pass
    for s in servers:
        s.store, s.worker, s.api_key = store, worker, api_key
    return servers


def main():
    ap = argparse.ArgumentParser(description="The kit's Google Maps engine (local HTTP API and web UI).")
    ap.add_argument("--port", type=int, help="default: SCRAPER_PORT from the environment or .env, else 8080")
    ap.add_argument("--data", default=os.path.join(browser.HOME, "data"), help="jobs and results folder")
    ap.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "0.0.0.0"),
                    help="0.0.0.0 is for the Docker image only, where Docker publishes the port on the "
                         "host's 127.0.0.1 (default: 127.0.0.1)")
    a = ap.parse_args()
    if a.host != "127.0.0.1" and not in_container():
        # On a laptop or server 0.0.0.0 opens the engine to the network: the Host check stops DNS
        # rebinding from a browser, not a machine that sends "Host: localhost" itself.
        sys.exit("✗ --host 0.0.0.0 is for the Docker image only. On this machine the engine listens on "
                 "127.0.0.1, which keeps other machines out.")
    env = read_env()
    try:
        port = a.port or int(env["SCRAPER_PORT"] or 8080)
    except ValueError:
        sys.exit(f"✗ SCRAPER_PORT is not a number: {env['SCRAPER_PORT']!r}")
    browser.make_home()
    browser.sweep_profiles()
    try:
        hold = lock_data(a.data)  # noqa: F841 - held for the engine's life
    except OSError as e:
        sys.exit(f"✗ Another engine already uses {a.data}: {e}. Stop it first (python3 scripts/engine.py stop, "
                 "or docker compose stop).")
    store = jobs.Store(a.data)
    headless = env["SCRAPER_HEADLESS"].strip().lower() not in ("0", "false", "no", "off")
    worker = jobs.Worker(store, log, headless=headless)
    try:
        servers = make_servers(port, store, worker, env["SCRAPER_API_KEY"], a.host)
    except OSError as e:
        sys.exit(f"✗ Cannot listen on {a.host}:{port}: {e}")
    # Only now: an engine that cannot bind (another one runs on this data) must not touch its jobs.
    resumed, failed = store.recover()
    if resumed:
        log(f"{resumed} job(s) were still working when the engine last stopped: they resume from their last "
            "finished keyword")
    if failed:
        log(f"{failed} job(s) stopped mid-run {jobs.MAX_RESUMES + 1} times: marked failed, rows kept")
    try:
        imported = store.import_kit1(os.path.join(browser.HOME, "kit1"), log)
    except Exception as e:  # the old jobs never stop the engine from starting
        imported = 0
        log(f"kit 1.x jobs not imported, tried again on the next start: {type(e).__name__}: {e}")
    if imported:
        log(f"{imported} job(s) from kit 1.x imported with their results")
    worker.start()
    chrome = browser.find_chrome()
    where = f"http://localhost:{port}" if a.host == "127.0.0.1" else \
        f"{a.host}:{port} in this container, published on the host's 127.0.0.1"
    log(f"engine {VERSION} on {where} (browser: {chrome or 'none found'}{'' if headless else ', as a window'}"
        f"{', API key required' if env['SCRAPER_API_KEY'] else ''})")
    if not headless and browser.always_headless(chrome):
        log("SCRAPER_HEADLESS=0 is set, but the only browser is the downloaded headless shell, which cannot "
            "open a window: install Google Chrome (or Chromium, Edge, Brave) for window mode")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    if hasattr(signal, "SIGBREAK"):  # Windows: scripts/engine.py stop sends Ctrl-Break to the engine's group
        signal.signal(signal.SIGBREAK, lambda *_: sys.exit(0))
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    code = 0
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:  # noqa: BLE001
        log(f"engine crashed: {type(e).__name__}: {e}")
        code = 1
    finally:
        worker.shutdown(wait=8)  # the job in progress saves its place and resumes on the next start
        log("engine stopped")
        # Website-pass threads may still be inside a fetch (up to SITE_HARD s each); the interpreter
        # would wait for them before closing the socket. The job is already saved: leave now.
        os._exit(code)


if __name__ == "__main__":
    main()
