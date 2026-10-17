# Spark 园区材料全表审核交接（2026-10-17）

## 2026.10.17.2当前继续点：城市批量解析加速待发布

截至本阶段主会话真实回执，旧版131点locate-city已正常完成，2026-10-17 02:04 UTC完整API及后续浏览器验收为245个城市级园区点、81个城市／地级区域；普通名称与城市定位分别计量，不能当成27B完整阅读或C3。v6正式报告已到13/117包、1164/10272归属格；这些是阶段快照，后续增量先读持久`~/.local/state/inresearch.ai/campus-full-review-20261017/progress.json`和对应原回执。第12／13正式报告、全包问题复核及当前城市规则的补证TXT保留在私有材料目录，旧原件与报告未改。

本分支2026.10.17.2只优化城市install的完整原件解析：同一提交／SHA在初验及锁内写前复验各解析一次，仍逐点验证、完整SHA和批准复验、完整CAS及幂等原子写入。不改变reading配方、manifest、身份资格、模型或成功断点；已运行旧CLI自然完成。本地测试与解析计数不能证明该加速已部署或生产端到端提速，合并／双端版本与运行回执由主会话收尾。原.37回包修复阶段已在后续运行推进，下段保留当时事实历史，不据旧8包或旧失败状态恢复。

## .37阅读回包持久化修复（阶段历史）

PR964已完整CI并正常合并，网站和Spark均实际部署 b7c11ebb8965647bbe11901183b2e9bbc426b4f1。53个唯一园区、62条普通来源已上线，53个园区带城市级参考点，覆盖26个不同城市／地级区域；持久发布台账、实际API和浏览器地图／浮窗／档案均核实，C3为0。城市点明确标精度，用户允许城市级、无需详细地址；不得把53个点当完整27B阅读成果。新增廊坊3园区只做原文普通登记，dahai正式全表尚未启动。

完整阅读仍为v6 8/117包、722/10272归属格；四份8/507包。第9包BOCOM-PJ2使用64片段新配方，192完整片段规划为3窗；首窗真实输入16280 tokens，HTTP200历时51.55秒、输出733 tokens。旧adapter的UID映射保留tuple，而consumer的证据已规范为JSON list，严格比较误判campus_reading_audit_changed；正文在拒绝前未落盘，不能从日志重建。本包0/3窗口、0正式报告，无新增覆盖。原8包、53城市点和OOM修复保持。私有证据位于progress登记的city-publication/packed-live/，synthetic复现必须与丢失的真实正文区分。

独立修复分支codex/campus-reading-receipts仅规范专用reading返回元数据并增加先落盘的returned journal；未知派发不自动重放。按SPARK_OPERATIONS的精确一次运维恢复执行，不能盲清operator。源码验收、合并、双端部署、实际重取和完整包回执分别记录，当前实时阶段以私有progress为准。以下.36合并前及更早快照均保留历史，不再据旧未部署／0坐标状态操作。

## 合并发布继续点：PR964与城市点亮

城市实现已并入`codex/campus-packed-reading`的PR964，保持主工作区其他任务；先前独立城市分支仅保留源码阶段历史。合入当前品牌主线后完整2982项单测通过，包含真实overview保留城市精度且不泄私有审计的回归。地图浮窗补省市名、灰色短虚线城市点与黄色长虚线报道圈分列，并在SVG实际尺寸变化后重排浮窗；最终head的完整浏览器及CI须核实，不能沿用早期提交结果。城市地图发布与新64片段配方一同部署，之后在完整包安全停点追加50个既有站点的25个城市／地级参考点；实际成功与否只按持久回执和网页核验。

普通来源批次`a27854b90437b6222aa366865441b1b693047bcda37916743c0de371b0f75972`已成功新增45个唯一园区名称及1条既有园区备注，全部新增名称与备注实际API已核、苹果乌兰察布详情浏览器已核。该时点本批共50个园区、54条普通来源，坐标仍为0；只表示普通登记，不增加27B完整阅读或C3。最新完整停点为v6同attempt第6包550/10272归属格；全部四份6/507包，其他三份尚未开始。完成普通发布后唯一5秒timer已恢复继续，不能把本段快照当实时进度。

