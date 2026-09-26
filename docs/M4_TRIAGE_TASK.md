# M4 资料分类与命名任务

> CURRENT · 2026-09-13 更新（首次采用 2026-09-09）。规则归属见 [framework/CURRENT.md](../framework/CURRENT.md)；本文件在 `framework/current_state.json` 以 `reading-m4-triage-20260912` 登记，scope 为 `m4-triage`。
>
> 本任务只约束 **M4 本机原件的整理**，是对 [04 阅读标准](../framework/04_reading_scoring_standard.md) §5/§6 在该范围内的替代（见 §10）。Spark 的阅读、评分与 originals 不可变规则不受影响，仍按 04 标准执行。

## 0. 实现状态（2026-09-13 源码核对）

| 步骤 | 状态 | 落点 |
|---|---|---|
| 全量清单与重复检测 | 已实现 | `inresearch.materials.inventory` 唯一写入器；`inresearch.materials.records` 统一读取旧/新格式 |
| L1 预览、模型打分、终端提交 | 已实现；默认改用共享研究模型 | `inresearch.workflow.l1_batch` 是唯一用例；`score`、`attribution`、`terminal_batch`、`progress` 仅处理各自 CLI 参数和呈现 |
| 提取摘要与 L2 交付 | 用例已拆分并补齐准入/重放/计划冲突规则 | `inresearch.workflow.attribution`、`inresearch.workflow.deep_read.DeepRead`；CLI 为 `inresearch.interfaces.deep_read`；不是 Spark 全文流程的替代 |
| 改名移动、日志与恢复 | 已实现并通过隔离故障测试 | `inresearch.storage.moves`、`inresearch.storage.jsonl`、`inresearch.materials.organize`；未操作生产原件 |
| M4 对照表导出与对账 | 已有代码 | `inresearch.materials.mapping` |
| Spark catalog 的 apply-triage | 已实现（2026-09-18），**尚未在真机 catalog 上执行** | `inresearch.workflow.apply_triage`；CLI `manage.py reader apply-triage`；见 §7.3 |

清单和阅读入口不移动原件；实际文件操作仍须按已给授权、对应操作计划和验收执行。模型更换不扩大原件操作范围。本次未操作 M4/Spark 原件，也未核对生产完成量。

## 1. 任务一句话

对 M4 本机 `/Users/m4/Downloads/所有raw materials`（87,501 个文件，251 GB）中的每一个文件，按 inresearch.ai 研究框架持续阅读、打分（10–0）、归入研究模块、给出规范文件名，然后在 M4 上真实改名并移动到新的资料库目录，同时把原路径、原文件名、新路径、新文件名记入以 **SHA-256 识别内容、原始路径识别物理副本**的对照表。M4 全部做完后，对照表才交给 Spark；Spark 依据表整理自己那份副本，不再自行分类。

## 2. 不变量

1. M4 上的文件**只改名、只移动，不修改内容、不删除**。改名移动不改变字节，所以 SHA-256 在前后保持一致，是唯一可靠的对接键。
2. 每次移动先核对 SHA-256，持跨进程锁写入并同步准备日志，用独占硬链接预留目标；再次核对同一文件与内容后移除旧路径，同步目录再记录完成。中断可能留下同一文件的两个名字，恢复按日志和哈希完成；哈希不符或路径冲突保留文件并报错，不覆盖已有内容。
3. 新资料库根目录与原目录同卷、并列，例如 `/Users/m4/Downloads/inresearch资料库/`；处理成功后文件从原目录移出；完成量由清单、有效判定与移动回放对账，空目录不能单独证明完成。
4. 同内容多路径（SHA-256 完全相同的多个副本）：只保留一份进分类目录，其余副本移到 `_to_delete/duplicates/`，表中 `action=duplicate`、`duplicate_of=<保留副本的新路径>`，全部原路径都记录；由用户统一删除。文件名相同但字节不同的不是重复，各自独立打分。
5. Spark catalog 的 `sha256` 列与表对接；Spark 的 originals 保持不可变，改名移动落在 Spark 的 library 链接上。
6. 每条决定必须写明：哪个模型、什么阅读层级、依据什么证据。不能从文件名推断“已读”。
7. 单次零分建议进入 `_review`；经复核确认无关才进入 `_to_delete/`，真正删除由用户一并操作。
8. 一个任务卡、一个输出契约；换模型不换契约。
9. 改名移动期间，`m4_preflight` 的 LaunchAgent 停用（它每 30 分钟扫描原目录），任务结束后改指新根目录。

