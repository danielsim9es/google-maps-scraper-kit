"""Prospect Intelligence — read-only reporting over the existing jobs.Store.

Zero new Python dependencies. Uses the same local-only/API-key guard as engine/serve.py.
Data is always derived from real job CSV files; there are no demo leads or invented KPIs.
"""

import csv
import io
import json
import math
import re
import urllib.parse
from collections import Counter

MAX_SCANNED = 50000
MAX_MAP_POINTS = 700
EXPORT_FIELDS = (
    "title", "category", "address", "phone", "emails", "website", "review_rating",
    "review_count", "latitude", "longitude", "instagram", "facebook", "linkedin",
    "tiktok", "youtube", "x", "source_job", "source_job_id", "scraped_at",
)
SOCIAL_FIELDS = ("instagram", "facebook", "linkedin", "tiktok", "youtube", "x")
VALID_SORTS = ("newest", "name", "rating", "reviews")
FORMULA = re.compile(r"^[\s\x00-\x1f]*[=+@\-\t\r]", re.UNICODE)


class InvalidQuery(ValueError):
    """An API query parameter is invalid; return HTTP 400 to the caller."""


def _positive_int(query, name, default, minimum, maximum):
    value = query.get(name, [str(default)])[0]
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise InvalidQuery("%s must be an integer" % name)
    if not minimum <= number <= maximum:
        raise InvalidQuery("%s must be between %s and %s" % (name, minimum, maximum))
    return number


def parse_query(raw):
    try:
        query = urllib.parse.parse_qs(raw, keep_blank_values=True, max_num_fields=25)
    except ValueError:
        raise InvalidQuery("too many query parameters")
    def text(name, max_length):
        value = query.get(name, [""])[0].strip()
        if len(value) > max_length or any(ord(c) < 32 for c in value):
            raise InvalidQuery("invalid %s" % name)
        return value

    sort = text("sort", 20) or "newest"
    if sort not in VALID_SORTS:
        raise InvalidQuery("sort must be newest, name, rating or reviews")
    raw_rating = text("min_rating", 5)
    try:
        min_rating = float(raw_rating) if raw_rating else 0.0
    except ValueError:
        raise InvalidQuery("min_rating must be a number between 0 and 5")
    if not math.isfinite(min_rating) or not 0 <= min_rating <= 5:
        raise InvalidQuery("min_rating must be between 0 and 5")

    return {
        "search": text("q", 120).casefold(),
        "category": text("category", 100).casefold(),
        "job": text("job", 80),
        "min_rating": min_rating,
        "email": text("email", 5) == "1",
        "phone": text("phone", 5) == "1",
        "website": text("website", 5) == "1",
        "sort": sort,
        "page": _positive_int(query, "page", 1, 1, 100000),
        "limit": _positive_int(query, "limit", 20, 1, 100),
    }


def _float(value, lo=None, hi=None):
    try:
        num = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(num) or (lo is not None and num < lo) or (hi is not None and num > hi):
        return None
    return num


