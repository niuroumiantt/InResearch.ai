# inresearch.ai 研究、事实与方法论审计（2026-09-06）

审计对象：`/Users/m5/code/inresearch.ai` 当前工作树的 framework、research、data/schema 与 data 实体/事实表、reports、DECISIONS 与 LIBRARY_REPORT。只读检查，未修改仓库；以下行业数字只作为内部资料的内容审计，没有外部核验其事实真伪。当前数量由脚本从 JSON/CSV/Markdown 重算，未套用旧 PANORAMA。文中“可用”指结构/流程达标，不代表行业事实已经核实。

**总体判断：方向值得继续，已建立相当完整的研究骨架和内部原型，但数据库与研究更新尚未形成可信、持续的闭环。现在应优先兑现“正确取数→证据可回查→可比性检查→结论更新→按需报告”，而不是继续扩页面、部件或材料总量。**

## 1. 当前真实进度

| 层 | 独立重算现状 | 解释 |
|---|---:|---|
| 研究模块 | 15 | 已有完整主题定义与持续问题 |
| Finding | 150，127 current、23 needs-review | 150 个ID全部唯一；全部修订日集中2026-08-14至08-17 |
| 项目 | 120 | 83标L8；单值IT容量24/120=20%，另17条仅按状态分拆容量，两者互斥；任一形式有容量41/120=34.2%，剔除1个portfolio后为40个单站；L8+任一形式有容量21/83=25.3% |
| 项目状态历史 | 14/120=11.7% | 缺少可用于历史转化率/交付周期的纵向样本 |
| 项目电力字段 | power_status 8/120；utility 11/120 | “可兑现电力是第一约束”的主张还缺对应底账 |
| 地理样本 | 北美69、欧洲17、亚太16、拉美6、印度5、中国4、中东3 | 中国工程资料多，不等于可聚合中国项目库已厚 |
| 公司 | 248 | 94有verified_date/实质profile，154缺；ticker45、CIK34、IR链接44 |
| 产品目录 | 175 | 全有website/spec_fields/representative_models；这些是产品线及待采字段声明，不是已核产品spec数据库 |
| 价格记录 | 207点、34序列 | 60点是未来年度预测；不能等同持续观测207次 |
| 合同/政策 | 各2条 | 尤其合同还是种子样本，不支持行业集中度/循环交易暴露估计 |
| 事实 | 119，覆盖124个指标定义中的88个 | 116精读、3据实生成；S2 31、S3 56、S4 32 |
| 事实交叉验证 | 2已交叉验证、3孤证已知、114缺省待交叉验证 | 应理解为候选/单源事实库，不能称119个可靠建模输入 |
| 监测指标 | 44，8有值（18.2%） | 36留白；8值中至少3个是样本聚合演示 |
| BOM | 46部件 | 42挂公司、38被产品覆盖、14挂指标、仅2挂价格序列；0显式finding引用 |
| 模块问题 | 116 | 全部为字符串，没有一项answered_by，所以机器无从知道150条Finding回答了哪些问题 |
| 派工 | assignments.records=0 | 有工单设计和首批intern说明，尚无仓库数据证明在线派工闭环跑过 |
| 文献索引 | CSV13663行；13617个new_path | 1204精读+350据实生成=1554（11.4%）；11102半自动（81.3%）；1007目录级（7.4%）；≥7分175行 |

所有实体表与facts的声明主键目前没有重复；products复合键 company_id+product_line、prices复合键series_id+as_of也唯一。CSV同new_path额外46行不是自动删除依据：有目录汇总和不同原名，报告规定去重键是new_path+old_name，应先核对文件实体再归并。（依据：[LIBRARY_REPORT.md](/Users/m5/code/inresearch.ai/docs/LIBRARY_REPORT.md:18)）

模块Finding分布：M01 7、M02 13、M03 5、M04 9、M05 14、M06 16、M07 8、M08 10、M09 12、M10 18、M11 3、M12 6、M13 6、M14 11、M15 12。待复核集中M06（10）、M07（4）、M08（3），其余M02/M09/M11/M15各1、M13 2。

