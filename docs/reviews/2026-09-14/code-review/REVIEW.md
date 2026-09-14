# 2026-09-14 全仓高阶代码审阅

> 审阅记录（historical role）。基线：分支 `claude/stoic-rubin-v8ndnf`，HEAD `5d7104e`。现行规则仍以 [framework/CURRENT.md](../../../framework/CURRENT.md) 为准；本文只登记发现、复核结论与本批处置，不构成新规则。

## 一、方法与基线

三组独立流水线并行审阅，每条发现由另一名不带上下文的复核者按四个维度反驳：事实是否成立、是否与现行规则/已采用决定一致、是否值得高阶报告、能否立即安全执行。复核后保留 94 条（后端 71 条中 4 条降级或部分驳回；前端/测试/文档 48 条中 4 条降级；视觉 21 条中 5 条判为已登记限制或环境伪影）。

| 项目 | 基线（修改前） | 本批修改后 |
|---|---|---|
| `governance --check` | 通过（794 文件） | 通过（见提交） |
| `validate --strict` | 通过，0 警告 | 通过，0 警告 |
| 单元测试 | 1049 通过（1 跳过） | 1051 通过（1 跳过） |
| 浏览器回归 core / model_assets | 全部通过 | core 通过（model_assets 未重跑） |
| 现网公开面 | 7 个登录前资源与源码 SHA-256 逐字节一致；`/login` HTML 与本地渲染 diff 为空 | 无变化 |

现网 14 个业务页在登录之后，本次无凭据，**未能核验**；只能确认部署外壳等于源码 HEAD，其余以本地隔离服务的 210 余张截图为准。

## 二、总体判断

1. **业务主链是通的，交接契约一致。** 材料 → L1 判定（`materials.records` 唯一有效结果）→ L2 打包（`reading_results` 唯一当前全文查询）→ 事实提交（`fact_contract` 唯一准入，facts → L1 → 回执锁序）→ 注册表/报告/网页，以及 HTTP/CLI 共用 `workflow.commands` 的三个写用例，CommitUncertain / Rejected 两侧映射一致。storage 层事务原语与 09 契约相符，且有真实进程并发与故障注入测试。
2. **最大的结构问题不是"错"，而是"多"。** 同一概念多处所有者：L1 评分管线拆在 triage/score/attribution/terminal_batch 四个互相 import 的 CLI 模块；研究问题任务由 workorders 与 registry.current_tasks 各算一次；两张 3D 页仍有 274 行逐字相同的内联脚本；九个页面各抄一份 fetch/转义/分桶/地图/指标状态 helper；写文件原语有 5 个别名、NoRedirect 有 3 份、SHA 与路径限定各 3–4 份。
3. **"旧入口只留转向"的收口没有做完。** 自标"历史勿用"的部署文件、过期两代的索引、面向已不存在目录的三个 CLI 命令，以及页面文案里的 `inresearch.py`/`serve.py`/`dchub`/`Datacenter Hub` 都还在活动路径。本批已清除可安全执行的部分（见第五节）。
4. **交付与规范的偏差集中在三处：** 机柜面板真实贴图从未上到 GPU（每次加载 5 条 GL_INVALID_VALUE）；下钻链条在任何宽度都被局部 topbar 遮住；member 角色可打开管理区页面且导航无高亮、管线按钮全露。前两项本批已修，第三项需产品决定（见 P3-1）。

## 三、优先级一：业务流程、边界与重复

### 高

