# 09 软件职责与写入契约

2026-10-11 对象通道扩展：workflow.stock_objects 以显式 JSON Pointer 确定性提取候选；workflow.object_review 核原件、接收来源、定位与对象封印，准备和实际具名C3采用分开。正式写入只追加 data/object_observations.json，一次锁内CAS/原子提交；不覆盖现有公司档案、产品候选、价格基线和模型参数。knowledge.object_observations 统一身份、区间、有效时间、冲突与所有者修订；严格校验检查账本。research_publication.json 声明公开字段，public_records 是首页与登录后分页 API 的同一服务端出口，仅统计允许公开的记录；不得直接序列化内部账本。API 支持对象/类型/公司筛选、最多100条分页，拒绝未知/重复参数。会员扩展须校验独立付费权益，不复用内部member角色，未实现时不授予访问。Fetchspec源采集/打包/接收允许无目标发现，声明模型目标仍核原合同；保持单一发布队列。

2026-10-11 条目采用职责：`workflow.targeted_research` 从现有归档验证字节 SHA，提取指定原生页，冻结对象/字段/范围及逐页上下文摘要；任务通道另冻结当前需求；不改 Reader 状态，不启动发布器。`workflow.project_review` 的 `object_excerpt`适配器重新解析同一源及对象绑定并核验逐页引文，`targeted_excerpt`继续校验任务需求；收到的日报事件可凭明确对象绑定使用空研究目标，继续执行实际C3、独立时间、范围及追加写入。`knowledge.site_metrics` 管水、电及强度指标的原生区间／期间／边界，`site_register` 仅投影园区地理、分角色主体与逐字段来源；不能据名字去重或据分期计算规划总量。Reader全文、局部采用、问题完成及网站发布保持独立状态。

2026-10-08：研究核验的 Spark 私有队列及请求/输出与正式源码记录分开。核验 worker 不写正式研究表；M5 发布器只在独立、可恢复的工作树追加通过 C3 B 的作者陈述/预测。正式上下文变化拒绝提交并保留旧审核，重新核验有独立尝试；已有结论、answer 与 GW 不因发布器改变。Git合并及配置模式验收、网站采用 API 支持闭包与 Spark published 回执分别计量。新任务发现与发表来源复验使用不同投影：前者过滤已采用，后者保留封存候选/原文页，以原件/报告封印和逐字段比较判断真实变化。单批错误和无变化的待CI/部署不能阻塞其他批次；已独立合并且head精确等于原审核commit只恢复网站回执阶段，继续实际支持闭包验收，保留失败恢复记录。服务/网络异常保留日志与阶段，不靠 reset、重读、删除原件或重启共享 Reader 恢复；永久审计包不随工作树清理。

2026-09-13，用户采用按核心契约、统一用例、脚本拆分、目录迁移、页面结构、旧实现退出的顺序整改。本规范仅定义软件运行边界，不替代 00–08 的研究规则和 M4 原件操作 scope。

## 权威和依赖

材料按内容 SHA-256 标识；M4 预览和精读打包在抽取前核对内容，在抽取后核对文件状态，清单后的替换或读中变化须重新登记，不能归到旧 SHA；文件路径属于观察和位置。原件、粗读判定、全文候选、口径事实、正式采用是不同对象，不互相冒充。L1 有效结果只由 materials.records 投影；一次失败尝试不能盖掉成功判定。reader 的任务和配方以 SQLite catalog 为准，默认模型变化不使已完成材料重读；重试不等于版本替换。

事实以 data/facts.json 和 metrics/data_contract 为准；已采用知识以 research_knowledge.json 及证据/依赖规则为准；reader 快照始终是候选。READ_LOG、网页、报告、目录 CSV 和任务列表是消费视图或执行记录。历史版本和来源冲突保留，更新日期与模型分数均不自动获得覆盖权。

代码按 materials、knowledge、workflow、delivery、adapters、interfaces、storage 分工。接口解析身份和参数，调用用例；用例组合领域判断及存储，适配器只转换模型/格式/外部系统协议。禁止领域依赖 HTTP。公共实现必须登记全部仓库内消费者及库外已知运行入口。移动文件后保留的反向依赖仍是未完成项。

任务视图只通过 `knowledge.registry.task_board()` 读取；接口不得把静态投影与动态任务再自行拼合。`workflow.workorders` 仅生成模块缺口投影，研究问题任务由 `current_tasks()` 从当前问题与已采用知识计算。

## CLI 参数所有权

`manage.py` 与 `python -m inresearch` 共用 interfaces.cli。命令名前的全局 `--root` 只用于
add-price、assign、receive-snapshot 三个统一 JSON 用例；缺省为 project_root。它选择传入用例的
项目根，仍受既有 storage_contract / INRESEARCH_RUNTIME_ROOT 或快照目标配置约束，不是全局隔离开关。
其他委派命令收到显式全局 --root 时，在导入和执行前退出 2 并说明用法，不能静默忽略。
命令名之后的目录选项由子接口解析，例如 `inventory --root ...`、`reader --data-root ...`；
不猜测统一改写为其他目录参数。源码根、网站运行根、原件/catalog 根继续分别拥有权威。

