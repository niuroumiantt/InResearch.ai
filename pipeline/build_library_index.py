#!/usr/bin/env python3
"""重建研报库索引 docs/LIBRARY_INDEX.md：小目录逐文件列出，大目录（>80 文件）记摘要。零依赖。"""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "docs" / "library"
LIMIT = 80

MAP = {"01_标准与规范": "M01/M05", "02_制冷与供配电": "M08/M09", "03_云计算": "M02/M03",
       "04_市场与研究": "M01/M03/M06/M11/M12", "05_数据中心设施": "M05/M10",
       "06_工程图纸": "爆炸图素材/M05/M10", "07_方案与模板": "M05/M10 工程实务",
       "08_培训与课件": "运维知识/M10", "90_待分类": "待归类"}


def dirstat(d):
    files = [f for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")]
    return len(files), sum(f.stat().st_size for f in files) / 1e9


def main():
    lines = ["# 第三方研报库索引 — docs/library/", "",
             "> 二进制不进 git；本索引进 git 作全量清单。大目录（>80 文件）仅记摘要，明细可用",
             "> `find docs/library/<目录> -type f` 查看。精读打分清单见 docs/LIBRARY_SCORES.csv。", ""]
    total_n, total_g = 0, 0.0
    for top in sorted(LIB.iterdir()):
        if not top.is_dir():
            continue
        n, g = dirstat(top)
        total_n += n; total_g += g
        lines.append(f"## {top.name} → {MAP.get(top.name, '')}（{n} 份 / {g:.1f}GB）")
        lines.append("")
        for sub in sorted(top.iterdir()):
            if sub.is_dir():
                sn, sg = dirstat(sub)
                if sn > LIMIT:
                    lines.append(f"- 📦 {sub.name}/（{sn} 份 / {sg:.1f}GB，摘要模式）")
                else:
                    lines.append(f"- {sub.name}/（{sn} 份）")
                    for f in sorted(sub.rglob("*")):
                        if f.is_file() and not f.name.startswith("."):
                            lines.append(f"  - {f.relative_to(sub)}（{f.stat().st_size/1048576:.1f}MB）")
            elif not sub.name.startswith("."):
                lines.append(f"- {sub.name}（{sub.stat().st_size/1048576:.1f}MB）")
        lines.append("")
    lines.append(f"共 {total_n} 份 / {total_g:.1f}GB ｜ 生成 {date.today().isoformat()} ｜ 重建：python3 pipeline/build_library_index.py")
    (ROOT / "docs" / "LIBRARY_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"索引重建：{total_n} 份 / {total_g:.1f}GB")


if __name__ == "__main__":
    main()
