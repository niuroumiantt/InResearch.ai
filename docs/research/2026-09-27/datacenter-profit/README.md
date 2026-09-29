# 数据中心盈利研究档案（造一座数据中心有多挣钱）

> 历史材料 · 2026-09-28 起 `cost.html` 已并入 `ledger.html`（统一经济模型 `data/datacenter_model.json`，唯一参考实现 `knowledge/economics.py`）；本目录记录当时的研究，不作当前执行指令。
> RESEARCH ARTIFACT · 2026-09-27 · 不是当前行业报价或投资建议。

本目录保存《造一座数据中心有多挣钱——账本上31%，壳层16%–20%，中国11%》专题反哺到 inresearch.ai 的研究实体：正文、来源清单、与 `cost.html` 的对账脚本，以及本次反哺台账。公众号 HTML、首图、正文图和制作脚本留在 `outputs/geluoke-research/2026-09-27-datacenter-profit/`，不重复复制。

## 权威边界

- 网页计算器当前口径：`data/datacenter_cost_model.json`（schema 2，本专题新增收益参照、两个情景预设与租金/造价基准）
- 计算公式实现：`web/components/datacenter-cost.js`
- 与研报口径对账：`profit-model.py` → `profit-model-results.json`
- 价格序列录入：`price_records.py`（160 条、105 个序列，`--apply` 追加到 `data/prices.json`；页面基准按序列取最新时点）
- 研究叙事：`article.md`；来源：`sources.md`（62 个机构组）
- 研究卡（10 张、369 个数据点）与研报页码摘录：`outputs/geluoke-research/2026-09-27-datacenter-profit/work/research/cards.json`、`work/report_facts.md`
- 本次反哺内容与去向：`feedback.md`

## 与 2026-09-14 成本档案的关系

2026-09-14 的研究基准（年化总成本约 11.678 亿美元、每有效设备小时约 4.10 美元）保持不变，Excel 工作簿不改。本专题只在同一公式上增加“租金 − 全成本”的收益参照，并以研报算例作为可切换的情景预设；预设的服务器/网络、设施/接入/土地拆分是作者拆分，研报只给 IT 与非 IT 两项。

## 边界提示

- 计算器的“每小时盈余”是超过资本成本率的部分；研报的 NOPAT/ROIC 按直线折旧与 21% 税率计算。两者收入一致、成本口径不同，对账数字见 `profit-model-results.json`。
- 租金基准来自各自时点的公开指数、厂商价目与研究报告，页面按“研究实测／预测估算／研究估算”标注，不代表当期成交价。
- 第三方研报原件不复制进 Git。
