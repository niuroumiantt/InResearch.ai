# SemiAnalysis资料筛选与采用记录

核验日期：2026年9月14日。文章第三版。

## 资料位置与读取范围

当前原件目录：[重要SemiAnalysis](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis>)。

目录包含77份PDF，总大小约1.33GB。与原Downloads目录逐文件比较SHA256，77份内容一致。按文件字节去重为71份；另有语言不同但主题相同的版本，不能当成独立证据。

已建立全部文件的题名、页数、文件大小、SHA256和首页索引。选出21份提取正文，重点核读成本、供电、融资和PJM相关章节，并渲染10页查看原图。**提取全文不等于逐页审阅，未宣称77份全部读完或全部核实。** 原件未修改、移动或删除。

## 已进入文章的资料

| 材料 | 日期与读取位置 | 本次采用 | 未采用或边界 |
|---|---|---|---|
| Rubin NVL72 vs GB200 Inference TCO | 2026-07-23；PDF第13–22页，图表重点第19–20页 | 第19页持有成本；复算约1.94倍的同约束吞吐打平门槛 | 未取得完整底层TCO模型；版本存疑的Token成本曲线不进入正文 |
| How Much Do GPU Clusters Really Cost? | 2026-04-20；第9–11、21–24、26、28–29页 | 故障影响范围、检查点和有效产出机制；构建64与4096GPU独立算例 | 不照搬供应商排名、成本差异百分比或2025历史租价 |
| The Onsite Gas Deep Dive | 本地PDF2025-12-31，官网2025-12-30；第11–12、25–30、39–40页 | 第39页工业燃机参数；1GW IT到1.68GW装机、59.5%平均利用程度 | 不把装机冗余系数当成可靠性证明；不同发电路线的成本不直接比较 |
| Nvidia GPU Debt Backstop | 2026-07-06；第4–9、12–13页 | 第7页明确标注为示例的收入分成；6.75、3.68、40%独立复算 | 不是标准合同，未验证所有交易的保障条款 |
| PJM’s $12B modeling mistake | 2026-08-16；第1–5、12–23和29–31页相关段落；重点19、21页 | 11.57B的时间范围与反事实性质；保留后两年仍约束于价格上限的结果 | 底层系统模型未独立重跑，不写成已确认违规收费或社会净损失 |
| Columbia Markus Academy讲义 | 2026-03-19；第26、28页 | 只提供Meta Hyperion融资线索，回到Meta公告核验 | 这份是Stijn Van Nieuwerburgh的Columbia讲义，**不是SemiAnalysis研究** |

上述PDF原件：

- [Vera Rubin NVL72 vs GB200 NVL72 Inference TCO  Architecture Analysis.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/Vera Rubin NVL72 vs GB200 NVL72 Inference TCO  Architecture Analysis.pdf>)
- [How Much Do GPU Clusters Really Cost_.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/How Much Do GPU Clusters Really Cost_.pdf>)
- [How AI Labs Are Solving the Power Crisis_ The Onsite Gas Deep Dive.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/How AI Labs Are Solving the Power Crisis_ The Onsite Gas Deep Dive.pdf>)
- [Nvidia GPU Debt Backstop Unleashes the AI Project Trinity Capital Offtake and Datacenters.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/Nvidia GPU Debt Backstop Unleashes the AI Project Trinity Capital Offtake and Datacenters.pdf>)
- [$12B of US ratepayers' money wasted on a modeling mistake and PJM wants to do it again.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/$12B of US ratepayers' money wasted on a modeling mistake and PJM wants to do it again.pdf>)
- [Datacenters-Slide-deck Columbia BS.pdf](</Users/m5/Library/Mobile Documents/com~apple~CloudDocs/Larry XIE/0FFFF_学习/重要SemiAnalysis/Datacenters-Slide-deck Columbia BS.pdf>)

## 回原文补充的证据