派工用例（2026-09-28）：`assign` 接受 `target_id`（目标表的行，唯一任务书）或 `workorder_id`（兼容工单）；新增 `register_delivery(target_id, evidence_path)`（HTTP `/api/deliver`）登记交付指针。两者只写 `data/assignments.json`，不改目标表；实习生只能改分配给自己的行。目标行投影 `/api/targets` 由 `workflow/dispatch.py` 按角色在服务端过滤（`mine=1`、`team`、`node`、`col`、`status`）。

全球园区任务跟踪（2026-10-12）：`workflow.research_tasks` 是协调工作包的唯一用例，`framework/research_task_plan.json` 提供新建任务及尚未分配的区域包，运行协调台账在 `data/raw/research-tasks/ledger.json`，不能经静态URL下载。登录后 `GET /api/research-tasks` 读取协调状态与既有地图容量口径；`POST` 要求 `X-Requested-With: research-tasks`、操作者、预期版本与唯一操作身份。member/admin可创建和分配，intern只能更新已分给自己的状态、交付指针及备注。版本比较、稳定锁、原子提交与同键重放防止并发覆盖，审计保留旧值与操作者。协调状态仅到“已交付”，不授予资料接收、研究采用或地图发布资格；这些回执继续由原流程独立证明。页面不采集或上传原件，不编造负责人、机器、截止时间或全球覆盖。

回执进 Git 载体（2026-09-29）：`knowledge/deliveries.py` 是运行库交付指针进入 Git 载体的唯一用例——`import_assignments(root, assignments_path)` 读运行库导出的 `data/assignments.json`，把带 `delivery` 的记录写成 `data/event_cards.json` 事件卡（目标行须存在、指针须是公网 URL 或仓库内相对路径、同一指针幂等），随后由 `knowledge/targets.py` 重建目标表；`check(root)` 校验卡片。只在作者 checkout 由 CLI `deliveries import / check` 调用，HTTP 不暴露；网站与 Spark 不回写 Git。

HTTP 访问边界（2026-10-12 替代原 reader 目录匿名规则）：只有首页 `/`、`/index.html` 与其必需资源/登录机制公开，首页数据API仅接受独占 `overview=1` 的有界投影。其他页面、完整API、研究JSON/文档/图册/模型下载均先经服务端登录门禁，GET与HEAD同查归一化路径；参数、编码、反斜线、路径别名与静态源路径不能绕过。admin/member/intern 保持既有权限，intern的旧reader读取能力显式登记，新任务页对登录团队可用。私有响应、匿名重定向与401均 `private, no-store` / `Vary: Cookie`；上线清除旧CDN公开缓存。现有机器bearer接收保留独立凭据检查，首页白名单不授予写权。

健康探针（2026-09-29）：`GET/HEAD /healthz` 在公开白名单内，只返回 `{ok, service, auth_required}`，不 stat 运行文件、不读登录态；容器编排、镜像与 infra 应用登记表三处探针统一探它，不探首页或登录页。

入口借用 sys.argv 调用旧子接口时，成功、导入失败、执行异常均恢复原参数对象；后续顺序调用
不继承前一次委派的参数。此适配不支持多个线程同时使用进程级 argv；并发任务使用独立进程。
子命令退出码、JSON 形状、模型配置及事务/重放/版本规则不在此层重复实现。

## 发布研究与运行状态

网站部署设置 `INRESEARCH_RUNTIME_ROOT`，`storage.layout.workspace_path` 根据
`framework/storage_contract.json` 解析逻辑路径。Git 发布镜像是正式 facts、知识、schema、
框架、指南及产品定义的权威；容器根只读。账号/密钥、价格、派工、产品资料处理计划与索引、
候选快照和上传原件位于独立持久目录。报告、简报、指标和队列是可重建投影；
`reports/HOW_TO_OUTPUT.md` 与模板仍随源码发布。指标定义来自镜像，每次按当前数据重算，
逻辑 URL 保持 `/framework/indicators.json`，运行文件为 `data/projections/indicators.json`。

无运行根的本地 checkout 是作者工作区，沿用源码写入；生产网站不承接正式研究文件修改，
正式采用/事实更新在受审核工作区经原用例提交后发布。模型/Reader catalog 仍按原件根配置，
不与网站运行根合并。旧卷内的正式事实和指南保留为历史副本，退出当前网站消费者。