数据审计入口：[projects.json](/Users/m5/code/inresearch.ai/data/projects.json:1)、[companies.json](/Users/m5/code/inresearch.ai/data/companies.json:1)、[facts.json](/Users/m5/code/inresearch.ai/data/facts.json:1)、[indicators.json](/Users/m5/code/inresearch.ai/framework/indicators.json:1)、[assignments.json](/Users/m5/code/inresearch.ai/data/assignments.json:1)、[LIBRARY_SCORES.csv](/Users/m5/code/inresearch.ai/docs/LIBRARY_SCORES.csv:1)。

本机工作区没有docs/library，因此此处所有CSV库内文件路径都不可打开；sources72条local_file中仅4条当前存在（原始报告/附件）。这不代表资料丢失。父任务另在Mac mini实测约7029文件、31.69GB；历史“28759份/91GB”是旧账本。用户随后确认资料已临时移走且全部在百度网盘；应登记迁移位置并核对下一轮下载清单，不视为资料缺失。旧索引自己明确声明已过期两代：[LIBRARY_INDEX.md](/Users/m5/code/inresearch.ai/docs/LIBRARY_INDEX.md:3)。

## 2. 需要先处理的实质问题

### A. 同一套九级漏斗已经有两种定义（高优先级）

口径手册L2=官宣规划、L3=土地、L4=电力申请、L5=电力确定；研究综合层却L2=土地、L3=许可、L4=并网确定、L5=融资关闭。并且M01仍称“六级项目状态”。同一个L4在不同输出里分别表示“提出申请”和“电力已确定”，会直接误导交付概率和在建容量。

证据：[01_data_standards.md](/Users/m5/code/inresearch.ai/framework/01_data_standards.md:27)、[M15.md](/Users/m5/code/inresearch.ai/research/M15.md:89)、[M01.md](/Users/m5/code/inresearch.ai/research/M01.md:40)。

建议：以唯一状态字典定义物理阶段；电力、融资、许可如并行进行，做独立维度，而不是硬塞进一条必然先后顺序。逐项目/分期保留证据与状态事件；验收为定义只存一份、全部视图引用同一字典、抽查20项目阶段无歧义。

### B. 证据记录“填了字段”与“机器能回到出处”是两回事（高优先级）

119条facts全部有locator，但84条source_id中只有3条指向sources表；其余81条是12位十六进制ID，不存在sources表，且这81条都没有local_file；另外35条没有source_id，其中14条locator直接引用research自己的结论。schema却明确source_id对应data/sources.json。现有校验只验证locator非空，没有检查来源外键、文件是否可达、source_id是否能解析。人可能凭标题找回报告，机器无法形成稳定证据链。

证据：[fact.schema.json](/Users/m5/code/inresearch.ai/data/schema/fact.schema.json:77)、[facts.json样例](/Users/m5/code/inresearch.ai/data/facts.json:1042)、[回引研究样例](/Users/m5/code/inresearch.ai/data/facts.json:588)、[facts.py](/Users/m5/code/inresearch.ai/pipeline/facts.py:85)。

另11条派生事实仅1条有derived_from；114条缺省待交叉验证，而schema明确“待交叉验证不参与任何推算”。校验只要求derivation文本非空，并未核验计算依赖、来源独立性或环路。2条“已交叉验证”也没有结构化第二来源列表可供机器验证。

证据：[事实交叉验证约定](/Users/m5/code/inresearch.ai/data/schema/fact.schema.json:158)、[派生检查](/Users/m5/code/inresearch.ai/pipeline/facts.py:94)、[派生样例](/Users/m5/code/inresearch.ai/data/facts.json:58)。

建议：统一source_id、document_id/cache_key、locator三种职责，提供迁移表；优先把对外要用的20条结论逐一修成“结论→事实→来源→原文页/段”，不为追求数量把缺证据的条目填成current。验收：这20条的全部关键数字有可达原文，派生可重算，无悬空ID、无结论自证。

### C. 看板三个已填数仍是演示，而且一个已经跨口径混加（高优先级）

“全球投运容量5.92GW”实际是库内样本汇总（只记录部分项目；计入单值与分状态容量两种字段后，容量覆盖仍仅41/120=34.2%）；“大额合同未交付余额400B”实际是300B算力采购合同+100B融资投资意向，后者不是未交付算力收入；“循环交易占比25%”也是这两条的金额加权。auto_note虽写了种子/示意，名称仍会被当成全球/行业观测值。