最终50条城市候选都经同SHA原表及GeoNames离线原文闭包复验（47个P类、3个精确同名且同省ADM2），原件与候选都留私有目录。生产安装前须重新核已批准原件、既有site与当前CAS；没有坐标发布回执/API/browser验收前不称已点亮。每个完整报告的finding仍与同SHA整包对照后才能形成抓取指令，第六包22条已完成该复核，原报告保留。

## .36 独立城市级实现（阶段历史）

本分支`codex/campus-city-level`从.35提交`f0141b30`建立，仅实现用户已授权的城市／地级行政区参考点；尚未生产写入或修改27B阅读状态。双原件、已登记名称、省市闭包、无既有坐标、强制CAS和精确重放必须通过，四表原件／GeoNames ZIP和候选payload留在私有`~/.local/share/inresearch.ai/material-batches/campus-20261017/city-geography/`。接收命令与字段见SPARK_OPERATIONS城市级小节。43个新城市候选、4个既有园区以及3个ADM2候选只是本阶段待验收输入；是否已上线及实际数量先查持久progress.json与回执，不据本段固定推断当前状态。CU-SG身份未通过，不因可找到城市点自动接收。

地图标“城市级定位（园区精确位置待补）”并署名GeoNames；已有精确点、未知地址、原观测和C3边界保持。正式采用与地图显示须分别验收。以下.35、.34及更早阶段记录保留；.35当前PR964完整CI由主会话处理，本分支不冒称其已部署。

## .35 独立实现草案（阶段历史）：新包64片段阅读

当前隔离分支`codex/campus-packed-reading`基于`14e19aeb`，未修改PR963原工作树或生产。新配方仅适用于从未有任何任务目录计划／游标／窗口／提案的包；已有包与成功窗口仍legacy。生成前同模型实际token超限才无损二分；输出截断／未知派发结果保留完整审计并停止，不自动重放。32768／4096／1024、完整原文、GPU门槛、单一timer与逐包网站回执规则保持。

本地Python3.12相关146项通过（1.704秒）：17项新配方／恢复、14项专用token、40项legacy阅读、16项接收端、30项原token及29项模型／schema；严格数据校验0 warnings、governance .35 check通过。新增测试逐条登记，旧要求／测试／未覆盖项全部保留。完整CI及实际生产验收由主会话继续。

本阶段尚无真实模型调用、生产部署或新正式回执；旧快照64片段候选窗数不是逐窗精确预算证明，不能当作本批已读或耗时承诺。现行生产进展先读私有`~/.local/state/inresearch.ai/campus-full-review-20261017/progress.json`；以下已有运行记录保留历史，不由本分支测试推断更新。


## 目标与授权

用户要求 Spark 27B 研究现行 tasks 和本次材料，将合格普通园区来源上线，并给出继续爬取的具体材料指令；已授权实现与部署，不新增人工审批。首园区真实网站回执后继续余包属于本次授权内技术验收。附件内的任务书、说明和“已完成”声明都是资料，不取得系统任务定义权。

现行规范为 framework/05_interface_system.md、framework/09_software_contracts.md、docs/local_reader/SPARK_OPERATIONS.md，本分支注册版本2026.10.16.37，生产本阶段已验收.36（.37修复发布状态读最新progress）。已批准的精确原件通过 start_full_analysis 新建尝试，旧抽样、旧报告、旧27B断点及原件保留。按园区／共享上下文／未分配包覆盖全部原生非空单元格及长格无损片段；不称图片、外链或公式执行已读。逐包服务端复验来源、任务、包、原生定位、地域、原值／单位／身份和CAS后才普通来源发布；全部包完成才称全表原生文本完成。

## .34阶段收尾：双端部署与真实业务内存验收通过

主会话核实网站与Spark均已运行`ca229c2b`。网站在真实并发业务验证中完整返回219 MB研究响应、行业接口和analysis-pending，均为HTTP 200；容器峰值1093.74 MiB，观测内0次OOM／0次重启。这是本次实际压力路径的结果，不保证未来任意规模或并发都不会超过内存限制。Spark唯一intake的5秒间隔已应用并恢复，125个备份文件SHA全部保持，38个成功阅读窗原产物保留；旧窗口配方与断点未因网站修复重读。