初始化仅对契约声明的种子建缺失文件，不复制整棵 data/reports，不覆盖已有状态。首次完成后
状态缺失必须修复；投影可重建。读路径与 `storage check` 不创建目录；`storage initialize`
持布局日志锁，并逐一持业务文件锁校验缺失与持久写入，不同时持多个业务锁，以免与资料库
INDEX→PLAN 顺序相反。初始化中断按同一布局/种子版本续做；中断后种子改变或布局变更明确
拒绝，要求恢复原发布或实施单独迁移。完成后新镜像不重播种子；A→B→A 只切研究版本，
运行写入保留最新。已有部署的预检要求原 admin 存储和 32 字节会话密钥，不能通过重建账号
或密钥掩盖丢失。原件、候选和日志均不随发布删除。

历史简报对 SEC 信号只生成 `review_suggestions` 及依据，退出自动改写 Finding 状态的
`mark_findings_needs_review`/`review_marked`；正式撤回/采用仍须研究审核。重新生成简报不是
正式知识版本替换。开放口径维度没有预设 values 时，工单要求按原文填写，不能跳过维度或崩溃。

## 写入与失败

所有权威文件的读改写锁覆盖完整读取、领域校验和提交，且跨线程及进程有效。原子替换不能代替此锁。临时文件同目录且唯一，文件 fsync 后替换，再 fsync 目录。无效候选不先写入再回滚；提交前的校验、临时写入或替换失败保留旧权威内容。替换已经成功而目录同步失败时，新内容已可见、掉电后的持久性未确认，抛出 CommitUncertain，不得声称旧内容仍在，也不得盲目回滚。价格、派工和快照的 HTTP/CLI 返回明确的提交不确定状态，调用者先读权威记录再按稳定键核对、恢复或重试；其他文件消费者沿 OSError 失败路径停止，逐用例恢复能力另行验收。内部日志损坏报错，只恢复未完成尾行。

多文件提交明确主提交点及恢复过程：事实成功提交后，阅读记账可以重放，不可因日志未写而重复插入事实。产品资料库 fetch/adopt 共用准入：准备日志→校验字节及归档→索引主提交→计划回执→关闭日志。任一步中断在下次写入前恢复；同 SHA 共用一个索引记录，输入原件不删除。不可将多个独立 rename 描述为单一事务。快照接收在锁内比较版本、校验和替换；重复和过时快照返回冲突。人工派工与价格写入的 HTTP/CLI 调同一用例，角色和状态规则只有一份。

L1 自动评分、预览重检、人工归属/限制修订与新终端包须带处理开始时的有效版本基线，锁内比较后才能提交。没有基线的历史终端包只能建立首次结果，不能覆盖已有成功；冲突后重新打包。重读替换须显式关联旧版本、原因和成功验证，切换前保持旧成功结果。

## L1 预览与判定用例

`workflow.l1_batch` 是 M4 L1 待处理选择、预览净化与格式预算、活动时段速率、版本候选的唯一实现。`score`、`attribution`、`terminal_batch` 和 `progress` 仅解析命令参数、调用该用例并呈现结果；`triage` 保留 preview/sample 与历史远端 batch 回收，不再提供转发到 score 的 run 命令。模型工作通过明确的调用函数注入；不能通过导入或修改终端 CLI 模块取得队列、预算或 ETA 规则。

L1 结果仍只通过 `materials.records.commit_result` 和调用开始时看见的 revision 提交。并发模型调用必须先占用预算槽；失败写入可重试，迟到结果因 revision 冲突被拒绝，不能覆盖后来的终端结果。没有活动时间样本时 ETA 为未知，不得以文件创建时间制造速率。版本候选仅报告同报告的可能重复，不移动、删除或自动替代材料。

全文 reader 的 documents 拥有内容身份、原件位置和当前版本指针；reading_runs 拥有独立配方、产物与执行状态，jobs 绑定 revision_id。current_readings 是唯一当前阅读投影；新版本 ready 后经审阅用例验证原件、覆盖、产物清单及报告 SHA，再在一个 SQLite 事务内比较基线并切换指针、保存审阅。旧版本和候选仍保留，重放不重复创建或倒序覆盖。导出持同一读事务，目录导出以版本文件名和最后原子提交的 manifest 形成一致入口；后台旧文件不作为当前选择器。

旧 SQLite 在持队列锁且完整备份后事务升级，移除 documents 的执行列，保留任务尝试、外键与旧产物路径；失败回滚，不丢弃孤立记录。库升级不同于源码发布，Spark/M4 实机升级须另验。重读不再次搬运原件与接收回执，library 名称保留为原件别名。

## CI 影响范围

CI 分流与 GitHub 必过门禁的唯一现行源是 [docs/CI.md](../docs/CI.md)。保留 `validate`、`browser (core)` 两个始终上报的名称，汇总计划所选检查；研究 JSON 与程序/规则修改继续全套，普通资料文案与图像按相关范围验收。精确 head、失败不得跳过及网站/Spark 实际回执要求继续执行。

