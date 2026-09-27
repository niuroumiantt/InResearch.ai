# 反哺台账：2026-09-27《造一座数据中心有多挣钱》→ inresearch.ai

> RESEARCH ARTIFACT · 2026-09-27 · 按 [专题反哺规则](../../../geluoke/专题反哺规则.md) 登记。状态：已采用条目已进入现行页面与数据；候选条目等待后续专题或事实层录入。

## 一、视角反哺（已采用）

文章把“数据中心挣不挣钱”拆成四层账本，`cost.html` 原来只算第一层的成本侧。本次把缺失的视角补进页面：

| 文章视角 | 原页面状态 | 本次去向 |
|---|---|---|
| 成本之上要看收入：租金 × 有效设备小时 | 无收入侧 | 新增“收益参照”输入与“租金能否覆盖全成本”卡片 |
| 研报算例是一个可切换的情景，不是行业均值 | 只有通用研究基准 | 新增预设“GB300 出租参照（100MW 折算）”，预设附口径说明 |
| 租金低于全成本时资本回收不足（H100 2026 年合约价） | 无 | 新增预设“H100 合约租金参照” |
| 数字要带时点与属性 | 页脚只有口径说明 | 新增“租金与造价基准”卡片，每条带来源、时点、属性 |
| 口径对账：CRF 年化 vs 直线折旧 + 税后 ROIC | 无 | `profit-model.py` 复算并写明两者差异 |

未采用的视角（需要新的页面或数据结构，先记为候选）：带电壳租约的成本收益率（NOI ÷ 造价）、四层利润分配（芯片／壳／算力／模型）、中国托管（每 MW EBITDA ÷ 造价）。它们对应 `research_graph.json` 的“价格、成本与商业”分支，适合作为下一次专题或独立页面。

## 二、数据反哺（已采用，进入 `data/datacenter_cost_model.json`）

| 条目 | 数值 | 时点 | 来源 | 属性 | 研究卡 |
|---|---|---|---|---|---|
| 1GW GB300 资本开支 | IT 230 亿 + 非 IT 160 亿美元 | 2026-09 | 摩根士丹利《AI 指南》p22、p27 | 预测估算 | report_facts A1/A2 |
| 每 GW GB300 GPU 数 / 利用率 / 租金 | 410,256 颗 / 75% / 8.5 美元 | 2026-09 | 同上 p26–27 | 预测估算 | report_facts A1 |
| 能源及其他运营支出 | 20 亿美元/GW·年 | 2026-09 | 同上 p27 | 预测估算 | report_facts A1 |
| H100 一年期合约租金 | 2.10–2.70 美元/GPU·小时 | 2026-04 | SemiAnalysis GPU 租金指数 | 研究实测 | gpu-rental-prices |
| H100 / B200 按需指数 | 2.82 / 3.68 美元 | 2026-04 | 同上 | 研究实测 | gpu-rental-prices |
| GB300 NVL72 五年折旧全成本 | 2.56–2.88 美元/有效 GPU·小时（80–90% 利用率） | 2026-08-31 | Data Gravity | 研究估算 | gpu-rental-prices |
| 绿地开发造价（不含 GPU） | 1,760 万美元/MW | 2026-09-03 | Cushman & Wakefield 公告 | 研究实测 | 09-14 档案 sources [3] |

预设中的作者拆分：100MW 折算后 IT capex 23 亿拆为服务器 20 亿 + 网络 3 亿；非 IT 16 亿拆为设施 13.5 亿 + 接入 2 亿 + 土地 0.5 亿；“能源及其他 2 亿/年”扣除模型电费 0.61 亿与需量费 0.18 亿后，其他运营支出取 1.21 亿。研报没有这些拆分，页面预设说明已注明。

## 三、价格序列录入（2026-09-27 第二轮，已采用）

`price_records.py --apply` 向 `data/prices.json` 追加 160 条记录、105 个序列，`manage.py validate --strict` 通过。页面“租金、造价与电价基准”改为按 `benchmark_series` 从价格库取每个序列的最新时点，新数据录入即显示，页面本身不再保存数字。

