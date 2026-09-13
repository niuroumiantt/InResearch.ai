#!/usr/bin/env python3
"""报告导出器：从知识层按需汇编研究报告。报告 = 数据库的导出物。

    python3 manage.py export                    # 全部模块 → 全量研究报告
    python3 manage.py export M08 M09            # 指定模块 → 专题报告
    python3 manage.py export --docx             # 同时产出 Word（需 python-docx，可选）
    python3 manage.py export --title "散热专题" M08

产出：reports/output/YYYY-MM-DD_<标题>.md（+ .docx）
规则（继承口径纪律）：
  - 只导出 current 状态的 Finding 为正文；needs-review/stale 带警示标注导出
  - 状态行与"待办"是内部字段，不进对外产出物
  - 每模块章节含模块定位（取自模块定义）；附录自动汇总全部证据来源（去重）
"""

from inresearch.paths import project_root
import re
import sys
from datetime import date

ROOT = project_root()
OUT_DIR = ROOT / "reports" / "output"

from inresearch.delivery.report import build_report, markdown_report


def main():
    args = [a for a in sys.argv[1:]]
    want_docx = "--docx" in args
    title = None
    if "--title" in args:
        title = args[args.index("--title") + 1]
        args.remove("--title"); args.remove(title)
    selected = [a for a in args if re.match(r"^M\d+$", a)]

    report = build_report(ROOT, selected)
    today = date.today().isoformat()
    title = title or report['title']
    lines = markdown_report(report, title, today)
    chapters = len(report['chapters'])
    if not chapters:
        print("No current report chapters", file=sys.stderr)
        return 1
    all_findings = [f for ch in report['chapters'] for f in ch['findings']]
    warn_count = report['review_count']
    sources = report['sources']

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w一-鿿：、]", "_", title)
    md_path = OUT_DIR / f"{today}_{safe}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"导出 {chapters} 章 ｜ {len(all_findings)} 条 Finding（{warn_count} 条带警示）｜ {len(sources)} 个来源")
    print(f"→ {md_path}")

    if want_docx:
        try:
            import docx  # noqa
        except ImportError:
            print("python-docx 未安装，跳过 Word 输出（pip install python-docx）")
            return 0
        docx_path = md_path.with_suffix(".docx")
        write_docx("\n".join(lines), docx_path)
        print(f"→ {docx_path}")
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