## 运行边界和验收

Claude CLI 暂为默认推理执行器，未来 Spark 或更大模型从 role/profile 配置接入；客户端与实际模型分别记录。Python 标准库是核心运行约束。源码目录、公开 URL、生产数据卷和远端启动命令分别登记；迁移源码不隐式搬动原件、账号、密钥或运行数据库。

共享页面结构显式声明，主题仅决定明暗外观及偏好，不通过猜测旧导航或重组任意 DOM 决定业务结构。

交互场景资源与场景语义分开：`scene-resources.js` 拥有异步 HDR 代次、超时/失败回退、PMREM target 替换及 CanvasTexture 池；bom3d/rack3d 只提供程序化环境和纹理配方。每次 retry 取新代，旧代迟到输入只释放不提交；新 target 提交后才释放旧 target。图片失败沿用同一个已有程序化 CanvasTexture，不把空加载对象称为兜底。dispose 幂等，清空仍由自己持有的 environment，停止页面渲染后释放 composer/renderer；它不释放外部可选模型或把来源许可变成运行判断。

验收分别披露实现完成、具体环境的验证、剩余工作。用业务流程、失败重试、独立进程并发和版本倒序/替换验证。测试全绿、成功部署、目录改名和行数变化均不能单独证明架构收敛。整改实施证据见 docs/reviews/2026-09-13/architecture；其计划和快照不反向成为规则源。


2026-09-13 集成核对：文本指纹和近似摘要仅为复核提示，不能代替原件内容 SHA，不能自动阻止另一内容版本开包或沿用其证据。合并单元格展开在分配前检查累计抽取预算，超限明确失败并保留原件；截断或超限不计完整阅读。

带 `twin_of` 的文本副本自动推测记录不是完整阅读证明，保留日志供复核，不能单独让另一 SHA 退出事实处理队列；后续事实处理回执可按其身份生效；全文结果仍须查询 reader catalog。

## L2 终端阅读用例

`interfaces.deep_read` 只处理命令参数、输出与错误；`workflow.deep_read.DeepRead` 显式绑定项目和运行路径，组合领域规则与存储。`materials.reading_policy` 是队列、打包和事实录入的共享准入规则；`materials.text_similarity` 只提供相似度提示；`workflow.reading_gaps` 维护指标缺口；`knowledge.provenance` 给出来源身份修复计划。事实约束仍归 `knowledge.fact_contract`，不经 L2 聚合转出口调用。

打包在全部有效 L1 判定中先解析唯一 SHA，再检查范围；歧义不能通过分数过滤变成唯一。L2 自动队列按 M4 任务卡默认 ≥7，显式点名可越过优先级分数，仍须满足成功判定、准入及已处理/again 条件。每次包生成独立目录，完整正文、提示和 manifest 写好后才发布目录；旧包不覆盖。返回 L1 的 result_revision，attribute/flag 须以客户端已看过的 expected-revision 提交，不能在收到旧指令时临时读取最新版作为其授权基线。

record 在事实锁内读取/校验/提交，并持相同的 L1 判定锁复核来源准入；锁顺序为 facts → L1 → 完成日志。自写材料与已标限制材料不能绕过队列直接录入，限制变更不自动改写既有事实。事实为主提交，完成日志按稳定请求身份幂等记录；相同事实重复提交不再插入，事实已提交而回执失败返回 facts_committed_receipt_pending。零条是允许的人工完成声明，不由空数组自动证明全文已读、重新评分或正式采用。

指标缺口按材料 SHA 与缺口文本取得稳定身份。缺口主提交先完成，随后才记完成回执；失败返回 gaps_committed_receipt_pending。重复提出不会重新打开 filled；重复销账可重放，未知 ID 仍拒绝。批量销账持整个台账锁，通过一次持久原子替换提交追加的历史行；不用多次追加冒充一次事务。损坏尾行沿既有 JSONL 恢复规则处理，中间损坏拒绝继续。

来源修复默认只输出计划。只使用明确的 SHA 前缀、精确登记路径或成功移动端点构成的缓存映射链；文件名、JSON 子串、未解析或互相冲突的身份路径不提供覆盖权。commit 须传干跑的 expected-plan；事实及相关台账在同一组锁下重读，计划绑定事实内容和具体解析候选，变化则拒绝。没有原件复核的历史事实不因机械补齐 SHA 自动取得质量验收。命令不指导自动降低测试基线。原 38 条历史缺口继续单独披露。

L2 事实处理回执保留 executor/model 及核实状态。终端提供的身份是 client_reported；缺失为 unknown，不推测当前默认模型。完成请求重放保留最初的归属，不能借重试替换旧执行身份。

