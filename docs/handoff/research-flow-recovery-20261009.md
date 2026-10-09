# 研究发布恢复交接（2026-10-09，m5 / m4）

## 当前运行与专题阶段

2026-10-09最新实核：17:23逐SHA为23登记、16份正文封存/7份queued，17:24对16份原件/manifest/chunks/report完整封印全部通过。PDF仍是native_text_only、visual=false、full_document_complete=false；封存完成不等于含图视觉深读。17:39已独立核公网和Spark发布闭环22条＝Alphabet B15（PR480＋PR487＋PR493）＋EIA具名代理A7（PR483）。原50为41C＋9S，仅C35–41七项有显式采用身份，另43未见显式绑定。PR499已实际补审并收窄首批6陈述/10证据的错误设施映射，原B、正文与完整before历史保留。最新main在17:40另有PR503同源新增1条，尚未在本轮核对其公网/ACK，不能写作已闭环23。旧队列恢复另计；具名时点、实际源码/服务与缺口见下方。

## 目标
解除持续零交付的发布误阻塞，用网站支持闭包与Spark回执确认恢复。

## 已定规则
- 历史材料的封存正文直接进入资料基座；正式回答、项目/合同/容量与作者陈述分别采用。默认跳过PDF图片，纯图片材料由用户处理。
- 原件、旧报告、模型审计及事实版本长期保留。恢复不重启共享Reader/relay，不降低C3，不把模型成功计为上线。

## 10:19–10:21历史采样与实现
- 10:19–10:21：本批136份已完成；研究16069候选/17394证据，9159排队、58条/12批待发表，当前调用0。
- 十二批逐包对比：两批是正式采用过滤造成的来源误变化，包含已上线7条；六批原始来源和研究上下文未变；四批确有上下文变化。原始PDF未因采用过滤改变。
- 每批失败隔离，等待CI/部署的无变化批次让出调度；来源复验保留原封存候选/原文页。精确审核head已另行合并时仅恢复网站回执，仍需原审计与实际HTTPS闭包。
- infra分工基本适用。Spark可用内存约92.75GB；M4 64GiB且未配置本项目常驻研究worker，已实际执行隔离源码回归：1939项、2项跳过、41.34秒。M5发起远程Codex调用，本机核数不是模型推理容量。
- 单元、治理、严格校验/注册表、Docker实际只读与A→B→A运行数据保留、本地完整浏览器已验。代码PR429；当时GitHub Actions四项报告失败，账户预算需单独核对，不用本地结果冒充云CI。
- 以上是采样及本地实现验收，生产恢复必须另查版本、私有发布日志、逐批实际回执与M5新调用。

## 早期计划（历史阶段）
1. 将已授权修复发布到M5/Spark，备份队列后加载独立研究worker；确认旧7条回执，不作为本小时新增采用。
2. 逐批处理六个上下文未变包和四个待重核包，观察待发表背压是否解除。云CI预算不可用需沿已有明确授权的真实本地验收发布流程。
3. 后续降低每小包独立PR/全站测试成本，考虑统一发布批次；本次未实现合批发布或跨主机多研究worker，不宣称线性提速。

## 入口
- 现行规则：`framework/CURRENT.md`、`framework/09_software_contracts.md`、`docs/local_reader/SPARK_OPERATIONS.md`。
- 源码：`research_review.py` / `research_publish.py`；回归：`tests/unit/test_research_flow_recovery.py`。
- 私有实测与日志：m5 `~/.local/state/inresearch.ai/flow-audit-20261009/`；不进Git。
- 当前主要问题在调度与发布出口，增加M4模型调用无法代替出口恢复。无新增待用户决定项。


## 14:22首包实际恢复与14:29当前边界

