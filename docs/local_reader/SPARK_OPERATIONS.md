# Spark 持续 reader 运行手册

> CURRENT · 2026-09-06。规则归属与替代关系见 framework/CURRENT.md。

本手册对应 `src/inresearch/workflow/reader.py`，不是旧 reader 脚本的启动说明。实现为 Python 标准库、SQLite 与单一队列持有进程（该进程内可开多个工作线程，见「并发与吞吐」）；部署、实际模型验收及同步状态由当次部署记录说明。代码通过隔离故障测试不等于 Spark 已完成部署。

## 数据落点与交付契约

以 Spark 实际登录用户的家目录为基准：

| 路径 | 用途与保留规则 |
|---|---|
| `~/code/inresearch.ai` | 源码与只读研究注册表；运行原文、数据库与凭据不进 Git |
| `~/.local/share/inresearch.ai/raw-materials/` | 持续投料；建议上传临时 `.partial` 文件，完整传输后在同目录原子改名 |
| `~/.local/share/inresearch.ai/originals/<sha前2位>/<sha>/<原名安全副本>` | 只读原件副本，完整 SHA256 定义内容身份；原始文件名另存台账 |
| `~/.local/share/inresearch.ai/catalog/catalog.sqlite` | 永久文档、每次投递、版本、任务与操作台账；不可当作缓存清理 |
| `~/.local/share/inresearch.ai/extracted/<doc_id>/` | 逐页提取、OCR 双读记录、无损分块；永久保留 |
| `~/.local/share/inresearch.ai/artifacts/<doc_id>/` | 注册表快照、执行配方、粗读、每块深读、逐级综合与报告；永久保留 |
| `~/.local/share/inresearch.ai/intake-receipts/received/` | 已处理 raw 接收副本永久保留；与 originals 分离，来源操作可追溯 |
| `~/.local/share/inresearch.ai/library/` | 分类与规范名的符号链接视图；原件身份不随改名变化；可回滚、可重建 |
| `~/.local/share/inresearch.ai/candidates/mapping-proposals.json` | 导出时生成的未映射/注册表已变更提案；不自动新增正式对象 |
| `~/.local/state/inresearch.ai/status.json` | 可重建健康快照；日志在用户 journal；锁位于 catalog，避免更换 state 路径绕过唯一队列持有者 |
| `~/.config/inresearch.ai/reader.env` | 本机私有配置，0600；凭据不可打印或提交 |


## 从 Mac 批量上传（执行机器必须是 Mac）

2026-09-06 批次源目录已由用户在 `m4@m4m` 终端确认：`/Users/m4/Downloads/所有raw materials`，约 267GB，含多级子文件夹。Spark 地址为 `spark@100.100.1.2`（tailnet；2026-09-08 infra 重新编号，旧 `100.73.13.53` 已作废，见 infra `docs/network-addressing.md`）。三台 Mac 若已跑过 infra 的 `bootstrap_mac.sh`，`ssh spark` 别名即指向该地址，家中有线直连可用 `spark-lan`（`192.168.50.2`）。后续批次采用新的批次名，不复用已开放的目录。

在**存文件的 Mac**按 Command + 空格，搜索“终端”，打开新窗口。提示符应为 `m4@m4m`；`spark@dgx` 表示仍在 Spark，不能运行 Mac 上传命令。`caffeinate` 是 macOS 的防休眠工具，不在 Spark 安装。

先确认源路径并建立隐藏暂存目录：

```bash
ls -ld "/Users/m4/Downloads/所有raw materials"
ssh spark@100.100.1.2 'mkdir -p /home/spark/.local/share/inresearch.ai/raw-materials/.m4-20260906.partial'
```

仍在 Mac 终端上传，源路径末尾斜杠表示传目录内容，保留所有子目录。目录在隐藏暂存区，reader 不会提前读取。输入 SSH 密码时屏幕不显示字符。