## 3. 阅读层级（read_level）

| 层级 | 含义 | 适用 | 打分性质 |
|---|---|---|---|
| L0 name_only | 只看文件名、路径、后缀、大小 | DWG/CAD、3D、图片、日志、压缩包、无法提取文本的文件 | 暂定，文件名带未读标记 |
| L1 preview | 按格式抽取后最多 6,000 字预览，PDF 可补取中段，模型路由 | 所有可提取文本的 PDF/Office 第一轮 | 暂定 |
| L2 full | 全文分块阅读 | L1 得分 ≥7 或用户点名 | 完整阅读与审核后才可确认正式评分 |
| L3 ocr | 配置的视觉模型逐页双次 OCR 后再 L1/L2 | 扫描件（约 2,496 份），第一轮不做 | 正式 |

L0 文件**不会因为没读就得 0 分**。图纸/CAD 默认归“图纸资产（未读）”，得分位显示未读标记。

清单工具的 `route` 字段给出每个文件的下一层级：`l1_preview` 或 `l0_name_only`。该判断只依据后缀与路径，属于暂定，任何时候都不构成“已读”。

## 4. 打分（score，10–0）

| 分 | 锚点 |
|---|---|
| 10 | 直接回答 research_questions 中的问题，含一手数据或可核验数字，覆盖 M01–M15 核心 |
| 8–9 | 数据中心/算力产业的行业报告、厂商一手资料、标准与白皮书，数据可引用 |
| 5–7 | 相关背景：上游半导体/存储/网络/电力，或时间较旧但仍有对比价值 |
| 2–4 | 弱相关：泛 IT、通用宏观、营销材料、重复版本 |
| 1 | 边缘：仅个别段落相关 |
| 0 | 与数据中心研究完全无关（个人文件、安装包、无关行业）。**进待删除视图** |

规则：

- 0 分需要 L1 及以上证据，或文件名/路径明确无关（如 `.dmg`、个人照片）；两个模型都判 0 才成立，否则进“待复核”。
- 兼容 04 标准的 importance 1–9：`importance = max(1, round(score * 0.9))`，两列同时记录。
- 暂定分（L0/L1）与正式分（L2/L3）分列，正式分出现前文件名用暂定分并带层级字母。

## 5. 分类目标（category）

`M01`–`M15` 研究模块（见 `framework/modules.json`）之外，增加四个非研究桶：

| 桶 | 用途 |
|---|---|
| `_drawings_unread` | 图纸、CAD、3D、大幅面文件，L0 归类，不进入文章阅读模型 |
| `_office_pending` | 需转换的 Office/加密文件 |
| `_review` | 模型分歧、无法判断、疑似敏感 |
| `_to_delete` | 0 分进 `_to_delete/unrelated/`，重复副本进 `_to_delete/duplicates/`；待用户一并处理 |

## 6. 文件名规范（new_name）

```
{score}{level}_{year}_{org}_{title}__{sha16}.{ext}
```

