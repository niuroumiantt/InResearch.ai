# CI 按影响范围验收

现行源：本文件。2026-10-10 替代每个 PR 与 main push 无条件执行完整浏览器及存储回归的配置。完整测试的场景、断言、密度和单项期限不缩减；只改变本次需要运行的范围。

## 执行位置与身份门禁（2026.10.17.5）

本仓 `niuroumiantt/InResearch.ai` 当前为公开仓库，全部 CI 使用 `ubuntu-latest`。公开、缺失或非布尔仓库可见性均不能路由到持久 Spark runner。未来仅当仓库为私有、infra 已登记专属仓库身份和 runner、仓库变量 `SPARK_CI_ENABLED=true` 显式启用时，同仓非 fork PR、main push、workflow_dispatch 和 schedule 才使用 `self-hosted`、`Linux`、`ARM64`、`spark-ci`。fork、缺失或不一致 head、未知事件仍走 hosted，不新增 pull_request_target，不改变仓库可见性。

`validate.yml` 五个作业与 `verify-data-center-publication.yml` 的 verify 使用同一分流。每个 self-hosted 作业仍在 checkout 前用本作业只读 `github.token` 执行系统 `python3 /usr/local/lib/ci-prefetch.py --authorize-only`。系统脚本、根所有的绑定及私有仓库门禁保持；失败不得忽略、继续或回退为未授权检出。登记、私有性和显式开关缺一不可；工作流本身不替代系统身份校验或恶意 workflow 隔离。

保留原 checkout、完整 base/head 差异、Node22、Python3.12、依赖缓存、19 个浏览器分片、存储／缓存／单元回归、所有场景和超时，以及 `validate`、`browser (core)` 两个必过检查。不得用手工状态、跳过或另一仓库的结果代替本 PR 最终 head 的真实 CI。

2026-10-17 PR973 原 scope 在系统授权阶段报 `private_repository_only`；这是公开仓库与私有 runner 策略不匹配。公开仓库改走 hosted，不放宽 infra 门禁，也不启动暂停的 Spark runner、Reader、intake 或研究服务。此前“完整 Spark CI 已可执行”的候选假设由本节替代；实际执行位置与成功以每次 GitHub Actions 回执为准。

## 分流

`scripts/ci_scope.py` 对精确 base/head Git 树的完整差异分类，不使用有文件数截断的 PR 文件列表。PR 使用事件 base 与 GitHub 合并测试提交，main push 使用 before/after；比较失败、缺失基线、空差异、删除、改名、符号链接或未知路径均跑全套。

| 改动 | 验收 |
|---|---|
| 非规范 Markdown、普通资料图片 | 内容 UTF-8、位图实际解码/全部帧、SVG 结构、新增本地 Markdown 引用、治理清单、严格数据校验与 registry；不启动浏览器及存储容器 |
| 已映射页面仅可见文字变化 | 上述基础检查、资产契约与对应现有浏览器测试；标签、属性、脚本、样式、template 或注释变化不算纯文案 |
| technical-atlas 图像 | 基础与资产契约、technical_atlas 真实渲染和下载测试 |
| models/textures 目录内图像 | 基础与资产契约、model_assets 三个既有消费场景 |
| 普通 web 图像 | 可直接定位到已映射页面时运行对应测试；共享 JS/CSS/JSON 或无法映射的消费者跑全套；无法确立消费者时也跑全套 |
| `data/research_knowledge.json` 仅追加有界研究资料 | 基础检查、固定研究/来源/审核/发布链路/HTTP 单元回归，单个 `browser (research)` 作业内执行既有 research_delivery 与 research_summary；不跑视觉资产、3D、装配、园区及存储容器 |
| `data/projects.json` 仅向既有站点追加 v2 观测 | 基础检查、固定研究回归及站点时间/数量/原件采用/项目 HTTP 回归，`browser (research)` 与 `browser (industry)`；不跑无关 3D、装配、园区矩阵及存储容器 |
| `data/object_observations.json` 仅追加有界对象观测 | 基础检查、固定研究/来源/对象采用/Fetchspec/HTTP回归，research 与 industry 浏览器；保留全部旧对象及记录，可添加完整且被新观测引用的唯一对象；无关3D与存储容器不运行 |
| 程序、页面结构、权限、schema、非追加研究数据、依赖、测试、CI、现行规则及未知改动 | 原完整单元回归、19 个浏览器分片、资产契约、verify、indicators 和 storage-container |

混合提交取所有影响的并集，任一全套条件覆盖轻量条件。规则入口和登记的操作指南不当成普通文案。派生清单仍须经治理检查验证；current_state 仅版本/日期变化、verification_contract 仅版本/审阅时间与本次实际修改文件的既有摘要变化可以随内容提交走轻量路线，规则和验收要求语义变化必须全套。图片是否很小不作为免检依据；资产登记或其它规范一起变化时按其实际范围处理。

手动运行 workflow_dispatch 与每日北京时间 02:17 的 schedule 总是全套。main push 也按实际差异分流；完整代码变更合并后的发布基线仍完整回归。同一 PR 推入新提交会取消过期运行；main/schedule 不主动取消在运行的发布验收。浏览器依赖与 Chromium、CI 图像解码依赖使用固定版本及缓存。

