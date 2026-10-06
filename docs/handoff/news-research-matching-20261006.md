# 新闻与研究材料匹配交接（2026-10-06，m5）

## 目标与已定规则

日报正文、iNews 线索和用户报告服务于现行三级账、四问、五类变量、六队；需求以 tco_targets 为唯一任务书。原件/版本/冲突保留；全文索引、深读、身份复核、C3 采用分别计量。新角度先提出在现有骨架的位置与理由，骨架改变须讨论。主工作区与历史 worktree 不覆盖、不清理。

## 本轮实现与验证

- 已实现：固定源新闻档案回放、完整计数、容量口径/水电审批/身份候选；日报按节登记原文与版本；PDF 页码候选索引、现行需求队列及内部匹配页；收件箱接收后自动索引；按节点/变量类回查 SHA 原件。
- Spark 阅读对齐：新版本冻结目标 SHA、节点/问题、变量类、六队与模型输入；命中缺口初始优先级 7，主输入 8；新版本节点分类取代强制旧模块分类。旧配方/产物/停放保留，最老合格任务仍每四次得到一次份额。原件路径不迁移。
- 验收：严格数据校验 0 warnings、registry 344 对象/458 问题；相关浏览器 supply/industry/datacenter_news 通过；全套 1678 项单元与治理通过；PR CI 以最终 PR 为准。版本 2026.10.06.1，04/06 替代链与显式验收映射一并提交。
- 部署前实际清点：Spark 35,917 个内容身份/87,044 来源观察；阅读 complete=2，仅 M01.md/M03.md 内部文件，不能称研报已消化；其余 blocked=24,209、queued=11,699、failed=7。停放、CAD/图纸、OCR 与真实故障不能混算。

## 原件、数据库与入口

M5 的日报和 SemiAnalysis 来源目录均保留；已复制、逐文件校验到 Spark `~/.local/share/inresearch.ai/incoming/m5-research-20261006/{daily-html,semianalysis}`，约 1.3GB。清单/私有回执在 M5 `~/.local/share/inresearch.ai/material-reviews/`，不进 Git。

Spark 主数据根为 `~/.local/share/inresearch.ai/`：供给库 `acquisition/catalog.sqlite` 与 `acquisition/blobs`；日报事件/解析历史/身份复核 `acquisition/daily-events.json`；Reader `catalog/catalog.sqlite`、`originals`、`extracted`、`artifacts`；候选视图 `library/candidates-by-node/<节点>/variable-N/`，新全文主链接 `library/by-node/`。JSON 账纳入采集备份，但不声称跨库单一瞬时备份或异机全产物恢复已验证。

网站登录后 `/supply.html#matching` 查看需求、报告页码、讨论提示、日报事件与阅读状态；`/projects.html?view=pipeline` 查看新闻。匿名新闻 API 不公开内部报告。正式项目/事实/价格仍在研究登记中，未核实候选不进入 GW 合计。95GW 为汇丰报告的 2025 全球 IT 负载估算，205GW 为 2030 预测，不能冒充本轮新闻普查。

## 接续与尚未覆盖

按 `docs/local_reader/ACQUISITION_OPERATIONS.md` 接收本批 71 PDF/61 日报版本（排除目录/说明），回放新闻、升级 Spark 干净源码并核对服务/发布与网站版本。实际生产数量、SHA、错误和发布回执保存到私有 material-reviews；Git 实现通过不代表部署完成。

现行 iNews 接口提供事件卡，没有已验证的日报 HTML 全文自动交换口；用户上传正文已接入接收索引。许多日报引用只含媒体名、缺原链接，须补原文定位；新园区消歧、全球投运/在建容量普查、全面语义新观点发现、图表阅读与 C3 核验尚未完成。旧 35,917 内容身份未全库按新需求重读，不无差别解除停放。待讨论角度目前包含有效吞吐、动态电网负载、scale-up 互连与现场供能；候选词检不是完整新角度研究。