证据：[indicators.json全球容量](/Users/m5/code/inresearch.ai/framework/indicators.json:36)、[循环与backlog](/Users/m5/code/inresearch.ai/framework/indicators.json:136)、[contracts.json两条种子](/Users/m5/code/inresearch.ai/data/contracts.json:4)。

建议：立即把展示区分为“已核监测/样本描述/待建”；backlog必须只按可比较的同类合同、执行状态与剩余履约义务构造，不把融资意向加进去。全局/行业指标需明确覆盖总体、分母和缺失率；无法给出分母时只报告样本。

### D. 知识正文的谨慎提醒没有约束标题、结论和状态（高优先级）

三个内部即可验证的例子：

1. M15-F10/F11的标题与结论把券商80%与信通院<30%当成三倍差距，并推出回本/亏损；同一Finding随后承认两者可能是不同利用率定义、根本不矛盾、不能断言假设失实。F11仍把它当成“两例同向乐观”。问题并非缺一句免责声明，而是主结论超出证据。（[M15.md](/Users/m5/code/inresearch.ai/research/M15.md:160)、[口径自认未对齐](/Users/m5/code/inresearch.ai/research/M15.md:162)、[第二次引用](/Users/m5/code/inresearch.ai/research/M15.md:183)）
2. M08-F9以2022经济性门槛15kW与2026补贴门槛15kW相同，推出“经济性门槛未下移”；但对浸没式的同一段论证又正确承认政策门槛与经济性门槛性质不同，不能证明技术经济性变化。冷板式也应采用同样逻辑。（[M08.md](/Users/m5/code/inresearch.ai/research/M08.md:174)、[自述不同口径](/Users/m5/code/inresearch.ai/research/M08.md:183)）
3. M14-F5仍标current，但口径提醒写明旧法规“几乎肯定已修订、替换或撤销，不得引用为现行法规”，且待办要求复核全部制度内容。只需内部一致性就足以判为需复核/历史快照，无需在本次审计猜测现行法律。（[M14.md](/Users/m5/code/inresearch.ai/research/M14.md:83)、[M14.md](/Users/m5/code/inresearch.ai/research/M14.md:95)）

附两条算术/逻辑待复核：M02-F10写130kW+14kW按1:1平均得到62kW，直接算术应72；如需按机柜宽度换算，应补足分母才能成立（[M02.md](/Users/m5/code/inresearch.ai/research/M02.md:162)）。M12-F7称“分子估值更高、分母ARR更高”两偏差都令比值更低，事实上方向相反，净影响未经量化不能下结论（[M12.md](/Users/m5/code/inresearch.ai/research/M12.md:94)）。

建议：研究审阅首先检查“标题/结论能否由证据推出”，而不只检查有没有口径提醒。给Finding加历史快照、推演假设、当前判断三种语义标签；设证伪条件、适用范围与来源依赖。验收为待发布Finding无“结论肯定但末尾承认尚未验证”的矛盾。

### E. 触发器与复核尚未闭环

今日直接调用只读verify.build_queue得到P1=23（全是既有needs-review），P2=24；并不代表其余所有数据新鲜。16个entity触发器引用（14条Finding、10个不同ID）不在companies注册表，43个indicator触发器引用（42条Finding、32个ID）不在indicators注册表。部分是本应指metrics的ID或尚未注册的构想，部分是google/china_mobile等别名。collect目前按entity:company_id精确字符串和SEC事件触发，未注册引用不会按预期刷新；periodic:90d等在verify中也未解析，仅使用365天总阈值。

证据：[collect.py](/Users/m5/code/inresearch.ai/pipeline/collect.py:87)、[精确匹配](/Users/m5/code/inresearch.ai/pipeline/collect.py:111)、[verify.py](/Users/m5/code/inresearch.ai/pipeline/verify.py:117)、[google别名实例](/Users/m5/code/inresearch.ai/research/M09.md:108)、[未注册指标实例](/Users/m5/code/inresearch.ai/research/M02.md:180)。

