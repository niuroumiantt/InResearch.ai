# 模型执行与客户端边界

> CURRENT · 2026-09-13。用户采用：暂用 Claude CLI 推理，Spark 恢复后通过配置接入，型号可替换；终端可接入同一项目；一份材料默认一套当前有效阅读结果。

## 1. 推理与操作分别接入

项目掌握对象、材料、问题、任务和采用规则。模型提供分类、阅读、抽取、翻译、综合等推理能力。确定性的哈希、状态计算、文件事务和写入校验由程序执行。能力已接入不代表对应业务流程已经实现或经过生产验收。

Claude Code、Codex CLI 等是操作客户端，分别记录 `executor` 与实际模型；客户端名称不能冒充模型名称。终端输入/输出仍经过项目用例和相同的数据校验。会话从 AGENTS/CURRENT 读取当前规则，聊天记忆不充当研究状态。现有 M4 `pack/record` 可交换相同输入包和结构化判定；完整统一任务 CLI/API 在后续阶段实现。

## 2. 配置与调用

版本化默认配置唯一入口为 `deploy/models.json`；本机可用 `INRESEARCH_MODEL_CONFIG` 指向同结构 JSON。配置通过角色引用模型档案；`research_default` 指向 `claude_sonnet`（Claude Sonnet 5），`core_review` 指向 `claude_opus`（Claude Opus 5.5），均使用本机已登录的 Claude CLI；`spark`（qwen3.8:27b）与 `spark_ocr`（qwen3-vl:8b）档案供 Spark 本机配置引用。分工按下文“按环节选模型”。型号、后端、地址、请求路由、上下文、输出预算、超时和并发上限均属于配置。密钥仅记录环境变量名称，值不入库。

`src/inresearch/adapters/models.py` 是公共推理接口。任务提示词、评分与证据语义校验由各业务调用者拥有。当前支持 Claude CLI、Ollama 与兼容 chat-completions 的 gateway；每次响应核对实际模型并覆盖模型自填的来源字段。请求路由名与实际模型名分开。接口失败不静默切换供应商或模型。

Claude CLI 在临时目录中以非交互模式运行，材料从标准输入传入；禁用工具、MCP、浏览器、项目指令与会话持久化。Reader 按 triage/read/synthesize 阶段传入 JSON Schema，由 CLI 以结构化结果返回；只有结果确实携带 `structured_output` 时，CLI 的 `stop_reason=tool_use` 才作为结构化输出完成接受。其余停止原因仍失败，模型身份照常核验。其他支持的后端使用各自 JSON 模式，由项目再次解析与校验。阅读引文还要逐字绑定原文；引用校验失败最多触发一次带明确反馈的重新生成，第二次仍失败则阻断，不降低证据门槛。认证与代理由 CLI 及运行环境负责，项目不复制 OAuth 凭据、不写死本机代理。`command` 可配置可执行文件的绝对路径；模型身份来自 CLI 的实际回答事件，并记录 `executor=claude-code`。用量统计可能包含 CLI 的辅助模型，不冒充阅读模型。这一推理适配器与终端操作客户端共享业务契约，但职责不同。

`text_json` 和 `vision_json` 是适配器接受的能力声明，须经目标模型的小样本验收后配置；声明本身不证明质量。OCR 必须显式配置 `ocr` 角色，当前视觉适配支持 Ollama。没有视觉能力的文本模型不能冒充读过图片。

Ollama 文本任务把 reader 各环节（triage/read/synthesize）的 JSON Schema 直接放进请求的 `format`，由受约束解码保证输出符合结构；未给 schema 的调用（如 OCR）仍用 `format="json"`。2026-09-27 起：此前仅 `claude_cli` 使用 schema，Ollama 只用 JSON 模式，中文摘要里的 ASCII 引号会提前结束字符串，整块丢掉必填的 `claims`（df93 第 2 块），表现为 `model_output_invalid`。schema 不进入档案身份与 `reading_identity()`，已冻结配方不受影响；受约束解码只保证结构，不保证引文正确，引文仍按原文逐字校验。

Ollama 档案可选 `repeat_penalty`（1.0–2.0）与 `repeat_last_n`（1 至档案上下文，惩罚回看的最近 token 数，Ollama 默认 64），均仅 Ollama：qwen3-vl 在温度 0 下遇到重复表格行或重复标语会循环，被 Ollama 以 `token repeat limit reached` 中止或写满 `num_predict` 截断；重复块长于回看窗口时惩罚不起作用。当前只有 `spark_ocr` 设 1.1 / 256；M4 ocr-worker 对仍失败的页再以 1.3 / 512 做一次救援双读（2026-09-27 起），实际参数记入该页 `_model`。`spark_ocr` 输出上限为 8192 token、上下文 16384（2026-09-27 起，ea7d 第 7 页正文超过 4096）；M4 本机配置是副本，须同步修改。两者都会改变输出，所以设了才记入档案身份与每页 `_model`；reader 冻结配方只比较 `reading_identity()` 的固定字段，不因此失效。惩罚可能压掉合法的连续相同数值（如“0.0 0.0 0.0”），双读一致不能发现这类误差，须抽查原件。

