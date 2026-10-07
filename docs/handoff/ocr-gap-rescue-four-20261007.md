# 四篇 PDF OCR 缺页救援交接（2026-10-07，m5）

## 完成交付与边界

点名的 12 个缺页已逐区域复读，8 页经受控接收补回；Spark 四篇全文阅读候选全部完成，实际网站快照于北京时间 2026-10-07 17:48:16 接收四篇。处理覆盖为 119/119 块、124/124 原件页、277,510/277,510 字符；处理完整不表示全部图片已辨读，也不代表语义审核或正式采用。四篇仍是 candidate，本任务 C3、项目及 GW 正式采用均为 0。

| 材料 / 原件 SHA 前缀 | 已补回的原件页 | 剩余真实缺页 | 完成覆盖（块 / 页） | 封存报告 SHA 前缀 |
|---|---|---|---|---|
| HBM / `138d2690` | 4、5 | 6 | 33 / 34 | `d9c353cd38a3b778` |
| TSMC / `72f5624b` | 7、8、9 | 无 | 17 / 18 | `86753c3172962c73` |
| Rubin CPX / `c30e5c58` | 15、16 | 29 | 30 / 31 | `cac6f68714fa3c51` |
| EDA / `c46a3585` | 22 | 17、34 | 39 / 41 | `72dd1d448291ccf5` |

HBM 6 的微小标签、EDA 17/34 的 GUI 小字经三次读取仍声明不可读；Rubin 29 成本表存在原件遮黑/截断，不能凭其他资料补造。网站保留缺页披露。原件 SHA、当前 revision、报告/manifest 完整性、8 个接收结果与当前缓存哈希链、网站逐字引句及覆盖字段已核对。网站知识索引从 0 起始；比对报告时加 1。

## 实现、测试与运行依据

- [PR #341](https://github.com/niuroumiantt/InResearch.ai/pull/341) 已合并：原生缺页发现、完整原始嵌入图像集核验、缩放/旋转输入哈希、独立双读、数字一致与正文装配；归档旧缓存后原子安装成功页，再通知 Reader，拒绝替换成功页或封存报告。未直接修改运行 catalog。
- 81 个图像出现位置（80 个唯一图像）保留全部原生、放大、失败和冲突读取。TSMC 按完整原始嵌入图像读取视口裁掉的表格行，页缓存明确来源范围；HBM 4 竖排标签保留旋转读取与先前冲突。接收只覆盖点名 8 页，另一批 28 份 PDF 未由本任务重置或迁移。
- [PR #342](https://github.com/niuroumiantt/InResearch.ai/pull/342) 的初步交接及页码判断在此替代：此前错误地取消网页加 1。现按正式 02 知识格式恢复 **Reader 报告 1 起始 → reader_export 唯一转换为 0 起始 → 供应投影原样保留 → 网页加 1 展示**；不重写封存报告。导出到供应投影的真实边界测试及浏览器第 1/17 页显示回归均通过。
- OCR 实现阶段 249 项相关测试及 Spark 24 项缺页测试通过；收口阶段 8 项供应测试、供应浏览器回归、治理检查、严格数据校验及注册表校验通过。规范验收映射已实际复审、更正此前错误要求；未覆盖原文语义核验不变。
- 观察到共享部署 `68670b87989af5b2f4e6ead1a1af7387cfff1153` 已同时包含救援代码及另一任务的默认正文策略；Reader 17:32 启动后续跑完成四篇。本任务没有另行重启共享 Reader 或覆盖其配置。四篇保留原冻结视觉 revision；新材料按现行默认正文规则执行，不能从本交接恢复旧 OCR 默认规则。页码修正的实际网站镜像与脚本哈希另存最终发布回执，不以源码版本冒充运行版本。
- 模型记录为 CLI 显式请求 `gpt-6.1-sol`；provider 未报告实际身份，`actual=null` / `explicit_cli_request_not_provider_reported`，不作已认证模型身份声明。

## 原件、候选与证据入口

- [网站匹配页](https://inresearch.ai/supply.html?day=2026-10-07#matching)：实际接收四篇候选，原件路径保持内部权限。
- Spark 永久数据：`/home/spark/.local/share/inresearch.ai/`。原件、旧缓存、失败读取与不可变报告保留，不用已封存候选重接缺页，不直接写 SQL。
- 原始读取证据归档：`offload/ocr-rescue-four-20261007/20261007T083237Z/evidence-20261007T083237Z.tar.gz`，435 文件、85,381,895 字节，SHA256 `c0211a8702ed420959c19a60fcea5b939c3f410cda512974b40c77ebd7433677`，传输后已验哈希；同目录 manifest 保留逐文件清单。最终候选及发布回执单独保存在同一任务的 `final-delivery/`，不覆盖原始归档。
- M5 私有任务目录：`/Users/m5/.local/state/inresearch.ai/ocr-gap-rescue-four-20261007/`。`candidates/<SHA前8位>.json` 含四份完整正文/报告；统一候选快照 `candidates/four-candidate-snapshot.json` SHA256 `a642edfc9bcb298d97d3e09f4c2ef8f216a9953b5856e885f0aa28edc32dc9ee`（4 文档、1,058 证据、973 陈述），未用四篇子集替换全站快照。
- `final-audit.json`、`candidate-receipts.json`、`candidate-export-receipt.json`、`website-latest.json`、`deployment-proof.json` 与最终发布回执保存完整身份/时间/哈希；`website-sample.py` 在服务器内存登录，凭据不进日志。`final-audit.py` 比对网站 0 起始索引加 1 后的封存原文页号。
- 只读进展入口：`/Users/m5/.local/state/inresearch.ai/hourly-progress/ocr-gap-rescue-four-progress-20261007.json`，原始 supplied snapshot 留存。`sample-progress.py` 只读 catalog；所有模型工作已结束。`deploy-reader.py` 已禁止执行，避免覆盖共享的新部署。

## 后续

本轮已授权救援与候选交付完成，无新增审批。四个真实缺页随候选明确交付；进一步语义核验与正式采用沿现行 01/04 标准另行开展。以后读取当前规范，不从历史交接恢复旧规则。
