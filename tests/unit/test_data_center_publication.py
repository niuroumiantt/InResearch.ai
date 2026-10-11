"""Publication verification rejects stale bytes and misleading health replies."""
import importlib.util
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("publication_verifier", ROOT/"scripts/verify_data_center_publication.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class Response:
    status = 200
    headers = {"Content-Type": "text/html"}
    def __init__(self, body, path):
        self.body = body
        self.path = path
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.body[:limit]
    def geturl(self):
        return verifier.ORIGIN + self.path


class PublicationVerifierTests(unittest.TestCase):
    def check(self, body, path="/report.html", expected=None):
        item = {"path": path}
        if expected is not None:
            item["sha256"] = verifier.sha(expected)
        with patch.object(verifier.OPENER, "open", return_value=Response(body, path)):
            return verifier.check(item, "revision", time.monotonic()+5)

    def test_stale_source_bytes_and_unhealthy_service_never_pass(self):
        body = b'<a id="datacenter-capacity-study" href="/research/data-centers-2026.html">Study</a>'
        self.assertTrue(self.check(body, expected=body)["ok"])
        self.assertFalse(self.check(body, expected=body+b"new source")["ok"])
        self.assertFalse(self.check(b'{"ok": false, "service": "inresearch"}', "/healthz")["ok"])
        self.assertTrue(self.check(b'{"ok": true, "service": "inresearch"}', "/healthz")["ok"])

    def test_exact_report_entry_and_fixed_https_origin(self):
        self.assertFalse(verifier.report_link_ok(b'<a href="/research/data-centers-2026.html">Wrong id</a>'))
        self.assertFalse(verifier.report_link_ok(b'<a id="datacenter-capacity-study" href="/login">Wrong destination</a>'))
        guard = verifier.FixedOriginRedirect()
        for url in ("http://inresearch.ai/report.html", "https://other.example/report.html",
                    "https://user:password@inresearch.ai/report.html", "https://inresearch.ai:8080/report.html"):
            with self.assertRaises(ValueError):
                guard.redirect_request(None, None, 302, "redirect", {}, url)
