# M4 资料分类与命名任务

> CURRENT · 2026-09-09 用户采用。规则归属见 [framework/CURRENT.md](../framework/CURRENT.md)；本文件在 `framework/current_state.json` 以 `reading-m4-triage-20260909` 登记，scope 为 `m4-triage`。
>
> 本任务只约束 **M4 本机原件的整理**，是对 [04 阅读标准](../framework/04_reading_scoring_standard.md) §5/§6 在该范围内的替代（见 §10）。Spark 的阅读、评分与 originals 不可变规则不受影响，仍按 04 标准执行。

## 0. 实现状态（2026-09-09）

已实现的只有第一步，其余仍是待建设计，不得据此声称已完成：

| 步骤 | 状态 | 落点 |
|---|---|---|
| 全量清单：SHA-256、L0 分桶、重复检测 | **已实现** | `pipeline/m4_triage.py inventory` / `summary` |
| L1 预览包生成 | 未实现 | — |
| Opus 5 批量打分 | 未实现 | — |
| 对照表 mapping.jsonl | 未实现 | — |
| 改名移动与操作日志 | 未实现 | — |
| Spark 侧 apply-triage | 未实现 | — |

清单工具**只读**：以只读方式打开文件，拒绝把输出写进源目录，不改名、不移动、不删除。改名移动的授权要等对应步骤实现并通过小样验收后另行取得。

## 1. 任务一句话

对 M4 本机 `/Users/m4/Downloads/所有raw materials`（87,501 个文件，251 GB）中的每一个文件，按 inresearch.ai 研究框架持续阅读、打分（10–0）、归入研究模块、给出规范文件名，然后在 M4 上真实改名并移动到新的资料库目录，同时把原路径、原文件名、新路径、新文件名记入以 **SHA-256 为唯一键**的对照表。M4 全部做完后，对照表才交给 Spark；Spark 依据表整理自己那份副本，不再自行分类。

## 2. 不变量

1. M4 上的文件**只改名、只移动，不修改内容、不删除**。改名移动不改变字节，所以 SHA-256 在前后保持一致，是唯一可靠的对接键。
2. 每一次移动之前先把原路径、原名、新路径、新名追加写入操作日志，再执行 `mv`（同一卷，原子且瞬时）。日志可反向重放，任何时候都能恢复原目录。
3. 新资料库根目录与原目录同卷、并列，例如 `/Users/m4/Downloads/inresearch资料库/`；文件处理完即从原目录移出，原目录清空即任务完成。
4. 同内容多路径（SHA-256 完全相同的多个副本）：只保留一份进分类目录，其余副本移到 `_to_delete/duplicates/`，表中 `action=duplicate`、`duplicate_of=<保留副本的新路径>`，全部原路径都记录；由用户统一删除。文件名相同但字节不同的不是重复，各自独立打分。
5. Spark catalog 的 `sha256` 列与表对接；Spark 的 originals 保持不可变，改名移动落在 Spark 的 library 链接上。
6. 每条决定必须写明：哪个模型、什么阅读层级、依据什么证据。不能从文件名推断“已读”。
7. 0 分（完全无关）移到 `_to_delete/`，真正删除由用户一并操作。
8. 一个任务卡、一个输出契约；换模型不换契约。
9. 改名移动期间，`m4_preflight` 的 LaunchAgent 停用（它每 30 分钟扫描原目录），任务结束后改指新根目录。

## 3. 阅读层级（read_level）