- **P1-1 L1 评分管线四模块互为依赖、逐字重复。** `workflow/triage.cmd_run` 只转发 `score.cmd_run`（同一操作两个 CLI 入口）；`triage.sample` 送 6000 字原始预览、`score.judge` 送 `clean_preview()[:400]`（两套输入口径）；L0 直写 + `commit_result`、workers 校验、预算槽、`MAX_WORKERS` 五处定义在 score/attribution/terminal_batch 逐字重复；score/attribution/progress 只为借 `pending/clean_preview/working_rate` 而 import terminal_batch。建议新建无 CLI 的共享用例（或并入 `materials.triage`）后各 CLI 只留参数与输出，删除 score 或 triage.run 转发之一。
- **P1-2 研究问题任务双算，首页与团队页口径已经分叉。** `workorders.build` 把 `question_tasks` 写进 `reports/workorders.json`（564 条中 415 条），`registry.current_tasks` 再算一遍并丢弃文件里同类行；`team.html` 走 `/api/tasks`（598 条），`index.html:401-416` 直接读文件（564 条）。03 §27 规定研究视图、团队页、派工共用 `current_tasks()`。建议 workorders 只产模块缺口工单与 module_stats，首页改读 `/api/tasks`。
- **P1-3 同 SHA 多副本的"代表副本"两套规则。** `triage.load_inventory` 取清单第一条非 `要删/reader/` 路径命名，`organize.keep_rank` 按（不在要删、最浅、字典序）选移动副本，已复现：移动 `资料/报告.pdf` 却用 `要删/x/报告(1).pdf` 起名。应收敛为一个函数并补同 SHA 不同目录的回归测试。
- **P1-4 首页每分钟无缓存重拉约 8 MB 原始文件。** `index.html` 的 `get()` 加 `?t=` 与 `cache:'no-store'`，`setInterval(render, 60000)` 重拉 facts.json（6.3 MB）、metrics.json、workorders.json 等只为算几个计数；2026-09-13 新闻投影决策只治理了 `/api/research` 轮询。建议增加轻量计数投影（并入 `/api/status` 或新建 `/api/overview`），页面只轮询新闻。
- **P1-5 候选目录被当作正式数据源。** `registry.build_catalog` 在运行索引为空时静默回退 `docs/inbox/inresearch-alignment/library_index.json`（生产首装即为空，故默认走回退）；`admin/product/index.html` 先加载 `companies_patch.json` 再以 `{...companies, ...patch}` 合并，实测 13 家公司 profile、6 家 ir_url 被补丁的 null 覆盖。索引回退是测试承认的设计但未在任何规范登记；补丁覆盖违反"候选与正式采用不互相冒充"。建议删除页面补丁合并，索引回退要么写入 03 要么删除。
- **P1-6 `office.extract` 对二进制 .ppt 丢失预算且不报截断。** L2 精读包以 600000 字调用却只得 20000 字，且 `truncated` 缺失，读者把截断当完整正文；xls/xlsx 在 grid 判定后再做二次切片同样不置标志。**本批已修**并新增测试。
- **P1-7 `deep-read skip` 仍接受未登记的完整 SHA。** 与 2026-09-13 对 `record --doc` 的修复不一致：手打错一位照样写入缺口台账与处理回执。**本批已修**（skip 与 record 共用 policy 默认严格解析）并新增测试。
- **P1-8 `mapping import-verdicts` 裸追加 L1 台账。** 不经 `JsonlStore.locked()` 与 `records.commit_result`，无 supersedes/result_revision。**本批已改走 `commit_result`**，冲突计入 skipped。
- **P1-9 `indicators.TODAY` 在导入时冻结。** 长驻服务运行超过一天后，每次加价触发的指标回填把 `as_of/updated` 写成启动日。**本批已修**为函数内取值。
- **P1-10 两张 3D 页 274 行逐字重复 + 标注牌绕过纹理池。** 下钻条 17 行与 12 行 CSS 完全相同；爆炸时间线 29 行相似 0.92；`label()` 直接 `new THREE.CanvasTexture`，17 个标注精灵不在 `texturePool`、`disposePage` 不释放，与 05/09"CanvasTexture 由 scene-resources 统一持有"不符（该批 consumers-after.csv 登记为 planned 却未迁）。renderer/composer/灯光/proceduralEnv 的重复 05 已登记为未完成。建议：`scene-motion.createExplodeTimeline`、`scene-resources.label`、`mountDrillBar` 三个共享入口，两页各删约 60 行。

### 中

