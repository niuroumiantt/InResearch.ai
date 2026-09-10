# M4 资料分拣操作手册

> 配套任务定义：[M4_TRIAGE_TASK.md](M4_TRIAGE_TASK.md)（候选提案）。本手册只列命令与顺序。
> 所有命令在 M4 本机执行。凡是改名、移动的步骤都单独标注，且都先出 dry-run。

解释器固定用分拣专用虚拟环境，换模型、换会话都不影响：

```
PY=~/.local/share/inresearch.ai/m4-triage/.venv/bin/python
S=~/code/inresearch.ai/pipeline
```

## 阶段 0 · 已完成

| 步骤 | 状态 |
|---|---|
| 停 Spark reader 服务 | 已停（`systemctl --user stop inresearch-reader.service`） |
| 卸载 M4 preflight 定时任务 | 已卸载 |
| 修复 `spark-lan` 指向 192.168.50.2 | 已修 |
| 全量 SHA-256 清单 | 已完成，87,352 个文件 |

清单结论（去重后）：

| 项目 | 数量 |
|---|---|
| 文件总数 / 总量 | 87,352 / 269.7 GB |
| 字节相同的重复副本 | 51,456，163.6 GB |
| 去重后唯一文件 | 35,896 |
| 派生产物（要删/reader/，跳过） | 12,918 |
| **L1 需要调用模型** | **16,022**，其中可提取文本 14,270 |
| 只按文件名归类（图纸/图片/日志） | 6,956 |

用户 2026-09-09 决定：`要删/reader/` 下的文本缓存、批次假态不送模型，仍入表。
内容相同的多份副本只判一次，优先取 `要删/` 之外的那份路径作为代表。

清单重跑（增量、可随时重复，只读）：

```
$PY $S/m4_inventory.py --workers 4
```

## 阶段 1 · L1 粗筛

### 1.1 免费干跑，不花钱，确认预览抽取正常

```
$PY $S/m4_triage_l1.py preview --limit 20 --text-only
```

### 1.2 配置 API 密钥（用户操作，Claude 不代填）

```
mkdir -p ~/.config/inresearch.ai
printf 'ANTHROPIC_API_KEY=%s\n' 'sk-ant-...' > ~/.config/inresearch.ai/anthropic.env
chmod 600 ~/.config/inresearch.ai/anthropic.env
```

### 1.3 50 份小样，人工验收

```
$PY $S/m4_triage_l1.py sample --limit 50
```

检查四件事：分数是否合理、模块是否对、拟定文件名是否可读、实测 token 与费用。
通过后才进入全量。不通过就改任务卡的打分锚点，再跑一次小样。

### 1.4 全量提交（Batch，半价，24 小时内回批）

```
$PY $S/m4_triage_l1.py submit
```

### 1.5 回收结果（可重复执行，只收已完成的批次）

```
$PY $S/m4_triage_l1.py collect
```

结果表：`~/.local/share/inresearch.ai/m4-triage/l1_results.jsonl`

## 阶段 2 · 去重（已完成 2026-09-09）

纯 SHA-256 判断，不需要模型，因此排在 L1 之前执行。

```
$PY $S/m4_triage_apply.py duplicates plan     # 只打印
$PY $S/m4_triage_apply.py duplicates apply    # 先写日志再 mv
$PY $S/m4_triage_apply.py duplicates revert   # 按日志反向还原
```

保留规则（确定性，plan 与 apply 结果一致）：优先「要删」之外的路径 → 非上一代 reader 产物
→ 路径层级更浅 → 字母序。零字节文件不视为彼此的重复，单独进 `_to_delete/empty/` 并保留原路径。

执行结果：

| 项目 | 变化 |
|---|---|
| 原目录 | 87,352 个 / 269.7 GB → 36,050 个 / 99 GB |
| `_to_delete/duplicates/` | 50,984 个 / 152 GB |
| `_to_delete/empty/` | 473 个零字节文件 |
| 抽样校验 | 原位置已空、新位置存在、SHA-256 一致 |

原目录留下 4,130 个空目录，未删除，等用户一并处理。

## 阶段 3 · 改名与归类（需要 L1 结果）

```
$PY $S/m4_triage_apply.py library plan
$PY $S/m4_triage_apply.py library apply
$PY $S/m4_triage_apply.py library revert
```

移动目标：`/Users/m4/Downloads/inresearch资料库/{分类}/{新文件名}`
操作日志：`~/.local/state/inresearch.ai/m4-triage/moves.jsonl`（移动前先写，可反向重放）

## 阶段 4 · L2 精读（待写）

只对 L1 得分 ≥7 的文件做，按章节切块，Opus 5，覆盖暂定分。

## 阶段 5 · 交给 Spark（待写）

```
$PY $S/m4_triage_export.py > mapping.jsonl
scp mapping.jsonl spark-lan:/tmp/
ssh spark-lan python3 ~/code/inresearch.ai/pipeline/continuous_reader.py apply-triage /tmp/mapping.jsonl --dry-run
```

## 修正：未读文件保留原始目录

第一遍归档时，未读文件（图纸、图片、衍生产物）只按文件名命名，父目录全部丢弃。
结果是广州项目和深圳项目的 `一层平面图.dwg` 并排躺在 `_drawings_unread/` 里，
除了 SHA 前 16 位没有任何东西能区分它们。