```bash
caffeinate -i rsync -rtvh --progress --partial \
  "/Users/m4/Downloads/所有raw materials/" \
  spark@100.100.1.2:/home/spark/.local/share/inresearch.ai/raw-materials/.m4-20260906.partial/
```

Mac 保持接电、联网、不合盖。中断后重复同一命令续传；不使用 `--delete` 或删除源文件。成功退出后校验全部文件内容，校验可能较慢：

```bash
caffeinate -i rsync -rcn --out-format='%i %n' \
  "/Users/m4/Downloads/所有raw materials/" \
  spark@100.100.1.2:/home/spark/.local/share/inresearch.ai/raw-materials/.m4-20260906.partial/
```

仅在校验退出成功、没有差异输出且源目录已停止改动时，才开放本批次：

```bash
ssh spark@100.100.1.2 'cd /home/spark/.local/share/inresearch.ai/raw-materials && test ! -e m4-20260906 && mv -T .m4-20260906.partial m4-20260906'
```

开放后阅读服务会处理稳定文件。Mac 原始资料继续保留；上传成功不等于已阅读，更不等于 C3 已采用。

`doc_id = doc-<完整 SHA256>`。相同字节只读一次，多个来源各有 source 记录。同一路径重新投递保留新的来源记录与 `version_seq/previous_doc_id`；路径改名不换内容身份。不同文件名与同名不同内容不会互相覆盖。完整阅读且 library 操作 committed 后，仍匹配登记签名与 SHA 的 raw 接收副本会先改名至隐藏隔离位置，核对移动后字节，再移至永久 `intake-receipts/received/`。这使处理后的文件退出 raw，**不会删除原件或接收副本**。同路径已被新投料替换时跳过旧来源搬运；隔离后发生变化则原样恢复，若原路径又有新文件则两份都保留并转 needs_review。每次操作持久记录，崩溃恢复不覆盖新投料。raw 为空仍不能证明全库阅读或采用完成，须查台账、coverage 与异常状态。相同字节再次投递只增加来源与接收归档任务，不再次调用模型。原件与 receipts 都在同盘，尚不等于异机备份。

`report.json` 包含 `doc_id/content_sha256`、执行与注册表版本、实际模型记录、`coverage`、候选对象/问题、逐条 evidence 与 claims。evidence 有原文短引文、页码、块号和哈希；每条 claim 独立映射注册对象/问题，不把整篇主题套到所有引文上。所有产物固定 `acceptance=candidate`。`coverage.complete=true` 只表示所有提取正文分块已经处理、页数/块数/字数对齐；不证明图表、数字解释或结论正确，不触发 C3 采用，也不自动关闭问题。

`export --dest /路径/snapshot.json` 原子生成主站接收契约：

```json
{
  "schema_version": 1,
  "graph_version": "2.1.2",
  "questions_version": "2.1.1",
  "knowledge": {"documents": [], "evidence": [], "statements": [], "answers": []},
  "reader": {"generated": "ISO8601", "status": "idle", "counts": {}, "stage_counts": []},
  "acceptance": "candidate"
}
```

每行有稳定 `id` 与 candidate 状态；evidence 的 `document_id` 指向 documents，并含 `page_index/locator`；statement 引用 evidence。`answers` 暂为空，综合摘要不冒充问题答案。导出按**当前部署注册表**过滤映射，原阅读报告仍保留当时版本；未知映射写入提案，不伪造 ID，不阻塞整批本地导出。若注册表尚未安装，阅读可继续产生待映射候选，Web 同步须等版本对齐。指定目录作为 export 目标时则逐 doc_id 导出报告、manifest 与 status。原件不会随快照上传；主站只保存可重建派生数据，发布器由独立脚本和用户服务维护。

## 首次安装与真模型 smoke

