# 09 软件职责与写入契约

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

workflow.supply 持有需求/任务计划的唯一用例，HTTP 负责权限与参数，supply.js 只消费服务端视图。能力目录随版本发布，运行台账复用 private data/raw 存储边界；台账读改写锁、expected_revision、UUID 回执共同防止覆盖和重复。交付、验收及正式采用尚未接入，前端不得模拟服务端完成状态。具体业务契约唯一见 06。