- **P1-11 精读队列"已读"判定结构性恒假。** `reading_queue.proven_complete` 要求 `LIBRARY_SCORES.csv` 的 `doc_id` 列，该列不存在（13,663 行 0 命中），于是"已消化 0 份"，workorders 据此生成 14 条"消化积压"工单派给团队。模块自述为保守迁移视图（有据保留），但下游工单不应再产生；要么退出该分支，要么按内容 SHA 经 `reading_results/records` 判定。
- **P1-12 私有路径拒绝规则三份、reader 令牌校验两份、账号锁第二套。** `http._gate` 129/138 行与 `static.source_path` 各写一次（138 行被 129 行完全覆盖，可直接删）；`intake_worker` 与 `api_reader_snapshot` 对同一 token 两套规则（Bearer 前缀、缺失时 401 vs 503）；`auth.user_write` 用 `.users.lock` 自建 RLock+fcntl，与 `storage.files.locked`（`.users.json.lock`）不互斥。建议 `static.is_private_url` 单一所有者、`_reader_credential_ok` 单一函数、账号改用 `locked()`（注意锁名变更时避免新旧进程混跑）。
- **P1-13 接口层重算领域统计。** `interfaces/deep_read.cmd_queue` 的 covered 与 `DeepRead.coverage()` 逐字相同并两次遍历结果做准入过滤；`http.py /api/tasks` 在接口层拼合 current_tasks 与 module_stats。09 规定接口只处理参数、输出与错误。建议 `DeepRead.queue_summary()`、`registry.task_board()`。
- **P1-14 Spark→网站两个客户端、发布定时器持可写 Reader。** `receive.py` 硬编码令牌路径与 `https://inresearch.ai/...`，`publish.py` 走 READER_* 环境；`publish` 为只读导出实例化 `ModelClient` 并 `Reader.initialize()`（可触发持锁迁移），外层手写 BEGIN/COMMIT 与 `catalog.read_snapshot` 冗余。建议共享 Spark 客户端配置，publish 改只读 Catalog + `reader_export.export_snapshot`。
- **P1-15 抽取路由两个所有者。** `materials.triage.extract_preview` 与 `delivery.reading_packet.full_text` 复制了后缀路由、三编码回退、textutil 调用与 subprocess 包装（共 4 份 run）。建议 adapters 层唯一抽取入口带 `preview/limit` 参数。
- **P1-16 adapters 包承载用例、SQLite 台账与 CLI。** `historical_brief` 自己解析 Finding（与 `delivery.report.parse_findings` 正则相同）并子进程跑 indicators；`acquisition` 持 schema、Collector 事务与 argparse；`asset_check` 是纯 CLI。09 的分层句与 README/登记表描述的实际目录相互矛盾，须二选一：搬动，或在 09 显式登记例外。
- **P1-17 Finding 状态解析器四处各一份**（report/historical_brief/verify/coverage），02 已指定 `delivery.report` 为统一解析器。
- **P1-18 `acquisition.Collector.archive` 自造原子写且不 fsync 目录**，与 `storage.files.atomic_write` 并存；写文件原语别名 5 个（`write_json as atomic_json`、`atomic_write as commit`、`registry.atomic_json`（src 内零消费者，仅测试用）、`inbox.atomic`、`historical_brief.atomic_write`）；NoRedirect 定义 3 次。
- **P1-19 进度/ETA 两个所有者**（`progress.collect` 与 `terminal_batch.cmd_status`，速率口径不同，后者 `st_birthtime` 在 Linux 回退分支必抛）；`attribution.cmd_test` 逐行读原始台账绕过 `current_results`。
- **P1-20 Reader 状态交接键不匹配。** `Reader.status()` 发 `backend` 字典，`research-graph.js:765` 只读 `reader.model`，"阅读模型"永不显示。建议前端读 `reader.backend?.model`。
- **P1-21 `submissions.py` 自带 2 倍冲突规则**（`CONFLICT_RATIO`，`>=`）不共用 `fact_contract.SPREAD_ESCALATION`（`>`），恰好 2 倍时两处判定相反；`--accept` docstring 声称复用合并流程但产物无程序消费者。
- **P1-22 两个 15 行状态壳**（`acquisition_status`/`reader_status`）各为读 reader 块全量构建产品目录并校验注册表；`registry.build_news` 已示范轻路径。建议合并为一个用例。
- **P1-23 数据中心成本模型四份**（`model.py`、JSON、JS、xlsx），`model.py` 输出路径错误开箱即失败且未被列为权威。建议 model.py 读 JSON 复算并断言与 JS 一致，或删除。
- **P1-24 模块问题三处逐字维护**（`framework/modules/Mxx.md` ⊂ `modules.json.questions` ⊂ `research_questions.json`），靠两个校验器保持同步；信源清单三个所有者（`modules.json beats` 唯一机器消费者、`docs/DATA_SOURCING.md`、`framework/05_source_map.md` 未登记草案）。均属文档明确保留的兼容设计，作为简化提案登记。
- **P1-25 生成投影作 seed 发布且陈旧。** `reports/workorders.json` 564→重算 659，`intake_review.md` 含 `_template` 占位，`brief.json` 留有 09 已退出的 `review_marked`；CI 不重算不比对。建议投影不进 Git 由 `storage initialize` 现场重建，或 CI 加"重算并 diff"。