def _integer(value):
    try:
        return max(0, int(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _key(raw):
    for name in ("place_id", "data_id", "cid"):
        value = (raw.get(name) or "").strip()
        if value:
            return name + ":" + value
    title = (raw.get("title") or "").strip().casefold()
    address = (raw.get("address") or "").strip().casefold()
    website = (raw.get("website") or "").strip().casefold()
    return "other:" + "|".join([title, address, website]) if (title or address or website) else None


def _normalize(raw, job):
    row = {k: str(raw.get(k) or "").strip() for k in EXPORT_FIELDS if k not in
           ("source_job", "source_job_id", "scraped_at", "review_rating", "review_count", "latitude", "longitude")}
    row.update({
        "review_rating": _float(raw.get("review_rating"), 0, 5),
        "review_count": _integer(raw.get("review_count")),
        "latitude": _float(raw.get("latitude"), -90, 90),
        "longitude": _float(raw.get("longitude"), -180, 180),
        "source_job": str(job.get("Name") or ""),
        "source_job_id": str(job["ID"]),
        "scraped_at": str(job.get("Date") or ""),
    })
    return row


def _matches(row, filters):
    if filters["job"] and row["source_job_id"] != filters["job"]:
        return False
    if filters["category"] and filters["category"] not in row["category"].casefold():
        return False
    if filters["email"] and not row["emails"]:
        return False
    if filters["phone"] and not row["phone"]:
        return False
    if filters["website"] and not row["website"]:
        return False
    if filters["min_rating"] and (row["review_rating"] is None or row["review_rating"] < filters["min_rating"]):
        return False
    if filters["search"] and not any(filters["search"] in row[field].casefold() for field in
                                     ("title", "category", "address", "emails", "phone", "website")):
        return False
    return True


def scan(store, filters):
    """One bounded, deduplicated snapshot of existing CSV data; never contacts Google.

    Jobs are newest-first. If a listing appears in multiple jobs, its newest occurrence wins.
    Returns (matching leads, unfiltered categories, all jobs, scanned, partial).
    """
    all_jobs = store.all()
    seen = set()
    leads = []
    categories = Counter()
    scanned = 0
    partial = False
    for job in all_jobs:
        # Filtering a specific collection must show its own rows, even when a newer
        # collection contains the same place. Cross-job deduplication applies only to all-jobs views.
        if filters["job"] and job["ID"] != filters["job"]:
            continue
        data = store.read_csv(job["ID"])
        if not data:
            continue
        try:
            rows = csv.DictReader(io.StringIO(data.decode("utf-8", "replace"), newline=""))
            for raw in rows:
                if scanned >= MAX_SCANNED:
                    partial = True
                    break
                scanned += 1
                key = _key(raw)
                if not key or key in seen:
                    continue
                seen.add(key)
                row = _normalize(raw, job)
                if row["category"]:
                    categories[row["category"]] += 1
                if _matches(row, filters):
                    leads.append(row)
        except csv.Error:
            # A torn or malformed source CSV must not take the rest of the dashboard offline.
            continue
        if partial:
            break

    sort = filters["sort"]
    if sort == "name":
        leads.sort(key=lambda r: (r["title"].casefold(), r["source_job_id"]))
    elif sort == "rating":
        leads.sort(key=lambda r: (r["review_rating"] is not None, r["review_rating"] or 0,
                                  r["review_count"]), reverse=True)
    elif sort == "reviews":
        leads.sort(key=lambda r: r["review_count"], reverse=True)
    return leads, categories, all_jobs, scanned, partial


def summary(leads, categories, all_jobs, scanned, partial):
    ratings = [row["review_rating"] for row in leads if row["review_rating"] is not None]
    by_category = Counter(r["category"] or "Não informado" for r in leads)
    by_rating = Counter(str(max(1, math.ceil(x))) for x in ratings)
    status = Counter(j.get("Status") or "unknown" for j in all_jobs)
    emails = sum(bool(r["emails"]) for r in leads)
    phones = sum(bool(r["phone"]) for r in leads)
    websites = sum(bool(r["website"]) for r in leads)
    coordinates = sum(r["latitude"] is not None and r["longitude"] is not None for r in leads)
    total = len(leads)
    return {
        "total": total,
        "with_email": emails,
        "with_phone": phones,
        "with_website": websites,
        "contactable": sum(bool(r["emails"] or r["phone"]) for r in leads),
        "social_profiles": sum(any(r[s] for s in SOCIAL_FIELDS) for r in leads),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "rated": len(ratings),
        "geocoded": coordinates,
        "email_coverage": round(100 * emails / total, 1) if total else 0,
        "phone_coverage": round(100 * phones / total, 1) if total else 0,
        "jobs": {"total": len(all_jobs), "pending": status["pending"], "working": status["working"],
                 "ok": status["ok"], "failed": status["failed"]},
        "categories": [{"name": name, "count": count} for name, count in by_category.most_common(7)],
        "rating_distribution": [{"bucket": str(i), "count": by_rating[str(i)]} for i in range(1, 6)],
        "options": {
            "categories": [name for name, _ in categories.most_common(100)],
            "jobs": [{"id": j["ID"], "name": j["Name"], "status": j["Status"]} for j in all_jobs[:100]],
        },
        "scanned": scanned,
        "partial": partial,
    }


def map_points(leads):
    points = []
    total = 0
    for row in leads:
        if row["latitude"] is None or row["longitude"] is None:
            continue
        total += 1
        if len(points) < MAX_MAP_POINTS:
            points.append({k: row[k] for k in ("title", "category", "address", "latitude", "longitude",
                                                  "review_rating", "emails", "phone", "website", "source_job_id")})
    return {"points": points, "total": total, "limited": total > MAX_MAP_POINTS}


def page_result(leads, filters, partial):
    start = (filters["page"] - 1) * filters["limit"]
    return {"total": len(leads), "page": filters["page"], "limit": filters["limit"],
            "items": leads[start:start + filters["limit"]],
            "has_more": start + filters["limit"] < len(leads), "partial": partial}


def export(leads, fmt):
    """(bytes, MIME). CSV formula injection is neutralized in exported spreadsheet cells."""
    if fmt == "json":
        return json.dumps(leads, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8"
    if fmt != "csv":
        raise InvalidQuery("format must be csv or json")
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(EXPORT_FIELDS)
    for row in leads:
        writer.writerow([safe_cell(row.get(field)) for field in EXPORT_FIELDS])
    return out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if FORMULA.match(text) else text


def handle(store, path, raw_query):
    """Return (status_code, response_body, MIME, additional_headers) for read-only routes."""
    filters = parse_query(raw_query)
    leads, categories, all_jobs, scanned, partial = scan(store, filters)
    if path == "/api/v1/dashboard":
        return 200, {
            "summary": summary(leads, categories, all_jobs, scanned, partial),
            "leads": page_result(leads, filters, partial),
            "map": map_points(leads),
        }, "application/json", ()
    if path == "/api/v1/dashboard/summary":
        return 200, summary(leads, categories, all_jobs, scanned, partial), "application/json", ()
    if path == "/api/v1/dashboard/leads":
        return 200, page_result(leads, filters, partial), "application/json", ()
    if path == "/api/v1/dashboard/geojson":
        m = map_points(leads)
        return 200, {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["longitude"], p["latitude"]]},
             "properties": {k: v for k, v in p.items() if k not in ("latitude", "longitude")}}
            for p in m["points"]], "total": m["total"], "limited": m["limited"]}, "application/json", ()
    if path == "/api/v1/dashboard/export":
        query = urllib.parse.parse_qs(raw_query, keep_blank_values=True)
        fmt = query.get("format", ["csv"])[0]
        body, ctype = export(leads, fmt)
        return 200, body, ctype, (("Content-Disposition", 'attachment; filename="prospects.' + fmt + '"'),)
    raise InvalidQuery("unknown dashboard route")