本轮旧ready12来自两份旧导入PDF，共36条拟采用B档作者陈述，均不属于新接收的美国电力23来源。原7个PR的真实CI均是`browser(core_a)`中`part_dossier`超过300秒失败；validate/core_b/model_assets/storage通过，不是预算未启动或取消。独立M4精确原head完整案例52秒通过，集成最新TA11后67秒通过；未删除3D深链、拖动、主题、接管或资源契约，也未仅增timeout。五个prepared草稿的真实失败则是旧基线审核摘要/清单陈旧；不盲重算当前规范摘要，也不覆盖它们的未提交研究草稿。

首包PR453：batch `7fc9b1661eb4fe585ab3a284846261f2a6876cd8f9e73067548833d8575c8634`、原attempt-0003、bundle SHA `9dbf052fa56a3b845b68b1dc8d488b3cafa0b656d8c50024b172d036eed61afc`保持。head从35b7bb0f→fb31df97→b1c63a2f，仅追加文档1/证据5/陈述5，旧记录和answers不变。最终以31dcd368/.23为基线，14:13:55当前来源/上下文/封存审计/固定独立抽样全通过；治理1605路径、strict零警告、registry353对象458问题、资产、1970单元、29浏览器suites/32场景、隔离Docker A→B→A存储、派生verify/indicators全部真实通过。用户在本会话明确授权完整本地验收后不等CI合并上线；没有伪造CI成功或新增全项目免检接口。14:16:12实际merge d054f542与精确审核树一致。

M5维护使用独立锁与原worker锁，先一致备份12包journal/审计及5份dirty草稿。GitHub推送受已有keychain错误-25308阻塞，未调整凭据，改由M4已有访问更新原PR并用核验SHA的增量Git bundle同步M5。记录保留原PR/head/包/attempt及base_refreshes。维护keeper在14:22:26实际恢复LaunchAgent，新PID25958、原配置路径、clean d054源码且PR445当前上下文重新审核逻辑可见；至少一轮真实status为published。不能仅以bootstrap返回值宣称服务恢复。

Spark于14:20:09从clean a5b7d052安全快进到d054f542，正式knowledge SHA91bcbf0c…与生产ledger相同。独立Reader仍clean faa83480、相同PID1906533/NRestarts0、持久91 override字节相同；scope5907及SHA保持。此次快进没有Reader/schema/catalog/runtime实现改动，也没有重启Reader/relay或修改共享scope。之前Reader短暂退出与另一任务后续恢复按时点分开，不能归因于本轮publisher维护。

原publisher自然在14:22:44以精确d054镜像完成真实HTTPS五条正文/采用状态/引文/原件支持闭包，14:22:45 Spark记录published5/background1。14:25独立公网HTTPS GET 200，五条正文、source candidate绑定与支持闭包全真；实际API未序列化的审计字段由当时部署curated ledger和稳定ID链另行绑定，未把字段缺席冒充API输出。proof SHA de4fa720…、正式knowledge SHA91bcbf0c…与Spark一致。[完整真实回执](../reviews/2026-10-09/research-publication/pr453-actual-closure.json)保留原CI观察、精确本地验收、服务恢复、源码同步、HTTPS与published。

14:29:37对原12包重新只读复验：published1、review_ready8、reviewing1、queued2。剩余11包中5包当前上下文仍一致，6包已变化；正常publisher已把部分旧PR按既有revalidate重新排队。每个后续实际采用都会改变相关问题/对象的上下文，必须逐包fresh复验，不复用首包或13:46的true。[逐包当前回执](../reviews/2026-10-09/research-publication/old-ready12-followup.json)只证明该时点，不是后续合并授权摘要。继续维护必须恢复原publisher并实核新PID/路径/状态，不留下停服。

美国电力原23份于13:35的正式支持C3为0，13来源566条资料可读和844候选分开计量；首包5条只计旧ready包恢复，不记入原23采用。现行流程继续原23逐篇阅读、C3、独立抽样与逐条支持闭包，不关闭问题或顺带改价格/GW/合同字段。[专题阶段](../reviews/2026-10-09/research-publication/original-23-stage.json)与[专题交接](us-datacenter-power-20261009.md)分别保留具名来源和缺口。

