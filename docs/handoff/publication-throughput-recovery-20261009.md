# 研究发布与阅读清单恢复交接（2026-10-09，m5）

## 目标与规则
打通真实阅读成果、C3核验、发表和网页验收。混排PDF只读文字，图片不阻塞；原件、失败尝试和旧封存包保留。候选可读与正式采用分别计量，研究陈述不自动增加项目/GW。自动发布器仍要求四项实际CI成功。

## 已完成
- PR467修复供应页500条匹配窗口截断导致完整阅读清单消失；不降低完整性或泄露私有路径。完整10个dossier网页场景逐个执行，保留原断言和每场景300秒期限，并增加第三分片；全部实际测试job在1e4bf8f5成功，最终聚合job被Actions预算阻止启动。随后用户在GitHub更新并合并04a09644，merge为1fb7c595，不能称新head全部CI成功。
- 发布器保留明确stdout校验错误；失败批次只有原封存/当前上下文/精确PR head复验通过，才能接收已批准main修复，旧错误与head留存，更新后重新等四项CI。
- 五个旧prepared包中，两个有效包沿原审计重放到已批准基线，原statement ID不变，形成PR471（2条）和472（6条）；三个上下文变化包走原revalidate。旧工作树、journal及SHA备份均保留。尚未把这8条记为上线。
- 15:07后main并入TA12、Reader复合键修复及PR466。实测治理检查发现current_state和两个完整分片测试的已审摘要落后；本次逐项审阅确认TA12加入、十场景/三分片无漏项、Reader只改变复合键联接，修复三项摘要并重新登记，不重写研究记录或图册。

## 当前状态与下一步
1. 最后公网实测15:09：164条正式研究记录。PR466已合并，但未到达该次网页采样；之后必须按实际ID/支持闭包核对增量。
2. 供应页修复前实测完整阅读153，阅读卡片0。部署后复查实际卡片、原文引文和候选身份；源码合并不等于网页已修好。
3. 发布器运行源码仍需在干净专用工作树安全fast-forward。维护必须先获取共享维护锁及原worker锁，在空闲时停原LaunchAgent，finally恢复原plist，并核对PID、实际版本和一轮status。不要与PR455维护争抢，不重启Reader/relay。
4. 23份美国电力来源已启用preferred-sources；15:00前实测真实领取preferred槽。不能重复配置或把共享relay调用数计为正式交付。
5. Actions预算仍可阻断新提交；不购买额度、不伪造check、不把历史通过移植到新head。现行自动CI门禁保持；实际人工合并、旧回执恢复和新增正式采用分别留证。

## 入口
现行规则见framework/CURRENT.md及docs/local_reader/SPARK_OPERATIONS.md。M5私有过程证据在标准state目录的publication-throughput-recovery-20261009；原发布journal位于research-publish。网页：/supply.html#matching和/node.html?id=root#evidence。后续以实时台账和真实网页为准，不从此快照推断持续进度。
