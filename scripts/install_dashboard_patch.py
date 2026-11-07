#!/usr/bin/env python3
"""Idempotently wire the Prospect Intelligence feature into the existing engine.

Run ONCE at the root of the fork, after copying the new files into place:
    python3 scripts/install_dashboard_patch.py

No third-party modules and no network calls. Refuses unexpected upstream layouts.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVE = ROOT / "engine" / "serve.py"
README = ROOT / "README.md"


def replace_once(source, old, new, label):
    if new in source:
        return source
    if old not in source:
        raise RuntimeError("cannot patch %s: source marker changed; review upstream before applying" % label)
    return source.replace(old, new, 1)


def patch_serve(source):
    source = replace_once(source,
        "import browser, jobs  # noqa: E402",
        "import browser, jobs, dashboard_api  # noqa: E402",
        "engine import")

    source = replace_once(source,
        'if key and path not in ("/", "/api/docs", "/api/openapi.json") and not hmac.compare_digest(',
        'if key and path not in ("/", "/dashboard", "/dashboard/", "/dashboard/app.js", "/dashboard/styles.css", "/api/docs", "/api/openapi.json") and not hmac.compare_digest('.replace('"/dashboard/styles.css"', '"/dashboard/styles.css"'),
        "public static dashboard pages")

    route = '''        if path == "/api/v1/dashboard" or path in (
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
'''
    anchor = '        if path == "/api/v1/jobs":  # null when empty, as before: the docs\' health check'
    source = replace_once(source, anchor, route + anchor, "GET routes")
    source = replace_once(source,
        '<nav><span class="mono">v{version}</span><a href="/api/docs">API docs</a></nav></header>',
        '<nav><span class="mono">v{version}</span><a href="/dashboard">Dashboard</a> · <a href="/api/docs">API docs</a></nav></header>',
        "old UI navigation")

    # Augment OpenAPI only once. This assignment follows the existing OPENAPI declaration.
    fragment = '''OPENAPI["paths"].update({
    "/api/v1/dashboard": {"get": {"summary": "Consolidated dashboard KPIs, paginated leads and map points. Reads existing local CSV jobs."}},
    "/api/v1/dashboard/summary": {"get": {"summary": "Filtered summary, categories, coverage and job counts."}},
    "/api/v1/dashboard/leads": {"get": {"summary": "Filtered, deduplicated and paginated collected businesses."}},
    "/api/v1/dashboard/geojson": {"get": {"summary": "GeoJSON feature collection, maximum 700 mapped businesses."}},
    "/api/v1/dashboard/export": {"get": {"summary": "Download filtered CSV or JSON; ?format=csv|json."}},
})

'''
    source = replace_once(source, '\n\ndef docs_page(nonce):', '\n\n' + fragment + 'def docs_page(nonce):', "OpenAPI routes")
    return source


def main():
    required = [ROOT / "engine" / "dashboard_api.py", ROOT / "engine" / "dashboard" / "index.html",
                ROOT / "engine" / "dashboard" / "styles.css", ROOT / "engine" / "dashboard" / "app.js"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing dashboard feature files: " + ", ".join(missing))
    if not SERVE.exists():
        raise SystemExit("Run this installer at the root of google-maps-scraper-kit; engine/serve.py missing")
    original = SERVE.read_text(encoding="utf-8")
    updated = patch_serve(original)
    if updated != original:
        SERVE.write_text(updated, encoding="utf-8")
        print("Patched engine/serve.py (GET routes, OpenAPI, safe static assets, original UI link).")
    else:
        print("engine/serve.py already includes Prospect Intelligence; no changes needed.")

    if README.is_file():
        content = README.read_text(encoding="utf-8")
        if "## Prospect Intelligence — dashboard do fork" not in content:
            content += '''\n\n---\n\n## Prospect Intelligence — dashboard do fork\n\nEste fork acrescenta um painel de prospecção em português sem substituir o coletor original.\nApós iniciar o motor com `python3 scripts/engine.py start`, abra\n**http://localhost:8080/dashboard** (ou ajuste a porta de acordo com `.env`).\nO painel agrega apenas resultados reais dos trabalhos locais, com filtros, mapa (Leaflet/OSM),\nKPIs, relatórios e exportação CSV/JSON. O motor de coleta e sua API continuam funcionando.\nDocumentação completa: [docs/dashboard.md](docs/dashboard.md).\n\nA coleta pode contrariar os termos da Google. Respeite LGPD, limitações do serviço,\nconsentimento e direitos de titulares. O mapa carrega recursos externos da Leaflet e\ntiles do OpenStreetMap quando a conexão à internet está disponível.\n'''
            README.write_text(content, encoding="utf-8")
            print("Updated README.md with fork dashboard instructions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())