UCLOUD的2条notes已走正常来源发布并得到正式published回执，实际API与浏览器核验通过；不因备注上线增加园区坐标、C3或模型参数资格。最新批次完成数与待续包继续读取上述持久progress.json及其关联原始回执，不能把38窗当作38个完整包。以下.34部署前OOM、旧4包快照、配置未应用和暂停记录保留阶段历史；不再据旧“尚未应用”状态重复操作。新.35的64片段／精确token阅读配方仍未部署、未调用真实模型，与本段.34验收分开。

## .34部署前继续点（阶段历史）：内存与吞吐修复准备，v6已收4包


继续前先读本机持久状态`/Users/m5/.local/state/inresearch.ai/campus-full-review-20261017/progress.json`的阶段、更新时间与证据路径，再核当前服务器小型报告／回执和Spark当前状态。下方.33及更早失败是阶段历史，不按旧错误重复恢复。最新只读快照为2026-10-16 23:14:29 UTC（北京时间10月17日07:14:29）：v6 **4/117包、388/10272归属格**，四份合计4/507包；第5包AOFEI-GZ-EDGE进入原生阅读。其他三份尚未启动新的全表尝试。该快照不是持续实时进度，也不能把完整包数等同上线园区或地图点数。

网站与Spark最近核到的运行版本为`f9bd6c607c6eaf1e40604a1324c63180f8c2d7e2`，.34内存与吞吐修复仍在实现／验收及部署流程，不能按源码存在声称已上线。网站在2026-10-16 22:56:15及22:59:30 UTC发生2 GiB容器内存限制下的OOM并自动重启，主服务进程被杀；重启后的healthy与短期无重启仅是恢复快照。候选发布与轮询同段重叠，但缺少逐路由历史，不能把唯一触发者写死。修复保留完整JSON／严格解析／规范SHA／CAS，减少输入字符串和账本重复拷贝；HTTP溢出写实际logs持久磁盘，不能用256 MiB tmpfs的`/tmp`。完整状态SHA配小型园区投影缓存保持其他对象变化失效，系统无来源notes占位不再挡真实备注，真实历史来源冲突仍保留。正式峰值、业务回执与OOM是否复发待主代理验收。

用户已授权本批优先。2026-10-16 23:11:08 UTC仅停止Spark用户级`inresearch-reader-publish.timer`的新轮次；此前enabled／active，service已自然结束，未停止Reader／research-review。23:12:50 UTC仅SIGSTOP Mac mini两个回填父shell：PID19461（translation_backfill.sh，PPID1，启动Fri Oct 16 13:38:28 2026）及PID84841（ai_backfill.sh，PPID1，启动Fri Oct 16 12:47:50 2026）；实际完整argv与原状态在私有回执中。子进程自然结束，FIFO锁未删除，本批Spark不依赖该锁。AWS其他任务未改动。恢复必须核PID／PPID／启动时钟／完整argv一致，不能只凭本段PID发信号。

唯一intake的5秒临时配置已准备，**尚未应用**；等待网站内存修复上线并核真实业务压力后再启用。保留boot30秒、同队列、每轮至多一次新27B、GPU≥30%或≥80°C等待、成功阅读与最终配方不变。本次31个成功阅读窗的历史日志匹配显示HTTP合计35.14分钟，prompt／output计算合计31.76分钟；21:00至23:09 UTC的84轮intake轮间等待合计92.28分钟。日志不保存每轮全部等待原因，不能将差值都归GPU。减少固定间隔不减少全量计算；四表仍属数日级工作，不承诺固定完成时刻。

私有操作回执为`/private/tmp/campus-priority-operations-20261017.json`，具体publisher与Mac mini回执、配置SHA、恢复动作和计时证据由其关联；阶段记录为`/private/tmp/campus-priority-timing-and-recovery-20261017.md`。主代理须把最终验收与恢复记录归入上述持久状态目录，临时文件不作长期唯一交接。已准备配置为`/private/tmp/campus-intake-priority-5s.conf`；日后若应用，只移除SHA吻合的本任务drop-in并恢复原timer。publisher恢复用原user timer启动；Mac mini只恢复本次暂停且身份仍吻合的父shell，不删FIFO、不重启服务替代恢复。