上游断言者契约的 claim/revision/forecast/争议索引统一由 knowledge.fact_contract 维护；录入在同一事实事务内补齐 disputed_by 并返回双方摘要，CLI 负责呈现 C3 A 档待审事项。服务生成的反向链接可在原请求完成后增加，不能令原事实请求重放失败。保留上游 asserter、disputes、supersedes 的形状约束；不将自动链接或终端提示当作已经完成 C3 审核。

record --doc 须匹配已登记的完整 SHA 或唯一前缀；无 --doc 的人工事实输入仍可携带未登记来源，其通过形状校验不表示来源已准入或原件已核验。已知来源的限制在事实事务内检查；打包仍要求唯一已登记成功 L1 和原件字节校验。record 回执仅证明这次录入/完成声明已持久保存，不能充当完整阅读或来源质量证明。


持续研究审核的内容包选择按04，以实际需求匹配及逐条原文检索词生成版本化上下文；完整研究语义不作预算裁剪，重复执行回执只用可回查哈希引用。队列重组只处理未执行批次，旧尝试和每条候选去向保留。发布器通过M5发送已合并main的增量Git对象到Spark，校验祖先、传输SHA及干净HEAD后快进，不改原件或事实。预算失败清单只投影标题、内容SHA、批次ID、大小、时间和错误分类，不向网站输出原件路径或模型请求，亦不产生采用权。

持续C3对象审核使用版本化提示和 `research_context.object_mapping_contract`，历史SYSTEM/SAMPLE常量保留。validate_reviews核对显式对象集合/注册ID/理由，verify_audit将独立抽样的实际proposed_reviews精确绑定，promote应用审核后对象归属而不修改封存候选。协议/目录真实变化沿既有context失效与revalidate处理，原件复验的document/items不因审阅协议升级而改写。knowledge.registry仅接受完整before+SHA的技术严格收窄补审，原审核/正文/引文/问题/状态不变，失效补审阻断支持闭包；不提供事实/结论替代或分发放宽入口。

## 审核来源偏好与公平租约

`workflow.review_preference`只读校验显式私有来源文件、已登记身份和当前完整版本；`research_review`在原单worker锁和ready背压内共享该轮快照。仅启用偏好时，queue.sqlite增加`review_scheduling`元数据表；三次偏好/一次原排序机会的连续计数与领取租约同事务提交，不改候选批次或旧失败。状态中的`last_scheduling`为上次领取审计，实际scope SHA、选中批次/来源和通道同时保存到attempt的`scheduling.json`，不进入模型提示或取得采用权。未配置不新增调度表、不改默认排序；完整封印仍经原packet路径复验，C3与独立抽样使用原冻结角色。

## 当前全文结果的共同消费者

workflow.reading_results.ReadingResults 使用 storage.catalog 的只读连接，在单个读事务内选择 current_readings 并调用 materials.reading_artifacts 的同一产物校验。ReadingStages 继承该产物责任；版本审阅继续使用相同封印检查。查询不初始化或迁移 schema；只读连接禁止写事务和直接 SQL 修改。它没有写入当前指针的接口。

reader current、deep-read current 和 L2 pack 是共同查询消费者。pack 在验证 M4 内容身份后复用当前报告所绑定的正文，并把 reading_result（状态、版本、报告 SHA 和原路径）写入任务包 manifest。并发激活不改变已经取得的快照，旧包保留旧版本引用；新版 ready/失败/重试和默认模型改变均不绕过既有 activate-revision。

L2 的 read_documents/remember_read 及 documents_read/already_read/eligible_unread 退出当前 API，分别由 processed_documents/remember_processing 和 documents_processed/already_processed/eligible_unprocessed 表示事实处理。receipt_log 沿用 l2_read.jsonl 文件名与稳定 operation_id；旧行仍供处理进度与重试恢复使用，不升级为全文报告。相似度的 processed 也仅来自该回执。status.reading 的 catalog_current_results 是 catalog 清单计数，非逐份新验收；具体结果须通过 current 校验。跨机器统一与旧资料导入未由本次只读接口自动实现。


## 视觉输入的共享导入与发布

materials.model_assets 拥有视觉输入内容身份与采用状态；workflow.model_assets 拥有候选导入用例；adapters.asset_download 只处理下载和格式转换，asset_check、HTTP 和静态路径共用领域校验。web/assets/models/manifest.json 是唯一登记主提交点，网站只读发布状态，不提供采用写入接口。候选/拒绝模型的存在不赋予默认场景显示资格。

导入使用 storage.files.locked 包住读取、同名核对、独占创建和登记提交。atomic_write(exclusive=True) 用完整临时文件的独占链接发布，旧两参数原子替换调用语义保留；目标存在即拒绝覆盖。二进制先发布、登记最后提交，中断留下的完整未登记文件在同内容重试时复用，不当作已登记；同名不同字节拒绝，新版本用新名字。登记已提交但同步失败维持 CommitUncertain 语义，重试先读取现行决定，不删除原件或重复登记。该流程不替代产品资料库既有预备日志，也不是所有多文件写入都已统一的声明。

