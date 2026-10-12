# 首次物理园区接入

接续 stock-expansion-20261011.md 与 stock-archived-gpu-20261012.md。对象账本上一批545条/152对象，不计本任务新增。用户优先唯一主体先落地，缺失后补，不要求模型用途。

## 本次实现与边界

`targeted_research.prepare(..., object_binding=..., initial_identity=...)` 冻结首次物理身份；随后使用source_kind=object_excerpt、target_ids=[]、initial_identity、首条v2 observation的project-review提案。initial_identity明确site_id/name/country/region/location/native_name/basis及可选省市街道，地址和坐标未知允许。名/阶段必须在首条审核字段，native_name必须在原件引文。原件SHA、局部上下文与具名C3照常执行，日常事件也可首次登记。

首条基线容量为空，容量随后作为有来源观测追加；主体不在审核字段时不能注入。拒绝重复名称/别名、身份不一致及注入历史。相同提案重放保留首次时间及字节。新增具名园区末尾纯追加通过完整JSON证明可走research+industry；代码规则、旧值/修订仍全套。

本次不扩展归档无URL园区原件入口、不实现失败隔离、不改变公开字段清单；不能声称171来源、17模型输入或9,653衍生关系已采用。首次能力本地测试不等于生产部署。

## 真实存量下一批

Spark三份已局部检查原件：Bosung SolaSeaDo（0065f33959cedf7f1101953a2bb5caf604b9f52ffdb727a040aeec348d087568）、Stockland Laverton 72–76 Cherry Lane（0266651176e476da247f8757ddf1f216b90bd5cbb8b86ab8aa7289aae8b29b33）、Macau Coloane Rua das Albizias 71–93（0451af6d40e97fb4de22c9ca9f6ed885fbb8027ea2b4da4983a82a4973f4743f）。当前126记录未命中上述名字/地址，不凭同城自动合并。前两份200/250MW未明IT口径，不并入IT；澳门up to40MW IT仍需保留上界/协议条件，不取精确40。三份尚未正式采用，实际计量另读私有回执。

私有续接目录：M5 `~/.local/state/inresearch.ai/initial-physical-site-intake-20261012/`；Spark同名。发布协调器仍唯一，已有PR838先实际published。不得重启Reader、删原件、或改主工作区；本任务stop标记须发布验收后移除并恢复原LaunchAgent。CI失败先修，不以改状态计采用。

本地完整单元测试2427项通过（74.521秒）；research+industry浏览器通过；规范映射/严格校验/registry已过。首次测试因并行更新治理清单影响源码不变性测试而失败，静止源码重跑通过；不属于放宽断言。GitHub最终head和生产版本另验。

## 首批扩大至七份存量原件

在上述三份基础上，补审Trino原Galileo Ferraris电厂、AWS Homer City Energy Campus、NTT TKY12和Revikon Gießen Katzenfeld原件。新增7个唯一园区、7条v2观测、21个字段（name/status/notes）；未绑定模型需求，容量为空，披露时间有原文日期证明，实际有效时点未知不补造；TKY12依原文已开工登记L6，其余按已公布规划登记L2。目标空不计模型验证。7条隔离审核/无写重放0.763秒，语义核对及CI等待另计。

全部旧126园区完整JSON保持，首批扩大版本替代三份试跑提案作为本批实际发布集合，三份不能再加算为10份。明确地址未取得的留来源地点，不伪造坐标；4.5GW发电、光伏电池和附近TKY11容量未串入本园区。私有adoption-proposals/receipts/isolated-acceptance保存完整审核。正式上线以后续生产回执为准。