先确保规范源码已落在 `~/code/inresearch.ai`；Python 3.9+，Linux 用户 systemd。PDF 工具需要 Poppler 的 `pdftotext/pdfinfo/pdfimages/pdftoppm`。推理默认配置见 `deploy/models.json`，当前因 Spark 不可用而暂选 Claude CLI；此配置不表示 Spark 服务已改用 CLI。恢复 Spark 部署时，用 `INRESEARCH_MODEL_CONFIG` 指向本机 JSON，将 `research_default` 设为 `spark` 并核对地址；型号、路由、预算及能力按 [08 模型执行](../../framework/08_model_execution.md)。实际响应必须匹配所选型号，失败不换模型兜底。

```bash
python3 ~/code/inresearch.ai/manage.py reader init
bash ~/code/inresearch.ai/deploy/spark-reader/install.sh
```

安装器创建不存在的配置文件、运行目录并安装启用用户 unit；不默认启动。配置已有时原样保留。修改本机 `reader.env` 后再运行 `systemctl --user start inresearch-reader.service`；以后更新用 `restart`。不要把 env 内容贴入日志。用户退出后继续运行需要该用户 `Linger=yes`；可用 `loginctl show-user "$USER" -p Linger` 只读检查，由部署任务处理是否启用。

真模型 smoke 使用**系统临时目录**，不会混入正式来源台账：

```bash
reader_smoke="$(mktemp -d -t inresearch-reader-smoke.XXXXXX)"
python3 ~/code/inresearch.ai/manage.py reader \
  --data-root "$reader_smoke/data" --state-root "$reader_smoke/state" \
  --stable-seconds 0 init
printf '%s\n' '服务器由处理器、内存、存储及网络接口组成。运行需要供电与散热。' \
  > "$reader_smoke/data/raw-materials/smoke.txt"
python3 ~/code/inresearch.ai/manage.py reader \
  --data-root "$reader_smoke/data" --state-root "$reader_smoke/state" \
  --stable-seconds 0 run --once
python3 ~/code/inresearch.ai/manage.py reader \
  --data-root "$reader_smoke/data" --state-root "$reader_smoke/state" \
  export --dest "$reader_smoke/snapshot.json"
```

这个短 txt 只产生一块，依次 3 次当前配置模型的真实调用（粗读、块深读、综合）及 6 个任务（包括接收副本归档）；冷加载时间由模型服务决定。默认每次 HTTP 900 秒，模型输出受结构化 JSON 与引文校验；有限重试可能使一次 smoke 保持 pending/failed，应检查真实错误码，不能把退出命令当完成证明。验收需看到 `counts.complete=1`、成对 coverage 相等、candidate 输出与实际 model。随后加文本 PDF、扫描 PDF 小样本验证实际 Poppler/OCR 环境。

正式单块最多 6000 字符且最多 12000 UTF-8 字节，页内分块不丢字符；ID 候选上下文限 4800 字节；综合批次约 15000 字节并分层缩减，输入/输出均留上下文余量。上下文和输出上限来自模型配置；输入超过预算明确阻塞，不静默截断。HTTP 调用时不持有 SQLite 写事务，因此发布器可读取快照。

## 统一配置与更换型号

默认 JSON 只有 `research_default` 与可选 `ocr` 角色，角色引用 `profiles` 中的配置。复制到本机配置目录后修改；不在各业务脚本中填写型号。旧 reader 的 CLI 参数优先于 READER 环境变量，后者优先于 JSON。从旧 env 迁移时移除已转入 JSON 的覆盖项；安装器保留原有配置，不替用户自动覆盖。

M4 上的共享入口也读取 `INRESEARCH_MODEL_CONFIG`。暂用 Claude CLI 时，在 M4 本机验证 CLI 登录、代理环境及 `python3 manage.py models --probe`。后续切换 Spark 档案时，将 `profile.url` 设为实际可达的 Spark 推理地址或本机到 Spark 的转发地址；`127.0.0.1` 只指执行机器本身。此代码变更不会自动建立网络转发或开放端口。

