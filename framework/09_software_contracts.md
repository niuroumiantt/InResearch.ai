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

全球园区任务跟踪（2026-10-12）：`workflow.research_tasks` 是协调工作包的唯一用例，`framework/research_task_plan.json` 提供新建任务及尚未分配的区域包，运行协调台账在 `data/raw/research-tasks/ledger.json`，不能经静态URL下载。`GET /api/research-tasks` 匿名读取白名单任务范围/状态与既有地图口径，登录后按角色读取协调字段；`POST` 要求 `X-Requested-With: research-tasks`、操作者、预期版本与唯一操作身份。member/admin可创建和分配，intern只能更新已分给自己的状态、交付指针及备注。版本比较、稳定锁、原子提交与同键重放防止并发覆盖，审计保留旧值与操作者。协调状态仅到“已交付”，不授予资料接收、研究采用或地图发布资格；这些回执继续由原流程独立证明。协调用例不采集或上传原件；匿名附件由独立的任务上传接口接收，不编造负责人、机器、截止时间或全球覆盖。

回执进 Git 载体（2026-09-29）：`knowledge/deliveries.py` 是运行库交付指针进入 Git 载体的唯一用例——`import_assignments(root, assignments_path)` 读运行库导出的 `data/assignments.json`，把带 `delivery` 的记录写成 `data/event_cards.json` 事件卡（目标行须存在、指针须是公网 URL 或仓库内相对路径、同一指针幂等），随后由 `knowledge/targets.py` 重建目标表；`check(root)` 校验卡片。只在作者 checkout 由 CLI `deliveries import / check` 调用，HTTP 不暴露；网站与 Spark 不回写 Git。

HTTP 访问边界（2026-10-12 用户纠正替代仅首页公开规则）：首页 `/`、`/index.html` 与任务页 `/tasks.html` 及必需资源/登录机制公开。首页数据API仅接受独占 `overview=1` 的有界投影；任务API匿名只读脱敏投影，POST仍认证。真实样例从私有运行目录只读，匿名只取得公开元数据及显式public产物；文件由ID白名单、逐级无符号链接打开、大小与SHA验证后交付，不能用任意path下载。未装/损坏不造成功状态，阶段由实际产物及真实收据决定。其他页面、完整API、研究JSON/文档/图册/模型下载均先经服务端登录门禁，GET与HEAD同查归一化路径；参数、编码、反斜线、别名与静态源路径不能绕过。admin/member/intern保持既有权限。私有、身份相关响应和拒绝响应均 `private, no-store` / `Vary: Cookie`；现有机器bearer接收保持独立凭据检查，匿名页面白名单不授予写权。

2026-10-15 替代任务上传发布边界：`POST /api/task-uploads` 仍只匿名接收待审原件，随机回执只读本份状态与反馈；所有响应 `private, no-store`，不提供公开列表或原件下载。指定 admin 的 `approve_and_analyze`／`start_analysis` 产生原单件分析权限；对已批准且精确点名的原件，`start_full_analysis` 按下段新建全表尝试。各动作绑定 SHA、状态版本和操作 UUID，旧 `approve` 不自动启动分析。默认抽样调用已授权的私有 loopback Codex CLI 中继，全表尝试只使用独立 campus_review 角色；审核结果通过机器 bearer 提交，但机器不能自行批准，网站对每条普通来源候选复验原生 XLSX 单元格、身份、单位、既有值及真实批准记录。持久发布器检查批准原件字节及接收/审批时钟，追加后行业读者投影须可查；重放不得重复写入或反馈。后台保留内部发布报告，回执仍只授权本份查询及批次恢复，任务页移除个人回执区；执行上下文统一为当前工作包、数据库、已完成成果及最新有效共同反馈，旧个人修改任务不再进入单份或联合模型。该自动通道不写 C3 研究结论或模型参数。

