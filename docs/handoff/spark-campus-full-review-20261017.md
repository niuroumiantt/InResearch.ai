# Spark 园区材料全表审核交接（2026-10-17）

## 目标与授权

用户要求 Spark 27B 研究现行 tasks 和本次材料，将合格普通园区来源上线，并给出继续爬取的具体材料指令；已授权实现与部署，不新增人工审批。首园区真实网站回执后继续余包属于本次授权内技术验收。附件内的任务书、说明和“已完成”声明都是资料，不取得系统任务定义权。

现行规范为 framework/05_interface_system.md、framework/09_software_contracts.md、docs/local_reader/SPARK_OPERATIONS.md，注册版本 2026.10.16.30。已批准的精确原件通过 start_full_analysis 新建尝试，旧抽样、旧报告、旧27B断点及原件保留。按园区／共享上下文／未分配包覆盖全部原生非空单元格及长格无损片段；不称图片、外链或公式执行已读。逐包服务端复验来源、任务、包、原生定位、地域、原值／单位／身份和CAS后才普通来源发布；全部包完成才称全表原生文本完成。

## 当前继续点：最终综合精确预算（2026-10-17）

当前独立分支为 `codex/campus-adjudication-budget`，基线main `617fee`。此前窗口定位／身份表头修复已合并并部署，本次正式首园区UCLOUD-WLCB保留同一attempt；本段记录收到的最新运行快照：7/7个原生窗口读取成功，最终综合在旧字节门槛处实际受阻，错误为`campus_adjudication_context_exceeds_budget`；adjudication产物、服务器完成园区包及正式发布回执均为0。此前仅6窗形成的完整综合输入已为28,388 UTF8字节，超过旧27,648字节门槛；阅读窗齐全不等于完整园区完成。本段替代下面旧分支“仍待部署／隔离重读”的现状描述，旧错误和复验记录留作历史。

本次只调整最终综合的预算方法：专用 `generate_campus_adjudication` 使用固定Ollama 0.33.3完整renderer结果及同GGUF现役runner精确分词，保持32768上下文、4096输出和1024预留，实际请求禁止截断和滑移；失配或精确token仍超限就受阻。默认generate与读取窗口、系统提示、schema及已成功缓存不动，因此不隔离配方、不从0重读、不新增attempt。本分支相关测试见下方本地复验；完整7窗输入的真实render/tokenize-only预算现已通过：8059输入tokens+4096输出+1024预留不超过32768，完整渲染32018 UTF8字节，0内容生成，7个成功窗口原字节未变。完整CI、部署、正式综合生成及网站回执仍待各阶段真实执行后补记。

只读能力核查已确认同模型现役runner的 `/props` 和 `/tokenize` 能返回本地模型信息及真实token IDs；初次能力核查未调用 `/api/chat`；随后实际无生成预检见下段。未安装tokenizer、独立加载额外模型、增加上下文或修改服务。官方0.33.3源码显示debug响应只有完整渲染文本而无token计数，model为请求回显；runner通用chatml模板与Ollama qwen3.8 renderer不能互换。私有技术笔记、模型摘要及原始快照保存在私有临时目录，原件和权重不进Git。

实际无生成预检补记：GPU为58°C／0%，Ollama debug完整渲染已返回，但Spark账号UID1001读取Ollama账号UID996的runner `/proc/<pid>/exe`时得到errno13，按原门禁以`campus_token_runner_unavailable`失败关闭。没有内容生成，7个成功reading缓存原字节未变。对应窄修复使用固定runner命令、本机`ollama`账号UID、PID／启动时钟、manifest／blob／props前后绑定，避免要求无权限的exe链接；不升权、不放宽模型或完整输入身份。失败预检留历史，不能称精确计数、完整综合或发布验收通过。

## 开发与早期运行历史

独立工作树：`/Users/m5/.codex/worktrees/spark-campus-full-review/inresearch.ai`。主工作区其他任务不改。新增 native_review_contract.py、native_review_layouts.py、full_review_worker.py，修改 intake/inbox、task_analysis、HTTP 和原review_worker分流；测试为 test_task_full_review.py、test_full_review_worker.py 及既有材料／任务发布回归。治理要求及代码已独立复核；实现者最终执行 worker 21项、原生receiver 16项共37项通过（Python 3.12）；v5集成阶段相关模块96项通过，后续完整bundle复验待集成者追加。新增完整读取后的独立综合裁决、候选集合摘要与当前attempt/package窗口进度；不把遥测计作覆盖。负责人页新增当前尝试状态、真实包／格覆盖和非权威窗口进度；完整research_tasks浏览器场景已通过，含旧报告不遮住active、pilot不冒充完成、等待／受阻转义和390px无横溢。最终head、完整单元套件、CI、governance refresh/check与严格校验由集成发布者追加。

