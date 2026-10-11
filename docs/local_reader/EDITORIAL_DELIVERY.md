# 文章与日报研究素材接收

用户持续授权已经完成的文章与日报进入 inresearch.ai 研究流程，不逐篇重问。2026-10-11 明确职责：写作、配图、制作、发布及生产端封装和发送全部归 inews.today；InResearch 负责接收、核验、阅读、正式采用和既有内容展示。

写作唯一入口为 [inews.today 编辑规则](https://github.com/niuroumiantt/inews.today/blob/main/docs/editorial/README.md)，共同要求见 [文风与配图总则](https://github.com/niuroumiantt/inews.today/blob/main/docs/editorial/style-and-figures.md)；三类产品分别见 [微信日报](https://github.com/niuroumiantt/inews.today/blob/main/docs/geluoke-daily-delivery.md)、[网站专栏](https://github.com/niuroumiantt/inews.today/blob/main/docs/columns.md)、[研究报告](https://github.com/niuroumiantt/inews.today/blob/main/docs/editorial/research-report.md)。本文件只规定研究接收，不规定文章长度、章数、首图风格、图片数量或制作工具。旧制作代码与独立写作规则已退役；历史文章、图片、提示词、原始材料和回执保留作追溯，不作为现行制作标准。

## 谁决定研究排队与插队

用户决定研究事项的轻重缓急。说“排队”就按普通顺序处理；说“插队”“优先处理”就将点名主题及其来源置于优先通道；说“不需要排队、直接上线”就立即推进已具备条件的研究发布步骤，不等无关主题清空，不要求重复授权。未点名项目保留原顺序；最新指令优先。

沿用一个审核队列和一个研究发布队列所有者。已领取任务保留归属，下一次领取或创建发布包时应用优先级，不另开竞争 worker。原件、全文阅读、来源核验、C3、必过 CI 和实际网站回执分别如实记录；优先级不表示这些步骤完成。缺材料或校验失败时说明具体缺口，先推进同专题已具备条件的项。

运行入口见 [Spark 操作指南的来源偏好](SPARK_OPERATIONS.md)：审核 `work --preferred-sources <文件>` 每轮读取用户点名来源；发布器的 `preferred_sources` 指向同一文件，`ready --preferred-sources <文件>` 将当前完整封存版本的已审核批次排前，同通道保留原序。下一轮应用文件变更，不改变来源身份、状态、重试预算或已持有的发布日志。

## 三个研究接收入口

- **公开网站专栏 feed**：Spark 的 `inresearch-editorial.timer` 每五分钟运行 `editorial-sync`，读取 inews 的 `/api/feeds/columns`。它是接收任务，不是写作任务。使用与读者页相同的可见条件；草稿、退回稿、内部全文与本机路径不导出。每轮从第一页开始，较早文章的修订也可接收；只接收本站自有正文与引用指针。
- **已完成研究报告或长文包**：inews 制作端按其现行规则验收并封装 `editorial-delivery-v1`。InResearch 用 `manage.py editorial-sync --bundle <manifest>` 接收 `article.md`、`sources.json` 和可选 `research.txt`。生产端 outbox 与发送任务已迁出本仓库；接收器不以三版 HTML、六章、母版或固定图数作为入库条件，也不替生产端声称成稿已验收。
- **微信日报研究包**：沿用 `manage.py daily-receive --input <目录>` 和既有 `research-delivery.json` 契约，核对 HTML、来源及可选研究侧车的身份和完整性。日报生产与发布在 inews；接收不生成新日报，也不直接改正式容量。

## 身份、完整性与研究阶段

文章包检查 UTF-8 正文、身份、来源 URL、路径、大小及实际 SHA，再调用现有 research-match。包内文件1–10个，单文件及正文不超过4 MiB，引用目录最多500条；这些是接收范围限制，不是文章配图数量要求。记录文章标识、内容版本、正文 SHA、引用目录、真实接收时间及回执；相同内容/版本重放不重复索引，改稿保留旧版。

阅读范围在稳定锁下追加文档，保留旧条目和日报配置；破损范围拒绝扩队列、修复后重试。与 Reader 共用最多10,000文档、存储不超过1 MiB的 read_scope；范围已满时旧 SHA 重放仍幂等，新 SHA 明确返回 `reader_scope_full`。

文章正文标为 `authored_analysis`。引用目录中的一手材料保留机构、原网址、发表日期、抓取状态、SHA和阅读范围；链接不表示原件已收到、全文已读或说法已证实。引用指针标为供应方提供、未独立核验；文章与其原件不重复计为独立证据。原件沿现行来源归属和交付流程接收，全文阅读、C3和正式采用独立执行；日期新不自动覆盖旧事实。

暂未出现在公开分页不等于撤稿，不删历史原件或撤销事实；v1不自动推断撤稿，明确撤回须独立登记。只有成功 SHA 核对与接收回执才能称“已送到”；匹配不代表已读或已采用。文章回执在 `material-reviews/editorial-deliveries.json`，最新 feed 同步在状态目录 `editorial-sync/latest.json`；日报使用既有独立接收回执。

## 验收边界

接收测试覆盖公开稿筛选、旧稿修订、分页、字段隔离、篡改、作者身份、去重、范围保留和失败恢复。职责边界测试防止本仓库重新引入文章制作脚本，并保留接收和研究 UI 图册入口。源码与测试通过不证明定时器已切换、生产端已迁移运行或网站已发布；这些另记实际版本和运行回执。

此链路不做文章创作、事实最终审定、版权判定或微信发布。现有文章展示、原始材料、研究数据和研究 UI 白底技术图册不随职责迁移删除。


## 合并与任务切换顺序

1. 先合并并验证 inews 的规则、文章生产与新发送端。
2. 在真实运行机器执行 inews 的显式迁移安装器，将旧 worker 切到新源码；保留既有队列、状态与服务身份，核对启用状态和实际回执。
3. 只有完成上述切换后，才能合并本仓库删除旧生产端脚本的变更，避免旧任务继续引用已删除路径。

当前没有实际运行机器执行能力，旧任务尚未确认切换；此PR保持待审，不以规则URL或源码提交代替运行迁移。具体私有安装参数只在生产仓库和运行环境处理。
