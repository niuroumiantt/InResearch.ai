# 四篇 PDF OCR 缺页救援交接（2026-10-07，m5）

## 目标与已定边界

补读 HBM 4/5/6、TSMC 7/8/9、Rubin CPX 15/16/29、EDA 17/22/34 共 12 个实际缺页，受控接收后让 Spark 完成全文候选并核对网站快照。原件、旧缺页和所有复读保留；不影响 M4 的另一批 28 份 PDF，不重置原文版本，不自动采用 C3、项目或 GW。

## 实现阶段已完成

- [PR #341](https://github.com/niuroumiantt/InResearch.ai/pull/341) 已合并，提交 `35837f0b98c2f559fb5748e21317f732386220de`。发现入口覆盖原生缺页缓存；接收验证原件身份、完整原始嵌入图像集合、缩放/旋转输入哈希、独立双读、数字一致与正文装配，归档旧缓存后先原子安装成功页，再通知 Reader。正文已封存或成功页不可替换。未直接写运行 catalog。
- 原始嵌入图像有 81 个出现位置（80 个唯一图像）；先保留原生读取，再将原始像素放大复读。TSMC PDF 视口裁掉的表格行按完整原始嵌入图像补读，来源范围在页缓存明确标注。HBM 第 4 页一个竖排标签另保留旋转复读与先前冲突，未静默覆盖历史。
- 249 项相关测试、治理校验、严格数据校验、注册表校验通过；四组 CI 通过。Spark 救援工作树的 24 项缺页测试通过。后续核对发现 matching 引句将 Reader 从 1 开始的页码再次加一；已修正，并以第 17 页夹具通过供应中心浏览器回归。
- 网站镜像已核对为 `inresearch-app:35837f0b98c2f559fb5748e21317f732386220de`，健康检查通过。Spark 源码已快进同一提交，旧 Reader 进程尚需在不丢 checkpoint 的前提下完成版本切换；源码版本不能冒充运行进程版本。

## 运行阶段（待补齐最终验收）

- Spark 已接收 HBM 4/5 与 TSMC 7/8/9，保留原提取 revision，分别重新提取为 34 页/33 块与 18 页/17 块。HBM 第 6 页 Micron HBM3E 图像的三次放大读取均声明存在不可读内容，保持真实缺页。
- Rubin 15/16 已核验，29 的全部图像仍在处理；EDA 三页待处理。不得把单一区域成功或重新排队计为全文完成。
- 网站真实登录后读取 `/api/supply`，16:06:56 的接收快照尚无四篇的完成报告。全文候选、当前 Reader 状态与网站接收时间需最终逐份复核。

## 入口与下一步

1. M5 私有任务目录：`~/.local/state/inresearch.ai/ocr-gap-rescue-four-20261007/`。`read-regions.py` 是两槽视觉复读任务；`assemble-results.py` 验证全部图像后装配成功页；`submit-results.py <SHA前8位>` 经 Spark 独立源码工作树执行受控 `gap_ocr --receive`，不得重接已封存篇。
2. `sample-progress.py` 以只读 catalog 更新 `~/.local/state/inresearch.ai/hourly-progress/ocr-gap-rescue-four-progress-20261007.json`。原始快照文件保留。完成复读后用 `archive-evidence.py` 把全部成功/失败读取、输入图像、历史及哈希清单归档至 Spark 的 `offload/ocr-rescue-four-20261007/<时间戳>/` 并核对传输哈希。
3. Spark 永久原件、数据库、缓存和候选在 `~/.local/share/inresearch.ai/`，只通过 Reader/受控接收入口推进。最终核对四篇当前报告、manifest、完整覆盖、剩余缺页及实际模型，导出候选，等待网站真实快照收到。
4. `website-sample.py` 使用服务器既有凭据内存登录，不输出凭据；完整网站响应保存在 AWS `/var/tmp/inresearch-ocr-gap-rescue-four-website.json`，M5 仅取四篇与接收状态的摘要，避免 9 MB 响应经日志管道阻塞。

## 待用户决定

无新增审批。已授权的补读、修复、接收、候选交付与部署继续执行；真实不可读项如实交付，不伪造识别成功。