2026-10-17 全表尝试替代：`materials.native_review_contract` 从批准 XLSX 确定性构建园区／未分配包、原生单元格和无损长格片段清单；`materials.full_review_worker` 由同一 intake 调度，独立使用 loopback Ollama 的 `campus_review`、单并发和有界轮次。`start_full_analysis` 只重开精确原件的新尝试，不修改旧批准身份、旧报告或原件；尝试身份进入模型执行、断点、proposal 和回写校验，禁止复用旧抽样结果冒充新覆盖。全部窗口完成后另用一个模型调用综合所有窗口摘要、完整原问题和候选及候选原文，裁决跨窗口身份、分期、口径、时点与冲突。按.33，最终响应只返回1至600字符且非空白的summary、精确覆盖全部原问题0起始索引的reviewed_finding_ids、仅新增跨窗问题的完整new_findings及原候选索引accept_candidates；不改写或新增候选事实。原阅读问题逐字保留，再追加新增问题，不能删减原问题或让模型重复抄写整份清单；索引可乱序，缺漏、重复、越界或布尔值均拒绝。综合完整输入和4096输出门槛保持，输入超预算或输出截断均明确受阻，不裁剪后宣称园区完成；最终裁决的请求摘要、实际模型及候选集合摘要随回执保存。27B受约束解码按本窗口实际可见原生单元格限定P0/P1/P2、字段、单位、名称、地点与定位枚举；地点值与定位须原样选同一个单格选项，不能拼接省市区或多个定位。枚举不能替代网站原值和身份复验。窗口读取与最终综合均带同一原件文件名、SHA、布局及用途；v5明确为历史对照，不因版本日期覆盖现有事实。阅读窗口配方同时冻结系统提示与解码schema摘要，阅读规则变更不得混用已成功窗口；最终综合问题也限定原生定位及P0/P1/P2。 问题定位须由工作表与该表实际可见单元格的关联分支约束，不能分别枚举sheet和cell后任意组合；最终综合沿同一定位配对规则。每个重复身份anchor携带同工作表同列的原生column_headers，表头只解释字段、不作待填数据格，禁止借用其他表同列含义；这些重复上下文不扩大原生覆盖或候选值定位。窗口未见某字段仅表示本窗待核，不等于整包缺失；已批准原文中的机柜数、单柜功率、容量口径与省市区列不可推算或混填成发布值。语义无效响应保留完整请求、原始结果与错误，仅在有界预算内重试未成功窗，失败不得推进游标或覆盖。旧反馈仍留历史，当前状态按新尝试与服务器确认的完成包计算。逐包提交沿用机器认证及持久发布，服务端重新读取同 SHA 原件、复算包／片段与原生定位、核现行任务／地域／原值／单位／对象和来源 CAS，保存幂等回执；部分写入恢复不能重复推理、发布或计数。原文覆盖和业务可采用性分开，未分配包也须完成。全部包有有效回执才形成全表原生文本完成；图片、外链、公式执行及事实核验不在此覆盖声明内。先验真实一个园区包的回执才恢复余包；GPU 利用率≥30%或温度≥80°C仅延后本任务，不更改其他服务。默认单件／联合抽样合同及未选材料行为保持。

2026-10-17 新包阅读配方（.35）：`packed_reading.select_recipe`在attempt/package级检查所有task-SHA目录；任何既有plan/progress/chunk/proposal或综合／派发审计均保留legacy。仅无旧产物的包写`reading-recipe.json`，绑定`campus-packed-reading-v1`、原件SHA、manifest SHA及package ID；任务更新不能使已开始包升级。新`chunks(..., packed=True)`最多64片段，原生分片、原序、完整上下文、identity与同列header均不变。默认chunks和generate继续旧字节门槛，原成功窗口／final／prepared proposal不因新配方改写或重读。

新`generate_campus_reading`只接受`stage=native_campus_reading`与该reading_recipe，保持固定本机27B、32768／4096／1024、think:false、truncate:false、shift:false，使用完整模板与同GGUF实际token证明。`ReadingBudgetExceeded`须附完整请求及真实计量证明，且没有派发生成；只有此类型可按原片段顺序中点二分，分拆历史逐次复算，不能任意重排或覆盖旧窗口。单片仍超限受阻。`before_dispatch(body,proof)`在最终资源／模型／请求核验后、completion之前持久落盘；成功完整raw response及已验证result保存后才推进游标，落盘响应可精确恢复而不再次生成。未知派发结果或`CompletionUnverified`留完整审计，输出截断不触发新包自动分拆／重放；删除status不能解除。正常形状／原生定位错误仍保存每份原响应并沿原三份上限处理。每轮最多一次内容生成，GPU热忙只延后本任务；预算分词和拆窗不计已读覆盖。最终综合与服务器发布校验不减。

