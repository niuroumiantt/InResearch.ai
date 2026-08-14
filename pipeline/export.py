#!/usr/bin/env python3
"""报告导出器：从知识层按需汇编研究报告。报告 = 数据库的导出物。

    python3 pipeline/export.py                    # 全部模块 → 全量研究报告
    python3 pipeline/export.py M08 M09            # 指定模块 → 专题报告
    python3 pipeline/export.py --docx             # 同时产出 Word（需 python-docx，可选）
    python3 pipeline/export.py --title "散热专题" M08

产出：reports/output/YYYY-MM-DD_<标题>.md（+ .docx）
规则（继承口径纪律）：
  - 只导出 current 状态的 Finding 为正文；needs-review/stale 带警示标注导出
  - 状态行与"待办"是内部字段，不进对外产出物
  - 每模块章节含模块定位（取自模块定义）；附录自动汇总全部证据来源（去重）
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
OUT_DIR = ROOT / "reports" / "output"

FIELD_ORDER = ["结论", "论证", "证据", "口径提醒"]
INTERNAL_FIELDS = {"待办"}


def parse_findings(md_text):
    """把研究文档拆成 finding 块：[{id, title, qtags, status, revised, body_lines}]"""
    findings = []
    cur = None
    for line in md_text.split("\n"):
        m = re.match(r"^##\s+(M\d+-F\d+)\s+(.*?)\s*(\{[^}]*\})?\s*$", line)
        if m:
            if cur:
                findings.append(cur)
            cur = {"id": m.group(1), "title": m.group(2),
                   "qtags": (m.group(3) or "").strip("{}"), "status": "current",
                   "revised": "", "body": []}
            continue
        if cur is None:
            continue
        s = re.match(r"^-\s+\*\*状态\*\*：(\S+?)\s*｜\s*\*\*修订\*\*：(\S+)", line)
        if s:
            cur["status"], cur["revised"] = s.group(1), s.group(2)
            continue
        cur["body"].append(line)
    if cur:
        findings.append(cur)
    return findings


def clean_body(body_lines):
    """剔除内部字段（待办），保留结论/论证/证据/口径提醒。"""
    out, skipping = [], False
    for line in body_lines:
        m = re.match(r"^-\s+\*\*([^*]+)\*\*：?", line)
        if m:
            skipping = m.group(1).strip() in INTERNAL_FIELDS
        elif skipping and not line.startswith("  "):
            skipping = False
        if not skipping:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def module_position(mod_doc_path):
    """取模块定义文件"定位与边界"第一段作章节导语。"""
    try:
        text = (ROOT / "framework" / mod_doc_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    m = re.search(r"##\s*定位与边界\s*\n(.+?)(?:\n##|\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def collect_sources(findings):
    urls = []
    for f in findings:
        for line in f["body"]:
            for u in re.findall(r"https?://[^\s)）]+", line):
                if u not in urls:
                    urls.append(u)
    return urls


def main():
    args = [a for a in sys.argv[1:]]
    want_docx = "--docx" in args
    title = None
    if "--title" in args:
        title = args[args.index("--title") + 1]
        args.remove("--title"); args.remove(title)
    selected = [a for a in args if re.match(r"^M\d+$", a)]

    registry = json.loads((ROOT / "framework" / "modules.json").read_text(encoding="utf-8"))
    mods = registry["modules"]
    if selected:
        mods = [m for m in mods if m["id"] in selected]
    today = date.today().isoformat()
    title = title or ("全球数据中心研究报告" if not selected
                      else "专题报告：" + "、".join(m["name"] for m in mods))

    lines = [f"# {title}", "",
             f"> 由 Datacenter Hub 知识层导出 ｜ 数据快照 {today} ｜ 框架 v{registry['version']}",
             "> 口径与核验规则见《口径与核验规则手册》；每条结论的证据分级：S1 监管文件 / S2 公司披露 / S3 权威第三方 / S4 媒体 / S5 推算。",
             ""]
    all_findings, warn_count, chapters = [], 0, 0

    for m in mods:
        rp = m.get("research")
        if not rp or not (ROOT / rp).exists():
            continue
        findings = parse_findings((ROOT / rp).read_text(encoding="utf-8"))
        if not findings:
            continue
        chapters += 1
        lines.append(f"## {m['id']} {m['name']}")
        pos = module_position(m["doc"])
        if pos:
            lines.append("")
            lines.append("> " + pos.replace("\n", " "))
        lines.append("")
        for f in findings:
            qtag = f"（{f['qtags']}）" if f["qtags"] and f["qtags"] != "new" else ""
            lines.append(f"### {f['title']}{qtag}")
            if f["status"] != "current":
                warn_count += 1
                lines.append("")
                lines.append(f"> ⚠️ 本条状态为 {f['status']}（最后修订 {f['revised']}），结论可能需要更新，引用前请核验。")
            lines.append("")
            lines.extend(clean_body(f["body"]))
            lines.append("")
            all_findings.append(f)

    # 附录：来源清单
    sources = collect_sources(all_findings)
    lines += ["## 附录：来源清单", ""]
    lines += [f"{i+1}. {u}" for i, u in enumerate(sources)]
    lines.append("")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w一-鿿：、]", "_", title)
    md_path = OUT_DIR / f"{today}_{safe}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"导出 {chapters} 章 ｜ {len(all_findings)} 条 Finding（{warn_count} 条带警示）｜ {len(sources)} 个来源")
    print(f"→ {md_path.relative_to(ROOT)}")

    if want_docx:
        try:
            import docx  # noqa
        except ImportError:
            print("python-docx 未安装，跳过 Word 输出（pip install python-docx）")
            return 0
        docx_path = md_path.with_suffix(".docx")
        write_docx("\n".join(lines), docx_path)
        print(f"→ {docx_path.relative_to(ROOT)}")
    return 0


def write_docx(md_text, path):
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Songti SC"
    style.font.size = Pt(10.5)

    def add_runs(par, text):
        pos = 0
        for m in re.finditer(r"\*\*([^*]+)\*\*", text):
            if m.start() > pos:
                par.add_run(text[pos:m.start()])
            par.add_run(m.group(1)).bold = True
            pos = m.end()
        if pos < len(text):
            par.add_run(text[pos:])

    for raw in md_text.split("\n"):
        if not raw.strip():
            continue
        h = re.match(r"^(#{1,3})\s+(.*)", raw)
        if h:
            doc.add_heading(re.sub(r"\*\*", "", h.group(2)), level=len(h.group(1)))
            continue
        if raw.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            add_runs(p, raw[2:])
            continue
        li = re.match(r"^(\s*)-\s+(.*)", raw)
        if li:
            p = doc.add_paragraph(style="List Bullet" if len(li.group(1)) < 2 else "List Bullet 2")
            add_runs(p, li.group(2))
            continue
        num = re.match(r"^\d+\.\s+(.*)", raw)
        if num:
            add_runs(doc.add_paragraph(style="List Number"), num.group(1))
            continue
        add_runs(doc.add_paragraph(), raw)
    doc.save(path)


if __name__ == "__main__":
    sys.exit(main())
