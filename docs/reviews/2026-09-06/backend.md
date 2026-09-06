# InResearch.ai 后端、数据管线与部署代码审阅（2026-09-06）

审阅方式：只读当前源码，读取 CLAUDE.md、docs/DECISIONS.md 中当前约定与相关历史；遍历全部 26 个 pipeline/*.py、deploy、.github、docs/local_setup，追加读取被 launch_reader 调用的 docs/local_reader/start.sh。没有修改仓库，没有操作真实用户/数据，没有联网采集。功能探针仅使用系统临时目录、临时 HTTP 端口、临时 Git origin；生产/infra 核对由主代理负责。下文优先级按“下一轮应先处理”排序，不把没有发生的故障说成已发生。

## 一、已实现的能力与现实边界

- 研究侧有六表校验、事实口径维度校验/可比组、Finding 状态提取、SEC 触发 needs-review、核验/精读/盲区/工单队列、投递三档分流与确定性抽样。
- 协作侧有 PBKDF2 密码、HMAC cookie、三角色、静态资源认证、用户 CRUD、自助改密、白名单任务执行、人工录价/派工接口；本地模式与远程认证分开。
- 采集侧有 news 信号桥接、SEC 原档、CIK 补录、vast.ai 现货价格、指标回填；产品资料库有计划/试爬/归位/索引/哈希核对；3D 有模型下载、打包、登记、检查与比较。
- “已经有脚本”不等于链路已可用。全量/专题导出当前都是 0 章；产品库两处必现 bug；每天 collect 没有调度 GPU 采价；投递/派工仍需真实团队通水验证。
- 基线校验显示：projects 120、companies 248、prices 207、policies 2、contracts 2、sources 74、products 175、bom_parts 46、产品计划 801、产品索引 0；事实 119、指标定义 124。此处只描述该快照，不替代主代理研究质量评审。

## 二、P0

本次没有确认仍在发生的 P0 全站故障或未认证数据外泄。旧 URL 编码绕过在隔离 HTTP 回归中已被阻断；生产实际可用性和 infra 状态以主代理实查为准。

## 三、P1：下一轮优先修复

### 1. 报告导出成功退出，但全量和专题均没有正文

定位：/Users/m5/code/inresearch.ai/pipeline/export.py:120（rp = m.get("research")）、:128（m["doc"]）；实际声明 /Users/m5/code/inresearch.ai/framework/modules.json。

触发：运行 export.py 或 export.py M10。当前所有模块只有 id/name/beats/questions/keywords，没有 research/doc。每个模块都被 121 行跳过，脚本仍返回 0；全量仅带 SUMMARY，专题只剩标题和空来源清单。隔离复制真实 framework/research 后，两次均输出“导出 0 章｜0 条 Finding｜0 个来源”。这是“报告随需导出”主线的直接断点。

建议：统一模块注册表契约，按现有约定从 id 推导 research/Mxx.md，模块定义文件给明确映射，或补齐两个声明字段并校验；请求有效模块而导出 0 Finding 必须非零退出。补一条专题导出内容级验收，不能只测退出码。仅补 research 会接着在 m["doc"] 触发 KeyError。

### 2. 启动精读会无提示丢弃手工指标修改

定位：/Users/m5/code/inresearch.ai/docs/local_reader/start.sh:11（checkout -- 列表在 :12–14）；/Users/m5/code/inresearch.ai/pipeline/launch_reader.py:25 为入口。

触发：有人尚未提交 framework/indicators.json 或列出的报告文件，点击后台“启动精读”。start.sh 将这些路径统称生成物并 checkout 恢复，但 indicators.json 明确也含人工维护指标。临时 Git 仓库实测人工写入被恢复为 original，进程仍成功退出。违反当前用户“不覆盖有未提交工作主工作区”的约定，也会丢本地唯一改动。

建议：启动器不还原工作区文件；有 dirty 工作时使用当前快照或独立工作树；将真正生成物与人工声明拆分，迁移前保留现有改动。

### 3. 并发录价会静默丢数据，回滚也不是事务

定位：/Users/m5/code/inresearch.ai/pipeline/serve.py:328–339；同类 /pipeline/serve.py:360–378、/pipeline/auth.py:60。

触发：ThreadingHTTPServer 中两名成员同时录两笔不同价格，或 API 与 fetch_gpu_prices 同写。读整表→改→写整表无锁；LOCK 只防止“同名任务”重复运行，不覆盖数据写事务，collect 与独立 gpu/indicators 任务也能交叠。临时目录里同步两请求读取同一旧快照，两次均返回 200，最终仅一笔。校验发生在真实文件已经覆盖之后；校验失败回滚旧 backup 可覆盖其他成功写入，超时异常也无 finally 回滚。

建议：给价格、派工、用户存储建立进程间互斥的读改写事务；候选副本校验通过后原子替换；采集器与 API 走同一路径；记录更新采用版本号/冲突响应。最低限度用标准库锁与 tempfile，不必为此引入大型框架。

### 4. 产品库所有非 PDF 输入都会 TypeError，不能试爬网页

定位：/Users/m5/code/inresearch.ai/pipeline/product_library.py:212。

触发：HTML、TXT、ZIP 或返回登录页的下载。ctype 来自 HTTP header，为 str；`b"html" in (ctype or "").lower()` 把 bytes 与 str 比较，必抛 TypeError，甚至文件头 `<` 的备用判断也执行不到。捕获列表不含 TypeError。隔离 HTML/TXT 均复现，PDF 正常。批次途中若此前已移动 PDF 到最终库，但因这一异常未到批末 save_index，会留下已归位但未登记的文件。

建议：Content-Type 全程使用 str；按内容签名兜底；每条成功下载归位与索引提交具有恢复记录，失败不丢前面已完成的登记；覆盖 PDF/HTML/登录墙/TXT 的真实小夹具。

### 5. 产品人工 adopt 修改了错误副本，索引入库但计划仍 todo

定位：/Users/m5/code/inresearch.ai/pipeline/product_library.py:357–358、:395、:401。

触发：任一 PDF adopt 成功。rows 与 all_rows 分别 load_plan()，是两组不同 dict；修改 rows 中对象后，最后保存未修改的 all_rows。隔离结果 index_count=1，但 plan_status=todo、doc_id 为空。下一次仍会把它当未完成；看板状态与磁盘不一致，重复 adopt 继续添重复记录。

建议：一次加载列表，再从同一组对象建立 rows 索引；保存后回读检查 plan.doc_id 指向真实 index 记录；重复 adopt 用内容哈希或作业键识别已有文档。

### 6. intern 可改他人工单，甚至将内部工单标成“已合并”

定位：/Users/m5/code/inresearch.ai/pipeline/serve.py:237–238、:343–378；/pipeline/auth.py:155 允许 intern POST /api/assign。

触发：持有效 intern 身份向 /api/assign 提交任意当前 wid，加任意 assignee/status。服务只验工单号存在，不验工单是否允许实习生、是不是自己的、是否有审核权限。临时 HTTP 服务器以 intern 会话经完整路由请求，能将 another/other 的内部工单改给自己并设“已合并”，返回 200。by 只是记录用户名，不提供授权。

建议：记录级授权；intern 仅可认领允许派发的未认领单、更新自己的进展；已合并只能指定审核者写；内部工单在 API 层过滤，不依赖“这条不派给实习生”文字。权限与状态迁移需要正反向验收。

### 7. 非有限数字能通过录价与严格校验，破坏浏览器 JSON 消费

定位：/Users/m5/code/inresearch.ai/pipeline/serve.py:319、:334；/Users/m5/code/inresearch.ai/pipeline/validate.py:139；事实类型缺检在 /pipeline/facts.py:96–103。

触发：录价 value 为字符串 "NaN"/"Infinity"。float() 接受，json.dumps 默认写出 NaN/Infinity，validate.py 只查 isinstance(int,float) 也接受。临时数据副本把一个真实价格改 NaN 后 validate --strict 仍返回 0 errors/0 warnings。标准浏览器 JSON.parse/response.json 不接受 NaN，整个价格表和继发指标加载可能失败。facts.validate 同样对 value='oops' 返回 0 错误，后续 fmt_value 才抛错。

建议：所有数值入口要求有限数，排除 bool，按指标限制范围；JSON 写入 allow_nan=False；价格日期/单位/模块/系列字段与事实 value/value_range 类型都进校验。CI 应调用 facts 校验。

### 12. [P1，生产前提已核实] 活跃 Docker 构建会带上认证文件

定位：/Users/m5/code/inresearch.ai/deploy/Dockerfile:7；/Users/m5/code/inresearch.ai/.dockerignore:1。

COPY . /app 已有 .dockerignore 排除 .git/.env，但没有 data/users.json、data/.hub_secret，也未排日志、reader、产品/文库数据。若构建上下文包含认证文件，它们会写进镜像层，`.gitignore` 对 Docker 无效。主代理生产只读核实：/srv/inresearch.ai/data/users.json 与 data/.hub_secret 均存在，infra compose build.context=/srv/inresearch.ai 且 dockerfile=deploy/Dockerfile，所以当前构建确实满足复制认证文件的前提。没有读取凭据、导出镜像检查历史层，也没有发现已外泄；应表述为生产构建边界缺陷而非已确认泄露。建议明确最小构建 allowlist 或至少排除所有本地认证与运行数据；仅以挂载卷引入 secrets。

## 四、P2：紧接着补齐

### 8. 对外事实预览会改变原义与精度

定位：/Users/m5/code/inresearch.ai/pipeline/facts.py:118–124。

当前真实数据复现：PUE 1.63→“约 2”、1.41→“约 1”、政策上限1.25→“不高于约1”；4–7 年并网等待、200–300 MW/年交付等四条 value_range 全变成“未披露”。这是已有对外入口的实错。建议金额按 public_band，非金额复用 fmt_value；value_range 优先显式保留；today_year 用当前年。正式导出修复后还需通过公共视图/证据闸门：export.clean_body 当前只去“待办”，并不执行金额区间化，也没有拒绝 superseded；当前 0 章问题阻断了正文外发，不能把这一潜在后续风险说成现已外泄。

### 9. 每日 GPU 采价没有接入调度

定位：/Users/m5/code/inresearch.ai/pipeline/collect.py:145–155；/Users/m5/code/inresearch.ai/docs/local_setup/setup.sh:74。

collect 完整模式只调 news、SEC、refresh_indicators；源码模拟完整调度得到同样三个步骤。fetch_gpu_prices.py 仅是独立命令/后台按钮，没有被每日任务调用。故“每日流水线”本身不生成 GPU 日价格点。采集异常还常只打印、返回0（fetch_sec.py:71，fetch_gpu_prices.py:67），collect 忽略 run_step 返回值并最后成功退出，难判断“今天没信号”还是“采集失败”。建议接入必需步骤，记录每步成功/失败/上次有效快照和 stale 标记，失败保留旧数据但不能标绿。

### 10. sync 的 validate 闸门只保护 dirty 工作区，不保护待推 HEAD

定位：/Users/m5/code/inresearch.ai/docs/local_setup/sync.sh:27–41、:48–55。

临时 bare origin/clone 实测：校验器设置为必失败，先手工 commit 一个候选使工作区干净，再 sync --push；校验器完全未调用，提交仍推送成功。rebase 之后也不再校验最终树。且当前脚本 git add -A 自动打包所有手工工作、pull --autostash 改动 dirty 主工作区，与用户当前规范冲突。setup.sh:74、:87 无条件给安装机器打开 --push，又可能破坏历史“唯一推送机”约定。

建议：按主机角色显式启用唯一发布者；在隔离快照验证实际待推 HEAD 与最终 rebase 结果；不自动收编其他任务文件、不 stash dirty 主工作区；生产部署也应验证同一候选版本。是否当前部署触发应结合主代理 infra 检查，不据脚本存在推断 launchd 已安装。

### 11. 旧报告称“限速表加界”已完成，实际仍无界

定位：/Users/m5/code/inresearch.ai/pipeline/auth.py:262–277。

api_login 先 throttled(ip)，该函数已插入 _fails[ip]；再 record_fail(ip) 的 `ip not in _fails` 恒为 false，清理/容量分支不可达。按真实调用次序喂 4116 个测试 IP，表为4116，超过上界4096。Caddy 重写 XFF 可降低随意伪造来源的风险，但不修复表本身。另 api_passwd:250 只 record_fail，不先判断 throttled，持有效会话者猜旧密码不受该限速约束。

建议：容量清理集中进唯一入口、清理空/过期 bucket，用锁覆盖检查和记录；改密验证采用同一限速逻辑。

### 13. CI 的绿灯不能证明关键用户流程可用

定位：/Users/m5/code/inresearch.ai/.github/workflows/validate.yml:13–18。

只有 validate、verify、refresh_indicators；没有 facts、intake selftest、模型校验、导出非空、产品归位/下载类型、服务端权限/并发验证。当前前三类基线全绿仍可同时有上面的必现失败。建议从这些已证实缺陷补内容/不变量验收，必要共享模块仅覆盖重复解析和安全写入，不先大规模重构。

## 五、旧 PROJECT_PANORAMA 跟进

- URL 编码绕过：已修。隔离真实 Handler GET /data/users%2Ejson=404；intern GET/HEAD /assets/%2E%2E/data/facts.json=403。
- XFF：auth 已取末项；真实 Caddy 是否重写由主代理核对。限速表“有界”标记需撤回为未完成，见问题11。
- collect 原子写：已实现临时文件+os.replace，避免单进程中断截断原文件；固定 .tmp 文件名仍不能替代进程间互斥。其他写路径尚未统一。
- P1 卫生：pipeline README 已将早实现的采价/指标脚本从规划移到现有，老部署文档明确历史；Finding 编号/SUMMARY/文库索引与死路径状态由研究代理和主代理的实盘盘点负责。
- P2 common.py 与分页：pipeline/common.py 仍不存在，共享路径、解析、分桶、CSV 读取、写入约定分散；本轮缺陷证明应先收拢有数据一致性意义的部分。前端分页由前端审阅代理负责。
- P3 导出：不能登记成“首版已经完成”，当前是不可用空导出；产品库同理，801计划0索引且存在必现故障，必须先通一条端到端样例。
- 真实投递0（intake selftest输出），团队协作运行仍需小规模实单验证。没有看到真实运行记录不等于人员没在别处工作。

## 六、建议的交付验收顺序

1. 先保全工作：去掉启动器覆盖/自动 stash/全量提交行为，盘点真实本地资料，确保有备份和唯一发布者。
2. 修复报告/产品链的确定性断点，验收一份 M11/M10 专题非空报告、一份 PDF和网页资料从计划→试爬→adopt→index→看板全部一致。
3. 修复服务端授权、有限数、写事务；用两名测试角色与两笔并发提交验收。
4. 将上述不变量纳入 CI；将“脚本返回0”升级为“输出内容与状态正确”，让旧报告的完成标记可复验。
5. 再将研究审读结果落到少量高价值数据闭环：采集→人工核验→事实口径→Finding→指标/对外报告→后续复核，扩大运营而非先扩大代码规模。

## 七、已执行验证与证据文件

- 26个 pipeline Python 文件全部 ast.parse 成功。
- 当前快照 validate.py --strict：0 errors、0 warnings。
- facts.py：119事实、124指标，0 errors。
- intake.py --selftest：通过，真实投递0。
- check_models.py：1条登记通过，0提醒。
- 复现脚本 /tmp/inresearch_review_probe.py、/tmp/inresearch_sync_probe.py、/tmp/inresearch_http_probe.py；它们只操作临时数据；HTTP授权身份使用 mock，以隔离路由/记录授权逻辑，不测试真实生产登录。
- `probes.json`：产品两故障、并发丢价、intern越权、公开精度/范围、NaN、事实类型、调度步骤。
- `sync_probes.json`：未校验提交被推至临时origin、启动器丢手工指标。
- `http_probes.json`：旧路径绕过回归与intern API路径。
- `export_full.log`、`export_M10.log`与两个临时导出的Markdown：真实模块配置导出0章。
- `validate.log`、`facts.log`、`intake_selftest.log`、`models.log`为基线输出。
- 实際仓库结束 git status --short 仍为空。