同一发布登记派生比较视图、已采用场景视图和允许的 GLB 静态路径，无第二份发布列表。作者修改在 Git 审阅与发布流程生效，下载器不自动采用或推送。外部下载包和 glTF 引用只在临时目录内解析，源材料不移动；核心仍使用 Python 标准库。


## 浏览器视口与镜头责任

scene-view 只持有画布尺寸观察、可见几何边界、透视适配及自动/用户镜头所有权；页面提供 renderer/composer 的尺寸回调、研究对象集合、固定导航与领域动作。model-assets 持有采用模型及加载代次，只读 objects 不复制登记或让消费者释放模型。part-inspector 独占预览 renderer 和克隆材质、借用原几何，退出清理观察与独占资源。比较台退出逐帧 setSize；主页面退出窗口尺寸/zoom 猜测，两种预览退出 rad×2.9 距离常数。此边界不表示全部 renderer、HDR、面板纹理或领域几何已统一。

## 资料供应规划（2026-09-21）

workflow.supply 持有需求/任务计划的唯一用例，HTTP 负责权限与参数，supply.js 只消费服务端视图。能力目录随版本发布，运行台账复用 private data/raw 存储边界；台账读改写锁、expected_revision、UUID 回执共同防止覆盖和重复。采集需求只能细化现行 target_id；服务端复验目标版本、可选问题的节点/变量类、责任队与目标主执行机。旧无目标需求只读保留，不能继续派工。原件包接收、阅读候选和 C3 采用分别处理，前端不得模拟完成；业务契约唯一见 06。供料的阅读查询必须使用 catalog.current_readings，与其他当前结果消费者一致，不从初始版本推断现状。读库失败显示状态不可取得，不冒充尚未登记。

knowledge.target_request_contract 只生成目标请求轮廓，knowledge.research_readiness 只聚合研究就绪度；生成器与 admin API 共用聚合。运行回执来自接收快照，缓存按真实 framework 目标/问题/图谱、模型与正式研究文件失效。目标问题链接仅为同节点/变量类的检索关系，范围仍须由任务说明与研究审核确认。不同队的当前新闻窗口与累计原件回执分母不相加，不自动回写 Git 状态。

2026-10-08：需求匹配v3仅归一PDF排版空白，不改变原文与证据。完整响应缺ID或虚构问题仍拒绝；逐条检索词失败隔离保留，其余候选继续审核。审计复验完整原始响应、接受/拒绝分区、模型输入SHA和独立抽样，旧协议原样复验。`retry-matching`只受理旧的检索词协议失败，保留全部尝试；不得借此重试或放行独立复核/原文失败。

2026-10-09显式暂态恢复：workflow.research_review拥有`retry-transient`的精确比较/排队用例，CLI只解析完整batch ID及expected-attempts/expected-error。坏参数在初始化队列前拒绝；仅耗尽原预算（至少四次）的deferred暂态模型错误白名单可受理，当前revision/report/完整封印/原件SHA与当前失败文件均复验。BEGIN IMMEDIATE事务同时保存每个候选的原去向、失败/封印SHA与恢复原因，并更新该批次去向；并发相同请求只允许一次成功，历史写入失败全部回滚。不得修改attempts、available、候选或原审计，不增加调度优先权；只排一轮，新的失败仍服从原预算，正常worker再核源身份与C3/固定抽样。catalog与queue为独立数据库，复验期间二次读取当前源指针，不宣称跨库锁；不得用此入口绕过认证/身份/格式/引文/抽样/语义错误或制造发布回执。

2026-10-10单任务阅读恢复补充：`workflow.reader_retry_job` 拥有既有 catalog 中 `retry-job` 的在线精确比较用例，CLI在构造 Reader/模型及取得 worker 生命周期锁之前分流，显式绑定数据根、doc/revision/read块、`model_cli_failed`、expected attempts、冻结recipe ID/文件SHA、request ID/by/reason。只接受当前 failed/read版本的唯一failed且无blocked/running任务、原预算已耗尽、目标无结果路径且无已有块缓存（存在则保留并拒绝）；复验原件SHA、context snapshot_hash、与reading_revisions同算法的recipe ID及冻结提取/粗读/全部成功块及块号/页号/字符数，不初始化库、不重抽取或调用模型。先保存0600的SQLite online一致备份和前快照，`BEGIN IMMEDIATE`重验同一快照与文件SHA后，只改目标jobs及reading_runs的state/error并保存meta事务marker；任何提交前失败均回滚，提交已可见后以marker为准，receipt写入失败不再次排队。attempts/max_attempts/available/时间/优先级、成功块、其他文档与scope/floor/model-wait保持；每个显式请求只恢复一轮，正常claim递增原次数，失败仍原预算终止。相同请求键幂等、改意图或破损审计拒绝；不完整prepare保留且须另经复核以新key恢复，后续独立人工恢复须重新比较当前实际次数/失败并记录新原因。该入口补充既有reader retry和研究retry-transient，不授予新模型执行、重读替换、C3或发布资格。

