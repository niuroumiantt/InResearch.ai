#!/usr/bin/env python3
"""Read-only M4 preflight for research-material batches.

This is deliberately not a reader and never writes Spark's catalog.  It builds
an auditable routing manifest from names, paths and suffixes so that reports
can be selected before drawings, CAD and archives consume the reading queue.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SOURCE = Path("/Users/m4/Downloads/所有raw materials")
DEFAULT_OUTPUT = Path("/Users/m4/.local/share/inresearch.ai/m4-preflight")

REPORT_WORDS = re.compile(
    r"(report|whitepaper|forecast|outlook|trend|market|semiconductor|"
    r"半导体|晶圆|存储|nand|dram|hbm|ssd|gpu|数据中心|idc|服务器|"
    r"techinsights|trendforce|world fab|硅|芯片)", re.I)
DRAWING_WORDS = re.compile(r"(图纸|平面图|剖面图|大样图|配筋|建筑|结构|机电|施工|dwg|cad)", re.I)
OFFICE_SUFFIXES = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf"}
ASSET_SUFFIXES = {".dwg", ".dxf", ".skp", ".rvt", ".ifc", ".3ds", ".max", ".fbx", ".obj", ".stl"}
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2"}


def route(rel: Path) -> tuple[str, int, str]:
    """Return bucket, priority and explainable reason; never claim content quality."""
    name = str(rel)
    suffix = rel.suffix.lower()
    if suffix in ASSET_SUFFIXES:
        return "asset_later", 0, "CAD/3D asset requires preview and licence review"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive_review", 0, "archive requires manifest before reading"
    if suffix in OFFICE_SUFFIXES:
        return "office_conversion", 1, "Office source requires conversion before reader intake"
    if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
        return "ocr_candidate", 1, "image source requires OCR or visual review"
    if suffix == ".pdf":
        if DRAWING_WORDS.search(name):
            return "asset_later", 0, "drawing-like PDF is retained outside report-first queue"
        if REPORT_WORDS.search(name):
            return "priority_read", 3, "report-like filename/path matches research themes"
        return "reader_candidate", 2, "PDF needs reader triage before content judgement"
    if suffix in {".txt", ".md", ".csv", ".tsv", ".html", ".htm"}:
        return "priority_read", 3 if REPORT_WORDS.search(name) else 2, "directly readable text source"
    return "format_review", 0, "unsupported or unknown format needs routing review"


def scan(root: Path):
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(names):
            if name.startswith("."):
                continue
            path = Path(current) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            bucket, priority, reason = route(rel)
            yield {
                "relative_path": str(rel), "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size, "bucket": bucket,
                "priority": priority, "reason": reason,
            }


def write_run(records, root: Path, output: Path):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = output / stamp
    run.mkdir(parents=True, mode=0o700)
    records = list(records)
    fields = ["relative_path", "suffix", "size_bytes", "bucket", "priority", "reason"]
    with (run / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    with (run / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(records)
    counts = Counter(r["bucket"] for r in records)
    priority = [r for r in records if r["bucket"] == "priority_read"]
    lines = ["# M4 预筛结果", "", f"- 生成时间（UTC）：{stamp}", f"- 只读来源：`{root}`", "- 本清单按文件名、路径和类型路由，不是内容质量或完整性验证。", "", "## 路由汇总", ""]
    lines.extend(f"- {bucket}: {counts[bucket]}" for bucket in sorted(counts))
    lines += ["", "## 优先阅读候选（前 100 项）", ""]
    lines.extend(f"- `{r['relative_path']}` — {r['reason']}" for r in priority[:100])
    (run / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run, counts


def main():
    parser = argparse.ArgumentParser(description="Build a read-only M4 material preflight manifest")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"source is not a directory: {args.source}")
    run, counts = write_run(scan(args.source), args.source, args.output)
    print(json.dumps({"run": str(run), "buckets": dict(sorted(counts.items()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
