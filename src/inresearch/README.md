# inresearch 程序职责与入口

核心仅依赖 Python 标准库。仓库根目录运行 `python3 manage.py <command>`；部署也可设 `PYTHONPATH=src` 后运行 `python3 -m inresearch`。不要直接执行包内部文件。

| 目录 | 责任与主要实现 |
|---|---|
| materials | `model_assets` 统一视觉输入身份与采用状态；`records` 为当前判读权威投影及版本提交；`triage` 为清单/预览契约；`naming` 为纯命名规则；`reading_artifacts` 共管原件、覆盖和封印校验；`reading_policy` 管 L2 准入，`text_similarity` 仅提示相似；`inbox`/`receive` 接收；`organize`/`mapping` 处理显式整理 |
| knowledge | `registry` 维护对象、证据、采用、当前任务；`fact_contract` 为唯一事实入库与审计规则；`provenance` 解析有依据的来源修复计划；`policy` 为共享价格规则；`validate` 为表间完整性 |
| workflow | `model_assets.import_candidate` 协调视觉候选导入事务； `commands` 为 HTTP/CLI 共享修改用例；`reader` 控制任务状态；`reading_stages` 执行候选判读；`reading_results` 查询唯一当前全文结果；`deep_read.DeepRead` 编排事实处理与回执；`reading_gaps` 管缺口事务；`score` 为模型批量评分 |
| delivery | `report` 为网页/Markdown/docx 报告模型；`reader_export` 生成候选及备份；`reading_packet` 生成终端精读包；`publish` 接收器协议适配 |
| adapters | `models` 根据 role/profile 选推理后端；`reader_model` 声明阅读任务；`office*` 分解容器/网格/二进制和 OOXML；采集、新闻和 3D 资产由命名明确的适配器处理 |
| interfaces | `cli` 为命令注册和 JSON 参数层，`deep_read` 承接 L2 终端协议；`http` 为身份/路由/错误层；`pages` 组合共享认证布局；`static` 只服务声明路径 |
| storage | `layout` 依 storage_contract 区分 Git 发布研究、持久状态与产物；`files` 覆盖完整文件事务；`jsonl` 处理持久追加和损坏尾行；`catalog` 管线程局部 SQLite 连接；`moves` 维护可恢复原件移动 |

稳定业务命令：`models --probe`、`reader`、`inventory`、`triage`、`score`、`batch`、`deep-read`、`organize`、`mapping`、`registry`、`facts`、`validate`、`export`、`serve`。参数见各子命令 `--help`。`add-price`、`assign`、`receive-snapshot` 接受 stdin JSON 或 `--input FILE`，与 HTTP 共用 `workflow.commands`；`--root` 只指定这三个修改用例的业务根，不改变其他命令的原件根或模型配置。

旧 fetch_sec、fetch_gpu_prices、m4_inventory 独立入口已删除；采集用 `acquisition sec/gpu`，清点用 `inventory`。旧 m4_local_reader 0–100 评分分支退出新任务，既有日志保留。未回收 Anthropic 批次仍可通过 `triage collect` 回收，不再创建新批次。

公开页面 URL 保持，源码位于 `web/pages`；唯一映射在 `web/routes.json`。`web/components` 拥有 shell、表单、报告行内渲染、部件查看器与序列摘要；`web/themes` 拥有偏好及风格。源码/测试目录不通过网站静态服务开放。

新模型、终端和网页功能调用现有用例，不能另建一套“当前结果”规则。Reader 任务 SQLite、M4 原件整理和网站账号仍保留各自正式 scope；不因目录迁移合并或清空运行数据。reader 的显式阅读版本与审核替换已经实现，L2 与 reader 已共用当前全文查询；真实跨机器数据根连接及历史资料迁移仍待验；产品资料库已使用可重放的预备日志，以索引为主提交点、计划为回执，保留输入原件，见整改交付台账。

校验顺序：治理 refresh/check → validate --strict → registry → `PYTHONPATH=src python3 -m unittest discover -s tests/unit` → `node tests/run_browser.cjs`。`facts` 使用同一事实契约审计既有记录，缺失原文哈希的记录如实报告，不用伪造值通过校验。