| 类别 | 序列（示例） | 记录数 | 来源等级 | 研究卡 |
|---|---|---|---|---|
| H100 一年期合约指数（区间中值） | gpu-hourly-h100-contract-1y，2023H1–2026-04 共 18 点 | 18 | research | gpu-rental-prices |
| H100 分段指数与历史中位数 | gpu-hourly-h100-{neocloud,hyperscaler,marketplace}-index | 16 | research | gpu-rental-prices |
| H200 / B200 / B300 / MI300X 指数、按需指数、挂牌中位数 | gpu-hourly-*-index、-ondemand-index、-ondemand-median | 11 | research / media | gpu-rental-prices |
| 厂商按需与预留价目 | gpu-hourly-*-ondemand-{lambda,nebius,runpod,verda,coreweave,aws,azure,oracle}、-capacity-block-aws | 29 | company / media | gpu-rental-prices |
| 中国整机月租 | gpu-monthly-*-cn-* | 3 | media | china-policy-costs |
| 研报假设与 TCO 估算 | benchmark-ms-gb300-rent-baseline、benchmark-ms-capex-per-gw-*、benchmark-gb300-nvl72-* | 10 | research / estimate | report_facts A1/A2、gpu-rental-prices |
| 造价 | construction-cost-greenfield-na、construction-cost-shell-per-it-mw-* | 7 | research / estimate | shell-lease-terms |
| 带电壳租约期均租金（作者计算） | shell-lease-rent-per-it-mw-year，11 单 | 11 | estimate | shell-lease-terms |
| 托管报价、REIT 收益率、空置率 | colo-asking-rent-*、colo-wholesale-rent-flapd-20mw-plus-eur、colo-rent-new-lease-dlr、reit-development-yield-dlr、vacancy-rate-na-cbre | 12 | research / company | cbre-jll-pricing-europe-apac、dlr-equinix-q2-2026 |
| 中国单位经济与电价 | cn-idc-*-gds、cn-colo-mrr-per-cabinet-vnet、cn-reit-fee-per-kw-month-gds、cn-dc-power-price-* | 9 | company / media | china-idc-companies、china-policy-costs |
| 电价与容量市场 | industrial-power-price-{us-*,ie,de,nl,no,se,fi,eu,my,jp,id}、pjm-capacity-price-bra-rto、ercot-realtime-all-in-power-cost | 34 | regulatory / research / media | power-price-benchmarks |

录入规则：`series_id + as_of` 唯一；区间取中值并在 `assumptions` 写明区间；作者由合同总额折算的租金记 `estimate` 并写明分母；公开页面不再更新的序列（SemiAnalysis 合约指数、研报假设）显式 `frequency: default`，避免按季度口径催更新。

## 三之二、仍未录入（候选）

- 超大规模 capex 与容量（2025–2028 分公司 capex、总算力 GW、ASIC 占比，report_facts A3）：属预测序列，等 `capex-*-annual` 序列口径确认后录入。
- 融资结构（3.21 万亿美元的股权/信贷拆分，report_facts A4）与高盛 2026–2031 分年 capex（report_facts B）：单次预测表，建议进事实层而非价格序列。
- 超大规模厂商折旧年限与未开始租赁承诺（研究卡 hyperscaler-depreciation-leases）：事实层候选，按 `knowledge.fact_contract` 补 asserter、caliber、locator。
- CoreWeave / Nebius / Applied Digital 财报与积压（研究卡 coreweave-q2-2026、nebius-applied-digital）：公司事实，进事实层。

## 四、研究问题（已立项）

`framework/research_questions.json` 新增 9 条 `origin: study-feedback` 问题（版本 2.2.0）：M11-Q11 带电壳成本收益率分布、M11-Q12 四层利润分配、M11-Q13 表外租赁承诺与 ROIC、M11-Q14 折旧年限对 NOPAT 的量化、M12-Q09 自建与租用算力的临界租金、M13-Q11 GB300/GB200 租金与全成本差距、M13-Q12 H100 租金口径调和、M14-Q11 中国托管收益率差距分解、M04-Q11 电价对 GPU 小时成本的弹性。验收要求作者计算附可复算脚本。

## 五、规范反哺

- `docs/geluoke/专题写作规则.md` 新增第九节“研究反哺”，指向本规则。
- 新建 `docs/geluoke/专题反哺规则.md`，规定每篇长文交付后的反哺步骤、落点与验收；第二轮补充“价格库是唯一数字来源，页面按序列取最新时点”。

## 六、本次未完成

- Excel 工作簿未加收益页（缺 openpyxl，且 09-14 基准不变，不影响一致性声明）。
- 事实层录入未做，见“三之二”候选；价格序列已录入。
- GB300 尚无公开租金指数，只有厂商挂牌与研报假设；M13-Q11 要求建立追踪序列。
