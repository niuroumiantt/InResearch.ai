# 模型执行与客户端边界

> CURRENT · 2026-10-07。用户采用：暂用 Claude CLI 推理，Spark 恢复后通过配置接入，型号可替换；终端可接入同一项目；一份材料默认一套当前有效阅读结果。

## 1. 推理与操作分别接入

2026-10-08：持续研究核验 worker 使用同一 `core_review` 角色，不硬编码 Codex 或 Spark 型号。每份核验尝试冻结实际配置、请求/响应摘要与模型返回身份；一次审阅后再以独立提示执行确定性抽样复核。并发受该角色 max_parallel 和发布背压共同限制。机器切换通过私有模型 JSON 并仅重启核验 worker，原件/Reader 当前版本/已审核及已采用条目保留；新上下文、新尝试另存，禁止把配置名称冒充实际模型返回值。

项目掌握对象、材料、问题、任务和采用规则。模型提供分类、阅读、抽取、翻译、综合等推理能力。确定性的哈希、状态计算、文件事务和写入校验由程序执行。能力已接入不代表对应业务流程已经实现或经过生产验收。

Claude Code、Codex CLI 等是操作客户端，分别记录 `executor` 与实际模型；客户端名称不能冒充模型名称。终端输入/输出仍经过项目用例和相同的数据校验。会话从 AGENTS/CURRENT 读取当前规则，聊天记忆不充当研究状态。现有 M4 `pack/record` 可交换相同输入包和结构化判定；完整统一任务 CLI/API 在后续阶段实现。

## 2. 配置与调用

版本化默认配置唯一入口为 `deploy/models.json`；本机可用 `INRESEARCH_MODEL_CONFIG` 指向同结构 JSON。配置通过角色引用模型档案；`research_default` 指向 `claude_sonnet`（Claude Sonnet 5），`core_review` 指向 `claude_opus`（Claude Opus 5.5），均使用本机已登录的 Claude CLI；`spark`（qwen3.8:27b）与 `spark_ocr`（qwen3-vl:8b）档案供 Spark 本机配置引用。分工按下文“按环节选模型”。型号、后端、地址、请求路由、上下文、输出预算、超时和并发上限均属于配置。密钥仅记录环境变量名称，值不入库。

`src/inresearch/adapters/models.py` 是公共推理接口。任务提示词、评分与证据语义校验由各业务调用者拥有。当前支持 Claude CLI、Codex CLI、Ollama 与兼容 chat-completions 的 gateway；Claude/HTTP 响应核对实际模型并覆盖模型自填的来源字段。Codex CLI 的身份边界见下文。请求路由名与实际模型名分开。接口失败不静默切换供应商或模型。

Claude CLI 在临时目录中以非交互模式运行，材料从标准输入传入；禁用工具、MCP、浏览器、项目指令与会话持久化。Reader 按 triage/read/synthesize 阶段传入 JSON Schema，由 CLI 以结构化结果返回；只有结果确实携带 `structured_output` 时，CLI 的 `stop_reason=tool_use` 才作为结构化输出完成接受。其余停止原因仍失败，模型身份照常核验。其他支持的后端使用各自 JSON 模式，由项目再次解析与校验。阅读引文还要逐字绑定原文；引用校验失败最多触发一次带明确反馈的重新生成；第二次仍不符的主张被剔除并留档，其余已核对的主张照常保存，不降低证据门槛（2026-09-27 起：此前整块阻断；b6b6、dd2d 首页侧栏文字抽取时混入正文，模型引用跨侧栏的句子，一条引文不符使整份文档失败）。认证与代理由 CLI 及运行环境负责，项目不复制 OAuth 凭据、不写死本机代理。`command` 可配置可执行文件的绝对路径；模型身份来自 CLI 的实际回答事件，并记录 `executor=claude-code`。用量统计可能包含 CLI 的辅助模型，不冒充阅读模型。这一推理适配器与终端操作客户端共享业务契约，但职责不同。