## 四、优先级二：优雅性、每个文件的意义

- **P2-1 页面 helper 复制 2–8 份。** fetch 包装 6 份、HTML 转义 8 份（覆盖范围各异，index/company 不转义 `>` 和 `'`）、capBuckets 2 份 + ops `projectCapacity` 逻辑不同（潜在口径分叉）、世界地图投影 2 份、tooltip 2 份、指标状态 2 份、最新价格取值 3 份。建议 `web/components/data-views.js`。
- **P2-2 两张 3D 页为 3 个小 helper 引入 59 KB 研究工作台 + 16 KB object-network**；`research-graph.js` 有 7 个无外部消费者的导出与 `TYPE_LABELS` 重复键。
- **P2-3 `site-skin.css` 13 个全站零消费者的旧研究页选择器**（`.rg-tab/.rg-record/.blk/.ui-standard` 等约 15 处声明）。
- **P2-4 页内被共享 CSS 整体覆盖的色板与死规则**：ops `.console`、六页 `.badge{color:#fff}`、index 无引用的 `@keyframes scroll`/`.tab.on`/占位行；ops 同一次加载三次读 brief.json、两次读 prices.json；13 页各抄一份 reset/body/.topbar/.tab（poster 两页因排除共享皮肤需保留）。
- **P2-5 `data/schema/*.json` 七份无代码消费者**，`fact.schema.json` 的 as_of/depth/evidence.required 已与 `check_fact` 漂移。09 把 schema 列为发布镜像权威，须二选一：validate 用最小校验器读 schema 成为唯一声明，或归档并让测试断言 fact.schema 与 check_fact 一致。
- **P2-6 `company_ids.py` 在 knowledge 层直接 urllib 访问 sec.gov**（09 禁止领域依赖 HTTP），UA 仍是旧项目名，无文档无测试；DECISIONS 待办 D3 仍需 CIK 回填，故应迁到 adapters 而非删除。
- **P2-7 `naming.py` 被 `triage.py:17` 的 14 名重导出遮蔽**，纯命名规则零直接消费者；账本路径常量在 triage/organize/progress 各算一遍；`PARTIAL_SUFFIXES`/partial 判定/SHA/时间戳/safe_path/文件名清洗各 2–3 份；`reading_stages._extract` 每页循环重读 recipe.json；`library.admit` 对同一字节做 4 次 SHA-256。
- **P2-8 `manage.py facts` 长期 exit 1**：38 条历史缺口是 09 明文"继续单独披露"的刻意状态，不应改基线；但 CLI 审计不传 claims 索引，碰撞规则只在 record 路径执行，可安全对齐。
- **P2-9 测试层：** `test_fact_contract.py` 2728 行中约 225 个用例只对 metrics.json/schema 的中文注释做子串断言、19 处纯字面量算术自证；L2 夹具三处在导入期各建永不清理的临时目录并复制 25 个未用 import；15 套浏览器测试 launch/错误收集/换肤循环/溢出断言各写一份，截图落盘三套约定（4 套无条件写 /tmp）；add-price 409/400 四处、JSONL 断尾六处重复断言；M4 系列 25 组 `_saved` 元组手工猴补全局；测试模块互相当 fixture 库导入；`verification_contract` 未登记 15 个仍在 CI 跑的测试文件。
- **P2-10 过期文案与脚手架**（本批已清除的见第五节）：`preflight.py` 硬编码 `/Users/m4`；`library.py:334` 死字符串；`materials/triage.py` 与 `workflow/triage.py` docstring 逐字相同；98 个包内文件中 43 个仍有 shebang、39 个有 `__main__` 块而 README 明令不直接执行——应作仓库级决定。
- **P2-11 docs 残留：** `docs/inbox` 的 digest_drafts/scored_batches/needs_password/path_migrations/project_registry/PHASE2_REPORT 为 2026-08 会话遗留；`docs/DATA_SOURCING.md`（259 张工单、引用已删除的 intake.py）与 `framework/05_source_map.md`（未登记草案）符合归档条件；`reports/templates/README.md` 描述不存在的模板；`reports/HOW_TO_OUTPUT.md` 指向不存在的 `pipeline/`；`research/M01.md:51`、`SUMMARY.md:11` 仍写治理列为失效的"L4 以下必须乘以历史转化率"且随 report.py 进入网页报告（role=research_record 被治理扫描跳过）；`bom.html` 把自认过期的 LIBRARY_REPORT"精读可直接引用"作为在线入口；`.gitignore` 有重复块；治理分类器把 docx/pdf/xlsx/.cjs 一律归为"项目配置"。

