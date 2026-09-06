#!/usr/bin/env python3
"""inews candidate import. Use --input with an acquisition.py export-news projection.
Current policy: framework/06_acquisition.md; the old news/data contract is retired.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 歧义词条：常见词/多义词，必须与语境词同现
AMBIGUOUS = {"meta", "switch", "lambda", "scala", "oracle", "frontier", "colossus",
             "prometheus", "hyperion", "eaton", "trane", "crusoe", "stack", "台达", "华为"}
CONTEXT = re.compile(
    r"data\s?cent|datacenter|\bai\b|\bgpu\b|cloud|compute|chip|cooling|server|hyperscal|"
    r"数据中心|算力|智算|液冷|散热|芯片|服务器|云|机房|英伟达|超算", re.IGNORECASE)


def build_terms():
    """返回 [(entity_id, entity_type, term, is_latin)]，词条已清洗。"""
    terms = []

    def clean(name):
        name = re.sub(r"[（(].*?[)）]", "", name)          # 去括号注释
        return [p.strip() for p in name.split(" / ") if len(p.strip()) >= 3]

    companies = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))["records"]
    for c in companies:
        for term in clean(c["name"]) + ([c["name_cn"]] if c.get("name_cn") and c["name_cn"] != c["name"] else []):
            terms.append((c["company_id"], "company", term))
    projects = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))["records"]
    for p in projects:
        for term in clean(p["name"]) + [a for a in p.get("aliases", []) if len(a) >= 4]:
            terms.append((p["site_id"], "project", term))

    compiled = []
    for eid, etype, term in terms:
        is_latin = bool(re.match(r"^[\x00-\x7f]+$", term))
        if is_latin:
            pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        else:
            pat = re.compile(re.escape(term))
        compiled.append((eid, etype, term, pat))
    return compiled


def main():
    import acquisition
    sys.argv = [sys.argv[0], 'news', *sys.argv[1:]]
    return acquisition.main()

if __name__ == '__main__':
    raise SystemExit(main())
