# M4 资料分类与命名任务

> CURRENT · 2026-09-12 更新（首次采用 2026-09-09）。规则归属见 [framework/CURRENT.md](../framework/CURRENT.md)；本文件在 `framework/current_state.json` 以 `reading-m4-triage-20260912` 登记，scope 为 `m4-triage`。
>
> 本任务只约束 **M4 本机原件的整理**，是对 [04 阅读标准](../framework/04_reading_scoring_standard.md) §5/§6 在该范围内的替代（见 §10）。Spark 的阅读、评分与 originals 不可变规则不受影响，仍按 04 标准执行。

## 0. 实现状态（2026-09-12 源码核对）

| 步骤 | 状态 | 落点 |
|---|---|---|
| 全量清单与重复检测 | 已实现 | `inresearch.materials.inventory` 唯一写入器；`inresearch.materials.records` 统一读取旧/新格式 |
| L1 预览、模型打分、终端提交 | 已实现；默认改用共享研究模型 | `inresearch.workflow.triage`、`inresearch.workflow.score`、`inresearch.workflow.terminal_batch` |
| 提取摘要与 L2 交付 | 已有代码 | `inresearch.workflow.attribution`、`inresearch.workflow.deep_read`；不是 Spark 全文流程的替代 |
| 改名移动、日志与恢复 | 已实现并通过隔离故障测试 | `inresearch.storage.moves`、`inresearch.storage.jsonl`、`inresearch.materials.organize`；未操作生产原件 |
| M4 对照表导出与对账 | 已有代码 | `inresearch.materials.mapping` |
| Spark catalog 的 apply-triage | 未实现 | §7.2 描述目标契约；不由脚本存在推断已完成 |

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
| L1 preview | pdftotext 首页+目录+首 4,000 字，模型路由 | 所有可提取文本的 PDF/Office 第一轮 | 暂定 |
| L2 full | 全文分块阅读 | L1 得分 ≥7 或用户点名 | 正式 |
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

### 7.3 Spark catalog 接口（尚未实现）

当前物理移动命令只适用于独立、未被 reader catalog 管理的副本；不是 Spark originals 的迁移命令。已识别的 reader `originals/` 根会被移动器拒绝。Spark 恢复后另做 `apply-triage`：核对 catalog 内容身份，仅更新优先级、元数据和 library 链接，保持 originals 不变。受控重读和采用替代另按 04 / 08 执行，不能把命名重排当成新阅读。

## 8. 模型与客户端协议

模型接入的唯一正式源是 [08 模型执行](../framework/08_model_execution.md)。当前暂由 Claude CLI 执行模型任务，Spark 恢复后通过配置接入；替代固定 Claude 主判与固定本机 8B 第二意见。换兼容型号通过配置完成，阅读层级、评分和原件范围不随之变化。

所有模型接收相同任务输入并返回相同判定字段。普通 `sample/run` 走共享推理接口；旧 `collect` 仅回收已提交的 Anthropic 批次，不再提交新批次。Claude Code / Codex CLI 可用同一 `pack/record` 契约，记录 executor 与实际模型（不可核实时记未知）。

一次判定不因是某个品牌或更大模型自动更可信。双模型复核时保留双方分数与依据；差异 >2 或分类不同进 `_review`；零分/无关的单次模型建议进入待复核，不直接路由到待删除目录。已有正式审核决定继续保留。日常只使用一套当前有效结果，旧行作为过程记录。

## 9. 吞吐与顺序

1. 先清单与哈希，再验证预览抽取。
2. 用当前配置模型完成 50 份代表性小样，核对模型身份、评分、引文、命名及耗时；不能沿用旧模型费用/耗时估算。
3. 按实测并发预算处理 L1；L2 范围保留本任务既有规则，Spark 按 04 对所有独立文章深读。OCR 单独验收其模型能力。
4. 客户端并发上限只约束对应进程，共享 GPU 的全局容量仍须结合实际运行调度。

## 10. 与 04 阅读标准的关系

| 04 标准的规则 | 本任务在 `m4-triage` 范围内的变化 |
|---|---|
| §5 importance 1–9 | 新增 score 10–0 为主分，importance 由 `max(1, round(score*0.9))` 换算并同时记录 |
| §6 “分数放元数据，不再随评分移动原件” | **M4 本机原件随评分改名移动**，以操作日志和 SHA-256 保证可逆可追溯。这是对 §6 的明确替代，只适用于 M4 本机原件；Spark 侧 originals 仍不可变，只动 library 链接 |
| §1 “不按低分剔除文章” | 0 分进待删除视图但不删除、不退出台账；由用户决定 |
| 01_data_standards.md §4 C3 采用分档 | 不变；本任务只管读取优先级与整理，不等于采纳 |