保鲜规则也分叉：手册价格30天，verify把GPU/Token价格设季度150天、年度455天、默认365天，benchmark跳过。按频率区分本身合理，但应统一声明，不能以代码私自扩宽替代研究认可的节奏；207点中60个未来as_of预测被“取最大as_of”当最新点，会掩盖来源预测本身的过期。应拆observation_period、forecast_horizon、published_at、verified_at。

证据：[手册](/Users/m5/code/inresearch.ai/framework/01_data_standards.md:64)、[verify频率](/Users/m5/code/inresearch.ai/pipeline/verify.py:33)、[取最新值](/Users/m5/code/inresearch.ai/pipeline/verify.py:96)。

### F. 工单数量正在掩盖完成度

116项问题都没有answered_by，所以即使研究已有150 Finding，生成器仍把所有问题叫“目前还没有答案”。259张工单中会混入已回答但未链接、未完成建模、真实缺资料三种完全不同工作。M11只有3 Finding是问题，但不能从“库中M11标签12条”直接推出必须采购更多材料；此前DECISIONS已经记录过M11材料被分类器漏掉的误诊。

证据：[问题声明](/Users/m5/code/inresearch.ai/framework/modules.json:53)、[生成规则](/Users/m5/code/inresearch.ai/pipeline/workorder.py:321)、[历史误诊](/Users/m5/code/inresearch.ai/docs/DECISIONS.md:1121)。

建议：先把问题→Finding→fact/indicator串起来；每个问题显式标未答/部分回答/已回答/证据待更新，而不是字符串有无链接二分。合并为10-15个当前可执行包，先试跑3个intern任务的assign→提交→复核→采用→关闭全过程，再按吞吐扩人。

### G. 输出承诺尚需实测；摘要与研究脱节

SUMMARY明确说只提炼了68条旧Finding，新增82条未吸收；既有23条复核自8月中旬积压。报告说明称可按需导出全量/专题，但export.py依赖modules.research/doc字段，当前模块声明没有这两个字段，父任务后端已实测确认导出0章、0条Finding，却仍exit 0。这是最值得优先打通的业务验收口。

证据：[SUMMARY.md](/Users/m5/code/inresearch.ai/research/SUMMARY.md:5)、[输出承诺](/Users/m5/code/inresearch.ai/reports/HOW_TO_OUTPUT.md:5)、[export.py](/Users/m5/code/inresearch.ai/pipeline/export.py:119)。

## 3. 思路中值得保留与应收敛的部分

**保留**：事实为原子、每个指标独立定义口径、未知留白；研究与输出分离；Finding可更新可证伪；资料阅读深度显式分层；原始资料本地保留/索引与研究版本化；BOM为探索入口而模块为责任边界。用户明确core是数据库而非UI，这也是最有持续价值的资产。（[DECISIONS.md](/Users/m5/code/inresearch.ai/docs/DECISIONS.md:1162)、[metrics.json](/Users/m5/code/inresearch.ai/framework/metrics.json:4)、[BOM数据先行](/Users/m5/code/inresearch.ai/framework/03_bom_and_collaboration.md:31)）

**收敛为可执行原则**：

- “MECE”适合指定每条事实/每个问题的维护责任，不适合禁止跨模块解释。总览说仅M15可引用跨模块结论，M05定义却明说引用M04结论，M08也承接M06。更合理的是单一维护源+跨模块引用图，而不是让所有交叉分析挤进M15。（[总览](/Users/m5/code/inresearch.ai/framework/00_overview.md:49)、[M05定义](/Users/m5/code/inresearch.ai/framework/modules/M05_土地与区域.md:5)）
- 把“领先物理空置率12-18个月”“每MW成交价最硬”当待验证投资假设，不要冻结成永不变的研究骨架。这些结论依市场、样本与周期变化，尚无时间序列回测支撑。（[总览](/Users/m5/code/inresearch.ai/framework/00_overview.md:46)）
- 同口径允许比较；不同口径应阻止直接算差/聚合，但仍允许带明确标签的对照。现文档反复说“不可并列”过强，政策门槛vs实测、不同地区成本恰是研究所需。区分“可并列展示”“可标准化比较”“可聚合”三种权限。
- 15模块继续作问题/责任轴；用户提出的价值链四层可作为业务与实体导航轴并用，避免替换全套。名称与九级漏斗/3D层级分开。A5仍是未决提案，本次不应擅改框架。（[DECISIONS.md](/Users/m5/code/inresearch.ai/docs/DECISIONS.md:216)）
- 46部件不需要立刻都有漂亮3D；先为用户最常查的10部件填实公司、代表产品、证据、价格/交期与观察点。钱/合同/客户不宜硬塞物理BOM，用关系与风险页连接即可。（[DECISIONS.md](/Users/m5/code/inresearch.ai/docs/DECISIONS.md:289)）