OCR 在同一文件内新增视觉 profile（`capabilities: ["vision_json"]`），将 `roles.ocr` 指向它。视觉适配当前支持 Ollama；旧 `READER_OCR_MODEL` 保留兼容。模型 revision 是冻结配置中的可选版本标识，不冒充服务端已验证的权重摘要。

修改配置后重启对应进程。新型号先按上面的隔离 smoke 验证实际模型、阅读覆盖与候选；同模型名称但权重改变时应更新 revision。已有任务不混用新旧配置；已完成结果保持不变。

## 日常运行与恢复

```bash
systemctl --user status inresearch-reader.service --no-pager
journalctl --user -u inresearch-reader.service -n 40 --no-pager
python3 ~/code/inresearch.ai/manage.py reader status
```

状态为 `idle/running/degraded`，另列每阶段数量、最老等待任务和错误码。`idle` 可能有退避中的重试或等待稳定的新文件，不能解释为全库已读完。状态中不记录模型响应正文、HTTP 凭据或异常响应体。

每轮最多入库 32 个稳定文件，扫描默认间隔 10 秒；文件须在连续扫描中稳定至少 60 秒。忽略 partial/隐藏文件及符号链接，入库读取前后检查 stat，并重新核对哈希；跨目录路径不允许逃出管理根目录。写原件后模型失败只重试阅读，不反复归档。原件复制与台账之间中断后，下次按内容寻址核对再登记；不会覆盖同名资料。

任务至少一次执行：领取即记录 attempts，进程中断后 running 回到 pending；已经原子写入的块/综合 checkpoint 可直接复用。模型响应尚未持久化时中断，恢复后该块可能再次推理。每任务最多 3 次，退避 30/60/120 秒；达到上限进入 failed，不无限压住队列。不可提取、路径/哈希不安全和 OCR 缺失进入 blocked。任一正文块未成功就不会综合为完成；其他文档继续处理。每 4 次调度至少 1 次取最老可运行任务，低分只影响先后。

重试或回滚需先停 worker，避免修改其运行中状态：

```bash
systemctl --user stop inresearch-reader.service
python3 ~/code/inresearch.ai/manage.py reader retry --doc-id doc-完整哈希
python3 ~/code/inresearch.ai/manage.py reader rollback --doc-id doc-完整哈希
systemctl --user start inresearch-reader.service
```

`retry` 不带 doc-id 会重试全部 failed/blocked，仅在已修复原因时使用。`rollback` 只移除台账中与原件相符的 library 符号链接，不删除原件、raw、阅读结果或来源链；已回滚的操作不会在启动时自动重建。崩溃前处于 prepared 的改名，或正常 committed 但丢失的视图，可从操作台账恢复。目标被用户文件占用/指向别处时转 needs_review，绝不覆盖。修正占位冲突后可 retry organize 任务。

一份材料只维护一套有效阅读结果；更换默认模型只影响新任务，已完成材料不会重读。执行配方冻结 backend/model/context、输出预算、请求路由、可选 revision、分块和注册表快照；旧配方补齐默认值后兼容本次升级。已有任务的推理配置不符时仍阻塞，恢复匹配配置后可 retry；自动选择旧配置和显式重读替换命令在后续实现，不能用删除台账来重读。可在同一配方追加已明确配置的 OCR 能力，逐页记录实际视觉模型，retry 从已保存页继续。

## 并发与吞吐