## 研究资料追加的边界

只对已存在的 `data/research_knowledge.json` v2.0.0 分类，比较完整 base/head JSON：仅 documents/evidence/statements 数组末尾可增加记录，所有旧记录的顺序、值与 JSON 类型不变，至少新增一条且各集合 ID 唯一。version、note、answers 和顶层结构不变；新增 statement 必须 partial_support_only=true，不携带正式 question_id、替代记录、放宽审核分布、对象映射替代或撤回状态。重复 JSON 键、非有限数字、未知结构、修改/删除/重排旧记录、正式答案或版本/规则变化均回到 full。不能仅凭文件名、行数、PR 标题或发布器声称追加而跳过测试。

research 路线运行 scope、validate、browser (research)、browser (core)，追加站点或四类对象观测另加 browser (industry)。validate 保留治理、严格数据、registry 全量引用校验，并执行固定的 test_research*.py、test_public_reader.py、test_publish_reader.py、test_verification_contract.py、test_ci_scope.py、test_site_*.py、test_project_review.py、test_targeted_research.py、test_industry.py、test_object_review.py、test_fetchspec_receive.py；选定入口缺失或空测试集报错。browser (research) 串行执行原有研究成果页与研究摘要/节点资料测试，industry 验收首页/列表/园区详情及筛选，不展开 core_a/core_b/core_c 或任何 3D、装配、园区矩阵；纯研究追加也不运行 asset-check 和 storage-container。资料真实来源、C3 与原件核验仍由既有审核/发布链路完成，CI 分流本身不授予采用或上线资格。

站点追加比较完整 JSON：顶层元数据、站点数量/顺序/身份、全部基线字段和旧观测的值/类型/顺序保持，唯一新观测 ID，只向 observations 末尾追加带 source_versions、adoption 和 fields 的 v2 观测。旧式新增站点、补地理基线、改旧记录、显式 revision/替代/撤回、来源或采用上下文改写、歧义 JSON 与无法判定的变化仍全套。基础严格校验和现有 C3 原件写入共同检查实际合法性，不把形状检测视为采用。含 projects 的 research 汇总必须包含 industry，缺失不得通过。当前实现和规范变更本批走全套；不是用新分类器跳过自身验收。

对象观测追加比较完整严格JSON：version=1及顶层结构不变，旧objects键值和所有旧records的顺序、值、类型完全不变，每批新增1–500条且ID唯一；新增对象的四类身份字段和摘要ID必须一致，并由新增观测引用。新增记录必须有原件/上下文SHA、定位、引文和adopted审核；来源为HTTPS URL，或URL为空且有与原件身份匹配的归档导入记录摘要、唯一正整数记录ID及真实带时区接收时间，目标为空。显式修订/替代/撤回、旧身份或标签修改、重复键、非有限值、未知结构、混合代码/规则变化全部回到full。CI只证明追加形状，不代替原件语义核对、C3、时间/区间校验、CAS或公开资格审核。对象或站点追加缺少industry浏览器不得汇总通过。存量提取器与此分类器的首次实现必须全套验收，后续纯追加才使用新路线。

混合提交取并集：追加研究资料同时改普通文案/图片仍保留其检查；同时改已映射页面或资产则加跑对应浏览器与资产契约；任一代码、规则或未知影响仍覆盖为 full。新增正式答案、既有事实更正/替代不属于此范围。

## 必过门禁

GitHub main 必过检查为 `validate` 与 `browser (core)`，均绑定 GitHub Actions（app_id 15368），管理员也受保护，无新增人工审批。保留现有名称兼容已经打开的 PR；`browser (core)` 现为 CI 影响汇总门禁，并不代表普通文案必须启动浏览器。

`validate` 始终执行基础及本次范围内的源码检查；registry 后校验 Git 事件卡的目标、对象绑定、指针与重复，坏载体不得通过目标快照被当作交付。汇总门禁通过 `if: always()` 始终上报：scope 与 validate 必须成功；计划选择的 browser/storage 必须成功；只有计划未选择的任务可为 skipped。失败、取消、缺失结果、计划错误或意外跳过均阻塞。不能靠过滤整个必过 workflow 或提交 skip 标记绕过检查。

`browser (model_assets)`、`storage-container` 退出全局必过名单：需要它们时由汇总门禁强制检查成功，不需要时明确跳过。旧 PR 的完整四检查结果仍满足保留下来的两个名称，不要求为名称迁移重推全部 PR。

研究发布器按精确审核 SHA 读取所有分页 check runs；两个具名门禁必须实际成功，额外运行的检查不得失败、待定或取消。条件未选择的可选任务可为 skipped，不能把必过门禁的 skipped 当成功。只有上述可证明的研究资料或既有站点观测追加走 research 路线，其余正式研究 JSON 修改仍全套。来源、C3、当前正式上下文、网站支持闭包、Spark 回执与独占队列协议保持各自验收。

## 修改与未覆盖范围