| 层级 | 含义 | 适用 | 打分性质 |
|---|---|---|---|
| L0 name_only | 只看文件名、路径、后缀、大小 | DWG/CAD、3D、图片、日志、压缩包、无法提取文本的文件 | 暂定，文件名带未读标记 |
| L1 preview | pdftotext 首页+目录+首 4,000 字，模型路由 | 所有可提取文本的 PDF/Office 第一轮 | 暂定 |
| L2 full | 全文分块阅读 | L1 得分 ≥7 或用户点名 | 正式 |
| L3 ocr | qwen3-vl 逐页双次 OCR 后再 L1/L2 | 扫描件（约 2,496 份），第一轮不做 | 正式 |

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
| `_drawings_unread` | 图纸、CAD、3D、大幅面文件，L0 归类，不进 27B |
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
python3 pipeline/m4_triage.py inventory --workers 8
python3 pipeline/m4_triage.py summary
```

默认源目录 `/Users/m4/Downloads/所有raw materials`，可用 `--root` 或 `M4_TRIAGE_ROOT` 覆盖；默认输出 `~/.local/share/inresearch.ai/m4-triage/inventory.jsonl`，可用 `--out-dir` 或 `M4_TRIAGE_OUT` 覆盖，输出目录必须在源目录之外，否则拒绝执行。

每行记录 `sha256, size_bytes, suffix, original_rel, original_name, l0_bucket, route, mtime, hashed_at`。追加式写入，中断后重跑自动跳过已记录路径。符号链接只登记不跟随，读不了的文件登记 `error` 而不是中断。`summary` 从清单算出分桶统计、唯一哈希数、重复组与可回收字节。

哈希在线程池里跑，`--workers` 默认 8、上限 16。251 GB 的一次性全量估计 1–2 小时，取决于磁盘。

### 7.2 对照表（未实现）

位置 `~/.local/share/inresearch.ai/m4-triage/mapping.jsonl`，另导出 `mapping.csv`。每个 SHA-256 一行，追加式版本化（新决定不覆盖旧行，`version` 递增）：

```
sha256, size_bytes, suffix, original_rels[], original_name,
category, score, score_status(provisional|final), importance,
read_level, new_name, new_rel(category/new_name),
action(keep_name|rename|to_delete|duplicate|review), duplicate_of,
models[{name, digest, prompt_sha256, score, category, rationale}],
evidence(≤500 字引文或文件名依据), decided_at, version
```

Spark 侧命令（待写）`continuous_reader.py apply-triage mapping.jsonl --dry-run`：只对 `sha256` 在 catalog 中且原件哈希复核一致的文档生效；只改 `priority`、library 链接名和目录、以及一个 `triaged` 状态；`_to_delete` 落为 `library/_to_delete/` 下的链接；不删原件、不改 originals。先 dry-run 出差异，再执行。

M4 侧实际落地：`/Users/m4/Downloads/inresearch资料库/{category}/{new_name}`，文件本体在此；操作日志 `~/.local/state/inresearch.ai/m4-triage/moves.jsonl` 逐条记录 `sha256, from, to, at`，与对照表互为校验。重评分导致再次改名时同样先记日志再移动，表中 `version` 递增，Spark 以最新版为准；`sha16` 留在文件名里保证任何版本都能对回同一文档。

## 8. 模型与多模型协议

- 用户 2026-09-09 决定：L1 与 L2 全程使用 Claude Opus 5（`claude-opus-5`），L1 完成后直接进入 L2。本机 qwen3:8b 可作为免费第二意见，但不作为主判。
- API 调用走 Message Batches（半价、异步），每批 ≤ 10,000 请求；结构化输出保证 JSON 契约。L1 预览文本会离开本机发送到 Anthropic API，这是采用该方案的已知代价。
- 所有模型收到同一份输入包：元数据 + L1 预览文本 + 本任务卡 §4/§5 的打分锚点与模块表 + research_questions 摘要；输出同一 JSON 契约。
- 每次输出记录模型名、digest、prompt 哈希；输出格式不合规直接记 `model_output_invalid`，不修补。
- 合并规则：两模型 score 差 ≤2 取均值四舍五入并保留双方分；差 >2 或 category 不同进 `_review`；`_to_delete` 需全体一致。
- 单模型阶段（Opus 5）同样按此契约记录，后加模型时无需改表。

## 9. 吞吐与顺序

1. L0 全量与 SHA-256 全量：一次跑完，约 1–2 小时。
2. L1：约 38,000 个候选，Opus 5 Batch 估算 300–400 美元，通常 24 小时内回批；正式开跑前用 50 份样本实测 token。
3. L2 只对 L1 ≥7 的做，按章节切块，Opus 5 Batch，规模取决于 L1 结果；L3 第一轮不做。
4. 先 50 个文件小样：人工核对模型身份、分数合理性、命名可读性，通过后再开 LaunchAgent。

## 10. 与 04 阅读标准的关系

| 04 标准的规则 | 本任务在 `m4-triage` 范围内的变化 |
|---|---|
| §5 importance 1–9 | 新增 score 10–0 为主分，importance 由 `max(1, round(score*0.9))` 换算并同时记录 |
| §6 “分数放元数据，不再随评分移动原件” | **M4 本机原件随评分改名移动**，以操作日志和 SHA-256 保证可逆可追溯。这是对 §6 的明确替代，只适用于 M4 本机原件；Spark 侧 originals 仍不可变，只动 library 链接 |
| §1 “不按低分剔除文章” | 0 分进待删除视图但不删除、不退出台账；由用户决定 |
| DECISIONS C3 采用分档 | 不变；本任务只管读取优先级与整理，不等于采纳 |