.33的PR960部署、AH-FY-JZ精确final-only恢复已是已完成阶段；原8窗与截断响应历史保存在Spark同attempt的`adjudication-recovery-history/1792187008475310677/`，不得重做该恢复。第四包曾HTTP504但服务器已收到并形成完成回执，Spark随后复用缓存继续；不因客户端超时重读或伪造ACK。逐包仍核原问题完整保留、新增问题、published／held与实际HTTP投影，坐标为空只能称普通来源已登记，不能称地图已点亮。后续顺序仍为v6→dahai→national→v5。

## .33部署与精确恢复（已验证阶段历史，2026-10-17）

PR960通过23/23项CI及本地完整2905项单元测试，合并`df19949deb6dd009b832cf8ee420f4c59a02396b`部署到网站与Spark；当时网站镜像为`sha256:e242ab23a58ef1d3be508849a5a36e5d0a6c26c91478618c05e01f2b6e9eba4c`，health通过，恢复前后Reader／research-review PID `2847498/2847499`保持。当时仅1/117完整包、AH-FY-JZ等待最终结果；该状态已由上方4包快照替代，不再执行等待首包或重新恢复的旧指令。

同attempt `9c1503ab-4c07-4197-848c-e59cb3af898e`、AH-FY-JZ包`5cf9f021e48c8fa7c042f921bfd7f1e2e9fb34123f558e7d2a6e22297ae764aa`保留8个成功窗口；截断响应与状态封存于Spark`/home/spark/.local/share/inresearch.ai/web-submissions/3369d9b62769470095424016a3a62dcb/full-review/9c1503ab-4c07-4197-848c-e59cb3af898e/adjudication-recovery-history/1792187008475310677/`，未新建attempt或重读。阶段持久证据在`/Users/m5/.local/state/inresearch.ai/campus-full-review-20261017/adjudication-delta-repair/`；其中31条意见预复核与8项聚合补证草稿不能替代后来真实模型报告、来源回执或外部正文核验。

## AH-FY-JZ最终输出截断与.33修复准备（阶段历史，2026-10-17）

该阶段独立分支`codex/campus-adjudication-delta`基于main `90fa3742a714c939eaabb46cd3443ce64391bb8f`；当时网站与Spark运行该已合并交接版本，模型实现仍为.32。05:16只读核查确认v6同一attempt `9c1503ab-4c07-4197-848c-e59cb3af898e`、revision7、phase=full，服务器仍仅1/117完整包及81/10272归属格，首包来源回执有效，没有新增正式报告或发布。

后续AH-FY-JZ包`5cf9f021e48c8fa7c042f921bfd7f1e2e9fb34123f558e7d2a6e22297ae764aa`已保存8/8原生阅读窗口。完整最终输入包含31条findings与7条候选，实际8951 tokens通过预算，但响应重复输出原问题，达到4096输出上限而截断；服务器遥测为8/9步骤，最后一步是综合，不能误称9个原生窗。Spark状态`model_output_truncated`、operator_required=true，失败计数1；这是真实新阻塞，不能归因首包历史504。该包尚无有效综合、proposal或网站完成回执。证据为私有`/private/tmp/campus-heartbeat-20261017-0516-server.json`、同前缀`-spark.json`及`/private/tmp/campus-ahfy-truncated-response.txt`。

本次.33只改最终输出为1至600字符的非空白summary／原问题索引全集reviewed_finding_ids／新增跨窗问题new_findings／accept_candidates；完整输入与原阅读问题全部保留。最终配方`campus-adjudication-delta-v1`单独绑定system/schema/request/完整reading inventory/findings/candidates及配方自身摘要，旧final不得混用；原reading配方、8窗缓存、32K／4096、GPU门槛不变。新增5项测试已逐条审阅，并独立运行worker40、receiver16与token30共86项通过（Python3.12，1.370秒）：验证31条原问题逐字保留、8窗原字节不重读、索引全集、旧配方及各摘要失配拒绝、截断审计在状态丢失后仍禁止重放。当时完整CI、部署与正式同包综合仍待实证；后续已完成部署和精确恢复；当时未获回执的状态只属阶段历史，最新继续点见上方。