现在未读文件保留来源目录树：

```
_drawings_unread/数据中心报告购买/01 解决方案/2019中国移动广州IDC/4 投标/图纸/__n_一层平面图__6dbed65c.dwg
```

文件名本身也带上识别性最强的几层——项目层加最内两层：

```
__n_2020.5 大数据安全产业示范基地及国家大数据安全靶场（数据区）_5#楼上_截面_WPJW2__f54e15b3.dwg
```

只保留目录树是不够的：文件一旦被发邮件或复制出去，`WPJW2.dwg` 又变回匿名。
文件名里已经写明的目录段不会重复写，所以本来命名就清楚的文件只会拿到日期和专业：

```
__n_2019.7_04电气专业_中国移动南方基地二期工程二阶段项目电气总平面图__aabb.dwg
```

名字上限 200 字节（macOS 每段允许 255），原文件名有保留额度，
再长的项目名也挤不掉它。

打过分的文件仍然平铺、不加上下文——它们的文件名里已经有分数、年份、机构、标题。

路径过长时从中间删段，保留最外层（哪批资料）和最内层（哪个项目、哪个子目录），
并留下可见的 `__` 标记，不静默丢弃。

### 把已经归档的文件搬到正确位置

```
$PY $S/m4_triage_apply.py restage plan     # 只读，先看会动多少
$PY $S/m4_triage_apply.py restage apply
$PY $S/m4_triage_apply.py restage revert
```

`restage` 从 `moves.jsonl` 回放出每个文件的当前位置，按现行规则重算目标，
只搬位置不对的。已经在正确位置的不动，重复执行收敛到 0。

## 修正：Excel / PPT 不再只看文件名

第一遍把 `.xlsx .xls .ppt .et .wps .dps .vsdx .vsd` 全部路由到 `_office_pending`，
一个字都不抽，模型收到的原话是"没有可提取的文本，只能根据文件名和路径判断"。
于是一份 11 张表的 Dell'Oro 资本开支预测工作簿拿了 8 分，而它的散文版摘要 PDF 拿了 9 分。

`m4_office_text.py` 用纯标准库读这两类容器（按魔数判断，不看后缀，因为
`.et/.wps` 两种格式都有人用）：

| 容器 | 格式 | 抽取内容 |
|---|---|---|
| `PK\x03\x04` | OOXML zip | 工作表名 + 共享字符串 / 内联字符串 |
| `\xd0\xcf\x11\xe0` | OLE2 复合文档 | BIFF 的 SST 与工作表名；PPT 的文本原子 |

iWork（`.numbers .pages .key`）和 `.mpp` 仍然没有标准库读法，继续按文件名判断。

### 重判当初盲打分的文件

```
$PY $S/m4_triage_pack.py pack --redo --limit 200
# 判完照常 record，新行会覆盖旧行（load_results 取每个 sha 的最后一行）
$PY $S/m4_triage_pack.py record --verdicts verdicts.txt
```

`--redo` 只挑「上一次结果是 level n、而现在能打开」的文件，不会把已经读过内容的重排一遍。
重判完记得再跑一次 `restage`，让分数变化反映到文件名上。

## 换一个语料跑（NAS、移动硬盘、另一个文件夹）

三个环境变量决定一次运行读哪里、写哪里、把账记在哪里。不设就是原来的 M4 语料，行为完全不变。

```
export INRESEARCH_SOURCE=/Volumes/NAS/研究资料          # 只读，永不修改
export INRESEARCH_LIBRARY=/Volumes/NAS/研究资料库       # 归档目标
export INRESEARCH_DATASET=nas                          # 这批语料的账本名
```

`INRESEARCH_DATASET` 是最要紧的一个。清单、L1 结果、移动日志都放在它下面：

```
~/.local/share/inresearch.ai/{dataset}/inventory.jsonl
~/.local/share/inresearch.ai/{dataset}/l1_results.jsonl
~/.local/state/inresearch.ai/{dataset}/moves.jsonl
```

**不改这个名字就去跑第二批语料，新的清单会追加进第一批的账本**，之后每个阶段都会读错。
名字必须是单个路径段，带斜杠会被直接拒绝。

两条硬约束：

1. **source 和 library 必须在同一个卷上。** 移动走的是 `os.rename`，跨文件系统会失败。
   `apply` 在动第一个文件之前就检查，不合格直接退出，不会先写几万条错误再让你发现。
   NAS 上就把资料库建在同一个共享里，别一个在 NAS 一个在本机。
2. **账本留在本机**，不要放到 NAS 上。多台机器同时写同一个 jsonl 会串行破坏。

顺序和本机一样：inventory → l1 → apply。网络盘上做 SHA-256 要把每个文件完整读一遍，
按千兆网估算大约 100 GB/小时，先用 `--limit` 跑一小批确认再放全量。

## 中途换模型

本手册的所有命令与状态都在磁盘上，与会话无关。换模型后，新会话读本手册和任务卡即可接手；
`l1_results.jsonl`、`inventory.jsonl`、`moves.jsonl` 是唯一进度依据，重复执行不会重复计费或重复移动。
