#!/usr/bin/env python3
"""收件箱扫描：列出 docs/inbox/ 新材料并按扩展名/文件名给出归类建议。零依赖。"""

from inresearch.paths import project_root
import sys

ROOT = project_root()
INBOX = ROOT / "docs" / "inbox"

HINT = [
    (("dwg", "dxf", "step", "stp"), "docs/library/06_工程图纸/"),
    (("xlsx", "xls", "csv"), "数据提取入六张表 → 原件归 docs/library/04_市场与研究/"),
    (("doc", "docx"), "自产 → docs/source/；第三方 → docs/library/按内容分类"),
    (("pdf", "pptx", "ppt"), "docs/library/ 按内容分类（标准/制冷供配电/云/市场/设施）"),
]
KEY = [("标准", "01_标准与规范"), ("规范", "01_标准与规范"), ("GB", "01_标准与规范"),
       ("液冷", "02_制冷与供配电"), ("制冷", "02_制冷与供配电"), ("散热", "02_制冷与供配电"),
       ("UPS", "02_制冷与供配电"), ("供配电", "02_制冷与供配电"), ("电源", "02_制冷与供配电"),
       ("云", "03_云计算"), ("市场", "04_市场与研究"), ("投资", "04_市场与研究"),
       ("设施", "05_数据中心设施"), ("图纸", "06_工程图纸"), ("平面", "06_工程图纸")]


def main():
    files = [f for f in sorted(INBOX.rglob("*")) if f.is_file() and f.name != "README.md" and not f.name.startswith(".")]
    if not files:
        print("收件箱为空。有新材料放入 docs/inbox/ 后再扫描。")
        return 0
    print(f"收件箱待处理 {len(files)} 份：\n")
    for f in files:
        ext = f.suffix.lower().lstrip(".")
        mb = f.stat().st_size / 1048576
        dest = next((d for exts, d in HINT if ext in exts), "docs/library/90_待分类/")
        kw = next((f"（文件名含「{k}」→ {v}）" for k, v in KEY if k.lower() in f.name.lower()), "")
        print(f"  {f.name}（{mb:.1f}MB, .{ext}）")
        print(f"    建议 → {dest} {kw}")
    print("\n处理方式：对 Claude 说「整理收件箱」即可（按内容核实分类、统一重命名、登记索引）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