- **队列所有权不变**：仍然只有一个进程持有 catalog 锁，中断任务回收与对账仍只发生一次；第二个进程照旧报 `another_worker_owns_queue`。多线程只发生在这一个进程内部。
- `READER_WORKERS`（默认 `1`，上限 16）设定该进程内的工作线程数。每个线程持有自己的 SQLite 连接，领取任务用 `BEGIN IMMEDIATE`，同一任务不会被领两次；`--workers N` 可在命令行覆盖。扫描与入库仍留在持锁线程，保持单写入者。
- 共享推理客户端的 `max_parallel`（默认 2）另行限制同时请求数；它不是跨进程全局限流。
- **改大线程数之前先放开 Ollama 服务端**。Ollama 默认串行处理请求，客户端并发只会堆在服务端队列里。需在 Ollama 服务上设 `OLLAMA_NUM_PARALLEL` 不小于 `READER_WORKERS`，并确认「并发请求数 × `num_ctx`」的 KV 缓存仍放得进显存，否则会触发换出，反而更慢。27B、32k 上下文下先从 2 起步，用 `ollama ps` 与 `status.json` 的处理速率核对后再加。
- 任一线程抛出未预期异常会停下整个 run 并向上抛出，与原先单线程一致，不会留下半跑状态。

修改后需重启服务生效：

```bash
systemctl --user restart inresearch-reader.service
```

## 格式与质量边界

- `.txt/.md/.csv/.tsv` 支持 UTF-8/UTF-8 BOM；其他编码或二进制内容明确阻塞。
- **M4 分担 OCR（2026-09-08 起，契约）**。M4 可对被阻塞的 OCR 页在本机跑视觉双读，把结果放到 Spark 的 `~/.local/share/inresearch.ai/offload/m4/results/<doc_id>/pages/<六位页号>.json`；M4 永不写台账。结果 JSON 必须带 `doc_id`、`content_sha256`（等于文档 SHA256）、`page_index`、`method="m4_vision_ocr_double_pass"`、`text`、`text_second_pass`、`ocr_model`、`blank=false`、`unreadable=false`、`verification`。哈希或页号对不上按完整性错误处理；两遍数字不一致阻塞 `m4_offload_numbers_disagree`。有 M4 结果的页不走排后、不计本地 OCR 预算、不受幅面限制；没有结果时本地路径照旧。视觉模型请求显式 `think=false`，回复正文为空时才接受 thinking 字段里的 JSON，其余仍按结构化校验拒绝。
- **OCR 排后、限量、不读图纸（2026-09-08 起）**。同一文档首次遇到需要 OCR 的页时不立即 OCR，而是把该文档优先级降为 `1` 并退回队列（`ocr_deferred_behind_text_documents`，不计尝试次数，默认 `READER_OCR_DEFER_SECONDS=300` 秒后可再领取），让有文字层的文档先读完；已抽取的文字页保留缓存。每篇文档 OCR 页数上限 `READER_OCR_MAX_PAGES`（默认 20），超出即阻塞 `ocr_page_budget_exceeded`，放大预算后 `retry` 从已存页继续。页幅短边 ≥ `READER_LARGE_FORMAT_POINTS`（默认 1150 pt，即 A2 及以上）的栅格页判为图纸，不送 OCR，阻塞 `large_format_page_requires_drawing_workflow`，原件照旧保留，等专门的图纸流程。视觉模型返回无法解析的输出按页面属性处理，阻塞 `ocr_output_invalid`，不再重渲染重读三次。这四条的依据：2026-09-06 批次两天只抽取成功 99 篇，时间全耗在 391 份 A0/A1 施工图的双读 OCR 与重试上。
- PDF 逐页提取；空文本、坏字符或检测到大型栅格图像的页走 OCR。OCR 未配置、不可读、双读空白判断或数字不一致时阻塞。启用例如 `READER_OCR_MODEL=qwen3-vl:8b` 前应核对实际安装模型；当前实现使用两次视觉提取，保存两份文本和模型记录。双读一致不是正确性证明。矢量图表、复杂排版与文字层质量仍须审阅，不能把处理覆盖率当视觉语义验收。
- `.docx/.pptx/.xlsx`、旧 Office、压缩包与其他格式目前为明确 unsupported。原包仍安全入库保留，不假称已深读。经批准转换/拆包后可投递独立文本/PDF，并另行登记父包关系；当前版本不自动拆包，也不声称已把复合 PDF 分成独立文章。
- 本服务提供候选阅读与粗分，不执行文件里出现的指令，不运行文档宏，也不自动修改 core facts。深读输出仅从已提供正文引用证据；所有正文块都送入模型，但摘要与候选引用不能替代原文复核。

