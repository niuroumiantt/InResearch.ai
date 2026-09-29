# Fetchspec 配合 inresearch.ai 新骨架重构交接（2026-09-29）

## 用户当前决定

新开独立任务整理 `fetchspec` 仓库。目标不是继续给旧爬虫打补丁，而是以
`inresearch.ai` 当前骨架、目标清单和供应契约为上游需求，重新审计并设计 Fetchspec，
使它稳定承担厂商产品身份、产品地图、官方规格载体、结构化参数和版本变化的发现、保存、
提取、交付及回执闭环。

本交接是任务上下文，不替代 `framework/` 的现行规范。新任务开始时必须再次同步两个仓库并
读取现行源；2026-09-29 的系统检查是审计材料，不是自动采用的规范。

## inresearch.ai 当前约束

- 当前研究骨架是一棵树、三级账、四问四段、五类变量、六队、一个节点模板；Fetchspec 是六队
  中负责厂商规格的一队，`inresearch.ai` 自身不实施爬取。
- 任务权威来自 `framework/tco_targets.json`，只领取 `team == "fetchspec"` 的目标。2026-09-29
  快照共有 351 条目标，其中 Fetchspec 130 条：6 sourced、124 needed。数量会变化，代码不得写死。
- `framework/supply_contract.json` 是供应与交付契约；inresearch 接收端已经支持 Fetchspec package
  v2.0：批次或逐文件携带 `target_ids`，接收前验证目标存在且属于 Fetchspec，并解析 `part_ids`。
- 目标是需求，产品规格是候选资料，正式研究事实必须经过提取、定位、口径核验和采用；Fetchspec
  不得直接写正式事实或把“收到文件”冒充“完成研究”。
- HTML、PDF、Office 文件是可追溯载体，不是最终产品。应先建立官方产品身份和产品地图，再按产品
  寻找最可靠、最易确定性解析的官方页面或附件，保存来源快照、SHA、语言、版本及适用型号。
- 英文和中文为当前需要的语言。优先原生 HTML 表格、JSON/结构化页面及原生 PDF 文本；只有不存在
  更好来源时才用 OCR 或模型补充，并记录方法与不确定性。
- 日常更新不是无界全站重爬：比较本地产品地图、官方目录/产品 sitemap、已知来源状态和内容哈希，
  只抓新增或变化；同字节去重，变更版本并存，局部消失不能自动判定停产。
- NVIDIA 当前是端到端样板：线上产品地图 595 项，237 个具体型号中 235 个已有规格；页面按需读取
  单项详情。它证明“产品身份 → 官方载体 → 参数表 → 数据库/CSV → inresearch 展示”可行，但不代表
  Fetchspec 整体架构已经收口。

应先读：

1. `inresearch.ai/framework/CURRENT.md`
2. `inresearch.ai/framework/current_state.json`
3. `inresearch.ai/framework/00_overview.md`
4. `inresearch.ai/framework/03_bom_and_collaboration.md`
5. `inresearch.ai/framework/06_acquisition.md`
6. `inresearch.ai/framework/09_software_contracts.md`
7. `inresearch.ai/framework/supply_contract.json`
8. `inresearch.ai/framework/tco_targets.json`
9. `inresearch.ai/docs/reviews/2026-09-29/skeleton/README.md`（审计建议，不是规范）
10. `inresearch.ai/docs/handoff/nvidia-product-catalog.md`

## Fetchspec 仓库现场，禁止破坏

- 路径：`/Users/m5/code/fetchspec`；远程：`niuroumiantt/fetchspec`。
- 2026-09-29 检查时，远程 `origin/main` 为 `203f54a`（PR #42，NVIDIA HTML 型号规格）；本地
  `main` 停在 `ac8a00c`，落后约 62 个提交。
- 当前主工作区检出 `codex/supermicro-expand-sitemaps`，HEAD `c438b74`；对应远程分支已删除，工作区
  当时干净，但该提交和相邻 Supermicro 分支可能仍是本机唯一副本。
- 本机还有多组 Fetchspec 工作树和本地分支，包括 NVIDIA 产品目录、产品地图、PDF 规格提取、网络
  文档、交付包及 product-supply-pipeline。部分远程分支已删除，不能把它们当缓存清理。
- 新任务必须先执行只读盘点：工作树、dirty/untracked/ignored、分支相对 `origin/main` 的 unique commits、
  已合并 PR 和运行路径引用。不得 reset、stash、覆盖、切换现有主工作区，也不得删除旧工作树。