`text_json` 和 `vision_json` 是适配器接受的能力声明，须经目标模型的小样本验收后配置；声明本身不证明质量。OCR 必须显式配置 `ocr` 角色，视觉适配支持 Ollama、Claude CLI 与 Codex CLI。没有视觉能力的文本模型不能冒充读过图片。Claude CLI 看图时，页面图片以一条 stream-json 用户消息（图片块加提示文字）经标准输入传入，工具仍全部禁用，图片哈希记入 `_model.image_sha256`。

reader 各环节 schema 中 `object_ids`、`question_ids` 不是必填字段（2026-09-27 起）：它们本可为空数组，reader 把缺失当空数组；设为必填时，Sonnet 偶尔省略空的 `object_ids`，Claude CLI 按 `--json-schema` 内部重试 5 次后以 `is_error` 退出，整份文档被阻塞。正文字段（摘要、claims、引文等）仍为必填。M4 另两次 CLI 失败是 Sonnet 把 read 摘要写成整份文档概述（3678 字，上限 1200）并漏掉 `claims`；read 提示因此写明摘要只写本块、1200 字以内（约 3–6 句），且顶层必须返回 `chunk_sha256`、`summary`、`claims`（无内容时为 []）。

read 回复的字段顺序为 `chunk_sha256`、`claims`、ID、`summary`（2026-09-27 起）：模型按 schema 顺序填写，摘要在前时 Sonnet 把发现写成长段摘要（1346–2805 字，比块本身还长）、漏掉 claims，CLI 5 次内部重试都重复同样错误。提示同时要求先写 claims、每条发现连同原文引文放入 claims 而不是摘要，摘要只简述本块。受约束解码的 Ollama 同样先生成 claims。

Claude CLI 报「response exceeded the … output token maximum」时记 `model_cli_output_limit`，同一次调用内以 `--effort low` 重试一次，并在该块 `_model.effort` 记录（2026-09-27 起）。原因：Sonnet 5、Opus 5.5 为自适应思考，忽略 `MAX_THINKING_TOKENS`；遇到密集块时思考占满输出预算（一例 14,282/16,384），回答放不下。其余调用不带 `--effort`；重试仍失败则按临时错误走 reader 的普通重试。

Claude CLI 的非零退出或 `is_error`（过载、断线、进程卡死）记 `model_cli_failed`，超时记 `model_cli_timeout`；reader 把这两种按普通模型失败处理：保留错误码，走每任务 3 次、30/60/120 秒退避的重试，不再整份阻塞（2026-09-27 起：M4 深读 21 份时 4 份因此阻塞，已完成的块均无失败、引文均核对通过）。认证失败、CLI 未安装、模型身份无法核实仍直接阻塞，重试解决不了。

Ollama 文本任务把 reader 各环节（triage/read/synthesize）的 JSON Schema 直接放进请求的 `format`，由受约束解码保证输出符合结构；未给 schema 的调用（如 OCR）仍用 `format="json"`。2026-09-27 起：此前仅 `claude_cli` 使用 schema，Ollama 只用 JSON 模式，中文摘要里的 ASCII 引号会提前结束字符串，整块丢掉必填的 `claims`（df93 第 2 块），表现为 `model_output_invalid`。schema 不进入档案身份与 `reading_identity()`，已冻结配方不受影响；受约束解码只保证结构，不保证引文正确，引文仍按原文逐字校验。

Ollama 档案可选 `repeat_penalty`（1.0–2.0）与 `repeat_last_n`（1 至档案上下文，惩罚回看的最近 token 数，Ollama 默认 64），均仅 Ollama：qwen3-vl 在温度 0 下遇到重复表格行或重复标语会循环，被 Ollama 以 `token repeat limit reached` 中止或写满 `num_predict` 截断；重复块长于回看窗口时惩罚不起作用。当前只有 `spark_ocr` 设 1.1 / 256；M4 ocr-worker 对仍失败的页再以 1.3 / 512 做一次救援双读（2026-09-27 起），实际参数记入该页 `_model`。`spark_ocr` 输出上限为 8192 token、上下文 16384（2026-09-27 起，ea7d 第 7 页正文超过 4096）；M4 本机配置是副本，须同步修改。两者都会改变输出，所以设了才记入档案身份与每页 `_model`；reader 冻结配方只比较 `reading_identity()` 的固定字段，不因此失效。惩罚可能压掉合法的连续相同数值（如“0.0 0.0 0.0”），双读一致不能发现这类误差，须抽查原件。

