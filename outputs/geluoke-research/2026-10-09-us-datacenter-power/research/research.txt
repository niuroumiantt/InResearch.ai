# 美国数据中心电力：inresearch.ai研究输入

研究时点：2026-10-09。

## 接收要求与本次边界

已查阅当前CURRENT、口径与采集规范、对象规则、research_questions、tco_targets及submission schema。需求来自现行问题与五类变量；节点和变量类别沿原登记，M04只作为兼容模块。材料、候选、正式事实和模型参数分别处理。本批为候选素材投递，尚未执行Reader深读/C3或远程数据库采用；未修改现行价格基准、项目GW、问题状态。

每份素材提供具名机构、原文URL、日期、访问状态、身份摘要、读取范围、中文导读与逐条定位。原始PDF/HTML存本机原件目录，受限网页仅归档工具响应，不能声称获得其原始字节。公众号文章为叙述稿，不作为原件的独立佐证，也不重复计作新证据。

## 命中的现行问题

| 问题ID | 当前问题 | 节点 / 五类变量 | 候选证据 |
|---|---|---|---|
| M04-Q01 | 主要电网（PJM/ERCOT/Dominion 等）的排队规模、平均等待年限、清退率？ | root / 第4类 | C10, C33, C34, S01 |
| M04-Q02 | 自备电源（behind-the-meter）项目的实际投运案例与经济性？ | root / 第1类 | C26, C28, C29, C30, S03, S05 |
| M04-Q03 | 核电/SMR 合同的真实交付时间表 vs 宣传？ | root / 第4类 | C24, C25 |
| M04-Q04 | 数据中心 PPA 价格走势；电价上涨向居民转嫁引发的政治反弹？ | root / 第3类 | C14, C15, C16, C17, C18, C19, C20, C21, C25, C26, C27, S02, S09 |
| M04-Q05 | 各情景下 2030 年电力供给能支撑多少 GW（M15 情景的核心约束）？ | root / 第1类 | C03, C04, C05, C06, C07, C08, C09, C21, C30, S01, S08 |
| M04-Q07 | 并网排队时长的区域差异 | root / 第4类 | C10, C11, C33, S04, S07, S08 |
| M05-Q04 | 社区反对（噪音/用水/电价）导致的项目延期或取消案例库？ | root / 第3类 | C23 |
| M09-Q01 | 大型电力变压器交期走势？扩产（新工厂投产时间表）能否追上需求？ | root / 第4类 | C12, C13 |
| OBJ-grid-definition | 电网接入与并网：定义、组成与边界是什么？哪些对象不属于它？ | site:grid / 第1类 | C01 |
| OBJ-grid-interfaces | 电网接入与并网：输入、输出、接口与上下游依赖是什么？哪些条件限制互换？ | site:grid / 第1类 | C02, S07 |
| OBJ-grid-alternatives | 电网接入与并网：有哪些替代方案？在同一口径下性能、成本和约束如何比较？ | site:grid / 第3类 | C22, S06 |
| OBJ-grid-supply | 电网接入与并网：价值如何形成？供应商、制造或交付环节、交期及生命周期成本如何分解？ | site:grid / 第3类 | C31, C32 |
| M04-Q11 | 各区域工业电价差异（得州 7 美分、弗吉尼亚 10 美分、爱尔兰 25 欧分、宁夏 0.36 元）对每 GPU 小时全成本的弹性是多少？租金差异能否覆盖电价差异？ | root / 第3类 | C35, C36, C37, C38, C39, C40, C41 |

## 逐项候选事实与机制

### C01　美国本土主要同步互联

数值：3 个；期间：截至2026-10-09；属性：定义。

口径：本土48州；不含AK/HI；有有限直流联络。