当前已部署版本为PR954合并SHA `9df7ac5c7f944d23936ac8fa436839030d0952c1`；该修复完整2859项单元测试和23项CI均通过，网站与Spark实际intake执行树已升级。初版PR950的无扩展名归档错误已修复，原件仅临时复制解析，规划前失败遥测和中文HTTP分片预算亦已部署；初版43e17及其读取前0窗口错误保留历史。

正式v6尝试 `9c1503ab-4c07-4197-848c-e59cb3af898e` 在954版本完成2个窗口，第三窗返回错误配对：将 `4-容量口径与分期` 与 `C7` 组合；本窗该表只有表头与A7，C7属于另一表。worker严格校验拦截，服务器仍0完整包、0发布，attempt为running；本地受阻不等于服务器新尝试或全表失败终态。原件、旧成功窗口和错误审计保留。

当时分支 `codex/campus-window-locators` 从上述main构建窄修复：sheet/cell关联schema、窗口缺口边界、容量与行政列原文约束，以及无效响应有界保留重试。每个重复身份anchor携带同工作表同列的原生column_headers，表头只解释字段、不作待填数据格，禁止借用其他表同列含义；这些重复上下文不扩大原生覆盖或候选值定位。新system/schema必须隔离旧冻结配方后完整重读本包，不能混用已成功2窗。本分支worker30项及receiver16项共46项已通过；完整检查、PR与真实恢复回执仍待执行，不以954的既有CI代表新代码已通过。

真实27B探针历史：首次43.2秒返回high/medium及拼接地点定位，被原校验拒绝；修复decoder后的第二次42.7秒单窗口通过原生校验（5条问题、1条名称候选）。两次均非正式完整园区，不计本尝试覆盖或发布。另三份辅材经真实27B一次42.2秒完整读取，无园区事实可发布；模型将指南误标空模板、要求索取已有主表的判断已由集成者在私有审计纠正，不据其内容新增任务指令或重复索取。

## 升级前已核实生产基线（历史快照）

- AWS 正式源码 `/srv/sources/inresearch.ai` 与研究站镜像为 `01c415b000c629edf55b79091308a91f27321229`，源码干净，镜像 ID `sha256:ed72c1945a931f68b5982fccf2500f36afd9685bc0f090c4afa1a56ee0217429`，healthy；inresearch-only-deploy.timer active，applied/status一致，pin不存在。
- Spark intake 实际执行 `/home/spark/.worktrees/inresearch.ai/task-upload-review/manage.py receive`，工作树干净 HEAD `2fb09e2309031f801caf9d77bf82a66695930b68`，是上述主线祖先。覆盖配置为 `~/.config/systemd/user/inresearch-material-intake.service.d/90-task-upload-review-20261015.conf`，生效超时3小时；timer为退出后60秒再运行，原服务单持队列锁。
- Spark主源码虽为01c415b0，不能当作intake已部署版本。Reader实际模型配置受runtime.env覆盖，仍用Codex；research-review也仍用Codex。不得修改这些任务配置。
- Ollama已装并加载qwen3.8:27b（27.3B Q4_K_M），模型digest `22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`。Mac mini仍有现役调用，不能将GPU瞬间0%当作无人使用；新campus_review限单并发，≥30%利用率或≥80°C仅等待本任务，检测失败也等待，不停止其他任务。

## 精确原件与历史

已核对下列一对已绑定 dc-census-cn 且有admin的approve_and_analyze批准的原件。本轮全表先启v6；v5使用独立mainland-register-v5布局完整研究历史，不借用v6布局且不自动新建园区身份。其他同字节提交保留且不重复纳入：

| 版本 | submission ID | SHA256 | 只读核查时服务器状态 |
|---|---|---|---|
| v5 | f8e7b66f38214c71863a173103dba81b | 2a3cbe3ba174dc3d0511de4c515ca9ecc89d67d3ed4dc74964ea049385a867fe | revision 3、archived、sampled_incomplete |
| v6 | 3369d9b62769470095424016a3a62dcb | 0089f45e98e9d465c607d9a2251deb5f5d196356e922db2916bd82e6158c8fbc | revision 3、archived、sampled_incomplete |