Reader JSON 快照可用重复的 `--doc-id` 显式限定交付范围。限定导出只包含所选且已有完整覆盖报告的当前文档；未知 ID 或尚未完成的文档整体拒绝，不部分导出。限定导出不覆盖 catalog 全局的 mapping-proposals 派生文件。快照里的 Reader 总体状态仍反映整个队列，局部材料成功不冒充整批健康；发布端继续逐文档核验完整 coverage，并只接收 candidate。

一个进程中的共享客户端冻结配置，重启后读取修改。`max_parallel` 限制该客户端同时请求数；它不等于跨进程或跨项目的 Spark 全局调度。reader 旧 `READER_*` 环境和 CLI 参数在入口转换，优先级为 CLI > 旧环境 > 选定配置；新部署优先使用统一 JSON，迁移时核对旧覆盖项。

### Codex CLI 临时批次（2026-10-06 用户采用）

用户要求暂时通过 Codex CLI 打通本批全部材料与后续日报。Spark 继续独占原件、SQLite 队列、候选数据库与网站发布；M5 用已有 Codex CLI 登录提供仅绑定 loopback 的鉴权推理服务，SSH 反向转发到 Spark loopback。认证值只在机器私有配置中，既有发布令牌仍只在 Spark；不复制 OAuth 或数据库至 M5。

角色档案 `codex_reader` 请求 gpt-6.1-sol / medium（两个推理槽），`codex_review` 请求同模型 / high；`codex_ocr` 显式配置视觉能力。版本化默认 Claude 角色不变；本批机器 JSON 选择 Codex 角色。恢复 Spark 或更换模型均替换机器角色配置；unfinished 的冻结任务按 04 新建执行版本，已完成结果保留。不能静默混用模型。

本适配器用 `codex exec --model --json --output-schema --ephemeral`，隔离工作目录，禁用 shell、应用、浏览器与其他操作工具、规则加载和联网检索；原文以标准输入传入。任何实际工具活动拒绝；CLI 的非终止配置诊断不冒充工具调用。JSON Schema 对所有对象补 required 和 additionalProperties=false；本业务可选 ID 列表以空数组表达，原文引句仍须逐字校验。视觉页通过图片参数输入并记录图片 SHA。

Codex CLI 0.160.0 JSONL 不返回实际 provider 模型，因此 `_model.actual=null`，记录明确请求、executor=codex-cli、reasoning_effort 与 identity_source=explicit_cli_request_not_provider_reported。不伪造实际模型已核实；这一限制不放宽其他后端的实际身份核验。本角色读取只产候选，不自动 C3。

2026-10-09 中继容量：槽位占满仍给旧客户端返回 `model_relay_unavailable`，附加 `reason=relay_busy`；新客户端将其识别为 `model_relay_busy`，按 04 仅让当前任务退避。真实传输不可用和额度等待保持原分类，不用容量忙伪报全局网络故障；模型、配方及并发上限保持。

2026-10-06 故障修复：CLI 的网络断流、HTTP 408/5xx 与额度失败分别进入连接或额度等待，不消耗文档尝试。诊断只存退出码、HTTP 状态、耗时、分类和错误摘要哈希，不存原文、令牌或原始 stderr；启动警告不能遮住末尾错误。无法分类的失败仍按有限重试处理，不能宣称历史错误原因已经还原。

Codex 图片页常规双读失败后，可显式将 `gap_ocr` 角色选为 `codex_ocr_rescue`（同一请求型号、high、vision_json）。只重渲染该页至 3200 像素，补读至多三次；任意两次均满足既有可读、空白和数字一致规则才接受。常规失败与全部补读原文/模型/图片哈希写入执行版本的 `ocr-attempts/`。仍不一致或不可读默认保持阻塞。点名 Codex 批次可显式设置 `READER_CODEX_OCR_ALLOW_GAPS=1`，在补读用尽后登记 `vision_ocr_gap`：正文为空，未读页/原因/各次原文与模型保持可追溯；不伪造 M4/Claude 来源。沿用既有每份 max(1, 总页数÷20) 的缺页上限，超过仍阻塞，候选报告必须警告，不能宣称缺页已读或自动取得 C3。视觉角色与实际图像输入逐页记录；冻结的正文模型配方不改。