## 4. 建议推进次序与验收

### 下一步：先做一轮“可发布研究闭环”（约1-2周）

1. 校准唯一状态字典；把混口径指标改为样本描述或留白；修复5条已发现的主结论/论证冲突。验收：状态定义无分叉，400B不再被称为未交付算力合同余额，研究主结论不强于证据。
2. 将23条needs-review分成“需新证据/仅别名触发/历史快照”，先复核进入下一份报告的条目；补20条核心结论的完整证据链。验收：新报告引用数字100%有source+locator+as_of，计算可复现，未核项明确隔离。
3. 打通一份M04/M09电力交付专题和一份M11/M12/M13单位经济专题的按需导出，重炼执行摘要。验收：全量150条被正确读取、专题仅含选定模块、状态/口径/源页随数字输出，实际在新工作区可复现。
4. 盘点三机资料本体与索引，确定一个资料主库/一个更新主机；做一次从备份恢复随机样本的演练。验收：所有选入报告的原文可打开，索引数量按实际文件清单重建，旧账本明确标历史。

### 随后4-6周：用三个窄研究面形成节奏

- **交付侧（M02/M04/M09）**：选择20-30个明确物理站点、每个分期有独立容量/状态/来源/复核日。主打“未来12个月何时可交付”，不急着声称全球普查。验收：目标样本≥90%关键字段完整；未知保持null且给原因；每次状态变更有事件和证据。
- **经济侧（M11/M12/M13）**：覆盖5家可比较运营/算力公司、10份同类型融资/租赁文件、6-8个价格或成本序列。至少包括GPU现货/长约、资本成本、租赁承诺与资产期限。验收：每周/每月按声明频率刷新，重复采集≥4轮；契约类型与现金流期限明确，不能跨模型/精度/交易类型混比。
- **中国工程与运行侧（M10/M14）**：在已有工程档案优势上补1-2个近期运行案例/结算或实际费用样本，区别建设期预算与运行经济性。验收：至少一份“预算→实际/设计→运行”同项目同口径配对，拿不到则形成明确证据缺口，不拿跨城市老预算假装时间序列。
- 运行3名/3单的小规模协作试点，用已准备的产品链接、GPU时租、ABS presale三单逐级试人。验收：工单有owner、截止日、提交、审阅、采用记录；按“可用事实/审阅小时”“退回原因”“新信源净增价值”评估，不能按读了多少页算产能。

### 3-12个月：把研究资产做成可维护产品

- 3个月：固定月报+事件更新两种交付；形成可查询的事实/证据/判断关系，任何答案可追到原件，任何来源修订可找到受影响结论。维护一组重要问题的SLA，而不是把116问题都当同优先级。
- 3-6个月：用真实协作量决定是否从JSON/CSV转SQLite/Postgres。增长触发条件应是并发写冲突、查询/审计成本与恢复要求，不因“将来会大”而提前重构。
- 6-12个月：建立历史截面与预测版本库，回测哪些先行指标有效；情景权重逐季留档，对已发生结果评估校准度；逐步形成中国工程成本、交付可信度、GPU算力单位经济三种可重复产品。
- 长期成功标准：核心用户能在数分钟内回答“我们知道什么、证据在哪、哪些不能比较、什么变化会推翻判断”；每月新增的是经过验证的事实/判断与更短的审阅时间，而不只是新增文件/页面/部件。

不建议现在做：全量再读一遍13k材料、继续无目标采购报告、同时扩建15个模块、为了全球大数强行补估MW、让新3D模型或第二套价值链命名占据主线。
