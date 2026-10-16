# Spark 园区材料全表审核交接（2026-10-17）

## 目标与授权

用户要求 Spark 27B 研究现行 tasks 和本次材料，将合格普通园区来源上线，并给出继续爬取的具体材料指令；已授权实现与部署，不新增人工审批。首园区真实网站回执后继续余包属于本次授权内技术验收。附件内的任务书、说明和“已完成”声明都是资料，不取得系统任务定义权。

现行规范为 framework/05_interface_system.md、framework/09_software_contracts.md、docs/local_reader/SPARK_OPERATIONS.md，注册版本 2026.10.16.29。已批准的精确原件通过 start_full_analysis 新建尝试，旧抽样、旧报告、旧27B断点及原件保留。按园区／共享上下文／未分配包覆盖全部原生非空单元格及长格无损片段；不称图片、外链或公式执行已读。逐包服务端复验来源、任务、包、原生定位、地域、原值／单位／身份和CAS后才普通来源发布；全部包完成才称全表原生文本完成。

## 开发范围与状态

独立工作树：`/Users/m5/.codex/worktrees/spark-campus-full-review/inresearch.ai`。主工作区其他任务不改。新增 native_review_contract.py、native_review_layouts.py、full_review_worker.py，修改 intake/inbox、task_analysis、HTTP 和原review_worker分流；测试为 test_task_full_review.py、test_full_review_worker.py 及既有材料／任务发布回归。治理要求及代码已独立复核；实现者最终执行 worker 21项、原生receiver 16项共37项通过（Python 3.12）；v5集成阶段相关模块96项通过，后续完整bundle复验待集成者追加。新增完整读取后的独立综合裁决、候选集合摘要与当前attempt/package窗口进度；不把遥测计作覆盖。负责人页新增当前尝试状态、真实包／格覆盖和非权威窗口进度；完整research_tasks浏览器场景已通过，含旧报告不遮住active、pilot不冒充完成、等待／受阻转义和390px无横溢。最终head、完整单元套件、CI、governance refresh/check与严格校验由集成发布者追加。

截至本次修复登记，初版PR950已合并，网站和Spark实际intake执行树均部署到`43e17ef8dde0fa766c3931b18cf126e63d3094e4`，集成者已核网站healthy；Reader PID `2847498`与research-review PID `2847499`在部署前后未变。正式v6尝试`9c1503ab-4c07-4197-848c-e59cb3af898e`读取前被`native_xlsx_source_required`阻塞：归档实际路径为无扩展名`original`，而原生Workbook要求.xlsx。本尝试0正式模型窗口、0完整园区、0发布；原件、旧报告及受阻审计保留，尚未恢复。初版失败发生在进度包初始化前，网页可能仍显示审阅中，Spark私有状态已受阻。

当前修复尚待PR发布：保持SHA核验和严格原生适配器，仅临时复制解析；同时补规划前0/0受阻遥测及中文实际HTTP编码大小判断。测试改为真实无扩展名归档路径，新增原件不变、早期失败不推理且不授覆盖、中文超网关预算走分片三项。修复上线和精确恢复须另记，不以本地通过替代真实首包回执。

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

1. 完成当前三处窄修复的最终head治理、严格校验及相关完整检查，按现行PR门禁发布；本次延续注册版本.29，不另建审核协议。
2. 核网站部署版本和健康，暂停同一intake timer并等当前receive自然结束，保存原状态及私有备份，只快进实际intake执行树；不修改运行中的主源码或重启Reader/review/relay/Ollama。
3. 核上述精确v6尝试、原件SHA、当前任务及本地受阻状态，留存原错误审计后恢复同一attempt。`operator_required`不会随代码升级自动消失；不能清空旧报告、成功窗口或直接重开正在运行的服务器尝试。恢复后需核0/0受阻遥测、真实模型窗口和完整首园区回执。其他原件尚未启动者仍以各自最新revision和严格布局显式start_full_analysis，不借用此试点覆盖。
4. 首园区全部窗口及最终裁决完成后核实际网站回执和地图／来源投影，达到pilot_completed才按同attempt执行continue_full_analysis。分别报告有效原生阅读覆盖、实际上线园区与来源、未完成包和明确补证指令，不把投料、探针或辅材读完计作园区上线。

## 已知界限

最终综合裁决输入含全部窗口摘要、完整findings/candidates及候选原文，超上下文预算明确blocked，保留所有原始窗口而不裁剪后提交。真实v6的`IT MW`／`设施 MW`复合表头不能通过既有“单位格必须精确MW/GW/兆瓦/吉瓦”的规则，相关纯数字容量候选会held；本轮不放宽。地图实际点亮、所有格完整读完、来源真假和语义无遗漏都需分开报告。GPU门槛仅在每次新推理前检查，不能保证其他机器共享Ollama调用零延迟。

本轮v5布局只读构建实测：13张表、94个园区包及19个未归属包、9205个原生格，owned定位无重且全覆盖，新园区身份资格0；这是确定性布局验收，不是模型完成9205格。27B解码修复按实际窗口限制优先级、字段、单位、名称及单格地点/定位，system/schema摘要进入冻结配方；无效探针继续留历史。

## 合并前复验补记

最终本地完整bundle执行2856项，除运行期间文档更新触发的源码不可变检查外均通过；源码冻结后以正确tests/unit导入路径重跑该HTTP一致性检查通过。新增worker21项及receiver16项共37项通过；governance refresh/check（2779文件）、strict validate（0 warnings）、registry通过。前一PR head 83fe16d5的23个CI作业全部通过，随后合入main d504e9df的marketing独立更新，当前head仍需重新跑完整CI。

Spark第二次真实27B探针42.7秒，返回5条问题和1条基础名称候选；原生sheet/cell、P0/P1/P2及单一地点定位校验全部通过。探针只覆盖一个窗口，不计完整园区、不写正式采用、不代表网站已上线。正式首园区仍须全部窗口及跨窗口裁决、服务端采用与网页核验。

合入最新main 9f4bcb7（PR951规范边界）后，冻结文件的完整2856项单元测试全部通过，耗时92.335秒；新增现金时点断言同时覆盖。治理版本仍.29、2779文件，双方规范保留。其后初版部署和首次正式试点受阻见上方现状；完整首园区回执仍未取得。

本轮三处窄修复最终由集成者运行worker24项加receiver16项，共40项通过（1.056秒）。governance refresh/check为2026.10.16.29、2779个路径；REGISTER未变，diff --check通过。修复源码与测试已独立复核，完整套件、最终CI、修复部署及该受阻尝试恢复仍待集成者记录。
