# 任务页匿名上传与审批交接（2026-10-14，m5）

## 目标

任何访客可在 `/tasks.html#upload` 上传作业；只有指定负责人批准原件后，Spark 才能领取，分析验收反馈按提交回执在页面折叠展示。

## 已定规则

- 员工上传无需登录；称呼仅供识别，不能作为身份凭据。每份新文件单独审批，审批绑定 SHA-256。
- 负责人是 `INRESEARCH_MATERIAL_APPROVER` 指定的 admin，未配置时为 `HUB_ADMIN_USERNAME`（默认 `admin`）。其他 admin 不可代批。
- 未批准、退回、旧归档记录均不进入研究端待领队列或内容接口。批准、Spark 归档、分析验收、正式研究采用与网站发布分别留痕。
- 回执码只在上传响应中给出，浏览器本地保存；换设备由提交人输入编号和回执码。公开访客不能列举或下载其他人的资料。

## 进度与实际回执

- PR [#917](https://github.com/niuroumiantt/InResearch.ai/pull/917) 已合并为 `907cbcdb3376a5ccd3c6c7b134b7ea390199f4da`；全套 CI 运行 `38590531599` 的 23 个作业成功。源码治理、严格校验、审批单元测试和真实浏览器场景通过。
- AWS `inresearch-only-deploy.service` 于 2026-10-14 15:47 UTC 成功，容器镜像标记为上述合并提交且健康。公网任务页展示上传区，上传脚本匿名返回 200；空文件匿名 POST 被接口按大小拒绝为 400。
- Spark 源码以经 SHA 核对的增量 Git bundle 快进到同一提交，原件与运行数据未移动。`inresearch-material-intake.timer` 已启用并于北京时间 23:56 自动触发；服务退出 0，实际 `received=0`。
- 尚无本功能下的真实员工材料被批准或分析；没有正式入库或发布回执。

## 下一步

1. 首份真实文件上传后，负责人在任务页登录，下载并核对文件与 SHA，再明确批准或填写退回原因。
2. 批准后核 Spark 下一轮收件回执；XLSX 仅归档和投递原件，具体表格核查仍由研究人员完成。负责人可在页面登记带时间的验收结论和修改反馈。
3. 正式研究采用与入库按现行来源和 C3 流程执行，不能用“批准”或“验收通过”代替。

## 入口

`framework/05_interface_system.md`、`framework/06_acquisition.md`、`framework/09_software_contracts.md`；`src/inresearch/materials/inbox.py`、`src/inresearch/materials/receive.py`、`src/inresearch/interfaces/http.py`；`web/components/task-uploads.js`；`tests/unit/test_material_intake.py`、`tests/research_tasks.cjs`。