- `score` 两位数字（`10`、`07`）；未读用 `__`（ASCII 排序时落在所有数字之后，已打分文件自然排前）。
- `level` 一个字母：`n` 仅文件名、`p` 预览、`f` 全文、`o` OCR。例：`09p_2025_TechInsights_DRAM市场报告Q1__a53fe9f20f9ddba3.pdf`
- `title`：原文件名有意义则保留原名（去掉下载编号、重复空格、`(1)` 之类），无意义则用模型提取的标题。缺失字段写 `未知`。
- 年份/机构/标题分别限 8/25/55 字符，与 Spark 现有 `_link_target` 的裁剪一致；`sha16` 保证唯一，不会同名覆盖。

## 7. 清单与对照表

### 7.1 全量清单（已实现）

```bash
python3 manage.py inventory inventory --workers 8
python3 manage.py inventory summary
```

所有阶段共用 `inresearch.materials.paths` 的 `INRESEARCH_SOURCE`、`INRESEARCH_LIBRARY` 与 `INRESEARCH_DATASET`。默认源目录 `/Users/m4/Downloads/所有raw materials`，清单写入 `~/.local/share/inresearch.ai/m4-triage/inventory.jsonl`。清单命令可显式指定 `--root` / `--out-dir`，兼容旧 `M4_TRIAGE_ROOT` / `M4_TRIAGE_OUT`；其他阶段需指向相同数据集。输出必须在源目录外。清单元数据绑定源根，移动日志绑定两个根，不能用原账本静默切换语料。

清单唯一写入格式为 `schema_version, sha256, size_bytes, suffix, original_rel, original_name, l0_bucket, route, mtime_ns, ctime_ns, device, inode, hashed_at`。持锁追加，未变化的文件续跑跳过，变化与失败路径重新读取；每路径取最新观察，旧观察留在日志中。符号链接不跟随。尾部断行先保留副本再恢复，中间损坏拒绝继续。

旧 `rel/size` 格式在统一读取边界兼容；继续清点前执行 `migrate-inventory`，完整备份后原子转换，不混写格式。旧 `m4_inventory.py` 独立入口已删除，清点统一用 `python3 manage.py inventory`。summary、分类、L2 深读队列、移动、导出与进度共同使用归一后的集合；一次失败不覆盖已有成功判定，尚无成功结果的文件仍算待处理。L2 通过 `inresearch.materials.records.current_results` 读取有效判定，不能另外按日志末行决定是否可深读。

哈希在线程池里跑，`--workers` 默认 8、上限 16。251 GB 的一次性全量估计 1–2 小时，取决于磁盘。

### 7.2 物理副本对照表（已实现）

`python3 manage.py mapping export` 原子写入 `mapping.jsonl`。首行登记版本、生成时间、源/目标根、数据集与文件数；之后每个物理文件一行 `sha256, from, to, size, stage`，正式保留副本携带当前判定、模型/执行者及来源信息。内容相同的额外副本仍各占一行，避免只按 SHA 合并时漏掉路径。以移动日志回放结果导出，不依赖已移动路径继续出现在最新清单。

导入验证表头、文件数、相对路径及重复目标；按 SHA 匹配本地清单，缺失或额外文件未对清时禁止 commit。plan/apply 共用路径和内容校验，plan 也会完整读取待移动文件计算哈希。跨根目录同名路径仍是一次移动。成功后按现存位置判断幂等，回退后可以重新执行；restage 必须先回退，才能回退其前面的 library 阶段。

两个根必须并列、同卷，文件系统支持硬链接与同步。若不支持，保留原件并停止，不自动改用跨卷复制。读取端只报告日志已提交的移动；中断待恢复的操作不计完成。进度中的 moved 是当前仍离开原位置的文件数，重复改名不会重复计数。

### 7.3 Spark catalog 接口

当前物理移动命令只适用于独立、未被 reader catalog 管理的副本；不是 Spark originals 的迁移命令。已识别的 reader `originals/` 根会被移动器拒绝。catalog 侧改用 `apply-triage`：核对 catalog 内容身份，仅更新优先级和 library 链接，保持 originals 不变。受控重读和采用替代另按 04 / 08 执行，不能把命名重排当成新阅读。

