# 投递审阅 — 机检结果与分流

> 三档：**A 必须你批**（≥8分／敏感／与现有结论冲突）｜**B 待模型审核**（5-7分命中工单，确定性抽样复核）｜**C 候选存档**（≤4 分）。未匹配工单的中分材料保持待匹配。
> 退回项已带理由码，直接回流给成员即可——**退回不给理由，下次照犯**。

共 23 件｜通过机检 23｜退回 0｜**需你批 4**｜待模型审核 0｜候选存档 0｜待匹配 19

## 🔴 必须你批（4 件）

- **7B** 2024 United States Data Center Energy Usage Report ( ｜ LBNL 2024 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
      ⚠️ **疑似与库内冲突**：「美国数据中心年度用电」= 58.0TWh，而库内「数据中心用电量」已有 415.0TWh（单一情景/全部数据中心/Global/模型输出/未注明/数据中心，2024）——**差 7.2 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心年度用电」= 176.0TWh，而库内「数据中心用电量」已有 415.0TWh（单一情景/全部数据中心/Global/模型输出/未注明/数据中心，2024）——**差 2.4 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心用电占美国总用电」= 4.4%，而库内「数据中心上架率」已有 99.0%（单项目/CN，2025-03）——**差 22.5 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心年度用电预测低端」= 325.0TWh，而库内「数据中心用电量」已有 945.0TWh（Base Case/全部数据中心/Global/模型输出/未注明/数据中心，2030E@2025-04）——**差 2.9 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心年度用电预测高端」= 580.0TWh，而库内「数据中心用电量」已有 1260.0TWh（Lift-Off/全部数据中心/Global/模型输出/未注明/数据中心，2030E@2025-04）——**差 2.2 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心占总用电预测低端」= 6.7%，而库内「数据中心上架率」已有 99.0%（单项目/CN，2025-03）——**差 14.8 倍**
      ⚠️ **疑似与库内冲突**：「美国数据中心占总用电预测高端」= 12.0%，而库内「数据中心上架率」已有 99.0%（单项目/CN，2025-03）——**差 8.2 倍**
      数：美国数据中心年度用电 = 58 TWh（Executive Summary / Figure ES-1；匹配PDF物理页 7,9,52,58,63,73）｜口径：数据中心整体，非AI独有；历史研究估算；2014
      数：美国数据中心年度用电 = 176 TWh（Executive Summary；匹配PDF物理页 6,52,57,76）｜口径：总设施能源估算；非全国逐表实测；历史研究估算；2023
      数：美国数据中心用电占美国总用电 = 4.4 %（Executive Summary；匹配PDF物理页 6,52）｜口径：分母美国全年总用电；历史研究估算；2023
- **7A** SCC Data Center Initiatives ｜ Virginia SCC 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
      ⚠️ **疑似与库内冲突**：「Dominion最低月输配电费用承担」= 85.0%，而库内「电费占比」已有 40.75%（营业收入/CN，2022-12）——**差 2.1 倍**
      数：Dominion适用新大型客户最低服务义务 = 14 年（WHAT IS THE MINIMUM CONTRACT OBLIGATION；匹配PDF物理页 1,2）｜口径：适用新增大型客户，非全美统一；SCC已公布未来适用条款；2027-01-01及以后签约
      数：Dominion最低月输配电费用承担 = 85 %（WHAT MINIMUM CHARGES WILL APPLY；匹配PDF物理页 1,2）｜口径：分母为其服务的输配电成本；2016年前客户豁免；已公布条款；SCC 2026-02-24说明
      数：Dominion信用不足新客户担保上限 = 60 %（WHAT COLLATERAL WILL BE REQUIRED；匹配PDF物理页 1,2）｜口径：分母最低合同费用；可能要求而非所有客户必缴；已公布条款；2027-01-01及以后签约
- **7A** Data Center Costs 24-0508-EL-ATA ｜ Ohio Consumers Counsel 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
      ⚠️ **疑似与库内冲突**：「AEP Ohio新大型数据中心最低合同容量付款」= 85.0%，而库内「数据中心空置率」已有 2.0%（单一市场/SG，2026）——**差 42.5 倍**
      数：AEP Ohio新大型数据中心最低合同容量付款 = 85 %（Update段落）｜口径：分母合同电力容量，非未消耗的电能；2025-11上诉；监管决定的官方机构说明；2025-07-09决定
      数：AEP Ohio最低容量义务最长期间 = 12 年（Update段落）｜口径：最长期限；保留爬坡细节待查完整费率；监管决定的官方机构说明；2025-07-09决定
- **7A** Americans Oppose AI Data Centers in Their Area ｜ Gallup 2026 ｜ → ['M04', 'M05'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
      ⚠️ **疑似与库内冲突**：「反对本地建设AI数据中心受访成年人比例」= 71.0%，而库内「数据中心占绿电直连项目比例」已有 8.0%（绿电直连项目装机/CN，2026）——**差 8.9 倍**
      数：反对本地建设AI数据中心受访成年人比例 = 71 %（Two in Three以上正文/图）｜口径：美国成年人态度调查，非电费因果证据；Gallup调查；2026-03-02至03-18调查

## 候选待匹配工单（19 件）

- **7A** Electricity delivery to consumers ｜ EIA 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** FERC Launches Targeted Action to Speed Large Load In ｜ FERC 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** PUCT Approves ERCOT Batch Zero ｜ ERCOT 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Distribution Transformer Webinar Text Alternative ｜ DOE 2026 ｜ → ['M04', 'M09'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7B** Data Centers in Virginia, Report 598 ｜ Virginia JLARC 2024 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** OpenAI contract approval and expected customer savin ｜ Georgia Power 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** One Year Later: Crane restart ahead of schedule ｜ Constellation 2025 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Amazon PPA Amendment: Transaction Highlights ｜ Talen Energy 2025 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7B** Key Questions on Energy and AI ｜ IEA 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Alphabet agreement to acquire Intersect ｜ Intersect 2025 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** 2026 Q1 Earnings Transcript ｜ Alphabet 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Large Load ｜ PJM 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** EPM Table 5.6.B, January-July 2026 and 2025 ｜ EIA 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** 2026 Long-Term Load Forecast Report ｜ PJM 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** PUCO Approves Onsite Power Project for Data Centers ｜ AEP 2025 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Making data centers flexible to benefit power grids ｜ Google 2025 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Transmission Siting and Permitting Efforts ｜ DOE 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** 2025 Long-Term Reliability Assessment ｜ NERC 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*
- **7A** Ratepayer Protection Pledge Proclamation ｜ White House 2026 ｜ → ['M04'] ｜ 格洛可专题研究 / Codex ｜ *自主发现*

