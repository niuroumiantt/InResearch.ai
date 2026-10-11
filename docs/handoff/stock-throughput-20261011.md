# 存量第四批与发布吞吐优化

接续 stock-pdf-expansion-20261011.md，已上线水位184条/38对象，上一批14条不重计。用户授权继续13份原件/28映射字段、优化CI与部署并每小时报告。

13份原件已核SHA与相关原生行列，10份得到35条候选（28映射+7额外原生字段），3份Micron目录原件仅含No results found，保留待补采。候选不能算采用。4项原生区间、未知时间留空、PSU尺寸来源差异保留，BBU柜与模块、变压器三列分别核对。

CI增加四类对象账本的严格有界纯追加证明，旧记录/身份/修订变更仍full；必跑research+industry及对象/Fetchspec来源采用回归。部署拆分稳定资产层，隔离AWS小样两次构建4.981秒/3.009秒，10层复用且内容/秘密隔离通过；这不是生产提速回执。srcdoc定位只读归档内联HTML、不执行脚本、不抓外部iframe，保留原件及相关上下文哈希、C3和CAS。此代码/规则补丁第一次必须全套CI。

本地2410项单元测试通过（92.500秒），行业与两项研究浏览器通过，治理/strict/registry通过；最终head和生产另验。核验队列与指标更新来自本次既有生成命令，保留其输出并审阅：容量由当前去重有效站点计算，区间/未知不按零冒充完整容量，不是旧事实人工修订。

Spark qwen3.8:27b实测未重启或切换Reader：变压器3字段全对6.025秒；BBU首次5字段4对9.189秒，漏掉90秒/六年条件；明确完整规格条件后5字段全对24.905秒。只验证小样可行，不代表全库准确率或正式采用。Python原件/引文/去重/身份校验与具名审核保留，模型候选不能自批。

Spark私有目录 /home/spark/.local/state/inresearch.ai/stock-throughput-20261011/ 保存native-review.json及qwen-trial*.json。M5候选暂在 /private/tmp/stock-throughput-candidates.json 与 stock-throughput-candidate-summary.json，须写入本机持久状态并补正式回执。原件不删除。

唯一协调器stop-coordinator现由stock-throughput-20261011持有；先核既有PR742实际发布，再提交优化补丁；优化实际发布并预热缓存后提交纯追加研究批，核网站镜像/API/首页和Spark版本。完成实际验收后删除自己的标记，恢复原LaunchAgent，禁止留下暂停。主目录有旧任务不能动；仅使用本Codex管理工作树。新版本必须高于最新远程现行版本，保留并行首页/地图整改。