Reader JSON 快照可用重复的 `--doc-id` 显式限定交付范围。限定导出只包含所选且已有完整覆盖报告的当前文档；未知 ID 或尚未完成的文档整体拒绝，不部分导出。限定导出不覆盖 catalog 全局的 mapping-proposals 派生文件。快照里的 Reader 总体状态仍反映整个队列，局部材料成功不冒充整批健康；发布端继续逐文档核验完整 coverage，并只接收 candidate。

一个进程中的共享客户端冻结配置，重启后读取修改。`max_parallel` 限制该客户端同时请求数；它不等于跨进程或跨项目的 Spark 全局调度。reader 旧 `READER_*` 环境和 CLI 参数在入口转换，优先级为 CLI > 旧环境 > 选定配置；新部署优先使用统一 JSON，迁移时核对旧覆盖项。

### 按环节选模型（2026-09-26 用户采用）

量大、判断简单的环节用本地模型，量小、要引用数字和证据的环节用 Claude，最强型号只留给决定质量的少数材料。不做同型号对比即切换；质量靠下述分工与 04 的覆盖、引文和数字检查保证。

| 环节 | 模型 | 说明 |
|---|---|---|
| L0 文件名分档 | 不用模型 | 规则判定 |
| L1 大批粗筛（Spark） | 本地 qwen3 系列 | 只作排序与粗分；本地模型分数偏宽、有锚定，不单独决定提升 |
| L1 打分与复核（M4，`research_default`） | Claude Sonnet 5 | 含 5–7 分边界与 ≥7 分待提升的复核 |
| OCR | 本地 `spark_ocr`（qwen3-vl:8b） | 只对优先级高的扫描件；不为无关扫描件做 OCR |
| L2 全文深读与事实抽取（终端） | Claude Sonnet 5 | Claude Code 会话以 Sonnet 5 执行 pack/record，`--model` 如实记录 |
| L2 核心材料与 C3 前审阅（`core_review`） | Claude Opus 5.5 | 9 分白皮书、复杂表格、数据相互矛盾或采用前审阅 |
| 长尾全文候选（Spark reader） | 本地 qwen3.8:27b | 只作候选阅读，不直接采用 |
| 翻译 | 本地 qwen3.8:27b-translate | 不变 |

更换默认型号只影响新任务；已冻结配方的 reader 任务和已有 L1 结果不重读、不改写。

## 3. 一份材料的一套有效结果

同一内容身份只维护一套当前有效阅读结果，由 reader catalog 的当前指针选择。reader current 与 deep-read current 共用 workflow.reading_results，不构建推理客户端；L2 事实处理回执不能成为第二套全文结果。尝试日志、局部检查点和被引用的历史依据可保留；失败重试不增加前台的阅读份数。

更换默认模型只影响新建任务，已完成材料不自动重读或改变结果。已创建任务使用冻结的推理身份、提示配方和上下文；不得中途混用新模型。现有 reader 在新配置与旧任务不符时阻塞，恢复原配置后可继续；自动选择旧配置仍未实现，已完成材料通过显式 reread 新建独立版本。

显式重读先产出待替换版本，经 04 §8 的覆盖与产物机检及审阅确认后，用旧版本基线和报告 SHA 原子更新当前指针；失败时旧结果继续有效。旧证据/回答/报告引用具体版本，不随当前指针变化。模型更大或结果更新不自动授予 C3 采用资格。单结果是使用规则，不能成为删除原文与已引用依据的理由。

## 4. 验收

代码契约测试覆盖配置切换、旧配方兼容、模型身份、结构化输出、失败恢复及不重复阅读。生产能力另用代表性材料验证覆盖、引文、数字与边界、耗时和失败原因；第二型号未实测时不能声称已经兼容。常驻服务是否生效以实际源码、配置与运行记录为准。

`python3 manage.py models --probe` 通过所选配置发送一条无研究材料的真实 JSON 请求，核对结构和实际模型；配置校验或交互式 CLI 登录成功不能代替这项检查。CLI 参数依据本机 `claude --help` 及 [官方非交互文档](https://code.claude.com/docs/en/headless)。