2026-10-17 最终综合独立配方（.33）：最终instruction与schema独立于已成功阅读窗口，`final_recipe.version=campus-adjudication-delta-v1`，同对象完整记录`system_sha256/schema_sha256/request_sha256/reading_inventory_sha256/findings_sha256/candidates_sha256`，外层另存`final_recipe_sha256`；reading inventory摘要覆盖按序的完整窗口结果。成功的adjudication与未绑定completion审计都保存此配方。恢复必须复算全部摘要，旧配方或无配方结果不能作为当前final缓存；仅修改最终指令／schema不重读原窗口。最终输入的原问题数组、窗口摘要、候选、候选原文及来源／任务／身份上下文保持完整；只替代最终重复输出要求，不改变原生覆盖、服务器发布或C3合同。reviewed_finding_ids须是全部原问题索引的唯一全集，new_findings沿同一原生定位校验且不以数组条数截短；worker保留原问题原文并追加新增问题后再提交，既有报告接收上限保持。畸形或旧形状响应为`campus_adjudication_delta_shape_invalid`，索引集合不完整为`campus_adjudication_findings_incomplete`；旧配方、未绑定结果和输出截断仍各按原拒绝路径保留。

2026-10-17 最终综合预算替代：`JsonModelClient.generate_campus_adjudication(system, user, json_schema=...)` 使用同模型精确token门禁；.35仅向上述未开始包的专用阅读入口扩展。默认 `generate` 及legacy阅读窗口保持原UTF8字节预算与冻结配方。综合仍保留全部输入，使用 `campus_review` 的32768上下文、4096输出和1024预留；完整渲染的实际输入token数加输出与预留不得超过上下文。不得用平均字数比、另一个tokenizer、较大上下文、裁剪摘要或额外生成调用绕过预算。

该专用通道仅接受已核Ollama 0.33.3与本机 `qwen3.8:27b`。先过现有GPU门槛，以同一完整system/user/schema请求 `_debug_render_only:true`，获取 `_debug_info.rendered_template`；无直接token计数，model回显不能单独证明权重身份。模型manifest/config实际摘要、模型层digest/size和文件属性保持绑定；这不等于每包重新计算整个权重文件哈希。然后选择固定命令、已复验的本机ollama服务身份、同GGUF、loopback端口、单槽和命令／props相符的现役tokenizer，仅在完整 `/tokenize` 操作前后核PID／启动时钟／命令／props与模型身份一致。合法16K或32K实例均可对同一完整文本分词，observed context不证明生成上下文；不读取跨UID受保护的exe链接或升权。分词显式 `add_special:false`、`parse_special:true`，以完整整数数组计数，不用通用chatml模板替代Ollama qwen3.8 renderer。

2026-10-17 服务身份命名空间补充（.32）：宿主身份可见时继续要求runner的四种UID均为本机ollama账号UID。受限调用方仅将自身UID单行恒等映射、长度1且ollama宿主UID不可表示时，才能进入namespace-masked校验；四种可见UID必须全部等于系统实际overflow值，不能直接把65534视为ollama。该分支还须由固定root system manager确认`ollama.service`已loaded/active/running、User/Group=ollama、Delegate=no、DynamicUser=no、PrivateUsers=no，runner为固定MainPID的直属子进程且父子同属精确`/system.slice/ollama.service`。父服务argv须精确为`/usr/local/bin/ollama serve`；每次身份采集按system manager快照A、父子进程快照A、父子进程快照B、system manager快照B核对一致，父子命令摘要、启动时钟、UID映射及调用方映射完整绑定，还须把masked runner快照的PID／启动时钟／命令摘要与外层最初选择该模型和端口的原始命令及最终stat逐项相等，分词前后继续复验。任何缺失／变化／异常均受阻。proof v2的tokenizer_binding.uid_binding.method记录direct_process_uid或system_service_parent_in_user_namespace，不关闭PrivateTmp、不读取受保护exe链接或升权；该补充仅证明分词服务身份，不能替代模型／完整输入核验或生成绑定。

精确计量证据 `ollama-campus-token-v2` 绑定本次system/user/schema、完整请求与渲染摘要、token数组摘要／计数／预算及共同 `model_binding`；`tokenizer_binding`只记录分词操作的实例，不作为跨请求租约。实际独立生成前后核同Ollama版本、manifest/config／模型层／renderer及文件身份，复核完整请求摘要，固定32768上下文、4096输出、`think:false`、`truncate:false`、`shift:false`；允许同模型合法PID变化。只有真实生成及结果校验通过后才记录 `generation_binding` 的模型绑定摘要、请求摘要、actual_model、前后模型核验标记与响应摘要，不声明生成PID；measure只渲染／分词，不能带生成凭据或授覆盖。schema先严格JSON复制，调用方后改内容不能改变已计量请求。此条替代.30要求分词、生成前后共用runner的限制；旧原件、阅读提示/schema和成功缓存不重读。

