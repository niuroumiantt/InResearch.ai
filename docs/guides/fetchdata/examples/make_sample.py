#!/usr/bin/env python3
"""Generate four SYNTHETIC offline examples; no network, no real research data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def build(output, team):
    root = Path(output) / team
    root.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc).isoformat()
    content = b'{"synthetic":true,"note":"Not a real source","price":7.5}\n'
    sha = hashlib.sha256(content).hexdigest()
    relative = "originals/" + sha + ".json"
    (root / "originals").mkdir()
    (root / relative).write_bytes(content)
    item = {"item_id": "synthetic-document", "source_id": "synthetic-source", "source_item_id": "synthetic-v1",
            "url": "https://example.invalid/synthetic.json", "title": "SYNTHETIC — never adopt",
            "publisher": "Example only", "retrieved_at": now, "sha256": sha, "path": relative,
            "content_type": "application/json", "access_scope": "public", "completeness": "complete", "version_of": None}
    revision = "0" * 40
    manifest = {"contract": "fetchdata-handoff/1", "provider_id": team,
                "delivery_id": "synthetic-" + team, "collector_revision": revision,
                "generated_at": now, "synthetic": True, "items": [item]}
    types = {"fetchstat": ("statistic_series", "electricity.industrial_price", "reported"),
             "fetchfilings": ("company", "finance.capex", "reported"),
             "fetchreports": ("study", "study.pue", "estimated"),
             "fetchquotes": ("product", "quote.price", "offer")}
    object_type, metric, kind = types[team]
    unknown = {"value": None, "precision": "unknown", "basis": None}
    observation = {"observation_id": "synthetic-" + team + "-1", "source_item_id": item["item_id"],
                   "object": {"type": object_type, "name": "SYNTHETIC — never adopt",
                              "match_status": "unresolved", "canonical_id": None, "identifiers": {}},
                   "metric": metric, "value": {"type": "number", "number": 7.5, "raw": "7.5"},
                   "unit": "synthetic_unit", "scope": "synthetic fixture only", "kind": kind,
                   "effective_time": unknown, "published_time": unknown,
                   "evidence": {"locator": "/price", "quote": '"price":7.5', "context": "Synthetic fixture, not evidence"},
                   "revision_of": None, "conflicts_with": [], "target_ids": []}
    counts = {k: 0 for k in ("scheduled_sources", "attempted_sources", "successful_sources", "unchanged_sources",
                             "failed_sources", "blocked_sources", "unattempted_sources", "duplicate_originals",
                             "matched_candidates", "conflicts", "received", "reviewed", "adopted", "published")}
    counts.update(new_originals=1, candidates=1, unresolved_candidates=1)
    report = {"run_id": manifest["delivery_id"], "team": team, "started_at": now, "finished_at": now,
              "collector_revision": revision, "counts": counts, "duration_seconds": 0,
              "bytes_downloaded": 0, "synthetic": True}
    for name, value in (("manifest.json", manifest), ("run-report.json", report)):
        (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "SHA256SUMS").write_text(sha + "  " + relative + "\n", encoding="ascii")
    (root / "observations.jsonl").write_text(json.dumps(observation, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "errors.jsonl").write_text("", encoding="utf-8")
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="new private/temp parent directory; existing team dirs are never overwritten")
    args = parser.parse_args()
    for team_name in ("fetchstat", "fetchfilings", "fetchreports", "fetchquotes"):
        print(build(args.output, team_name))
