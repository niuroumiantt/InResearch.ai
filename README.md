# inresearch.ai

一座 AI 数据中心，可以被追问到底：它怎么建、由什么组成、怎么运转、挣不挣钱，每个数从哪来、缺什么。围绕骨架节点提出问题，用可定位原文形成证据和陈述，再经审核形成回答与交付。目标是解释原理、比较方案、核对数据与诊断约束；材料量、模型评分和漂亮报告本身不代表研究完成。

当前规则从 [framework/CURRENT.md](framework/CURRENT.md) 进入；实现与本地验收见 [2026-09-13 架构交付](docs/reviews/2026-09-13/architecture/DELIVERY.md)。记录中的源码测试与生产发布分开计量。

## 项目的第一层边界

| 领域 | 负责什么 | 当前入口 |
|---|---|---|
| 研究定义 | 对象、关系、问题、范围与验收 | `framework/research_graph.json`、`research_questions.json` |
| 原文与阅读 | 内容身份、版本、任务、覆盖、候选及恢复 | `src/inresearch/workflow/reader.py`；运行 SQLite 与原件不进 Git |
| 知识与采用 | 原文定位、事实、非数字陈述、支持/反证及 C3 采用 | `src/inresearch/knowledge/registry.py`、`data/research_knowledge.json` |
| 任务与交付 | 从当前缺口生成任务；从有效结果生成网页与报告 | `knowledge.registry.current_tasks`、`src/inresearch/delivery/report.py` |
| 推理适配 | 根据角色配置调用模型，核对能力、预算和实际身份 | `src/inresearch/adapters/models.py`、`deploy/models.json` |
| 操作界面 | 网页、CLI 接入相同用例；主题与导航共用基础 | `src/inresearch/interfaces/http.py`、`web/components`、`web/themes` |

唯一逻辑（见 [00 研究框架总览](framework/00_overview.md)）：一棵树（骨架）、三级账、四问四段、五类变量、六队、一个模板。M01–M15 只是兼容属性 `legacy_module`；`research/Mxx.md` 的结论只作成果页的专题目录，不再是知识中心。兼容 Finding 不自动取得骨架节点证据的 C3 资格。

## 模型和客户端

当前 Spark 不可用，暂用本机已登录的 **Claude CLI** 推理。后续接 Spark、换更大型号通过配置完成，业务代码不以模型品牌或参数规模决定研究规则。每次记录实际模型与执行者；Claude Code、Codex CLI 是操作客户端，不用终端名称冒充模型。

同一材料默认一套当前有效阅读结果。失败重试不覆盖成功结果，换默认模型不自动重读已完成材料。原文、被引用的历史证据和尝试日志保留；受控重读通过 reader 的 reread / inspect-revision / activate-revision / reject-revision 共用用例，完整统一任务 CLI/API 等剩余边界见 [08 模型执行](framework/08_model_execution.md)。

```bash
python3 manage.py models --probe
python3 manage.py serve
```

站点默认在本机 `127.0.0.1:8000`。推理认证与代理由 CLI 和运行环境提供，项目不保存 OAuth 凭据或本机代理地址。网页容器不因此获得本机 Claude 登录态。

## 页面与目录

一级导航七项：行业总览（`/`，市场规模、地图、主体与项目）、数据中心研究（`node.html`）、账本（`ledger.html`）、爆炸图（`bom.html`）、采集（`supply.html`）、成果（`report.html`）、管理（`ops.html`，仅 admin）。角色四种：admin 七项，member 六项，intern 只见采集入口（自己的目标行），公开只读的 reader 不登录即可看行业总览、数据中心研究、爆炸图、成果与账本的基准预设，字段在服务端按角色过滤（白名单见 `src/inresearch/interfaces/public.py`）。节点页是四问的局部视图；2D/3D、规格库和主体是同一骨架节点的入口。明暗独立设置，桌面和手机都按 [05 界面规范](framework/05_interface_system.md) 验收。

网页与命令行报告共用有效内容集合；历史版本保留入口，生成日期不冒充核验日期。采集与派工只从目标表出发，旧模块工单只作兼容任务。

## 常用路径

| 路径 | 用途 |
|---|---|
| `framework/00_overview.md` | 唯一逻辑：一棵树、三级账、四问四段、五类变量、六队、一个模板 |
| `framework/01_data_standards.md` | 数据口径与核验纪律 |
| `framework/02_knowledge_format.md` | 文档、证据、陈述、采用与兼容 Finding |
| `framework/current_state.json` | 唯一现行规则、替代关系与影响路径 |
| `data/facts.json`、`framework/metrics.json` | 带口径和时点的数字事实及指标定义 |
| `research/` | 模块兼容研究记录 |
| `src/inresearch/README.md` | 程序入口与用例 |
| `docs/local_reader/M4_TRIAGE_RUNBOOK.md` | 独立语料清点、判定与文件整理 |
| `tests/run_browser.cjs` | 使用临时服务运行全站浏览器测试 |

源码位于 `~/code/inresearch.ai`。新运行数据位于 `~/.local/share/inresearch.ai/`，日志和运行状态位于 `~/.local/state/inresearch.ai/`；原件、数据库、密钥、账号和上传不进 Git。已有运行目录按实机登记核对，不随源码清理迁移。

## 检查与更新闭环

```bash
python3 manage.py governance --refresh
python3 manage.py governance --check
python3 manage.py validate --strict
python3 manage.py registry
PYTHONPATH=src python3 -m unittest discover -s tests/unit
# 浏览器依赖单独安装；CI 固定版本并执行同一入口
node tests/run_browser.cjs
```

变更现行规则时同步规范、实现、替代关系及清单。`inresearch.knowledge.verify`、`inresearch.workflow.reading_queue`、`inresearch.workflow.workorders`、`inresearch.knowledge.coverage` 仍可生成专项检查或兼容输出；它们不再代表四套并列的研究任务事实源。

## 采集与发布

inews.today 是独立产品、独立仓库，提供明确约定的数据中心新闻投影；inresearch 消费验证后的投影，负责专业资料、产品规格及研究证据。旧“本库不知道 inews”与直接读取对方目录的方案均已被 [06 采集规范](framework/06_acquisition.md) 替代，不复制上游业务。

网站沿用 infra 的正式发布流程；原件和 reader 服务须在实际运行机器单独验收。部署入口与健康检查见 `infra/inresearch-host/README.md`。Spark 恢复前不推断其版本、完成量或模型可用性。

行业总览的容量为已追踪园区合计，非全球普查。市场规模、主体布局、项目分期与精选新闻可分别下钻；建设中与筹备机会分列，新闻线索持久保留且不自动计入容量。