## 五、优先级三：实际网站交付与代码预期

- **P3-1 member 角色可打开 `data-section="admin"` 的 ops/compare 页**，导航无任何高亮，ops 完整渲染 16 个仅 admin 可执行的管线按钮（点击后 403），只隐藏用户区。`site-shell.render` 只区分 intern/admin，`http._gate` 只对 intern 白名单。注意 member 按规则允许录价格而录入表单只在 ops.html，所以不能简单对非 admin 返回无权限页；建议 ops 按 `/api/whoami` 隐藏管线区，shell 对不在当前角色导航中的 section 给出归属提示，并把 member 纳入导航断言。截图：`screenshots/ops-member-folk-light-1440.png`。
- **P3-2 机柜面板真实贴图从未显示。** `texturePool.image` 在 onload 把 256×64 画布改为 PNG 原尺寸后只设 `needsUpdate`，three r160 不重新分配 `texStorage2D`，五次 `texSubImage2D` 均被驱动以 GL_INVALID_VALUE 拒绝，GPU 上仍是程序化前脸而 `ready()` 返回 ready。**本批已修**（尺寸变化时先 `texture.dispose()` 触发重上传）；建议 `scene_resources.cjs` 加 GPU 读回像素与 PNG 相关的断言。
- **P3-3 下钻链条任何宽度都不可见。** `.drill{top:54px}` 沿用旧 46px 顶栏，实际被共享 `.topbar`（top 53px、高 52、z-index 30）完全盖住，≤900px 又 `display:none`，等于死代码仍占请求。**本批已改为** `calc(var(--ui-bar-height) + 56px)`；窄屏形态与是否并入研究关系仍待决定。截图：`screenshots/bom3d-folk-light-1440-drill-hidden.png`。
- **P3-4 `cost.html` 硬编码 `#fff` 与 43px 顶栏偏移**：folk 深色主按钮对比度 1.17，二级导航被共享顶栏遮住 10px。**本批已改用** `--ui-on-accent` 与 `--ui-bar-height`。
- **P3-5 换肤栏在 materials 与三张认证页高 72px、其余 53px**：`#ui-skinbar` 未声明 box-sizing，依赖各页 reset。**本批已在共享规则中声明**。截图：`screenshots/materials-skinbar-72px.png`。
- **P3-6 GPU/AI ASIC 概念部件预览为一块黑色薄板**：`part-inspector` 默认 `iRotX=-0.35` 叠加 9° 仰角从下方掠射，看到无光照底面；净倾角改为 +0.35 即得清晰基板。截图：`screenshots/rack3d-gpu-dossier-black-preview.png`。
- **P3-7 `compare.html` 归属 admin、无入口、硬编码深色画布底色与 4 个无消费者 class、三种页面命名**。本批清除了死样式并把底色改为 `--ui-scene`，归属与入口待定。
- **P3-8 现网交付细节：** woff2 以 `application/octet-stream` 交付（slim 镜像无系统 mime 表，**本批已由代码声明**）；登录页与公开资源不发送任何缓存/安全响应头且 Server 头暴露 Python 补丁版本（05 未承诺，属加固缺口）；无用户时 503 文案向访客展示已作废的 `docker compose exec dchub` 命令（**本批已改**）。
- **P3-9 其余低优先级：** 一级导航键盘焦点环被 `.ui-navigation{overflow:auto}` 裁成两条竖线；`doc.html` 链接 `word-break:break-all` 拆词（"CURREN / T"）；cost 标题孤字换行；team.html 一次渲染 598 张工单、手机页高 14 万 px；admin/product 与 company 每次加载各一条预期 404；company.html 两段永不产出内容的分支（`data/raw/sec` 被 static 拒绝、`modules[].research` 字段不存在）；四页文案指引已删除的 `inresearch.py`（**本批已改**）。已登记为限制、无需再报的：手机端展开面板遮住主体（05 明示未完成）、rack3d 无头合成伪影（scene-framing DELIVERY 已记录）。

