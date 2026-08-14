# 按需输出 — 使用说明

> 输出不是固定的。数据库在，任何角度的报告都是"一句话需求 → 生成器 → PDF/Word/Excel"。

## 已有的输出器

| 命令 | 产出 |
|---|---|
| `python3 pipeline/export.py --docx` | 全量研究报告（执行摘要 + 15 章，md + Word） |
| `python3 pipeline/export.py M08 M09 --docx --title "散热与电力设备专题"` | 任选模块组合的专题报告 |
| `python3 pipeline/output_map.py` | 全球 Top 10 数据中心园区地图（HTML + PDF，标注容量与用电量估算） |
| `python3 pipeline/output_map.py 15` | Top 15 版本 |

产出物统一落在 `reports/output/`，带数据快照日期，可复现。

## 怎么提新的输出需求

直接用一句话描述"角度 + 形式"，例如：

- "五大 Neocloud 的容量扩张曲线，折线图，PPT 一页"
- "中国 vs 海外的液冷渗透率对比，双栏表格，微信公众号排版"
- "所有 needs-review 结论清单，按模块分组，Excel"

每个需求会变成 `pipeline/output_*.py` 里的一个新生成器——写一次，以后同样角度随时重跑最新数据。

## 输出的口径纪律（自动继承）

所有输出器必须：数字可溯源到库内记录；混合口径必须拆列标注；推算值必须附公式与假设
（S5 级）；规划容量不得写成投运规模。详见《口径与核验规则手册》。

## 技术底座

HTML/SVG 排版 → 本机 Chrome 无头渲染 PDF（零 Python 依赖）；Word 由 python-docx 生成；
世界地图底图在 `assets/world.geo.json`。