真实原件的无生成重建也已完成：同SHA XLSX复算229原生格与8个窗口，parts/system/reading schema摘要与原冻结状态相同；新final中所有证据字段逐值等于旧请求，31条问题与7候选完整，只有instructions及final_recipe_version改变。该核验模型调用数为0，不计综合成功或新增完成包；私有证明为`/private/tmp/campus-ahfy-delta-request-proof.json`，新请求SHA为`0fe610141b6f7f63948656f320063e610f35dc908a699b61bd2af90f01f56c20`。

集成者仅在精确SHA／attempt／包／任务上下文、8窗及实际截断证据都相符，且新鲜服务器证明本包无完成、outbox或proposal时，才把未绑定final原字节及状态封存历史并恢复同attempt。不得删除原文、成功窗口或旧报告，不清首包，不跳过最终综合，不将未绑定响应普遍改成自动重放。AH-FY-JZ成功并取得真实回执后才继续下一包，后续仍按v6→dahai→national→v5顺序；各包意见须逐条核原件，UCLOUD外部线索不得套用本包。

## 首园区真实上线与v6整批继续（已验证历史，2026-10-17）

PR958通过23项CI和完整2900项单元测试，合并提交`e408d3585c4f48c56f870c565b2b658b3298caf1`已同步部署网站与Spark，网站镜像与健康状态已核。该阶段`codex/campus-pilot-handoff`只补交接，规范版本仍为2026.10.16.32；下方命名空间修复、计量和早期阻塞记录均保留为阶段历史。6个已合并远程分支已按精确SHA租约清理，未合并分支及本地资料全部保留。