### 正文合批调用（2026-10-07）

`read_batch` 沿用同一阅读角色、型号与 effort，每次输入 2–4 个相邻短块，受冻结配方的总字符预算约束；返回逐块的 index/hash、claims、IDs 与 summary。每个块只使用自己的原文与允许 ID；公共 transport 仍隔离材料中的指令。合批产物逐块继承真实调用 provenance，错引纠正记录其实际单块调用；摘要以 1–3 短句为目标，主张保持关键范围、日期、单位、条件和反证，不以节省输出为由漏读正文。

批量错误可回退单块，认证/完整性错误保持失败；额度或连接等待不继续放大请求。机器并发从 2 调至 4 须同时核对 Reader workers、客户端 `max_parallel` 与 M5 relay `--parallel`，先用真实样本核对耗时、来源绑定和质量；不据调用次数推定报告完成数或承诺线性提速。型号保持本批 gpt-6.1-sol/medium；仅增加执行槽不触发旧配方重读。

### 按环节选模型（2026-09-26 用户采用，未被本批覆盖的环节）

量大、判断简单的环节用本地模型，量小、要引用数字和证据的环节用 Claude，最强型号只留给决定质量的少数材料。不做同型号对比即切换；质量靠下述分工与 04 的覆盖、引文和数字检查保证。

| 环节 | 模型 | 说明 |
|---|---|---|
| L0 文件名分档 | 不用模型 | 规则判定 |
| L1 大批粗筛（Spark） | 本地 qwen3 系列 | 只作排序与粗分；本地模型分数偏宽、有锚定，不单独决定提升 |
| L1 打分与复核（M4，`research_default`） | Claude Sonnet 5 | 含 5–7 分边界与 ≥7 分待提升的复核 |
| OCR | 本地 `spark_ocr`（qwen3-vl:8b） | 只对优先级高的扫描件；不为无关扫描件做 OCR |
| OCR 缺页补读（M4，`gap_ocr`） | Claude Sonnet 5（`claude_sonnet_vision`） | 只读 qwen 救援后仍失败的显式缺页；同样双读一致才采用，否则仍为缺页 |
| L2 全文深读与事实抽取（终端） | Claude Sonnet 5 | Claude Code 会话以 Sonnet 5 执行 pack/record，`--model` 如实记录 |
| L2 核心材料与 C3 前审阅（`core_review`） | Claude Opus 5.5 | 9 分白皮书、复杂表格、数据相互矛盾或采用前审阅 |
| 长尾全文候选（Spark reader） | 本地 qwen3.8:27b | 只作候选阅读，不直接采用 |
| 翻译 | 本地 qwen3.8:27b-translate | 不变 |

更换默认型号只影响新任务；已冻结配方的 reader 任务和已有 L1 结果不重读、不改写。

## 3. 一份材料的一套有效结果

同一内容身份只维护一套当前有效阅读结果，由 reader catalog 的当前指针选择。reader current 与 deep-read current 共用 workflow.reading_results，不构建推理客户端；L2 事实处理回执不能成为第二套全文结果。尝试日志、局部检查点和被引用的历史依据可保留；失败重试不增加前台的阅读份数。

更换默认模型只影响新建任务，已完成材料不自动重读或改变结果。已创建任务使用冻结的推理身份、提示配方和上下文；不得中途混用新模型。现有 reader 在新配置与旧任务不符时阻塞，恢复原配置后可继续；自动选择旧配置仍未实现，已完成材料通过显式 reread 新建独立版本。未完成首次阅读可按 04 的 restart-unfinished 显式迁移；旧尝试保持，执行入口不是完成结果指针。