2026-10-09发布验收提速：完整浏览器core按统一已审阅suite清单分core_a/core_b并行，保留所有suite、密度场景与逐项断言/期限；browser(core)聚合只在全部matrix成功后通过，模型资产场景沿用。旧发布尝试被新attempt替代前，将完整journal不可变地保存到旧attempt目录，新journal保留相对路径与实际SHA，不能用新状态覆盖旧失败审计。


## 显式本地与汇总发表职责

workflow.research_publish拥有缺省CI/显式local模式、精确同源组和私有first_seen窗口、manifest/固定检查实际回执、普通push/match-head及部署/public canonical/逐batchACK恢复。任务默认4批/24条/300秒不修改审核queue、评分、原context或模型；旧journal继续推进。回执绑定精确head/main/成员/log SHA，head更新失效重验，不伪造CI。

research_review.promote_group持同一formal-write锁，全部成员先按未改baseline完成原audit/core/sample/context，再内存追加、registry/闭题保护后一次写入；单包promote兼容。旧记录/answer/闭题集合不变，跨成员引用/对象冲突整组拒绝；完全已应用的精确requestSHA重放沿旧无写协议。

local发表须核actual running/healthy digest与tag一致、merge属于运行source历史、外部health200/ok和全部公开stmt/ev/doc。私有audit/context/before不外送；原CLI逐成员proof保留batch/attempt/bundle和健康时点。闭包SHA按proof标记的encoded-v1顺序，不与其它compact/排序算法直接等同。

GitHub主线、不同publisher state和多个queue ACK不是一个事务，背压非跨机器锁。部分ACK按实证继续，远端commit而本机未记时重新实核并幂等ACK。准备真冲突保留具名恢复；旧小PR CLOSED自动superseded尚未实现，不假记MERGED/篡改历史。默认CI保持，生产显式配置及唯一驻留加载另留实际回执。

## 2026-10-10 源码审查的边界修正

Reader 与 editorial 接收复用 workflow.reader_scope.read_scope 的存储范围合同，10,000 文档/1 MiB 上限、有效内容身份与失败关闭一致；enroll 在原稳定锁内追加，已有 SHA 重放可在满容量成功，新增超过容量则不修改原范围。不因此扩张配方、改变优先级或授予采用。facts CLI 在加载事实前用标准参数解析处理帮助与未知选项，--summary 保留相同契约审计和失败退出码，只省略全指标展开；原文哈希缺口不自动修复。程序职责 README 的退役 SEC/GPU 入口说明和供应目标的交付协议原则与现行实现对齐。

## 源码目录与命名（2026-10-10 整改）

| 目录 | 所有权 | 不应混入 |
|---|---|---|
| framework | 当前规则、声明与生成目标；CURRENT 只作路由 | 运行台账、不断追加的发布过程 |
| data | storage_contract 登记的研究发布 JSON/CSV | 原件、账号、密钥、运行 SQLite |
| src/inresearch/materials | 原件身份、接收、提取输入和覆盖契约 | HTTP/CLI 展示 |
| src/inresearch/knowledge | 数据口径、研究身份与只读语义聚合 | 平台认证与模型调用 |
| src/inresearch/workflow | 用例编排、状态转换与写入权威 | 第二套数据判定规则 |
| src/inresearch/storage | 原子文件、追加日志、SQLite 与布局 | 研究采用判断 |
| src/inresearch/adapters | 模型、Office/PDF、新闻与厂商等外部协议 | 自定研究目标 |
| src/inresearch/interfaces | CLI、HTTP、权限与页面投影 | 重复实现用例 |
| src/inresearch/delivery | 报告、候选快照、导出与传输 | 不经审核直接修改采用 |
| scripts / deploy / tests | 构建发布工具 / 机器服务声明 / 相应验收 | 唯一业务逻辑或生产数据库 |
| docs/archive / docs/reviews / docs/handoff | 失效指令 / 历史评审证据 / 阶段交接 | 当前执行规则 |

模块与脚本采用 snake_case 的领域名+用途，测试随对象命名；避免泛化的 map/progress/policy/new/old/final2。已将 map 改为 project_capacity_map、progress 改为 triage_progress、policy 改为 data_rules；CLI 的 map/progress 是现有调用协议，注册表直接指向新实现，不留空转发模块。新增 target_request_contract 与 research_readiness 明示目标请求和研究就绪度。目录中的同名 reader/triage/model_assets 是不同层责任，不因同名自动判为重复实现。