## 备份与恢复验证

14 天基础设施任务队列不是本服务的档案层。catalog、originals、intake-receipts、artifacts 与 extracted 均无自动 TTL。本版 backup 使用 SQLite 在线快照，复制该快照引用的原件、接收副本、隔离保留件与成果，输出 SHA256 清单；未完成备份保留 `backup.partial.json`，不能作为完整恢复点。建议以同一用户权限写入独立磁盘/另一机器，执行后验证清单，再登记其物理位置；同盘备份不抵御整盘故障。

```bash
python3 ~/code/inresearch.ai/manage.py reader backup --dest /已准备好的独立存储/reader-20260906
```

目标必须不存在且在运行 data/state 之外。备份包含已登记原件；尚未稳定/入库的 raw 投料不包含在 catalog 备份中，投料来源应继续保留或单独备份。不要直接复制运行中的 `catalog.sqlite` 而漏掉 WAL。

恢复先停止 worker 和发布器，在**新的空目录**校验 manifest 的 catalog/file 哈希；将备份根 `catalog.sqlite` 放入新根 `catalog/catalog.sqlite`，将 originals/intake-receipts/artifacts/extracted 及清单中接收隔离件保持相对路径复制，初始化新 state。以相同 backend/model 和源码配方启动：running 任务重领，prepared 接收归档/视图操作恢复，缺失的 committed library 链接重建；来源根路径由新 data 根重定位。读完的原件不应重新投递来代替恢复 catalog。恢复 smoke 完成、文档/来源数和哈希对账后再安排正式路径切换，旧数据及失败备份保留。自动恢复 CLI、跨模型重新处理与独立文章拆分尚未实现，不能在验收报告中记为完成。

测试命令：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p test_continuous_reader.py -v
```

测试只在系统临时目录通过注入模型验证状态与证据契约，不提供生产 fake 参数。真实推理和实际部署需单独验收并留存运行记录。

## 已部署发布器与后续源码更新

2026-09-06 已在真实 Spark 启用 reader、`Linger=yes`、`qwen3-vl:8b` OCR 和五分钟发布器。主站实际收到候选快照；验收版本与边界见 `docs/reviews/2026-09-06/IMPLEMENTATION.md`。生产目录等待用户投料，测试文档不入生产库。

发布器定义在 `deploy/spark-reader/inresearch-reader-publish.service` 与 `.timer`。它加载 `~/.config/inresearch.ai/reader.env` 和 `publish.env`，使用 `~/.local/state/inresearch.ai/reader-sync.token`（0600）向 HTTPS 主站提交候选。主站 token 文件为 `/srv/inresearch.ai/data/.reader_sync_token`，与用户登录权限分离。配置 `READER_RELEASE` 记录本次已安装的 Git SHA，源码更新后同步修改并重启 reader；不能仅修改这个标签冒充发布。

```bash
systemctl --user status inresearch-reader-publish.timer --no-pager
systemctl --user start inresearch-reader-publish.service
cat ~/.local/state/inresearch.ai/publish-status.json
```

首次源码由 m5 对 GitHub main 核对 SHA 后以 Git bundle 传入，在规范目录初始化完整 Git checkout。Spark 没有保存通用 GitHub token；后续可从已认证 m5 生成 main 的 bundle，传到 Spark 并 fetch。更新前核对当前源码无未提交/未跟踪文件，停止 reader，在 main 上 `git merge --ff-only` 已验证远端 SHA，再安装版本化 units、更新 release 配置并重启。不要 reset/stash/覆盖 dirty 工作区，也不要 rsync 覆盖正在执行的源码。

主站按 infra 的正式整体发布流程跟随 GitHub main；不能为提速旁路其部署锁、数据库保护或发布提交。Web 快照是派生副本，不代替 Spark 永久台账和原件备份。