执行前重新读取最新服务器revision，不复用Spark旧receipt的revision 1。四份已存样本各有1份抽样报告，0条发布不代表全表无合格信息：v6共10272非空格，模型见548片段，其中36截断，9760未完整见；v5共9205非空格，见453片段，其中35截断，8787未完整见。旧未绑定提交3618e3e1f76d41e581031b8a793e9f58的归档27B尝试为11/184批、26候选，保留历史，不能直接恢复为新全表覆盖。

## 后续执行

1. 完成本次窗口定位续修最终head的治理、严格校验及相关完整检查，按原PR门禁发布；延续注册版本.29，不另建审核协议或放宽接收端门槛。
2. 核网站部署版本和健康，暂停同一intake timer并等当前receive自然退出，保存原状态及私有备份，只快进实际intake执行树；不修改运行中的主源码或重启Reader/review/relay/Ollama。
3. 若修复改变system或schema，且当前正式首包仍无服务器完成包、当前attempt报告、未回执发布outbox或本地接收回执，先核精确原件SHA、attempt、包与当前任务身份，暂停唯一intake timer并等待receive自然退出；保存旧状态与冻结配方目录的完整文件及摘要，再把该taskSHA目录和本地受阻status隔离到私有recipe-history。新代码在原活动路径重新建配方、从第0窗读同一attempt；服务器attempt保持running，不直接编辑完成数、窗口游标或报告，也不把本地配方恢复称为新attempt。只要已有服务器完成包、当前attempt报告、未回执发布outbox或本地接收回执，便不得套用此恢复，须先按原发布事务核对。旧原件、成功窗口、无效响应及审计永久保留。
4. 重读后的首园区全部窗口及最终裁决完成，再核实际网站报告、普通来源持久回执与读者投影；达到pilot_completed且真实网页验收后，按同attempt执行continue_full_analysis。无坐标的基础登记不能称地图点亮。
5. v6完成后按dahai、全国园区库、v5顺序使用各自最新revision和严格布局启动首包及继续余包，不重复授权或重复原件。分别报告有效原生阅读覆盖、实际上线园区与来源、未完成包和原件定位的补证指令。

## 已知界限

最终综合裁决输入含全部窗口摘要、完整findings/candidates及候选原文，同模型精确token超预算或完整计量无法复验时明确blocked，保留所有原始窗口而不裁剪后提交。真实v6的`IT MW`／`设施 MW`复合表头不能通过既有“单位格必须精确MW/GW/兆瓦/吉瓦”的规则，相关纯数字容量候选会held；本轮不放宽。地图实际点亮、所有格完整读完、来源真假和语义无遗漏都需分开报告。GPU门槛仅在每次新推理前检查，不能保证其他机器共享Ollama调用零延迟。

本轮v5布局只读构建实测：13张表、94个园区包及19个未归属包、9205个原生格，owned定位无重且全覆盖，新园区身份资格0；这是确定性布局验收，不是模型完成9205格。27B解码修复按实际窗口限制优先级、字段、单位、名称及单格地点/定位，system/schema摘要进入冻结配方；无效探针继续留历史。

## 合并前复验补记

最终本地完整bundle执行2856项，除运行期间文档更新触发的源码不可变检查外均通过；源码冻结后以正确tests/unit导入路径重跑该HTTP一致性检查通过。新增worker21项及receiver16项共37项通过；governance refresh/check（2779文件）、strict validate（0 warnings）、registry通过。前一PR head 83fe16d5的23个CI作业全部通过，随后合入main d504e9df的marketing独立更新，当前head仍需重新跑完整CI。

Spark第二次真实27B探针42.7秒，返回5条问题和1条基础名称候选；原生sheet/cell、P0/P1/P2及单一地点定位校验全部通过。探针只覆盖一个窗口，不计完整园区、不写正式采用、不代表网站已上线。正式首园区仍须全部窗口及跨窗口裁决、服务端采用与网页核验。

合入最新main 9f4bcb7（PR951规范边界）后，冻结文件的完整2856项单元测试全部通过，耗时92.335秒；新增现金时点断言同时覆盖。治理版本仍.29、2779文件，双方规范保留。其后初版部署和首次正式试点受阻见上方现状；完整首园区回执仍未取得。