2026-10-17 分词期竞争恢复：只有生成请求尚未提交、模型binding仍一致的tokenizer缺失或在 `/tokenize` 操作中明确轮换，adapter才产生 `campus_token_runner_contention`。分词传输失败须再次核实例确已消失／变化才可取得此资格，未知网络／JSON错误不放行；合法请求间PID变化不需要重试。worker仅对此专用错误沿原连续失败小于3次、300秒退避，每次重做GPU、完整渲染、模型与分词预算，第三次要求运维核查。原两种runner错误码不直接取得资格；版本／权重／输入／token超限及其它验证失败保持受阻。completion提交后的传输结果未知或模型绑定／输出检查失败不自动再次生成；已返回但未绑定的请求、响应、proof及摘要保存为私有 `unverified-adjudication.json`，即使遥测status丢失也阻止自动重放，不形成采用或覆盖。此机制不增加共享Ollama全局锁，不改其他调用或成功阅读窗口。

全表归档适配在核准原件SHA后，仅将无扩展名`original`临时复制为`source.xlsx`交给现有原生解析器；原件不改写，扩展名及格式限制不放宽。直传大小按接收端实际JSON编码后的HTTP字节计算，超过6000字节沿既有3000原字节分片／摘要提交，避免中文转义后越过网关限额。规划前的来源或配置错误也向当前已开放未完成包上报0/0受阻遥测，不形成窗口或格覆盖。

全表操作沿用指定负责人认证的 `POST /api/materials/review` 与 `X-Requested-With: material-intake`。`start_full_analysis` 的精确字段是 `id/sha256/expected_revision/operation_id/action/layout_id/reason/pilot_package_id`；同操作重放必须原样，批准原件及现行工作包须重新核对。`continue_full_analysis` 的精确字段是 `id/sha256/expected_revision/operation_id/action/attempt_id/reason`，仅在同尝试首包已取得服务器报告并处于 `pilot_completed` 时开放余包；实际网站读者回执须先核实并记录继续原因，不用客户端自报完成替代服务器状态。默认路径不自动重开已有报告。窗口遥测沿用机器认证的 `POST /api/intake-worker/analysis-progress`，精确绑定 `id/sha256/attempt_id/package_id/window_completed/window_total/state`，可附有界 `reason`；只接受 reading/waiting/blocked 及当前已开放包，旧报告不阻止新尝试进度显示。包完成数与已覆盖格数只能从服务端有效回执推导，旧抽样进度不能覆盖全表尝试。

布局白名单由 `materials.native_review_layouts` 拥有，材料不能自定义解析规则。v5历史原件使用单独登记的mainland-register-v5严格布局，按13张表及“信息有效期”表头核对，完整覆盖原生内容；因无对象身份裁定表，不自动新建园区，已有园区仍守当前身份、原值与冲突门槛。表名／表头不符或版本不明时拒绝猜测布局；重复园区ID的行保留到未分配内容，不能错误串联。原生园区关系与计数资格仅决定可否提交新的普通来源身份；分期／楼栋／组合、列有父对象或待核计数不能自动提升成独立物理园区。来源自报已核验仍是未经外部核实的来源声明；没有新园区资格的包继续审阅并可按既有身份规则补充已登记园区，不跳过覆盖。

2026-10-16 同批联合审阅：`materials.batch_review` 维护私有批次清单。匿名 `POST /api/task-uploads/batch-status` 用私有批次凭据找回失响应原件的回执；`POST /api/task-uploads/batch` 逐一验证 `{id,receipt}` 后封存实际收到的成员，失败文件另列，封存后拒绝新增成员；批次摘要仅投影数量，完整成员编号仅负责人可见。`POST /api/materials/review-batch` 仍要求指定admin、同源请求头、唯一operation_id与每份id/SHA/expected_revision，同当前工作包的精确清单全部通过后才开放worker领取。联合审阅共用任务／台账上下文，输出逐件绑定文件身份、SHA与原生定位，跨文件关系验证双侧定位。私有分片上传及 `/api/intake-worker/analysis-batch-commit` 不放宽WAF或机器权限；提交前在任务锁内复验所有原件与冻结上下文，持久checkpoint用于部分回写恢复，不能重复推理或发布。外部上下文变化仍拒绝，坏定位、未批准成员、异工作包和抽样候选均不能取得上线权。旧单件入口及历史结果保持可追溯。

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

### 完整JSON与来源上下文的内存边界（2026-10-17，.34）