14:29阶段下一步（历史安排）：先复验仍ready的包；来源或研究上下文变化经既有revalidate保留旧attempt/PR后重新C3，prepared草稿在保留旧diff/审计的独立树集成已审阅最新基线再验；完整适用本地验收后精确head合并，按既有来源同步→实际HTTPS→Spark published顺序闭环。没有新的待用户决定项。


## 16:08–16:42实际反哺进度（历史阶段，北京时间）

原23份来源已登记并补源，16:08:29逐SHA核对14份complete且报告字节/封印一致、9份queued。PDF仍保留native_text_only、visual_review_performed=false和full_document_complete=false；complete只表示该Reader正文/封存范围完成，不等于整篇含图视觉深读。NERC在15:30仍为262/262块但未封存，15:31:39实际完成原生正文封存、15:52只读已见14篇complete；不是本次review重载新完成；块数与整篇完成分开记录。该时点正式支持13条：Alphabet B档作者陈述6条与EIA具名代理A档历史表格观察7条；16:35核对另一原23包PR487的实际公网与Spark published3后，已验证闭环累计16条＝Alphabet B9＋EIA专项A7。资料可读、Reader新候选、review_ready和正式支持记录分开；没有关闭问题或改变旧价格/事实/模型。另16:31根审确认首批Alphabet六条文本支持仍成立，但原机器object_ids误含system:control，不能表示设施DCIM/BMS采纳；其企业软件/运营安全归属待真实reviewer审计修复。原候选/证据与旧映射历史保留，本轮不静默更改；相关fe2e旧bundle暂停采用。

原投递50项是C01–C41共41数字候选和S01–S09共9机制/接口陈述，不存在C42–C50。EIA七条以source_submission_ids明确对应C35–41；Alphabet现九条来自同源Reader新提取，没有原Cxx绑定。当前可证原50显式对应7，另外43未见显式采用绑定，不自动判拒绝，也不将同源正式16写成“原50已采用16”。逐项见[50项身份索引](../reviews/2026-10-09/research-publication/original-50-identity-index.md)。