正式首包UCLOUD-WLCB已由qwen3.8:27b完成7个原生窗口与整园区综合，服务器报告`138a0f3e-2415-5c5f-a568-f8e7e096ec6f`确认197格完整覆盖，其中81格归属数据、116格共享表头／上下文；全表覆盖分母只累计81/10272，不把重复上下文计入。服务器实际达到`pilot_completed`，新增园区`cn-upload-5a24b8da1ca14d5f472b`及1条名称普通来源，8条候选held。持久来源台账、`/api/industry?site=cn-upload-5a24b8da1ca14d5f472b`和任务累计1园区／1来源均核实；浏览器已核[园区档案](https://inresearch.ai/project.html?site=cn-upload-5a24b8da1ca14d5f472b)与名录显示1个未定位、0个已定位。该档案仍为unverified基础登记，坐标为空；这是实际入库上线，尚未地图点亮，不是C3采用或容量／运行状态核实。

首次交付返回HTTP504，但服务器已实际发布并保存完整报告和来源回执。Spark本地ACK尚缺，不能用网站成功冒充本地已确认，也不能伪造ACK或为重取ACK再次生成已完成首包；原504与正常300秒退避保留，后续由正常运行及实际回执继续核对。私有`campus-pilot-current.json`是首包完成时快照，不代表后续余包已经完成。

31条原模型意见已逐条与同SHA完整包核对，人工反馈仅校正重复索取、表头误判、跨窗未见与真实缺口；原件、原始报告及候选历史未改。正常反馈API以`revision_required`保存为revision6，仍处于`pilot_completed`；反馈原文不是注入后续模型的新任务。随后同一attempt `9c1503ab-4c07-4197-848c-e59cb3af898e`经正常`continue_full_analysis`取得revision7，phase=full、state=running，完成1/117包，v6余116包开放；无需重读已完成首包或再向用户索要逐批批准。v6全部完成后按dahai、全国园区库、v5顺序各自首包验收再继续，四份合计507包当前只完成1包。

原始正式回执已只读导出，10个文件SHA全验、未读包明确pending：`/Users/m5/.local/share/inresearch.ai/material-batches/campus-20261017/正式回执-首园区-20261017/`；网站容器原导出为`/runtime/data/.campus-admin-operations/exports/pilot-20261017-0357/`。逐条人工复核保存在`/Users/m5/.local/state/inresearch.ai/campus-full-review-20261017/pilot-31-findings-reconciled.json`；可执行补证单为`/Users/m5/.local/share/inresearch.ai/material-batches/campus-20261017/首园区具体补证指令.txt`，校正说明为同目录`首园区反馈校正.txt`。这些原始31条意见和原始next-actions不能未经复核直接当成爬取指令。UCLOUD的节能审查、环评／地块坐标、分期／楼栋及运营披露线索只适用于这个已绑定园区，不能套用到其余园区。

本次证据索引在私有state的`pilot-completed/`及`namespace-binding/`，工作快照另见`/private/tmp/campus-pilot-current.json`、`campus-userns-merge.json`、`campus-userns-spark-deploy.json`、`campus-userns-website-deploy.txt`、`campus-v6-continue-receipt.json`、`campus-pilot-feedback-receipt.json`、`campus-pilot-formal-export-result.json`。继续只按实际服务器包／格回执和普通来源投影报告进度；后续模型语义、其他园区的来源真假、完整全表与地图定位仍各自核验。

## 正式intake用户命名空间身份核验（已部署历史，2026-10-17）

该阶段分支`codex/campus-userns-binding`基于main `3fe1b3b`；PR957的23项CI已通过并合并，网站与Spark已同步部署。proof v2在SSH环境对完整7窗输入实际计量8059 tokens通过，正式timer首次仍以`campus_token_runner_unverified`受阻。不能把SSH通过当作systemd正式运行通过；仍是7/7成功阅读窗口、0最终综合产物、0服务器完成包／0正式发布回执。

实际同单元诊断先遇GPU等待，随后捕获精确失败：`_runner_identity`第162行预期本机ollama UID996，runner四种UID却显示65534。私有`/private/tmp/campus-timer-trace-latest.json`保留具体进程／模型／配置及失败位置；`/private/tmp/campus-userns-readonly-result.json`显示调用方UID1001只有1001→1001、长度1的映射，系统overflowuid为65534。root system manager报告`ollama.service`的User/Group=ollama、MainPID2158、ControlGroup=/system.slice/ollama.service；目标runner是其直属子进程且同精确cgroup。临时trace已撤回、原ExecStart恢复，原件、7窗与原attempt均未改；诊断不算综合或发布。

本次.32只补充分词服务身份：保留直接UID校验；对严格单UID自映射下的不可表示宿主UID，结合实际overflow、固定root服务配置、非委派cgroup、直属MainPID、父子命令／启动时钟／映射作完整重复核验，proof v2记录方法。不得直接接受65534、关闭PrivateTmp、升权或改动模型与预算。原阅读recipe、32768／4096、GPU门槛及分词／生成生命周期分离保持；该阶段110项夹具已通过（复验见文末），当时完整CI、部署、正式同单元综合及网站回执尚待验收；本次真实完成结果见上方当前继续点。

## 分词实例与生成模型分离（已部署历史，2026-10-17）

该阶段独立分支`codex/campus-runner-retry`以main `72a8fe2`为基线。PR956的23项CI通过，网站与Spark均已部署并核健康；完整7窗输入的实际8059 tokens计量已通过，但正式最终综合尚未取得结果或回执。02:49:59 debug按32K完成后，02:50:00同模型blob被另一调用切为16K并带shift，32K实例门禁以`campus_token_runner_unavailable`阻塞；原始模型日志保留在私有`campus-ollama-contention-complete.log`。7个成功窗口未改，0综合生成结果、0服务器完成包／正式发布回执。

集成者曾依据精确失败时钟、模型日志和新的网站状态证明只恢复一次最终步骤，保留7个窗口与同一attempt。进一步核对固定版本Ollama源码确认：scheduler引用在独立API结束时释放，debug之后或completion返回后均可合法更换同模型runner；.30跨这些请求保持同PID的要求不成立。当时.31直接替代该约束，不发布临时扩大runner重试草案。最终proof v2以tokenizer_binding仅证明/tokenize操作前后实例稳定；同GGUF合法16K/32K均可完整计数。generation_binding独立证明固定模型与完整32768/4096/no-truncate/no-shift请求及前后模型身份，不声明生成PID。只分词期确认竞争有限重试；生成后未绑定模型响应保留审计禁止自动重放。读取缓存不变，该阶段的实际生成与网站回执尚未取得；后续正式运行根因见上方当前继续点。

## 最终综合精确预算阶段（已部署历史，2026-10-17）

当时独立分支为 `codex/campus-adjudication-budget`，基线main `617fee`。此前窗口定位／身份表头修复已合并并部署，本次正式首园区UCLOUD-WLCB保留同一attempt；本段记录收到的最新运行快照：7/7个原生窗口读取成功，最终综合在旧字节门槛处实际受阻，错误为`campus_adjudication_context_exceeds_budget`；adjudication产物、服务器完成园区包及正式发布回执均为0。此前仅6窗形成的完整综合输入已为28,388 UTF8字节，超过旧27,648字节门槛；阅读窗齐全不等于完整园区完成。本段替代下面旧分支“仍待部署／隔离重读”的现状描述，旧错误和复验记录留作历史。

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

1. 冻结.34实现与规范后，在最终head完成完整语义／摘要、来源冲突与不可变性、缓存失效并发、HTTP gzip／HEAD／精确长度／异常清理等相关测试、完整套件、治理与严格校验，按原PR／CI门禁合并。以私有真实大库测内存峰值，不拿小夹具或health代替。
2. 先部署网站并核镜像、logs实际持久卷、业务接口、来源接收／回执及容器峰值和OOM／重启计数；再暂停唯一intake timer，等在途receive自然结束，保存状态，只快进其实际执行树并恢复。保持Reader/review／Ollama、成功窗口、final配方、原件和旧审计，不执行历史清缓存或重读恢复。
3. 网站业务内存验收通过后，按私有回执安装唯一intake的5秒临时drop-in并核实际生效值。每轮仍一新27B，热忙等待；若发布回写超时，先对账服务器已完成报告、outbox与幂等身份，再复用持久缓存恢复，不能由超时推定未发布。
4. 持续分别报告服务器完整包／归属格、真实上线来源／园区、坐标点亮、当前窗口及具体阻塞；输出逐条定位的补抓材料指令并复核模型误判。v6之后按dahai、全国园区库、v5的最新revision及严格布局启动，不重复授权或计入旧抽样完成。
5. 本批完成或明确结束优先期后，只按匹配SHA恢复本任务临时timer配置，启动原先active的publisher timer；确认两个Mac mini父shell仍是本次暂停的同一启动身份后SIGCONT。记录恢复回执、残留异常与实际吞吐，不覆盖其他配置或恢复用户原先暂停的任务。

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

.31最终分离方案本地复验：逐条复核tokenizer仅在/tokenize前后绑定、合法16K tokenizer及请求间PID变化仍用完整固定32K生成、分词传输错误只在复核实例竞争后重试、模型变化与生成结果未知仍停止、未绑定响应持久审计与7窗不变。旧“生成前后PID变化必须拒绝”的两项测试被模型变化拒绝与合法PID轮换测试替代，其他既有覆盖保留；独立同5模块104项通过（1.361秒，bundle Python3.12）。真实生产仍以当前回执核验，不能用本地夹具或旧v1的8059token预检宣称v2正式综合／pilot／网站发布成功。


用户命名空间身份核验.32复验：逐条审阅新增6项测试，覆盖严格masked正例及父服务启动时钟复验，错误／多行／非恒等／非单UID映射、实际overflow不符、父子UID／映射／cgroup／PPid异常，证据读取失败永久拒绝，以及固定systemctl命令／隔离bus与host环境／3秒和8192B上限、错误／重复／缺失服务属性与超时拒绝。最后补强父服务argv精确为`/usr/local/bin/ollama serve`，单次身份采集以system manager前后快照包住父子进程两次快照；新增测试拒绝服务MainPID、父子启动时钟或runner命令在采集期间变化，原反例增加父命令假路径／非serve／额外参数。另将helper双快照与外层首次原始命令、PID及最终stat绑定，第6项测试拒绝helper两次快照虽一致却已偏离最初端口选择，以及helper后启动时钟变化。旧直接UID测试增加明确identity method且不调用systemctl，全部旧测试方法保留。独立执行`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src <bundle-python3.12> -m unittest tests.unit.test_ollama_token_budget tests.unit.test_full_review_worker tests.unit.test_task_full_review tests.unit.test_model_runtime tests.unit.test_ollama_schema`，110项通过、1.523秒；其中token模块30项。`git diff --check`通过，未执行治理refresh或生产变更。冻结adapter SHA256为`bc561f83cd5e8d4ba107b681c06436ca8b0e96b2fbcfeb09a8c607930986b89d`，token测试为`b772f93ea682e568e7802b675d3f08b16d80f0222ac2a2ef58eea2bfb1f695d6`；夹具不替代正式同单元计量／生成与网站回执。