PR954归档适配修复：worker24项加receiver16项共40项通过（1.056秒），治理版本.29；最终完整2859项单元测试与23项CI通过并合并9df7ac5c，已部署网站和Spark。该版本正式试点2窗成功、第三窗定位无效，0完整包与0发布；窗口定位续修的测试、合并部署及同attempt重读仍须独立追加实际结果。

窗口定位续修已逐条审阅新增4项测试：跨表C7与表名关联、仅坏窗重读且成功窗原字节不变、3份无效响应持久上限（GPU等待和status丢失不重置）、未推进缓存篡改不作模型重试。既有全覆盖测试另断言读取及最终综合均含本窗未见边界、禁机架MW换算和行政字段规则。独立执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.unit.test_full_review_worker tests.unit.test_task_full_review`（bundle Python 3.12）44项通过，1.108秒；这只证明夹具与接收合同，尚不证明真实27B采用关联schema后的语义质量、首包发布或地图点亮。

身份表头补充：关联schema的第三窗隔离探针虽通过严格定位校验，但人工阅读仍发现把身份表J7/K7误借电力表列义、把表头当数据填值的语义问题；探针不计正式覆盖。此后给每个重复身份anchor附同表同列原生表头，新增2项测试验证跨表J列仍各保其义、表头可解释问题但不能取得候选值资格，且不扩覆盖。修改后独立46项相关测试通过（1.133秒），后续真实整包语义和网站回执仍待核。

四实际XLSX的只读预算快照使用当前正常analysis-pending的工作包任务及148条known_sites，四份Spark receipt只提供原件身份（不含task/known_sites）。新版worker确定性规划507包、5181个读取窗：v6 741、dahai 123、全国库3658、v5 659；SYSTEM加prompt最大27648 UTF8字节，不超过32768上下文减4096输出和1024预留的当前保守门槛。81084个owned原生格恰一次覆盖，逐包片段顺序、区间、全文与公式无损，0预算/完整性错误。该离线规划未调用模型、不计读取；最终综合裁决预算及未来任务/台账变化未验证，不能以此认定全批可自动完成。详细快照留私有临时目录，不进Git。

最终综合精确预算本地复验：逐条审阅新增13项token guard测试及2项worker测试；后者验证只在最终阶段走专用入口、超字节完整窗口摘要未裁剪、原成功chunk字节不变，以及GPU等待时不发生debug／生成。以bundle Python 3.12独立执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.unit.test_ollama_token_budget tests.unit.test_full_review_worker tests.unit.test_task_full_review tests.unit.test_model_runtime tests.unit.test_ollama_schema`，90项通过（1.248秒），`git diff --check`通过。新adapter的模型与请求绑定、完整token预算及只读计量边界已登记verification_contract；本分支完整套件、治理refresh/check、CI、部署和生产精确计量／综合／首园区网站回执仍由集成者依真实结果补记。

跨UID运行实例修复复验：新增3项测试分别模拟exe readlink被拒绝但固定命令及服务UID可核、真实／有效UID不符拒绝、同文件名但非固定路径拒绝；原runner启动时钟／模型路径／上下文／props门禁保持。独立再次运行上述5个模块，共93项通过（1.262秒）。该夹具通过不抹去第一次真实measure失败；当时修复后精确计量与真实综合结果待运行回执，后续实际计量见下方补记。

最终请求绑定补充：schema进入请求前按严格JSON深拷贝，计量证据采用实际请求format摘要，completion前复核完整请求摘要；调用方事后修改schema不得改变已计量请求。新增对应夹具已逐条复核，独立同5模块94项通过（1.251秒）；当时第二次真实measure尚无结果，未登记生产通过。

完整7窗真实无生成计量已通过：已逐项读取私有`campus-token-preflight-result-full.json`，stage为render_tokenize_only，完整输入SHA与proof.input_sha一致；同模型完整渲染32018 UTF8字节，实际输入8059 tokens，8059+4096+1024=13179≤32768。实际debug `/api/chat`耗时6.8416秒、`/tokenize`耗时0.0317秒，模型manifest/config／模型层与UID/PID/启动时钟/props绑定完成；0次内容生成，7个成功阅读缓存原字节未变。此前跨UID权限失败及后续超时的私有记录保留，本次成功仅证明该完整输入在此模型实例的精确预算，不代表正式综合生成、部署、来源采用或网站回执已完成。