`storage.json_stream`按有界输入块读取完整JSON，避免同时保留文件大小的Unicode输入串；跨块字符串、数值与容器仍完整还原，保留调用方重复键／非有限值等严格解析规则，拒绝尾随和畸形内容。返回值仍是完整文档，单个长值及对象树仍占内存，不能宣称总内存恒定或以跳过记录降低峰值。规范JSON摘要和原子写入按既有规范字节流逐块计算／落盘，与原完整序列化SHA逐字节等价；不得改变CAS、重放、回执身份或来源历史。

来源发布合并只去除随后还会完整复制的重复账本副本；共享旧records的阶段只读，合并结果必须与输入分离，校验失败不得修改原状态或部分提交。任务审核的`site_context`只缓存小型`version/sites`投影和完整来源状态的规范SHA，不保留完整objects／records树，也不能用小投影SHA替代全状态CAS。缓存按解析后根目录区分，最多4个根；同一进程单一构建者串行冷读，以实际文件路径、设备、inode、大小、mtime_ns及ctime_ns判失效，读取前后身份变化必须重试且有界失败。返回的小投影仍防御性复制；任何对象／记录等非园区变化都须改变完整SHA并使旧任务上下文失效，不能靠缓存跳过发布时锁内复验。

JSON HTTP响应逐块编码，超过1 MiB的缓冲溢出到既有私有logs持久磁盘目录，不用容器内存型`/tmp`承接大型响应。小型JSON及health响应不解析或创建运行时logs目录；只有实际缓冲溢出时才解析并准备该目录。gzip按请求协商，q=0不压缩；编码／压缩全部成功后才发送状态和精确Content-Length，GET逐块发送，HEAD保留同一表示的长度和编码头而不发正文。正常结束、断连或异常均关闭临时缓冲；磁盘不可用不得降级为无界内存缓冲或把半份JSON报为成功。部署时核实际logs卷而非仅看路径名称，保持原认证、公开投影和响应语义。

无来源notes占位的唯一例外由01口径手册定义；其他原值冲突、信息时钟、唯一身份、原件／原生定位和CAS均保持。内存修复不改变27B阅读／最终配方、成功缓存、32768／4096预算或一次一调用规则。验收须比较完整解析／规范SHA、不可变输入、缓存失效与并发冷读、gzip／HEAD／Content-Length及异常清理，并在实际大库和生产业务路径记录RSS／容器内存峰值、OOM与重启变化；源码测试、health成功或短期未重启不能证明OOM已经修复。

### 2026-10-11：具名阅读调度

具名阅读顺序可用 `reader prioritize` 显式提高：绑定 doc_id、当前 revision_id、expected_priority、新 priority、唯一 request_id、by 与 reason。dry-run只读；在线 SQLite 事务比较当前版本与旧优先级，只改指定 reading_runs.priority 并同事务写 reader_priority 审计。重复请求幂等，异意图、旧版本、终态或降低优先级拒绝。它不构造 Reader/模型、不取得第二个 worker、不取消在途任务，不改原件、冻结配方、job/预算、模型 importance、C3 或采用；既有四分之一最老任务机会保留。

定量采用在最终checkout从原侧车复验当前需求定义SHA及完整契约；第二次实际调用按完整冻结样本包核验，异范围/原文/拟采用结果拒绝。历史审计及已应用精确重放保持。

站点观测的时间解析与顺序由 `knowledge.observation_time` 统一，容量标量/区间和单位由 `knowledge.site_quantity` 统一；`site_timeline` 只做不可变历史及当前投影，`project_review` 持有原件/C3/物理身份/基线核验与追加写入。`project_review_reader` 是既有 Reader 的只读适配器，不创建第二个正式库、日报或模型队列。正式写入时间在首次成功时生成，重放保留；接收时间只从实际台账派生，披露时间须有该版本原文定位。strict validate 同时检查单条结构与跨记录修订链，不能让手工 JSON 绕过目标存在、范围、完整字段束和具体所有者决定检查。

### 站点周期调度的运行边界（2026-10-11）

既有 `research_review` worker在原领取循环前调用 `SiteTracking.tick`；它只写同一SQLite中的 `site_tracking_*` 表，不取得第二个worker或发布器，不修改旧审核任务/重要性/次数。周期、输入签名、失败重试和去重均持久化；`research-review status` 输出规划水位与阻塞状态，完成采集/采用/发布计数保持未知，不能用任务规划数代替。坏输入和规划错误隔离于既有研究审核。状态投影按周期有索引查询最新记录；大量失败仅输出计数、摘要SHA及至多8条/每条200字符样例，完整错误保留私有run/attempt台账，避免空闲轮次持续输出全历史缺口。周期和来源语义规则唯一源见06，真实执行链尚未接通的部分明确保留。