Alphabet首包[PR480](https://github.com/niuroumiantt/InResearch.ai/pull/480)实际于15:45:18合并0e1d6e56；精确head5f957432本地1983单元及适用浏览器/治理/strict/registry通过，完整不变代码浏览器沿用已验收基线并明确记录。旧prepared失败为73c基线的验收摘要陈旧，修正已由PR475提供；旧dirty树、补丁、attempt1、bundle3e6cedc2和8份审计保留，在独立最新基线重放相同审核正文，不覆盖草稿。M5恢复新PID35290后，15:47:37实际HTTPS支持闭包，15:47:38 Spark published6；15:50独立公网再验6/6。六条仅为管理层署名产品/客户/工作流陈述，未知来源确切日期、>30倍工作流分母等限制保留，不能推导支出、IT GW或当前独立认证。[完整闭环](../reviews/2026-10-09/research-publication/pr480-alphabet-actual-closure.json)。

EIA专项[PR483](https://github.com/niuroumiantt/InResearch.ai/pull/483)实际于16:02:40合并64021203，head4142d56a；1989单元、严格校验/治理/registry与M4实际HTTP均通过。具名代理按现行01§4审核完整原HTML、表头、七行与注释，采用仅2026年1—7月累计工业均价的历史公布观察，初步值身份保留。与旧5.6.A七月单月价格期间不同，七月旧值、frequency、模型和问题文件均未改；M04-Q11保持open。它是独立A专项，不伪造B队列attempt或published ACK。

16:08:29 AWS source/applied/image tag均6402120399f9933d8d91dfcbcbdd427729061fc4，镜像sha256:d1b3ca1b527ab666a38ef9653c33260d59c877873d0629a6da75ae8a809727b0，healthy且公网health200。16:07:54真实公网HTTPS七条全文/署名A/最小五字段委托/引文/原件SHA/阅读版本/report支持链全真；EIA资料API同源15条可读、URL与downloaded_original身份匹配。原Alphabet六条在新镜像复验全真。生产与Spark正式ledger同SHA d43e2a9d13650acc5782a691cc48b2cc099c083858bc64681a59b6426765cdb6，新registry同8919ae84cb62accafaa58664652b47f68cea76917e2328cfedd7a8b27ab7dddc。[专项闭环](../reviews/2026-10-09/research-publication/pr483-eia-ytd-actual-closure.json)。

原publisher另包[PR487](https://github.com/niuroumiantt/InResearch.ai/pull/487)的head5a7add0d/merge7fad4687、attempt1/bundle36c265b5保持。16:28:59独立公网HTTPS三条原文/候选/报告/支持闭包全真，16:32:30网站proof绑定b52镜像，16:32:31 Spark实际published3/background3，16:35:33只读实核；proof SHA1e0ec65b9f0da08bb15886c55fa777c6efe5d9c25077ae3e18a4de0027fdf4d6。三条分别为管理层对资本投入回报的定性判断、2027资本开支方向性展望与Search查询总体使用量；均保留来源日期未知、非独立认证/已执行支出/AI算力增长的限制，object_ids均仅actor:alphabet-google。不是549的三条，也没有原C/S绑定。[独立闭环](../reviews/2026-10-09/research-publication/pr487-alphabet-actual-closure.json)。

M5先自然idle、独立维护锁+worker锁下一致备份1424文件/114journals，精确Git增量bundle同步后原journal字节SHA全部相同。16:04:23实际恢复唯一publisher新PID57656，正确runtime640/新registry，16:04:57已产生真实新status且无error。Spark唯一review在16:11:17零在途自然idle、一致队列/catalog备份后16:11:18载入同源码，新PID2216083；新CLI七条A均supported，16:11:20新review实际开始按23偏好认领原23的两批，16:13:47仍有一批在审；原Reader仍PID1906533/NRestarts0及独立faa83480/91/limits，未重启Reader/relay。

共享scope在15:49:21已被未知外部操作者由5907减600至5307、无新增，SHA9b2b63fd6ffe00508d1a6d7066d6b4f69711226ac8f72578946011f33e86e66d；这不是本轮publication或review reload所做，未恢复旧scope。重载前确认当前scope合法、全已登记、原23都在，保护这些当前字节及23来源偏好397e208f…原样；include_daily额外3项的有效循环范围5310与原scope5307分别计量。[实际重载与scope边界](../reviews/2026-10-09/research-publication/eia-review-runtime-reload.json)。

16:08原23审核批为111queued/6ready/1reviewing/8deferred/7split_context/1reviewed/1published；唯一published是Alphabet B6，A7不虚构另一B ACK。全局ready10低于12，但队列仍未完成。[逐SHA阶段](../reviews/2026-10-09/research-publication/original-23-stage-1608.json)。下一包549b5c7c attempt2/bundle5553229d在16:13:08原件/8审计/固定抽样/当前context全真，三条管理层计划/预测已根审，原PR485/head d619本地相关40单元/浏览器/实际HTTP/旧记录不变校验通过。16:23:09正式main已被其它包更新至c176，实际fresh context变为false，故没有合并或正式发表；保留原PR/head/包/attempt与通过回执，16:26:27已按现行ready-only revalidate回queued，原8审计/包SHA与Reader/scope全同；16:26:55精确d619原PR485关闭为失效上下文，branch/attempt/journal/本地验收全部保留。继续原C3，不沿用旧true。其余包如context变化必须经原revalidate保留旧attempt再审。

旧Oracle/GPU成本材料PR453、PR455及另一操作者PR466不属于原23，分别计量；不得将旧ready恢复数回填专题来源/候选。原件20与工具存档正文3、三份原站字节null持续保持。其余九份全文封存、尚未对应的43原投递候选、合同/GW/园区电价/模型及微信实际发布继续待验。


16:32另发现原publisher LaunchAgent缺失且旧PID57656已退出，操作者/原因未知；本轮此前16:04真实恢复仍有独立回执。确认独立维护锁和worker锁均空闲、无其它publisher进程后，16:34:35取得双锁并一致备份117 journals，原plist字节保持，仅bootstrap原服务为PID2818，备份前后journal相同。16:42:16已产生新一轮真实pr_open、error=false。16:42只读runtime后来已到e968，publisher源文件16:41更新；PID2818早于该变动，不据Git文件声称后来代码已经载入内存。registry8919在16:34启动前已是现行版本。[缺席恢复与新状态](../reviews/2026-10-09/research-publication/publisher-unowned-gap-restoration.json)。


## 17:00–17:40对象补审、真实载入与原23续进（北京时间）

17:00:16整点只读快照为14份正文封存、8 queued/1 running，IEA125/138、report/manifest均未生成，不称整篇完成；Reader仍1906533/NRestarts0。17:23:11另一次实读已16 complete/7 queued，其中IEA138/138与NERC262/262均封存；17:24:35逐份完整verify_seal的原件、manifest、chunks和report全部通过。IEA本次新完成与NERC15:31:39既有封存分开；PDF原生正文范围和未视觉/full_document_complete=false保持。JLARC3/154当时有relay不可用错误，来源剩余七份继续原Reader队列，未为此修改relay或评分。17:23原23队列256 queued/9 deferred/21 split_context/4 ready/2 reviewed/3 published/2 reviewing；这与17:00的117 queued是不同时间发现及分拆后的队列，不把数量增加称任务倒退或完成。[整点快照](../reviews/2026-10-09/research-publication/original-23-stage-1700.json)、[17:23逐来源](../reviews/2026-10-09/research-publication/original-23-stage-1723.json)、[16份完整封印](../reviews/2026-10-09/research-publication/original-23-sealcheck-1724.json)。

[PR499](https://github.com/niuroumiantt/InResearch.ai/pull/499)已于17:05:33实际合并10ae8469，精确head913124a9；本地2004单元、治理/strict/registry和实际HTTP通过。首PR480的六条文本与十条支持证据只收窄错误设施IDs为[]，原B审核/原文/限制/来源/状态和完整before＋compact SHA长期保留，实际root具名代理A补审及最小五字段委托可回查；没有撤回文本、改原Reader候选或闭题。新包使用reviewed-object-mapping-v1冻结353对象目录，core必须给显式IDs和理由、允许空映射，独立抽样校验实际拟采用对象。不能从旧Reader标签或AI名称推导设施归属。

M5在17:07:14真实自然idle（稳定PID18897、无子进程、status落盘及2–20秒睡眠窗口）后以独立维护锁＋原worker锁一致备份1580文件/120 journals。17:09:43原Git增量bundle安全快进e968→10ae，120份journal字节及配置不变；恢复责任在尝试bootout前已登记，finally恢复原LaunchAgent。17:10:06唯一新PID57180从原runtime载入新registry，17:12:37实读首轮status为published且无error；不能仅以bootstrap返回值或磁盘更新证明恢复。[M5实际回执](../reviews/2026-10-09/research-publication/object-mapping-publisher-runtime.json)。本任务只操作M5 publisher，未操作Reader/relay；后续仅正式数据追加不会触发重复模块重载。

Spark的首次重载在停服务前发现canonical10ae已被并行PR493追加到29af，failclosed保留旧PID；审阅精确兼容增量后，17:15:19唯一review自然零在途、一致queue/catalog备份，17:15:21正常载入29af的新PID2433760。Reader仍同1906533及独立faa83480/91/limits，当前scope5307/SHA9b2b…、23偏好397e…、env/unit逐字节不变；旧5907→5307外部操作者仍未知，不恢复旧scope。[唯一review真实载入](../reviews/2026-10-09/research-publication/object-mapping-review-runtime.json)。17:16:23/24新PID实际发出SYSTEM_OBJECTS＋v1/353对象core请求，17:19:25实际SAMPLE_SYSTEM_OBJECTS请求也绑定同目录；17:21:04两包真正ready，17:21:43纯只读audit/context当时通过、固定抽样各1 confirmed。Alpha ca5404 attempt6为5 B提议＋1 defer、对象仅actor:alphabet-google；LBNL2494a6 attempt3为5 B提议＋1 background、对象[]。这10条当时只是已审待发布，不加到正式22，也不豁免后续fresh context。[实际core](../reviews/2026-10-09/research-publication/object-mapping-resident-core.json)、[实际sample](../reviews/2026-10-09/research-publication/object-mapping-resident-sample.json)、[首两包审计](../reviews/2026-10-09/research-publication/object-mapping-first-ready-audits.json)。

外部[PR493](https://github.com/niuroumiantt/InResearch.ai/pull/493)于17:07:59实际合并29af，head83edeab0、原6ee5 attempt4、bundle0cd22165保持；本轮没有创建/合并该PR或改队列。独立逐条读连续原生第6–9页、17/17逐字引文及当前14条相关陈述、5条legacy、4个开放工单，六条有限作者陈述成立：广告竞价改进/AI Max阶段/Hilton客户案例/Etsy查询案例/Search广告支出分母/Direct Offers报名测试。Hilton为“五分之一支出”，不能误成“少花五分之一”；>30%的分母是客户Search广告支出，非客户数、全部广告或企业AI预算；Direct Offers仅报名测试，不称生产采用。来源确切日期未知，产品当前状态、AI总支出/算力或GW结论均未认证。旧包没有新对象协议字段，保留历史B审计与抽样，不把本轮回查冒称协议升级。[六条完整独立语义复核](../reviews/2026-10-09/research-publication/pr493-independent-semantic-review.json)。

17:39:17真实公网HTTPS六正文/十七支持/原候选与原件SHA/原B及来源URL/role全部true，control/network/it三设施页均排除新增6＋17；资料API本次只核匹配分页50行，total113不冒称全量113已逐行读。Spark原6ee5于17:10:46生成绑定29af的真实website-proof、17:10:47 published6，17:36只读确认；proof SHA ba50809f…与原bundle/六稳定ID一致。[PR493完整闭环](../reviews/2026-10-09/research-publication/pr493-actual-closure.json)。至此独立核过的原23正式发布22＝Alphabet B15＋EIA专项A7；七EIA为专项A路径，不虚构另一B ACK。原50仍仅C35–41七项明确绑定，其他43未见显式映射；同源新提取数不回填原候选。

17:37:59 root实际公网复验PR499原6＋10全部单项true、实际原B＋具名A/委托/补审历史/支持链与三设施排除均成立，.36 registry/review源码同；正式表采用独立深比兼容的29af SHA ed7768fc。17:30首读仅全表SHA不等（并发PR493追加），16单项已全true；原完整JSON被二读同名覆盖，只按当时真实工具输出恢复窄观察，明确recovered/not original raw，原raw SHA不可用且未补造。[最终完整公网回执](../reviews/2026-10-09/research-publication/object-mapping-public-https.json)、[恢复的首读观察](../reviews/2026-10-09/research-publication/object-mapping-first-observation-recovered.json)。17:40:21 AWS自然timer已source/applied/config42762106、镜像55036305…running/healthy、.36及公网health200，未手动切换或数据迁移。[精确AWS回执](../reviews/2026-10-09/research-publication/object-mapping-aws-health.json)。

17:40:22最新main外部PR503又追加同Alphabet源一条订阅业务陈述/一证据，严格source层支持计数到23、显式原50仍7；此时本轮尚无该新增1条的独立公网/ACK闭包，已核published22与main23分开，不先宣称23全上线。后续仍按当前原件/封存/对象协议/审计/固定抽样/context与精确PR逐包核验、真实HTTPS及Spark回执后才增加完成数；不查或等CI，不改全局publisher策略、原资料、价格系列、GW/合同/模型或问题状态。原20下载原件＋3工具响应正文、三原站字节null及微信实粘/发布待验边界保持。