- 实施应从最新 `origin/main` 创建新的隔离工作树与 `codex/` 分支；只把经审计仍未进入 main 的有效
  逻辑迁入新设计，避免重新叠加历史分支。
- 原件和运行数据不进 Git。M5 NVIDIA 临时数据曾位于 `/Users/m5/Downloads/tempfetch`；任何现有
  `~/.local/share/fetchspec`、下载目录、交付台账和原始材料都可能是唯一副本，未经盘点不得迁移或删除。

## 新任务应完成的工程

1. **现状审计**：以最新远程 main 为基线，列清公共模块、站点适配器、NVIDIA/Supermicro 特化、交付
   实现、历史分支独有逻辑、测试与数据边界；判断保留、迁移、替代或归档，不能只写新方案。
2. **上游需求入口**：为 Fetchspec 增加明确的 inresearch 目标导入/同步层，读取契约和
   `team=fetchspec` 目标，生成本地任务快照；保存上游版本/摘要，拒绝未知目标和过期形状，不复制研究
   事实权威。
3. **产品驱动采集核心**：统一“公司 → 官方产品分类 → 系列/平台 → 具体型号 → 官方来源载体”的稳定
   身份图；sitemap 是变化候选，不是产品本身。提供 incremental、定向 refresh、人工复核和断点续跑。
4. **公共模块与站点适配器**：公共层负责请求政策、robots、节流、重试、内容寻址存储、URL/语言规范、
   frontier、版本/差异、表格提取、台账和交付；站点层只描述入口、分类、身份、动态页面和例外解析。
   以解决具体公司为优先，但禁止复制 200 套完整爬虫。
5. **确定性提取优先**：先找同一产品最易解析且最权威的官方页面，再依次尝试 HTML/JSON、原生 PDF、
   Office，最后才是 OCR/模型。参数保持厂商原表名、列、单位、典型/最大条件、脚注、配置和适用型号；
   另做可比较字段映射，不能覆盖原值。
6. **本地数据库与导出**：产品、产品关系、来源观察、字节版本、参数表、参数单元、变化、任务绑定、
   交付和错误分表；支持 CSV 导出、人工抽查、跨产品筛选。文件名变化与内容相同、URL 相同与内容变化、
   产品名不变与规格修订必须分别表达。
7. **交付闭环**：生产 v2.0 包并真实填充批次/逐文件 `target_ids`，带 SHA256、来源、语言、产品身份、
   版本和 supersedes；接收回执要能回到本地 ledger。需与 inresearch 共同设计“运行回执 → 作者 checkout
   导入 → Git 目标四态刷新”的可审核通道；当前 delivered 状态没有完整写回路径，不能宣称已闭环。
8. **样板迁移与验收**：先用 NVIDIA 迁移并保持现有 595 项产品地图及规格成果，再用 Supermicro 验证
   第二家公司是否只需小型适配器。测试重复运行、增量无变化、新增型号、同 URL 新版本、语言过滤、
   异常恢复、包校验、目标绑定、CSV 与 inresearch 接收。完成源码、文档、规范、测试、PR、合并与清理。

## 明确不做

- 不以“抓完整网站 URL”作为成功标准，也不把营销页、脚本文件或 sitemap URL 数量当产品数。
- 不重新下载内容哈希相同的文件；不覆盖历史版本；不因 URL/文件名变化就丢弃新观察。
- 不让 Spark 执行爬取。当前 M5 可完成 NVIDIA 样板的抓取、提取和交付；Spark 是否重新参与归档/阅读是
  后续部署选择，不应写死在采集核心。
- 不依赖模型通读所有文件来找固定规格；结构化规则先提取，模型用于表头映射、歧义和例外复核。
- 不清理旧分支、旧工作树或原件来“整理仓库”；先证明已合并、无唯一提交、无运行引用再另行清理。

## 完成定义

从一个当前 Fetchspec 目标出发，可以在新工作树中重复执行：读取目标 → 选择公司/产品范围 → 对比产品
地图 → 只抓新增/变化的官方来源 → 确定性提取规格并保留证据 → 查询数据库/导出 CSV → 生成带
`target_ids` 的 v2.0 包 → 被 inresearch 接收并关联 `part_ids` → 获取可追溯回执。NVIDIA 与 Supermicro
至少各通过一次；无变化重跑不重复保存字节，不丢历史，不直接写正式研究事实。
