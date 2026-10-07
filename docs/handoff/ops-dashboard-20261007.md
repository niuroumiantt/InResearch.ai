# 管理后台 dashboard 交接（2026-10-07，m5）

## 目标与已定边界
用户要求 `ops.html` 自动看到健康、指标、进展、阻塞、长期错误与 pending 定位，操作独立呈现。直接替代旧按钮控制台；不自动执行采集/阅读/重排，不改变候选与采用边界。

## 完成内容
- `/api/ops` 和独立完整日志下载只限 admin；页面自动刷新，UTC+8、新鲜度/缺数据/失败明确。
- 发布诊断只读当前执行 revision，分块/文档/完整阅读/交付分开，1h/24h 时间窗、队列最早100样本、每错误类最早3定位样本。错误分执行异常、材料缺口、策略暂存。
- 事实复用 check_fact，核验复用 build_queue，目标行按既有台账；手动任务存开始/结果/耗时/退出码，完整日志保留，展示最近50次历史。旧日志结果未知。
- 05、Spark 手册、现行注册表和验收映射同步更新至 2026.10.07.8；新观测实测在 Spark 全台账查询约1秒（不修改 catalog），普通 worker 心跳不增加诊断扫描。

## 验收与实际限制
管理后台单元与浏览器测试、全站明暗/手机矩阵通过；严格校验、registry、governance 通过。全量本机1855单测有1个未改动的 retention SQLite WAL 备份只读打开失败，已用 origin/main 原文件复现；Linux CI另验。真实发布与版本以本任务 PR、部署探针和新发布快照核对。

队列筛选仅100条全队样本及每错误3条；无全库在线分页、全服务 journal 或已确认异常行号。代码给的是阶段入口，日志再定位。完整手动日志从新版首次运行留存，旧截断日志不能恢复。资料处理缺口、C3采用和原件事实仍须研究/运维处理。

## 入口
`web/pages/ops.html`、`web/assets/ops-dashboard.{js,css}`、`workflow/operations.py`、`tests/unit/test_operations.py`、`tests/ops_dashboard.cjs`。网站走 infra 独立部署；Spark 在干净 canonical checkout 快进源码，新 publisher 进程即可带诊断，运行中的 reader 不必为dashboard重启。