## 六、本批直接落地的处置

代码修复：`knowledge/indicators.py`（日期取值）、`workflow/deep_read.py`（skip 解析）、`adapters/office*.py`（.ppt 预算与截断、xls/xlsx 二次切片标志、删 `ROW_NUM`）、`materials/mapping.py`（走 `commit_result`）、`interfaces/http.py`（503 文案、横幅、`--offline` 死参数、woff2 MIME、重复行）、`knowledge/facts.py`（删两个未用常量）、页面/文档串中的退役名称（team/doc/ops/admin/index、organize/progress/attribution/verify/auth/map/Dockerfile）、`web/themes/site-skin.css`、`datacenter-cost.css`、`bom3d/rack3d .drill`、`scene-resources.js`、`compare.html`、`rack3d.html` 死规则。

退出与归档：删除 `materials/scan_candidates.py`、`materials/repair_paths.py`、`delivery/library_index.py` 及 cli/TASKS/ops 按钮，删除 `docs/local_reader/start.sh` 与 `.claude/settings.local.json`；`deploy/Caddyfile`、`docker-compose.yml`、旧 `README.md` 与 `docs/LIBRARY_INDEX.md` 移入 `docs/archive/2026-09-14/`（带 HISTORICAL 头），`deploy/README.md` 改为指向 infra 的现行说明，`docs/inbox/README.md` 改为现行入口转向页；`current_state.json` 的 operations 政策不再把退役桩 `setup.sh` 列为现行实现。

测试与验收映射：新增 `SkipTests.test_an_unregistered_full_hash_is_refused_like_record`、`PptTests.test_the_caller_budget_is_honoured_and_a_cut_is_reported`；删除只钉死常量的 `test_the_other_validator_agrees`；`verification_contract.json` 相应更新三份测试文件摘要并登记两条新测试，基准版本 2026.09.14.7。

**未落地、需业主决定或另批实施：** 第三、四节的结构性合并（P1-1/2/3/5/10–25、P2-1–11）、P3-1 的角色可见性、P3-6/7/9 的视觉打磨、`data/schema` 的去留、投影是否继续进 Git。上述项不因本批测试全绿而视为完成。

## 七、复核中被驳回或降级的判断（避免误报）

- "`manage.py facts` 长期红灯是缺陷"：09/DELIVERY 明文保留 38 条债务的非零退出，属刻意状态，不改基线。
- "`reading_queue` 恒假是未经采纳的判定"：模块自述为保守迁移视图且登记为实现，问题在下游工单，不在判定本身。
- "`library_index.py` 已被 inventory 替代"：没有决定宣布 docs/library 索引作废；本批按"过期两代且生成器在仓库环境不可运行"退出并归档，若本机仍需该索引可从归档恢复。
- "`framework_poster.html`/`poster.html` 应删除"：两页是 05 明文保留的排除项，但页脚 facts 119 已失真、含旧导航且无入站链接，建议改为 docs 交付快照。
- "`registry.atomic_json`/`inventory.bucket` 重导出可删"：仅测试消费，删除需同步改测试，本批未动。
- "手机端面板遮住主体"、"rack3d 幽灵矩形"、"研究页五视角横向滚动"：分别为 05 明示未完成项、已记录的无头伪影、设计取舍。
