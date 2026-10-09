# 美国数据中心电力专题交接（2026-10-09，m5原交付、m4续做）

## 目标

按用户采用的需求→地区瓶颈→项目真实性→成本分担→供电路线→布局变化主线，补美国电力底图，交公众号HTML及inresearch.ai研究文字，并更新唯一长文规则。

## 已定规则

- 长文规则v2.6明确A行业编辑讲解为主、B科技报道叙事辅助，明确双交付与需求驱动溯源；原件、候选、正式采用分别处理。
- 不用申请MW、PPA规模或未来日期冒充投运IT；保留反证及原文失败访问。
- 微信正文图片JPG/PNG单张<1MB；本地复制包不等同素材上传，未实粘标待验证。

## 已完成

- 正文约1.29万汉字/1.50万非空白字符；三种HTML、首图、14张解释图（3地图、3工程、8数据/关系/阶段/对照）及数据图/独立文字SVG、来源、50条候选、23份投递、需求快照与缺口。
- 桌面/手机整篇无溢出，浏览器剪贴板往返15图保留（含首图）；真实素材字段23/23通过；原件和响应SHA分开核对。
- 规则、替代登记和验收映射在`codex/us-datacenter-power-20261009`独立工作树修改。主工作区另一任务未切换、暂存或覆盖。

## 下一步

1. 用户审稿；需要时修改同一article.md并同步图、HTML和包。
2. 在用户公众号编辑器实际粘贴/上传图片。本轮未发布。
3. Spark已实际接收23份来源并候选匹配；23/23当前Reader已注册，11:39:55快照完整封存1/queued22，无hold，沿既有队列继续阅读。解析器修复PR #436已合并部署，DOE/PJM两份已追加scope。正式采用与闭题仍须现行审核回执。

## 待用户决定

无新增确认步骤；剩余审核/发布不在本轮素材生成范围。

## 入口

规则：`docs/geluoke/专题写作规则.md`。成品：`outputs/geluoke-research/2026-10-09-us-datacenter-power/`；本机原件：`~/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/raw/`。反哺：`docs/research/2026-10-09/us-datacenter-power/README.md`。原独立工作树：`~/.worktrees/inresearch.ai/us-datacenter-power-20261009`；m4续做工作树：`~/.codex/worktrees/us-power-intake-20261009/inresearch.ai`，分支`codex/us-power-intake-20261009`。

## 本次修订

已核对inews PR256合并及口吻/目录/提示词实际代码。五张用户参考与三张新图、去小字版的原始PNG共10件保存在本机visual-originals，并另交zip；Git内有发布衍生图、可移植参考预览与提示词。公众号约3.50MB、单图<1MB，14幅正文手机截图已逐张查看。旧稿HTML/文本在本机history/v1和history/v2保留，旧资产和规则由Git及归档保留。未改技术图册迁移队列、事实库、远程数据库或网站服务。继续修改先重制图文，再刷新治理清单。

第三版按用户最新纠正重组全文：先确定每张图的问题，图型由内容决定。第一章地图紧接首段，工程图名称直接引向对象，费用/预测/合同/投运状态放入图面。45条来源访问身份、52条记录，研究23件和50条候选仍保持原范围。新版重跑制图必须复审figure-plan，旧图不当作当前配图。此前PR #423现已合并；v2.6/第三版PR #427：https://github.com/niuroumiantt/InResearch.ai/pull/427 现已合并；分支codex/us-datacenter-power-matching-20261009。CI因Actions预算阻止启动，不能记为CI通过；源码合并不证明公众号或网站实际发布。

最新远程基线0f7dc743上的TA-05/06/07与技术图册记录已保留，本次仅替代长文政策；治理基准2026.10.09.08、1501文件，重跑9项治理单测/严格校验/引用检查通过。成品delivery.zip约22.1MB、研究原件约45.8MB、图像原件约22.1MB在主工作区同名成品目录；zip和原件不入Git。

## m4续做：真实接收与图9修正

23/23来源已实际接收（20下载原件+3工具响应UTF-8载体）、候选匹配23/错误0；147传输文件及89上游原始归档文件SHA已核对，永久incoming与acquisition/blob路径见checks/spark-intake-final-receipt-20261009.json。响应SHA与派生SHA分别保留，原站字节SHA仍为null；URL仅保留来源侧车，catalog未完整导入URL。既有scope133条与include_daily保持，先追加21条，解析器部署后再加DOE/PJM两条至156。

2026-10-09 11:39:55北京时间最终Reader快照：23/23注册、hold0，queued22/complete1，triage14/read2/extract6/complete1，chunks_read13、完整封存报告1（Crane工具响应正文载体）。PR #436解析修复已合并部署；Reader旧PID776486安全退出后于11:27:32启动同服务，新PID1644248 active/running，Spark源码b5e669ab、解析器SHA322b316bbc5bc0bce0c3fc4b4835b2a23c7f9d42f06c0f81ae20f17a26aaa650。首次扫描another_worker_owns_queue及21注册/封存0为历史阶段，未强占；后续安全换代与23注册独立留回执。正式事实、价格、GW、模型、研究问题未改，C3未运行，不称23份已深读。当前台账见docs/research/2026-10-09/us-datacenter-power/INTAKE-20261009.md。

图9总题居民→客户，保留原数据与条件；SVG/PNG、article alt/图注、生成源和三版HTML同步，其他13图及历史检查保留。新图手机目检、三HTML×390/1000共6次检查已实际通过；本轮检查另存，不推定公众号实粘/发布。续做zip在本工作树reports/output/geluoke-delivery/，不覆盖m5旧包。

初次交付历史原话“本轮未远程导入”“本次修订未合并或上线”描述当时阶段；PR #427合并与本轮接收已经发生，当前状态以上述回执为准，公众号与正式采用仍未完成。
