#!/usr/bin/env python3
"""Offline regression tests for the fork dashboard; no scraping, network or Chrome."""
import csv
import importlib.util
import io
import pathlib
import sys
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import dashboard_api as app


COLUMNS = ["title", "category", "address", "phone", "emails", "website", "review_rating", "review_count",
           "latitude", "longitude", "place_id", "data_id", "cid", "instagram"]


def csv_bytes(rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


class Store:
    def __init__(self, jobs=None, files=None):
        self.jobs = jobs or []
        self.files = files or {}

    def all(self):
        return self.jobs

    def read_csv(self, job_id):
        return self.files.get(job_id)


def sample_store():
    jobs = [
        {"ID": "new", "Name": "Cafés SP", "Date": "2026-11-07T12:00:00", "Status": "ok"},
        {"ID": "old", "Name": "Cafés SP antigo", "Date": "2026-11-06T11:00:00", "Status": "failed"},
    ]
    new = csv_bytes([
        {"title": "Café Central", "place_id": "p1", "category": "Café", "address": "Rua A, São Paulo",
         "phone": "+5511999888777", "emails": "contato@exemplo.com", "review_rating": "4.8",
         "review_count": "32", "latitude": "-23.55", "longitude": "-46.63", "website": "cafe.com.br",
         "instagram": "https://instagram.com/cafe"},
        {"title": "Padaria Centro", "place_id": "p2", "category": "Padaria", "address": "Rua B",
         "website": "padaria.com.br", "review_rating": "not-a-rating", "latitude": "-999", "longitude": "-46.62"},
        {"title": "=HYPERLINK(bad)", "place_id": "p3", "category": "Café", "address": "Rua C",
         "review_rating": "2.1", "review_count": "2"},
    ])
    old = csv_bytes([
        {"title": "Old Café", "place_id": "p1", "category": "Café", "emails": "old@example.com",
         "review_rating": "3.1"},
        {"title": "Drogaria", "place_id": "p4", "category": "Farmácia", "address": "Rua D",
         "latitude": "-23.56", "longitude": "-46.61", "review_rating": "5"},
    ])
    return Store(jobs, {"new": new, "old": old})


class TestAPI(unittest.TestCase):
    def test_empty_dashboard_is_real_zero(self):
        status, body, ctype, _ = app.handle(Store(), "/api/v1/dashboard", "")
        self.assertEqual((status, ctype), (200, "application/json"))
        self.assertEqual(body["summary"]["total"], 0)
        self.assertEqual(body["summary"]["average_rating"], None)
        self.assertEqual(body["map"]["points"], [])
        self.assertEqual(body["leads"]["items"], [])

    def test_dedupe_coverage_and_ratings(self):
        _, body, _, _ = app.handle(sample_store(), "/api/v1/dashboard", "")
        s = body["summary"]
        self.assertEqual(s["total"], 4)  # p1 from the newest job, not both
        self.assertEqual(s["with_email"], 1)
        self.assertEqual(s["with_phone"], 1)
        self.assertEqual(s["with_website"], 2)
        self.assertEqual(s["average_rating"], round((4.8 + 2.1 + 5.0) / 3, 2))
        self.assertEqual(s["jobs"], {"total": 2, "pending": 0, "working": 0, "ok": 1, "failed": 1})
        self.assertEqual(body["map"]["total"], 2)
        self.assertEqual(s["social_profiles"], 1)
        self.assertEqual(s["email_coverage"], 25.0)

    def test_filter_by_rating_and_email(self):
        _, result, _, _ = app.handle(sample_store(), "/api/v1/dashboard/leads", "min_rating=4&email=1")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["title"], "Café Central")

    def test_filter_search_category_and_job(self):
        _, result, _, _ = app.handle(sample_store(), "/api/v1/dashboard/leads",
                                     "q=São%20Paulo&category=Caf%C3%A9&job=new")
        self.assertEqual(result["total"], 1)
        _, other, _, _ = app.handle(sample_store(), "/api/v1/dashboard/leads", "job=old")
        self.assertEqual([r["title"] for r in other["items"]], ["Old Café", "Drogaria"])

    def test_pagination_and_sort(self):
        _, body, _, _ = app.handle(sample_store(), "/api/v1/dashboard/leads", "sort=rating&page=2&limit=1")
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["items"][0]["title"], "Café Central")
        self.assertTrue(body["has_more"])

    def test_geojson_valid_coordinates_only(self):
        _, body, _, _ = app.handle(sample_store(), "/api/v1/dashboard/geojson", "")
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual(len(body["features"]), 2)
        self.assertEqual(body["features"][0]["geometry"]["coordinates"], [-46.63, -23.55])
        self.assertNotIn("latitude", body["features"][0]["properties"])

    def test_csv_injection_sanitized(self):
        _, content, mime, headers = app.handle(sample_store(), "/api/v1/dashboard/export", "format=csv")
        self.assertIn("text/csv", mime)
        self.assertTrue(headers[0][1].endswith('prospects.csv"'))
        data = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        self.assertIn("'=HYPERLINK(bad)", [x["title"] for x in data])
        self.assertTrue(any(row["phone"].startswith("'+") for row in data))

    def test_json_export_and_invalid_format(self):
        _, content, mime, _ = app.handle(sample_store(), "/api/v1/dashboard/export", "format=json")
        self.assertIn("application/json", mime)
        self.assertIn('"Café Central"', content.decode("utf-8"))
        with self.assertRaises(app.InvalidQuery):
            app.handle(sample_store(), "/api/v1/dashboard/export", "format=xml")

    def test_bad_queries_fail_closed(self):
        for query in ("page=0", "page=aaa", "min_rating=nan", "min_rating=6", "min_rating=-1",
                      "sort=random", "limit=200", "q=" + "x" * 121):
            with self.subTest(query=query[:20]), self.assertRaises(app.InvalidQuery):
                app.parse_query(query)

    def test_scan_cap_signals_partial(self):
        with patch.object(app, "MAX_SCANNED", 2):
            _, body, _, _ = app.handle(sample_store(), "/api/v1/dashboard", "")
        self.assertTrue(body["summary"]["partial"])
        self.assertEqual(body["summary"]["scanned"], 2)
        self.assertEqual(body["summary"]["total"], 2)

    def test_map_limit_signals_clipping(self):
        with patch.object(app, "MAX_MAP_POINTS", 1):
            _, body, _, _ = app.handle(sample_store(), "/api/v1/dashboard", "")
        self.assertEqual(body["map"]["total"], 2)
        self.assertTrue(body["map"]["limited"])
        self.assertEqual(len(body["map"]["points"]), 1)

    def test_malformed_csv_does_not_crash(self):
        store = Store([{"ID": "j", "Name": "Bad", "Date": "", "Status": "ok"}], {"j": b"\xff\xfe"})
        _, body, _, _ = app.handle(store, "/api/v1/dashboard", "")
        self.assertEqual(body["summary"]["total"], 0)


class TestInstallPatch(unittest.TestCase):
    def test_patch_is_idempotent(self):
        spec = importlib.util.spec_from_file_location('patcher', ROOT / 'scripts' / 'install_dashboard_patch.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        source = '''import browser, jobs  # noqa: E402
OPENAPI = {}


def docs_page(nonce):
    pass
class Handler:
    def guard(self):
        if key and path not in ("/", "/api/docs", "/api/openapi.json") and not hmac.compare_digest(
            key, key):
            pass
    def do_GET(self):
        if path == "/api/v1/jobs":  # null when empty, as before: the docs' health check
            pass
PAGE = """<nav><span class="mono">v{version}</span><a href="/api/docs">API docs</a></nav></header>"""
'''
        patched = mod.patch_serve(source)
        self.assertIn('dashboard_api.handle', patched)
        self.assertIn('/dashboard/app.js', patched)
        self.assertIn('OPENAPI["paths"].update', patched)
        self.assertEqual(patched, mod.patch_serve(patched))


if __name__ == "__main__":
    unittest.main(verbosity=2)