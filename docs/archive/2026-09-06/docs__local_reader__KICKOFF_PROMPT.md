> HISTORICAL — 已被替代。保存于 2026-09-06；下文是历史原文，不构成当前指令、授权或服务状态。现行入口：[当前基准](../../../framework/CURRENT.md)。

> **历史入口已废止（2026-09-06）。不要执行下文旧批次指令。** 现行永久 worker 见 `SPARK_OPERATIONS.md`、`PROJECT_BRIEF.md`，所有独立文章均须深读，原件与账本永久保留。以下仅留作历史记录。

# 本地项目启动指令（复制给本地模型/本地 Claude Code 即可开工）

> 用法：工作目录是主文件夹的 reader/ 子目录（~/code/inresearch.ai/reader，不进 git），把下面整段作为首条指令发给本地会话。
> 本地会话需要能读 ~/code/inresearch.ai/docs/library/ 与主仓库的两个标准文件。

---

你是 datacenter-reader 项目的执行者。这是一个独立的本地流水线项目，目标：把
`~/code/inresearch.ai/docs/library/`（17,843 份行业材料）逐份读取、打分、重命名归类，
并为高分材料产出消化草稿。主研究项目在 `~/code/inresearch.ai/`（git 仓库），你的产出
以批次文件形式交回该仓库，**不要直接修改主仓库的 LIBRARY_SCORES.csv 和 research/**。

## 开工前必读（主仓库内）

1. `framework/04_reading_scoring_standard.md` — 打分标准 v2：七维度、分数锚点、命名规范。打分只用这套标准。
2. `docs/local_reader/PROJECT_BRIEF.md` — 项目计划：四层分诊（T1→T4）、阶段、交接契约。
3. `docs/LIBRARY_SCORES.csv` — 已打分 36 份，是你的校准样板；不要重复打分已在其中的文件。

## 每份材料的处理流程

1. 提取文本（pdftotext / PyMuPDF；xlsx 用 openpyxl 读表头和数据规模）。提取失败的记入 failed 清单，不猜内容。
2. 按标准 v2 七维度打 importance（1-9）与 confidence（A-C）。
3. 起新名：`{importance}{confidence}_{年份}_{主题四到八字}_{机构}.{ext}`，移动到 library 对应主题目录。
4. 写 summary：≥200 字，**尽量多装可落库的数字**（序列、份额、价格、产能、日期）。
   硬约束：每个数字必须能在提取文本中原文找到，找不到的标 `[未核]`。禁止编造。
5. 追加一行到当前批次 CSV（列结构与 LIBRARY_SCORES.csv 完全一致：
   new_path,old_name,importance,confidence,year,org,module,summary,scored）。
6. importance≥8 的：另写消化草稿（Finding 格式：结论/论证/证据/口径提醒/待办，
   参考主仓库 research/M06.md 里任意一条的结构），存为
   `digest_drafts/{分数}{置信}_{主题}_{机构}.md`。

## 批次纪律

- 每处理 20-40 份出一个批次：`batch_YYYYMMDD_NN.csv` + 对应草稿，复制到主仓库
  `docs/inbox/scored_batches/` 与 `docs/inbox/digest_drafts/`，由主仓库会话审计合并。
- **每批开头先重打 3 份校准样板**（从已有 CSV 里取一份 9 分、一份 8 分、一份 5 分，
  不看原分数盲打）；偏差 ≥2 分就停下，重读标准再继续。
- 从 T1 层开始：SemiAnalysis合集（242）→ 英文机构报告（130）→ 半导体与上游（300）。
  T2/T3/T4 策略见 PROJECT_BRIEF，未到层级不要提前碰一万份中文报告集。
- 优先捞四类内容（当前知识层最缺）：数据中心**运营/总包/劳动力**（M10）、
  **利用率/调度**（M13）、**中国渠道数据**（M14）、**选址**（M05）。

## 你可以自建的东西

- 本地脚本、缓存、断点续跑机制随你设计（这个项目不受主仓库零依赖铁律约束）；
- 但交回主仓库的只能是上述两种文本产物，格式不得自创。

从 T1 第一个目录（SemiAnalysis合集）开始，先跑通 5 份的完整链路给我看，确认格式后再放量。