显式重读先产出待替换版本，经 04 §8 的覆盖与产物机检及审阅确认后，用旧版本基线和报告 SHA 原子更新当前指针；失败时旧结果继续有效。旧证据/回答/报告引用具体版本，不随当前指针变化。模型更大或结果更新不自动授予 C3 采用资格。单结果是使用规则，不能成为删除原文与已引用依据的理由。

## 4. 验收

代码契约测试覆盖配置切换、旧配方兼容、模型身份、结构化输出、失败恢复及不重复阅读。生产能力另用代表性材料验证覆盖、引文、数字与边界、耗时和失败原因；第二型号未实测时不能声称已经兼容。常驻服务是否生效以实际源码、配置与运行记录为准。

`python3 manage.py models --probe` 通过所选配置发送一条无研究材料的真实 JSON 请求，核对结构和实际模型；配置校验或交互式 CLI 登录成功不能代替这项检查。CLI 参数依据本机 `claude --help` 及 [官方非交互文档](https://code.claude.com/docs/en/headless)。

缺页补读（2026-10-07 补充，原双读规则保持）：`python3 -m inresearch.adapters.gap_ocr --data-root <数据根> --doc-id <id>` 同时发现 `offload/m4/results` 的 `m4_vision_ocr_gap` 和当前 revision 抽取缓存的 `vision_ocr_gap`。先核对原件 SHA，逐页渲染，由配置的 `gap_ocr` 角色独立读取；前两次不一致可再读一次，任意两次通过可读、空白一致、两遍非空页都有文字、空白页两遍皆空、数字一致才接收。全部尝试原文、两遍模型与图片哈希按唯一时间路径保存，失败页继续保留缺页。Codex 补页记 `offload_vision_ocr_double_pass`，不冒充 M4 或 Claude；旧 Claude 补页 method 仍兼容。补读提示略去纯装饰背景，不补造原件不存在或被遮挡的文字。

小字图表可按原件内嵌图片分区双读。接收包 `--receive <页结果.json>`（可重复，一次限一个 doc）须携带当前 `recovery_revision_id`；原始 RGB/灰度内嵌 PNG 可用临时 PDF 包装经 Poppler 放大（1800–6400 像素）；只放大原始像素，不生成新细节，可按 90 度整倍数旋转以读取竖排标签，保存原图与输入图哈希、尺寸和方向，接收端复现转换。每张内嵌图片的全部独立读、成对序号、模型与图片哈希保存到 `recovery_evidence`。接收端从哈希一致的 PDF 重新抽取原生文字及所有内嵌图片，核对图片全集、字节哈希、两次不同读取、既有双读规则和完整正文拼接。图像原件有文字但仍不可读时整页保持缺页；黑色遮挡与截边不推断。完整内嵌图片可能超出页面视窗，正文须显式标注 `source_image_scope`，它是原件内嵌范围的候选，不声称这些文字在页面视窗内可见。

接收仅替换仍在 extract 阶段、同内容/页号/当前 revision 的显式缺页，不改原件、成功页、完成产物或 catalog。先归档旧缓存、旧 inbox 和新读原文，再原子替换该页缓存；整份成功补页批次安装完才写 inbox 通知。运行中的 Reader 通过既有 `requeue_offloaded` 受控接口重新排队，直接复用其余缓存；缓存已安装但通知中断时可幂等重收。直接渲染补救也保存全部尝试；M4 旧补页路径保留定向失效缓存的恢复逻辑。未通过仍为缺页，报告/缺页上限/C3 门槛保持原规则。

占位输出拒收（2026-09-28 起）：M4 深读 30 份中，Sonnet 在 11 份综合与 6 个块摘要里写了“测试摘要”“测试要点一”一类占位文字（6484 的是“测试摘要，用于诊断key_points参数解析问题。”，紧随一次 key_points 缺失的结构化输出失败），结构合法，未被拦下；Opus 读的 b3ff 无此问题，主张与引文均无占位。reader 现对块摘要、综合摘要与要点拒收占位文字（`model_output_placeholder`），按普通模型输出错误退避重试。已完成的受影响报告不原地修改，经 `reader reread` 重读、审阅后切换。