```bash
python3 manage.py reader apply-triage --mapping /path/to/mapping.jsonl
python3 manage.py reader apply-triage --mapping /path/to/mapping.jsonl --commit
```

不带 `--commit` 只出计划，一个字节都不写。两步都在 reader 的排他锁内执行，因此不会与正在运行的 reader 交错；`--commit` 会逐份重新哈希原件（这正是校验本身），所以计划是秒级的，提交要把语料整读一遍。

**前置条件：catalog 必须已是 v2。** 命令在构造 Reader 之前先只读地查 `PRAGMA user_version`，v1 直接拒绝并指向 `manage.py reader init`（它会先整库备份再迁移），**不会顺手替你迁移** —— `Reader.initialize()` 本来会，而那对一个「只出计划」的命令是错的副作用。2026-09-18 真机核对：Spark 的 catalog 仍是 v1，32,734 份文档、没有 `reading_runs` 表，所以这一步在真机上是必经的。

匹配只按 `sha256`，不按路径 —— 目录是人手重排过的，内容是唯一还能对上的键。只处理 `stage=library` 的行；`duplicates` 不归置。已有 `library_rel` 且与目标不同的文档报 `conflict` 并原样保留，不覆盖：哪个归置正确是判断，不是本命令能替人做的决定。`importance` 超出 1–9 就不改优先级（与阅读产出同一道边界）。目标路径逃出 `library/` 一律拒绝。

写入只有两处：`documents.library_rel` 和初始 reading_run 的 `priority`。链接由 reader 自己那条已验证路径创建（`library/… → originals/…` 软链，建前比对 catalog 记录的摘要），因此与 reader 自己归置的条目共用同一套 `operations` 日志与 `reader rollback` 回退。**不创建 reading_run，不设置 `report_rel`/`activated`，不改 `current_revision_id`** —— 这条由 `tests/unit/test_apply_triage.py` 钉死。

## 8. 模型与客户端协议

模型接入的唯一正式源是 [08 模型执行](../framework/08_model_execution.md)。当前暂由 Claude CLI 执行模型任务，Spark 恢复后通过配置接入；替代固定 Claude 主判与固定本机 8B 第二意见。换兼容型号通过配置完成，阅读层级、评分和原件范围不随之变化。

所有模型接收相同任务输入并返回相同判定字段。普通 `sample/run` 走共享推理接口；旧 `collect` 仅回收已提交的 Anthropic 批次，不再提交新批次。Claude Code / Codex CLI 可用同一 `pack/record` 契约，记录 executor 与实际模型（不可核实时记未知）。

一次判定不因是某个品牌或更大模型自动更可信。双模型复核时保留双方分数与依据；差异 >2 或分类不同进 `_review`；零分/无关的单次模型建议进入待复核，不直接路由到待删除目录。已有正式审核决定继续保留。日常只使用一套当前有效结果，旧行作为过程记录。

## 9. 吞吐与顺序

1. 先清单与哈希，再验证预览抽取。
2. 用当前配置模型完成 50 份代表性小样，核对模型身份、评分、引文、命名及耗时；不能沿用旧模型费用/耗时估算。
3. 按实测并发预算处理 L1；L2 范围保留本任务既有规则，Spark 按 04 §1 分层阅读：有效优先级 ≥7 或点名全文深读，1–6 摘要深度，0 分与 reader 衍生物回流停放。OCR 单独验收其模型能力。
4. 客户端并发上限只约束对应进程，共享 GPU 的全局容量仍须结合实际运行调度。

## 10. 与 04 阅读标准的关系

