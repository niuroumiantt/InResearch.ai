# 首批阅读候选正式采用交接（2026-10-07，m5）

## 目标与已授权范围

用户同意以20–30条为首批推进B档独立复审、采用与网站发布；A档整理为所有者决策卡。沿现行01/04标准，不降低原评分绕过A，不恢复OCR默认策略，不覆盖其他活跃任务或重启共享Reader。

## 完成的研究记录

从四篇已封存候选中选30条：Rubin CPX25条（原重要度7），HBM5条（原重要度8）。模型实际复审后，19条B档采用、8条A档待所有者、2条重复、1条背景。背景条仍保留7分，不沿用模型误标的C档。A档包括HBM5条与Rubin3条；重复指向未采用A项时仍保持候选。

正式表新增1份来源文档、20条证据、19条有条件作者陈述；采用时点及来源时点分开。原件为2025-09-10的SemiAnalysis Rubin报告，SHA256 `c30e5c58d0b04df766c1481c6f55659cde21f62ad41dfb1fbcf07193260a9294`，阅读版本 `rev-438b89f9fbb74619804c42a12326e76d`，封存报告摘要 `cac6f68714fa3c51032e9cbdcadbd38d7bf8876ba4f88bff310e0b1efa30e12b`。保留原候选ID；限定后的陈述使用独立采用ID，避免与运行候选相同ID/不同文字冲突。

19条均经配置的core_review真实模型调用及主会话逐原页核验；固定候选集合按SHA256(batch_id|candidate_id)取ceil(10%)，实际2条复核通过（chunk17 claim5/7，原件18页及19页继续句）。代词回指及同硬件标题补齐明确证据，跨页条件留在限制。原始请求/输出、失败及发布修订保留。CLI显式请求gpt-6.1-sol；provider实际身份未报告，actual=null，不称认证模型身份。

全部采用是有时点、明确归属和限制的author_claim；不认证普遍规律、2026量产状态、数值性能或商业利用率。不改价格/GW/模型输入及旧Finding，不新增正式answer，研究问题关闭增量0。Rubin29、HBM6及EDA17/34真实缺页保留，采用条目不依赖它们；来源处理覆盖完整不代表全部图片已核验。

## 证据、检查与发布入口

- 正式源码：`data/research_knowledge.json`；研究规则未变；节点页增加准确状态标签和按需采用详情，摘要仍不含正文/引句。verification_contract已复审展示要求、实际测试与未覆盖项。治理清单随数据与交接刷新。
- 私有数据：M5 `~/.local/share/inresearch.ai/reading-adoption/2026-10-07-first-batch/`；脚本/日志在 `~/.local/state/inresearch.ai/reading-adoption-first-batch-20261007/`。
- Spark永久复审包：`/home/spark/.local/share/inresearch.ai/material-reviews/reading-adoption/2026-10-07-first-batch/review-20261007T110330Z/review-package.tar.gz`，53文件、375765字节，SHA256 `066d9f7d46ec57d652019468301ca4e16c599465848fcfa29cada44648a702c7`，已核对传输摘要。同目录manifest逐文件登记；原件、旧OCR证据与候选版本保留。
- `formal-write-receipt.json`、`operator-audit.json`、`batch-dispositions.json`保存完整采用ID、抽样与逐项去向；`owner-decisions.md/json`保存8张A卡及原文依据，保持私有，不把受限原文决策包另设公开下载页。
- 已完成本地governance check、严格数据校验、registry及research/report_model测试。研究摘要/节点页浏览器回归覆盖状态、按需请求、失败重试、转义与窄屏。PR #348四项CI通过，合并4e6cd65b且AWS健康；正式文件/API19条核对通过。生产详情发现全量接口约60MB，后续修正为当前节点的curated采用详情与支持闭包，无runtime/catalog及私有路径；新增HTTP/权限/撤回与浏览器回归通过。最终CI及页面回执以私有发布包为准，不把源码交接当上线证明。
- 线上入口：[全部19条采用陈述](https://inresearch.ai/node.html?id=root#evidence)、[GPU陈述](https://inresearch.ai/node.html?id=part%3Agpu)、[HBM陈述](https://inresearch.ai/node.html?id=part%3Ahbm)。`website-ui-proof.json`、`deployment-proof.json`和Spark delivery归档回执保存实际API逐记录/支持链及页面验收，原件页码从0起始转换展示。

## 待所有者决定

8条A档暂不采用。01§4规定原评分≥8、真实冲突或改写旧结论需所有者；本次没有将其记成所有者本人审阅，也未获具名A代理采用委托。先看私有决策卡，按条选择采用限定观点、暂缓或另行委托；改写既有结论与放宽分发限制仍须所有者决定。后续使用当前规范，不从本交接扩大授权。