来源：[EIA｜Electricity delivery to consumers](https://www.eia.gov/energyexplained/electricity/delivery-to-consumers.php)；源日期：None。

定位：Electricity interconnections小节；短引：Three。命中：OBJ-grid-definition。状态：候选。

### C02　FERC大负荷改革适用区域运营商

数值：6 家；期间：2026-06-18；属性：监管行动。

口径：FERC管辖六家，不含ERCOT；不是六家垂直电力公司。

来源：[FERC｜FERC Launches Targeted Action to Speed Large Load Integration](https://ferc.gov/news-events/news/ferc-launches-aggressive-targeted-action-speed-large-load-integration)；源日期：2026-06-18。

定位：正文及The Six Grid Operators；短引：six。命中：OBJ-grid-interfaces。状态：候选。

### C03　美国数据中心年度用电

数值：58 TWh；期间：2014；属性：历史研究估算。

口径：数据中心整体，非AI独有。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary / Figure ES-1；匹配PDF物理页 7,9,52,58,63,73；短引：58。命中：M04-Q05。状态：候选。

### C04　美国数据中心年度用电

数值：176 TWh；期间：2023；属性：历史研究估算。

口径：总设施能源估算；非全国逐表实测。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 6,52,57,76；短引：176。命中：M04-Q05。状态：候选。

### C05　美国数据中心用电占美国总用电

数值：4.4 %；期间：2023；属性：历史研究估算。

口径：分母美国全年总用电。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 6,52；短引：4.4%。命中：M04-Q05。状态：候选。

### C06　美国数据中心年度用电预测低端

数值：325 TWh；期间：2028；属性：2024版预测。

口径：2024年报告情景低端，不是2026年实际。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 7,52；短引：325。命中：M04-Q05。状态：候选。

### C07　美国数据中心年度用电预测高端

数值：580 TWh；期间：2028；属性：2024版预测。

口径：与低端同一模型情景范围，不做简单平均。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 7,52；短引：580。命中：M04-Q05。状态：候选。

### C08　美国数据中心占总用电预测低端

数值：6.7 %；期间：2028；属性：2024版预测。

口径：分母该报告预测的2028美国总用电。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 7,52；短引：6.7%。命中：M04-Q05。状态：候选。

### C09　美国数据中心占总用电预测高端

数值：12 %；期间：2028；属性：2024版预测。

口径：预测分母；非当前全国占比。

来源：[LBNL｜2024 United States Data Center Energy Usage Report (corrected URL)](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)；源日期：2024-12。

定位：Executive Summary；匹配PDF物理页 7,52；短引：12.0%。命中：M04-Q05。状态：候选。

### C10　ERCOT批次研究的大负荷资格规模门槛

数值：75 MW；期间：2026-06-18；属性：公布规则。

口径：另须满足资格条件，不是投运IT容量。

来源：[ERCOT｜PUCT Approves ERCOT Batch Zero](https://www.ercot.com/news/release/06182026-puct-approves-ercots)；源日期：2026-06-18。

定位：正文第三段 qualified projects；短引：75 megawatts。命中：M04-Q01, M04-Q07。状态：候选。

### C11　ERCOT Batch Zero最终输电计划

数值：2027 年秋季；期间：2027；属性：公布预期节点。

口径：研究/计划时间，不是所有项目投运时间。

来源：[ERCOT｜PUCT Approves ERCOT Batch Zero](https://www.ercot.com/news/release/06182026-puct-approves-ercots)；源日期：2026-06-18。

定位：正文 transmission plan；短引：Fall 2027。命中：M04-Q07。状态：候选。

### C12　配电变压器交期

数值：3—6 月；期间：2019；属性：DOE转录所述历史调查。

口径：配电变压器，不推广到所有主变压器。

来源：[DOE｜Distribution Transformer Webinar Text Alternative](https://www.energy.gov/oe/distribution-transformer-webinar-text-alternative)；源日期：None。

定位：lead time相关段落；短引：2019。命中：M09-Q01。状态：候选。

### C13　配电变压器交期

数值：1—2年以上 年；期间：2024；属性：DOE转录所述历史调查。

口径：不冒充2026年现货或工厂报价。

来源：[DOE｜Distribution Transformer Webinar Text Alternative](https://www.energy.gov/oe/distribution-transformer-webinar-text-alternative)；源日期：None。

定位：lead time相关段落；短引：2024。命中：M09-Q01。状态：候选。

### C14　Dominion适用新大型客户最低服务义务

数值：14 年；期间：2027-01-01及以后签约；属性：SCC已公布未来适用条款。

口径：适用新增大型客户，非全美统一。

来源：[Virginia SCC｜SCC Data Center Initiatives](https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf)；源日期：2026-02-24。

定位：WHAT IS THE MINIMUM CONTRACT OBLIGATION；匹配PDF物理页 1,2；短引：14 years。命中：M04-Q04。状态：候选。

### C15　Dominion最低月输配电费用承担

数值：85 %；期间：SCC 2026-02-24说明；属性：已公布条款。

口径：分母为其服务的输配电成本；2016年前客户豁免。

来源：[Virginia SCC｜SCC Data Center Initiatives](https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf)；源日期：2026-02-24。

定位：WHAT MINIMUM CHARGES WILL APPLY；匹配PDF物理页 1,2；短引：85%。命中：M04-Q04。状态：候选。

### C16　Dominion信用不足新客户担保上限

数值：60 %；期间：2027-01-01及以后签约；属性：已公布条款。

口径：分母最低合同费用；可能要求而非所有客户必缴。

来源：[Virginia SCC｜SCC Data Center Initiatives](https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf)；源日期：2026-02-24。

定位：WHAT COLLATERAL WILL BE REQUIRED；匹配PDF物理页 1,2；短引：60%。命中：M04-Q04。状态：候选。

### C17　AEP Ohio新大型数据中心最低合同容量付款

数值：85 %；期间：2025-07-09决定；属性：监管决定的官方机构说明。

口径：分母合同电力容量，非未消耗的电能；2025-11上诉。

来源：[Ohio Consumers Counsel｜Data Center Costs 24-0508-EL-ATA](https://occ.ohio.gov/content/data-center-costs-24-0508-el-ata)；源日期：2026-01-21。

定位：Update段落；短引：85 percent。命中：M04-Q04。状态：候选。

### C18　AEP Ohio最低容量义务最长期间

数值：12 年；期间：2025-07-09决定；属性：监管决定的官方机构说明。

口径：最长期限；保留爬坡细节待查完整费率。

来源：[Ohio Consumers Counsel｜Data Center Costs 24-0508-EL-ATA](https://occ.ohio.gov/content/data-center-costs-24-0508-el-ata)；源日期：2026-01-21。

定位：Update段落；短引：12 years。命中：M04-Q04。状态：候选。

### C19　典型Dominion居民发电及输电月成本增量

数值：14—37 美元/月（不变价）；期间：到2040；属性：2024长期情景估算。

口径：特定模型情景，非当前全国涨幅。

来源：[Virginia JLARC｜Data Centers in Virginia, Report 598](https://jlarc.virginia.gov/pdfs/reports/Rpt598.pdf)；源日期：2024-12-09。

定位：Summary printed v；匹配PDF物理页 9；短引：$14 to $37。命中：M04-Q04。状态：候选。

### C20　Georgia Power大负荷组合客户预计年度节省

数值：9.5 亿美元/年；期间：从2029起；属性：公司预测。

口径：组合口径；非单项目/已兑现现金收益。

来源：[Georgia Power｜OpenAI contract approval and expected customer savings](https://www.georgiapower.com/news-hub/press-releases/contract-openai-approved-part-portfolio-delivering-950-million-annual-savings.html)；源日期：2026-08-26。

定位：projected incremental revenue段落；短引：$950 million。命中：M04-Q04。状态：候选。

### C21　Georgia Power / OpenAI新增合同需求

数值：3200 MW；期间：2026-08-26披露；属性：合同公告。

口径：新增需求合同，不识别成投运或IT功率。

来源：[Georgia Power｜OpenAI contract approval and expected customer savings](https://www.georgiapower.com/news-hub/press-releases/contract-openai-approved-part-portfolio-delivering-950-million-annual-savings.html)；源日期：2026-08-26。

定位：contract filed in July段落；短引：3,200。命中：M04-Q05, M04-Q04。状态：候选。

### C22　Georgia Power / OpenAI灵活响应承诺上限

数值：1000 MW；期间：2026-08-26披露；属性：合同公告。

口径：承诺上限，不是已观测调度能力。

来源：[Georgia Power｜OpenAI contract approval and expected customer savings](https://www.georgiapower.com/news-hub/press-releases/contract-openai-approved-part-portfolio-delivering-950-million-annual-savings.html)；源日期：2026-08-26。

定位：flexible demand response段落；短引：1,000。命中：OBJ-grid-alternatives。状态：候选。

### C23　反对本地建设AI数据中心受访成年人比例

数值：71 %；期间：2026-03-02至03-18调查；属性：Gallup调查。

口径：美国成年人态度调查，非电费因果证据。

来源：[Gallup｜Americans Oppose AI Data Centers in Their Area](https://news.gallup.com/poll/709772/americans-oppose-data-centers-area.aspx)；源日期：2026-05-13。

定位：Two in Three以上正文/图；短引：71%。命中：M05-Q04。状态：候选。

### C24　Crane重启目标

数值：2027 年；期间：2025-09-23公告；属性：公司目标。

口径：停运机组重启目标，非已投运电力。

来源：[Constellation｜One Year Later: Crane restart ahead of schedule](https://constellationenergy.gcs-web.com/node/9421/pdf)；源日期：2025-09-23。

定位：PDF第1页第三段；短引：2027。命中：M04-Q03。状态：候选。

### C25　Microsoft支持Crane重启的购电期限

数值：20 年；期间：2025-09-23公告；属性：已披露合约期限。

口径：PPA，不解释成全部电流直供微软园区。

来源：[Constellation｜One Year Later: Crane restart ahead of schedule](https://constellationenergy.gcs-web.com/node/9421/pdf)；源日期：2025-09-23。

定位：PDF第1页第一正文段；短引：20-year。命中：M04-Q03, M04-Q04。状态：候选。

### C26　Talen/Amazon全合同规模

数值：1920 MW；期间：2025-06-11；属性：合同安排。

口径：既有核电能源/容量协议，不等于新增装机或IT。

来源：[Talen Energy｜Amazon PPA Amendment: Transaction Highlights](https://www.sec.gov/Archives/edgar/data/1622536/000162828025030559/a20250611talenbusinessup.htm)；源日期：2025-06-11。

定位：公司演示材料Slide 4；短引：1,920 MW。命中：M04-Q02, M04-Q04。状态：候选。

### C27　Talen/Amazon合同期末

数值：2042 年；期间：2025-06-11；属性：合同安排。

口径：有延长选项；实际负荷按阶段爬坡。

来源：[Talen Energy｜Amazon PPA Amendment: Transaction Highlights](https://www.sec.gov/Archives/edgar/data/1622536/000162828025030559/a20250611talenbusinessup.htm)；源日期：2025-06-11。

定位：Slide 4；短引：2042。命中：M04-Q04。状态：候选。

### C28　现场燃气可靠供电装机超配区间

数值：30—70 %；期间：2026模型；属性：IEA模型估算。

口径：分母所服务需求；取决配置，非全部园区固定系数。

来源：[IEA｜Key Questions on Energy and AI](https://iea.blob.core.windows.net/assets/3179f7f8-01f6-4dd6-bffa-c9f7b73f1dc9/KeyQuestionsonEnergyandAI.pdf)；源日期：2026-04-16。

定位：Executive Summary；匹配PDF物理页 11；短引：30% to 70%。命中：M04-Q02。状态：候选。

### C29　已土地清理或建设的美国现场燃气项目

数值：约五分之一 比例；期间：2026报告观察；属性：IEA卫星观察。

口径：项目数观察，不是投运比例或发电量。

来源：[IEA｜Key Questions on Energy and AI](https://iea.blob.core.windows.net/assets/3179f7f8-01f6-4dd6-bffa-c9f7b73f1dc9/KeyQuestionsonEnergyandAI.pdf)；源日期：2026-04-16。

定位：Executive Summary；匹配PDF物理页 11；短引：one-fifth。命中：M04-Q02。状态：候选。

### C30　全球数据中心现场燃气2030装机预测

数值：15—27 GW；期间：2030；属性：IEA预测。

口径：全球，主要在美国；不可改写美国现有装机。

来源：[IEA｜Key Questions on Energy and AI](https://iea.blob.core.windows.net/assets/3179f7f8-01f6-4dd6-bffa-c9f7b73f1dc9/KeyQuestionsonEnergyandAI.pdf)；源日期：2026-04-16。

定位：Executive Summary / Figure 6.4；匹配PDF物理页 11；短引：15-27 GW。命中：M04-Q02, M04-Q05。状态：候选。

### C31　Alphabet收购Intersect现金对价

数值：47.5 亿美元；期间：2025-12-22宣布；属性：协议对价。

口径：现金之外承担债务；并非全部交易企业价值。

来源：[Intersect｜Alphabet agreement to acquire Intersect](https://www.intersect.com/news/alphabet-announces-agreement-to-acquire-intersect-to-advance-u-s-energy-innovation)；源日期：2025-12-22。

定位：开头收购对价段；短引：billion in cash。命中：OBJ-grid-supply。状态：候选。

### C32　Alphabet完成Intersect收购

数值：2026-03 日期；期间：2026-04-29披露；属性：公司财报披露。

口径：后续事实替代仅宣布协议状态，资产不全已投运。

来源：[Alphabet｜2026 Q1 Earnings Transcript](https://s206.q4cdn.com/479360582/files/doc_events/2026/Apr/29/2026_Q1_Earnings_Transcript.pdf)；源日期：2026-04-29。

定位：PDF第13页CapEx段；匹配PDF物理页 13；短引：closed in March。命中：OBJ-grid-supply。状态：候选。

### C33　PJM大负荷登记工具计划上线

数值：2027-02-01 日期；期间：2026-10-09网页；属性：待批准方案/工具计划。

口径：页面标Pending FERC Approval，不冒充已全面生效。

来源：[PJM｜Large Load](https://www.pjm.com/markets-and-operations/large-load)；源日期：None。

定位：Existing and Future Large Load Registry；短引：February 1, 2027。命中：M04-Q01, M04-Q07。状态：候选。

### C34　PJM按区域汇总登记信息计划公开

数值：2027-03 日期；期间：2026-10-09网页；属性：待批准方案/工具计划。

口径：计划信息公开，不是所有新增需求投运。

来源：[PJM｜Large Load](https://www.pjm.com/markets-and-operations/large-load)；源日期：None。

定位：Public Registry Information；短引：March 2027。命中：M04-Q01。状态：候选。

### C35　Texas工业平均电价

数值：6.72 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Texas / Industrial 2026 YTD；短引：Texas。命中：M04-Q11。状态：候选。

### C36　Virginia工业平均电价

数值：10.08 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Virginia / Industrial 2026 YTD；短引：Virginia。命中：M04-Q11。状态：候选。

### C37　Arizona工业平均电价

数值：7.66 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Arizona / Industrial 2026 YTD；短引：Arizona。命中：M04-Q11。状态：候选。

### C38　Georgia工业平均电价

数值：7.99 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Georgia / Industrial 2026 YTD；短引：Georgia。命中：M04-Q11。状态：候选。

### C39　Ohio工业平均电价

数值：10.32 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Ohio / Industrial 2026 YTD；短引：Ohio。命中：M04-Q11。状态：候选。

### C40　Oregon工业平均电价

数值：8.33 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / Oregon / Industrial 2026 YTD；短引：Oregon。命中：M04-Q11。状态：候选。

### C41　U.S. Total工业平均电价

数值：9.03 美分/kWh；期间：2026-01至2026-07；属性：EIA初步估计。

口径：售电收入÷售电量；非数据中心合同报价。

来源：[EIA｜EPM Table 5.6.B, January-July 2026 and 2025](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b)；源日期：2026-09-24。

定位：Table 5.6.B / U.S. Total / Industrial 2026 YTD；短引：U.S. Total。命中：M04-Q11。状态：候选。

### S01　PJM近期大负荷预测要求较明确建设/服务承诺，远期非确定项目折减

来源：[PJM｜2026 Long-Term Load Forecast Report](https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf)；源日期：2026-01-14。

定位：PDF第6页（正文第4页）；短引：firm。命中：M04-Q01, M04-Q05。状态：候选。

### S02　JLARC当时独立成本研究认为当前服务成本已适当分配，同时预测增长提高未来系统成本

来源：[Virginia JLARC｜Data Centers in Virginia, Report 598](https://jlarc.virginia.gov/pdfs/reports/Rpt598.pdf)；源日期：2024-12-09。

定位：PDF第9、62页（正文摘要v、44）；短引：full cost of service。命中：M04-Q04。状态：候选。

### S03　Talen/Amazon项目建立电网连接后转表前零售，过渡期部分表后

来源：[Talen Energy｜Amazon PPA Amendment: Transaction Highlights](https://www.sec.gov/Archives/edgar/data/1622536/000162828025030559/a20250611talenbusinessup.htm)；源日期：2025-06-11。

定位：Slide 4；短引：Front-of-the-Meter。命中：M04-Q02。状态：候选。

### S04　PJM IRAS截至查看时仍待FERC批准

来源：[PJM｜Large Load](https://www.pjm.com/markets-and-operations/large-load)；源日期：None。

定位：Registry及IRAS标题；短引：Pending FERC Approval。命中：M04-Q07。状态：候选。

### S05　俄亥俄AEP现场项目采用天然气固体氧化物燃料电池，客户承担项目成本

来源：[AEP｜PUCO Approves Onsite Power Project for Data Centers](https://www.aep.com/news/stories/view/10262/)；源日期：2025-06-05。

定位：正文Bloom系统段；短引：solid oxide fuel cells。命中：M04-Q02。状态：候选。

### S06　Google以可调度机器学习负荷与电力公司开展需求响应合作

来源：[Google｜Making data centers flexible to benefit power grids](https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/how-were-making-data-centers-more-flexible-to-benefit-power-grids/)；源日期：2025-08-04。

定位：与I&M / TVA合作正文段；短引：machine learning。命中：OBJ-grid-alternatives。状态：候选。

### S07　跨州输电涉及多个司法和土地权利层级

来源：[DOE｜Transmission Siting and Permitting Efforts](https://www.energy.gov/oe/transmission-siting-and-permitting-efforts)；源日期：None。

定位：正文选址许可部分；短引：state。命中：OBJ-grid-interfaces, M04-Q07。状态：候选。

### S08　NERC风险结果使用有时点的需求与资源假设；部分新加速资源未纳入

来源：[NERC｜2025 Long-Term Reliability Assessment](https://www.nerc.com/globalassets/our-work/assessments/nerc_ltra_2025.pdf)；源日期：2026-01-29。

定位：PDF第8—11页；短引：not included。命中：M04-Q05, M04-Q07。状态：候选。

### S09　白宫保护居民成本的承诺需与地方具体费率及合同衔接

来源：[White House｜Ratepayer Protection Pledge Proclamation](https://www.whitehouse.gov/presidential-actions/2026/03/ratepayer-protection-pledge-proclamation/)；源日期：2026-03-04。

定位：公告正文；短引：Ratepayer。命中：M04-Q04。状态：候选。

## 保留的反证和状态更新

JLARC当时认为现有服务成本已被适当分配，不支持把全部居民涨价都归为直接补贴。PJM近端预测下修不代表实际用电下跌。Alphabet完成收购是后续事实，项目资产投运另查。Talen既有核电PPA不计新增装机。Georgia客户节省是公司未来组合预测。

## 未采用线索

起点文章中的七家运营商垂直垄断、三大网完全不通、以PUHCA代替FPA解释批发监管，均已修正。3000家公司数量未作为当前统计采用；各州暂停日期和全国电费翻倍未有足够原文，不采用。

## 剩余缺口与下一步原件

- M04-Q01：排队规模、平均等待、清退率仍缺相同年份与去重口径的地区原表；不采纳未追到原件的474GW总数。 下一步：PJM/ERCOT大负荷登记与月度进度，不混发电排队。
- M04-Q02：现场电源案例有官方项目与模型；实际投运日期、实耗、设备造价和燃料到户合同仍缺。 下一步：项目许可、运营披露、实测负荷、燃料电池与燃机分别取材。
- M04-Q03：Crane公司目标与部分进度已补；NRC当前页下载受限，不能独立证明全部复运条件已满足；SMR商业投运另需逐项目。 下一步：NRC许可/检查与公司后续里程碑双向核对。
- M04-Q04：费率保护条款已补，公开摘要不是删节客户合同全文；实际居民账单因果与Georgia节省兑现仍待查。 下一步：SCC/PUCO完整费率、成本服务研究、负荷实现与收入。
- M04-Q05：全国能量预测与区域方法有资料；2030新增可交付GW的统一分期清单仍缺。 下一步：建立同一项目身份、接入点、年度阶段和可靠容量。
- M04-Q07：Batch/IRAS与设备瓶颈明确；园区实际送电等待分布不能从制度计划推算。 下一步：同一批次研究开始、合同、送电及实际爬坡。
- M04-Q11：7条州工业初步均价可登记为对应范围候选；不能替代园区能量/需量费率或GPU成本。 下一步：Dominion、AEP、Georgia Power、Oncor具体适用费率与条件。
- M09-Q01：DOE配电变压器历史调查已补；2026大型主变与开关柜型号/工厂交付报价仍缺。 下一步：设备类别、额定电压、工厂报价日和订单排期。

## 导入办法

先解压研究原件包与交付包，检查originals-manifest SHA；研究正文research.md可送当前正文阅读入口，submission.json可经`python3 manage.py submissions <本research目录>`登记校验。该命令校验候选，不执行正式数据库采用。需求快照SHA与问题ID用于匹配；没有真实workorder不虚构工单。不得把本包直接当成日报daily-receive事件包，也不得将格式通过回执当作C3回执。采纳后按现行事实/价格载体写入并返回采用ID；本篇不更改基准。


## 第三版图文修订的原始资料补充

2026-10-09：地图改为根据US Census州多边形重绘，三大互联范围对照EIA/ERCOT官方图；州界与概览系统分界分别处理。得州覆盖不是全州，有限直流联络的位置仅示意，不用于站点接入判断。配套身份和读取范围见work/v3/visual-sources.json及本包sources.json。

现场电源图改为AEP披露案例采用的固体氧化物燃料电池；DOE材料补充了电化学产生DC、燃料处理与电力转换的基本机制。Bloom原站工具响应仅作设备路线核对，原始HTML下载403和响应身份分别保留，不采用厂商性能或排放宣传。新图不构成新项目投运证据。

原有23件submission与50条候选保持原版本和阶段；本补充资料尚未进入额外submission、深读/C3、远程数据库或模型采用。正式问题覆盖和缺口仍按已有快照，插画与来源数量不自动关闭问题。
