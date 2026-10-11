#!/usr/bin/env python3
"""Read-only verification of this checkout's published research files."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://inresearch.ai"
WAIT_SECONDS = 480
MAX_BYTES = 8 * 1024 * 1024
DOCS = "docs/research/2026-10-11/data-centers"
FILES = [
    (f"web/pages/research/data-centers-2026{s}.html",
     f"/research/data-centers-2026{s}.html")
    for s in ("", "-us", "-sea", "-cn", "-projects")
] + [
    (f"{DOCS}/project-ledger.json",
     "/research/data-centers-2026-project-ledger.json"),
    (f"{DOCS}/chart-data.json",
     "/research/data-centers-2026-chart-data.json"),
    ("web/pages/report.html", "/report.html"),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(body):
    return hashlib.sha256(body).hexdigest()


def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")),
          flush=True)


class ReportLink(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (tag == "a"
                and attrs.get("id") == "datacenter-capacity-study"
                and attrs.get("href") == "/research/data-centers-2026.html"):
            self.found = True


def report_link_ok(body):
    parser = ReportLink()
    parser.feed(body.decode("utf-8"))
    return parser.found


class FixedOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != "https"
                or parsed.hostname != "inresearch.ai"
                or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            raise ValueError("redirect left the fixed HTTPS origin")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WaitExpired(RuntimeError):
    pass


def expire(_signum, _frame):
    raise WaitExpired("publication verification deadline reached")


OPENER = build_opener(FixedOriginRedirect())


def check(item, commit, deadline):
    result = {
        "source": item.get("source"),
        "url": ORIGIN + item["path"],
        "expected_sha256": item.get("sha256"),
        "observed_at": now(),
        "http_status": None,
        "ok": False,
    }
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WaitExpired("publication verification deadline reached")
        request = Request(
            result["url"] + "?publication_verify=" + commit,
            headers={
                "User-Agent": "InResearch-Publication-Verifier/1",
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            },
            method="GET",
        )
        with OPENER.open(request, timeout=min(12, remaining)) as response:
            result["http_status"] = response.status
            final = urlsplit(response.geturl())
            if (final.scheme != "https"
                    or final.hostname != "inresearch.ai"
                    or final.path != item["path"]):
                raise ValueError("unexpected final URL")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("response exceeded byte limit")
            encoding = response.headers.get("Content-Encoding", "").lower()
            if encoding in ("", "identity"):
                body = raw
            elif encoding == "gzip":
                body = gzip.decompress(raw)
            else:
                raise ValueError("unsupported content encoding")
            if len(body) > MAX_BYTES:
                raise ValueError("decoded response exceeded byte limit")
            result.update(
                content_type=response.headers.get("Content-Type"),
                content_encoding=encoding or "identity",
                bytes=len(body),
                wire_sha256=sha(raw),
                actual_sha256=sha(body),
            )
            if response.status != 200:
                raise ValueError("HTTP status was not 200")
            if item.get("sha256") and sha(body) != item["sha256"]:
                raise ValueError("published bytes differ from checkout")
            if item["path"] == "/healthz":
                health = json.loads(body)
                if health.get("ok") is not True or health.get("service") != "inresearch":
                    raise ValueError("health response does not identify the healthy service")
            if item["path"] == "/report.html":
                result["report_link_ok"] = report_link_ok(body)
                if not result["report_link_ok"]:
                    raise ValueError("report entry link was not found")
            result["ok"] = True
    except WaitExpired:
        raise
    except Exception as error:
        if isinstance(error, HTTPError):
            result["http_status"] = error.code
        result["error"] = str(error)[:300]
    return result


def main():
    started = time.monotonic()
    receipt = {
        "event": "publication_verification_final",
        "schema_version": 1,
        "started_at": now(),
        "origin": ORIGIN,
        "wait_limit_seconds": WAIT_SECONDS,
        "ok": False,
        "attempts": 0,
        "checks": [],
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        if commit != os.environ.get("GITHUB_SHA", commit):
            raise ValueError("checkout does not match GITHUB_SHA")
        version = json.loads(
            (ROOT / "framework/current_state.json").read_bytes()
        )["version"]
        if version not in (ROOT / "framework/CURRENT.md").read_text():
            raise ValueError("CURRENT and current_state versions differ")
        receipt.update(checkout_sha=commit, source_version=version)

        items = [{"path": "/healthz"}]
        for source, path in FILES:
            body = (ROOT / source).read_bytes()
            if source.endswith(".json"):
                json.loads(body)
            if path == "/report.html" and not report_link_ok(body):
                raise ValueError("checkout report entry link is missing")
            items.append({
                "source": source, "path": path, "sha256": sha(body),
            })

        deadline = time.monotonic() + WAIT_SECONDS
        signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, WAIT_SECONDS)
        try:
            while time.monotonic() < deadline:
                receipt["attempts"] += 1
                receipt["checks"] = []
                for item in items:
                    receipt["checks"].append(check(item, commit, deadline))
                pending = [c for c in receipt["checks"] if not c["ok"]]
                emit({
                    "event": "publication_verification_attempt",
                    "attempt": receipt["attempts"],
                    "pending": [
                        {"url": c["url"], "http_status": c["http_status"],
                         "error": c.get("error")}
                        for c in pending
                    ],
                })
                if not pending:
                    receipt["ok"] = True
                    break
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(10, remaining))
            if not receipt["ok"]:
                receipt["error"] = "publication did not match before deadline"
        except WaitExpired as error:
            receipt["error"] = str(error)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    except Exception as error:
        receipt["error"] = str(error)[:300]

    receipt.update(
        finished_at=now(),
        elapsed_seconds=round(time.monotonic() - started, 2),
    )
    emit(receipt)
    message = json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::notice title=Publication verification receipt::" + message, flush=True)
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