删除前核对导入、命令注册、路由、服务/cron、当前指南与测试。私有未调用辅助函数可直接删除；平台动态调用或外部稳定入口须先核对消费者。历史源代码快照退出运行入口，保留为审阅证据；不把年龄当成无用证明，也不保留已确认无用途的占位或注释。

### 参数级派工与派生缺口（2026-10-11 R1/R2）

`knowledge.target_request_contract.resolve_request` 统一解析供应中心参数需求。新建和续派都校验 requirement_id、登记范围字段、已审核问题、来源队和执行机；未接通渠道不能产生 planned 任务。旧混合记录保留但不能续派。此边界不改变实习生任务分配与原件交付指针协议；后者不是参数证据验收。`knowledge.research_gaps` 是正式源的只读投影，CLI 私有导出与管理员 material-flow 共用生成函数；不写事实、答案或采用。

### 大候选库与运行视图（2026-10-11）

Reader 完整候选快照继续保存在私有 `data/research_runtime.json`，原件与 C3 权威不变。接收端先执行现行身份/覆盖/冲突校验，再以流式 JSON 原子落盘，避免同时创建完整输出字符串。正常新版本只读取前版的小型生成元数据；精确重放比较排除接收时间的规范语义 SHA，并核对完整快照 SHA。缺少派生元数据时，仅逐字节一致的大文件重放可重建视图；否则拒绝并要求显式重建，不能覆盖旧快照来掩盖失败。

`delivery.runtime_summary` 从已校验快照生成私有 `data/raw/research-runtime/research-runtime-control.json`：运行计量、当前接收/匹配信息，以及每份完整阅读的至多六条陈述、三条原文预览。它记录源文件身份、完整 SHA、语义 SHA 和正式研究基线 SHA；是可重建视图，不是第二个正式证据库。缺失、源变化或基线不一致时显示待生成，不能在普通页面请求里回退读取大型候选库。小于等于 8 MiB 的旧快照保留经过原校验的兼容读取。供应、材料流、运维、新闻与回流接口使用该视图；计数、全文覆盖和候选身份保持分开。

完整研究库读取按文件身份及图谱/问题版本缓存同一份规范化结果；重型研究 HTTP 响应与候选接收共用内存互斥，接收前释放缓存。缓存不授予采用，也不替代接收校验。交付预览用一次索引关联代替逐文档遍历全库。首次部署可执行 `manage.py runtime-summary --refresh` 重建，持同一源文件锁，核对原件指针和正式库冲突，不改完整快照、模型值或正式记录。容量上限与实际峰值仍需按运行数据验收，不能以健康路由成功代替业务接口可用。

### 2026-10-11：具名阅读调度

具名阅读顺序可用 `reader prioritize` 显式提高：绑定 doc_id、当前 revision_id、expected_priority、新 priority、唯一 request_id、by 与 reason。dry-run只读；在线 SQLite 事务比较当前版本与旧优先级，只改指定 reading_runs.priority 并同事务写 reader_priority 审计。重复请求幂等，异意图、旧版本、终态或降低优先级拒绝。它不构造 Reader/模型、不取得第二个 worker、不取消在途任务，不改原件、冻结配方、job/预算、模型 importance、C3 或采用；既有四分之一最老任务机会保留。

定量采用在最终checkout从原侧车复验当前需求定义SHA及完整契约；第二次实际调用按完整冻结样本包核验，异范围/原文/拟采用结果拒绝。历史审计及已应用精确重放保持。

站点观测的时间解析与顺序由 `knowledge.observation_time` 统一，容量标量/区间和单位由 `knowledge.site_quantity` 统一；`site_timeline` 只做不可变历史及当前投影，`project_review` 持有原件/C3/物理身份/基线核验与追加写入。`project_review_reader` 是既有 Reader 的只读适配器，不创建第二个正式库、日报或模型队列。正式写入时间在首次成功时生成，重放保留；接收时间只从实际台账派生，披露时间须有该版本原文定位。strict validate 同时检查单条结构与跨记录修订链，不能让手工 JSON 绕过目标存在、范围、完整字段束和具体所有者决定检查。

### 站点周期调度的运行边界（2026-10-11）

既有 `research_review` worker在原领取循环前调用 `SiteTracking.tick`；它只写同一SQLite中的 `site_tracking_*` 表，不取得第二个worker或发布器，不修改旧审核任务/重要性/次数。周期、输入签名、失败重试和去重均持久化；`research-review status` 输出规划水位与阻塞状态，完成采集/采用/发布计数保持未知，不能用任务规划数代替。坏输入和规划错误隔离于既有研究审核。状态投影按周期有索引查询最新记录；大量失败仅输出计数、摘要SHA及至多8条/每条200字符样例，完整错误保留私有run/attempt台账，避免空闲轮次持续输出全历史缺口。周期和来源语义规则唯一源见06，真实执行链尚未接通的部分明确保留。