分类器、门禁、映射或必过设置改变须同步本文件、AGENTS、current_state、verification_contract、相关发布器和测试，并 refresh/check 治理清单。修改本机制本身必须全套验收；先验证新工作流，再把保护名单收敛至两个始终上报的门禁，并回读确认管理员保护与 app 身份。

测试覆盖研究追加/旧记录类型与顺序/结论及规则变化/ID碰撞/歧义JSON/替代声明/混合范围/固定相关测试和仅研究浏览器别名，以及文案/图片分流、损坏图像、新增失效引用、页面结构与脚本变化、共享消费者、混合与超过 300 文件的差异、删除/改名/符号链接、元数据与实际规则变更、全套场景覆盖和每种作业状态的门禁判断。它不判断研究事实是否正确，不代替图片人工审美/逐项发布验收，不保证外部链接在线，也不自动推断任意间接资源依赖；无法明确映射的 web 消费者按全套处理。历史 PR 的实际失败与验收回执保留。

## 批次与效率（2026-10-10 整改）

一个能够独立验收的相关变更组成一批，规范、实现、生成器与测试同 PR；等本地校验完成再推送候选，避免连续推送取消已在跑的 PR 检查。修正失败先定位共同根因，不让多个资料 PR 重试相同基线错误。本轮代码/规则变更按全套验收，不调整单例/作业时限或门禁。

效率分别报告阅读完成、问题闭环/关键输入减少、正式采用与实际网站回执、待发 PR 数和最老等待时间。CI 用实际运行和各作业耗时判断瓶颈，取消、排队与运行耗时分开；没有测量依据不先放宽时限。

## 部署缓存

Dockerfile固定使用1.19.0语法，将web/assets、docs/design、docs/inbox和LIBRARY_SCORES.csv分别放入可独立复用的COPY --link层；其余源码只复制一次并明确exclude这些路径。研究记录或审计文档追加不会重新导出大型资产层。所有原有运行文件仍进入镜像，.dockerignore的Git、凭据、运行库和原件隔离保持；只读根、持久卷、健康检查与infra原部署/回退流程不变。

storage-container完整路线另执行tests/container_cache.py：用实际Dockerfile构建两版隔离输入，修改单条研究数据，验证稳定层相同、最终数据不同、资产存在且敏感伪造夹具未进入镜像。首次冷构建、后续缓存构建和生产发布分别实测；缓存命中不能代替公网/Spark验收。实现依据：[Dockerfile COPY文档](https://docs.docker.com/reference/dockerfile/#copy)。

首次园区登记的纯资料追加：完整JSON维持全部旧站点顺序、基线、旧观测与顶层结构；仅末尾增加最多100个具有冻结identity_registration和具名采用v2观测的园区。身份字段一致、容量基线为空、首条name/status一致、目标为空且有对象绑定/断言；重复ID/名称、旧值改变、显式修订和结构不明回full。必须跑研究、站点写入、industry及research浏览器；此形状证明不代替来源语义审核，新实现本身仍跑全套。

## 重型浏览器分片（2026-10-12）

PR839实际core_a耗时516秒；technical_atlas约94秒，chip_package两场景约219秒，在同一作业内串行。将technical_atlas和chip_package分别移入现有矩阵的独立作业，其余场景保持，测试验证全部case恰好一次覆盖；300秒单场景和15分钟作业时限、validate/core汇总与所有断言保持。只改变全套作业编组，不扩大纯资料豁免，也不改变发布器按精确head检查所有作业的要求。首次修改全套运行，是否提速以新实际CI回执为准。

首页最新动态是有界窗口；历史估算和预测从对应园区档案验证，不要求历史样例永远出现在最新动态。实际首页仍验证所显示site_id与有效时间对应、未知时点明示和完整备注不挤入标题流。

## 普通园区来源登记的追加分流（2026-10-12）

v3普通来源登记可进入既有research路线：完整JSON证明旧基线/身份/观测及其类型、顺序不变，只末尾追加；registration为unverified、无reviewed_at/伪造review/revision、target_ids=[]，字段绑定与稳定site_id一致，来源SHA及HTTPS或真实归档导入摘要齐备。首次新园区要求冻结identity_registration、首条名称一致、基线容量为空，阶段可null且verified_date为null。仍须strict/registry/治理和固定来源登记、站点与研究回归，browser research+industry均必过。旧身份/旧值/历史修订/代码规则变化仍full；CI只证明结构，不判断来源内容真假，也不授予研究采用。本机制本批全套验收，后续纯资料批才使用分流。

## Independent ordinary data releases (2026-10-12)

Ordinary source additions publish through source-publish to persistent storage, outside code PRs, GitHub Actions and image builds. Per-batch checks cover bounded strict JSON, stable identities, source shape, fields/times/intervals, immutable history, atomic append and replay; then verify actual homepage/API responses. They do not certify factual truth or C3 support. Code, schema, permissions, UI and normative changes keep the existing PR checks. Daily 02:17 Asia/Shanghai full regression remains. This first mechanism and UI repair run full CI; later ordinary data imports do not. Research conclusion adoption keeps its separate queue.