1. [CoreWeave Rubin测试介绍](https://coreweave.com/blog/nvidia-vera-rubin-nvl72-on-coreweave-10x-more-tokens-per-megawatt-than-blackwell)：每兆瓦吞吐与TCO分开；供应商结果不等于采购验收。
2. [Meta Hyperion合资公告](https://investor.atmeta.com/investor-news/press-release-details/2025/Meta-Announces-Joint-Venture-with-Funds-Managed-by-Blue-Owl-Capital-to-Develop-Hyperion-Data-Center/)：采用公司披露的设施开发边界、初始租期和附条件残值保障；不沿用讲义中未核实的债券与交易价推算。
3. [Monitoring Analytics原始报告](https://www.monitoringanalytics.com/reports/Reports/2024/IMM_Analysis_of_the_20252026_RPM_Base_Residual_Auction_Part_A_20240920.pdf)：其2025/26单期敏感性范围与SemiAnalysis两期估算不同，不能把两者当成同一结论的重复确认。

## 已识别的口径冲突与处置

- GPU集群资料：正文大规模训练比较提到1.10、1.15等相对成本，第24页上方图示却出现1.05、1.09；同页下方费用归因图与上方金额也不完全相同。没有自行选择较大的一个作为结论。正文改用可检查的独立故障算例。
- Rubin资料：第19页文字与持有成本表一致，采用该处输入。第20页曲线含早于正文日期的更新标注，曲线与数字表之间存在需要版本解释的差异，外部供应商数据还附有未独立核验说明。未采用这一页的Token成本绝对值、整条曲线或采购节省百分比。
- 现场燃气资料：只采用指定工业燃机情景。燃料电池段的使用寿命叙述与表格不同；不把整张跨技术比较表无条件复用。报告里的1.20系数不等同于完成N+1+1或可用率认证。
- PJM标题中的“浪费”是作者立场。正文改为有时间范围的反事实估计，明确实际账单、假设下可减少的付款和社会净资源损失之间的区别。
- 2026-09-11的Backstop Universe汇总了多种承诺与风险安排。本次没有把其总规模直接写成已确认债务或担保余额。需要逐项合同与公司披露才能汇总。

这些疑点不意味着整篇报告没有价值。它们决定可用的是分析机制、特定参数或已披露事实，而不是无条件沿用全部结论。

## 已提取、尚未作为新增量化结论采用

| 资料方向 | 暂不新增量化引用的原因 |
|---|---|
| Behind-The-Meter Power（2026-09） | 项目订单与法务许可判断仍需逐项原件；本文先采用边界清楚的装机算例 |
| Everyone Wants To Be A Neocloud / Oracle | 公司经营策略可补充背景，本轮优先可核验的成本机制 |
| GB200 BOM / AI Server Cost（2023） | 可用来拆部件，但旧代际价格不能直接当2026采购价 |
| Memory Mania / CPO | 资料重要，暂未把专有供需和价格预测纳入当前基础模型 |
| AI Training Load Fluctuations | 需将波动测试、储能需求与实际电价规则衔接后再货币化 |
| Water Footprint | 跨行业比喻的功能单位与地域边界不同；保留原文现场与上游分账 |
| Cancellation / Microsoft Freeze | 供给预测、公告和投运分母不能混用；专有供给数据库本次未独立重建 |
| InferenceX / Trainium / TPUv7 | 测试模型、量化和交互标准不同，尚未制作跨平台采购排名 |

## 本轮改动与可复算数据

正文在第05、10、14、18、21章增加五组分析，新增三张原创图表。原100MW模型参数和结果保持不变。这批资料先形成第三版；随后结合Bernstein原件修订为第四版，约2.04万汉字，23章、31张图、49项来源记录。

新增工作簿“资料案例”页，列出三个图表的输入与公式，以及承购分成、Hyperion和PJM的原始观察值。当前工作簿34项公式与参数变动检查通过。所有输入注明是研究估计、公司披露还是本文假设。

后续更新：用户已另外提供Bernstein 2026-06-08完整20页PDF，第四版已完成成本表和关键脚注核对，见bernstein-report-trace.md。原作者Excel底稿尚未取得。