| 04 标准的规则 | 本任务在 `m4-triage` 范围内的变化 |
|---|---|
| §5 importance 1–9 | 新增 score 10–0 为主分，importance 由 `max(1, round(score*0.9))` 换算并同时记录 |
| §6 “分数放元数据，不再随评分移动原件” | **M4 本机原件随评分改名移动**，以操作日志和 SHA-256 保证可逆可追溯。这是对 §6 的明确替代，只适用于 M4 本机原件；Spark 侧 originals 仍不可变，只动 library 链接 |
| §1 “不按低分剔除文章” | 0 分进待删除视图但不删除、不退出台账；由用户决定 |
| 01_data_standards.md §4 C3 采用分档 | 不变；本任务只管读取优先级与整理，不等于采纳 |


2026-09-13 集成核对：文本指纹和近似摘要仅为复核提示，不能代替原件内容 SHA，不能自动阻止另一内容版本开包或沿用其证据。合并单元格展开在分配前检查累计抽取预算，超限明确失败并保留原件；截断或超限不计完整阅读。

带 `twin_of` 的文本副本自动推测记录不是完整阅读证明，保留日志供复核，不能单独让另一 SHA 退出事实处理队列；旧回执仍保留，全文结果须查询 reader catalog。


## 11. L2 命令与修订基线

软件职责和事务权威见 [09 软件契约](../framework/09_software_contracts.md#l2-终端阅读用例)。`deep-read queue` 自动门槛为 7，`--min-score` 可用于当次优先队列；`pack --sha` 显式点名仍保留准入与事实处理状态检查，已处理材料加 `--again`。SHA 有歧义即拒绝，不取第一份。包的正文、brief 和 manifest 使用同一独立目录，按返回路径读取，不再拼接旧固定 sha16 目录。

`queue`、`pack` 给出 L1 版本。`attribute` / `flag` 新请求必须带 `--expected-revision <所读版本>`；冲突后先查看新判定再形成修改，不静默沿用旧终端结果。`backfill-provenance` 先干跑，逐项核对候选路径与 SHA；应用时用 `--commit --expected-plan <计划摘要>`。事实或解析依据变化需要重新复核。

record 接受事实数组或含 records/facts 数组的对象；`--doc` 是完整 SHA 或唯一前缀。相同事实和完成请求重放不重复计数；事实成功而回执失败时重放同一输入。`skip` 保留缺口，再记录人工完成声明；重复 skip 不重新打开已经 filled 的缺口，`gaps --filled` 重复提交返回已完成。空数组或日志存在不证明实际深读质量。当前 L2 用例不自动把 L1 的分数/层级升级为全文正式评分，也不授予 C3。

record 的 `--executor` / `--model` 写入本次完成回执；未提供记 unknown。外部客户端声明明确标为 client_reported，不冒充程序已验证的模型身份。请求重放保留原归属，不以新的客户端名字改写旧阅读记录。


### 共用当前全文结果（2026-09-13）

`python3 manage.py deep-read --reader-data-root /实际reader数据根 current --sha 完整SHA` 与 `reader --data-root 同一根 current --sha 完整SHA` 返回同一当前全文报告；亦可共用 READER_DATA_ROOT。未指定时均为 ~/.local/share/inresearch.ai，不能把 M4 的 dataset 子目录误当成已存在的 reader 库。查询不调用模型、改写库或移动原件。

pack 自动复用验证通过的当前报告和页块；返回 reading_result 状态、版本、报告 SHA 和原路径，任务包固定该版本。无合格报告时仍提供抽取输入，但不报告已完成全文。record/skip 只产生事实处理回执，pack --again 不产生新阅读版本；需要全文重读继续走 reader reread/inspect-revision/activate-revision。

终端 JSON 的 documents_read/already_read/eligible_unread 已退出，改为 documents_processed/already_processed/eligible_unprocessed；相似提示改为 same_text_already_processed、same_text_packed_not_processed 和 processed。旧 l2_read.jsonl 字节不迁移，其历史名字不改变回执含义。status.reading 单列 catalog 清单状态，不把旧人工声明自动认定为全文合格。真实 M4/Spark 数据根连接和旧资料审计仍须实机验收。
