# Relay诊断与候选增量交接（2026-10-13，m5）

## 目标

补齐CLI超时诊断、安全轮换暴露的relay凭据，并用Spark和网站实际数据验收增量同步；定时汇报保持暂停。

## 已定规则

- 用户明确授权上述修复与验收，不恢复半小时汇报。现行操作以 `framework/CURRENT.md` 和 [Spark操作手册](../local_reader/SPARK_OPERATIONS.md) 为准，本文件只记录交接。
- 保留原件、成功分块、队列次数/available及候选；候选接收与正式采用分开，材料更新次数不能相加当作新增新闻。
- 不输出完整服务环境、凭据或原始CLI错误。私有JSON、数据库备份和token不进Git。

## 进度

- 已完成：[PR906](https://github.com/niuroumiantt/InResearch.ai/pull/906) 补有界stdout终止JSONL及stderr首尾诊断，未知超时与认证失败保留安全分类。23项完整CI通过；本任务安装的relay源码为 `32c2b645`。
- 已完成：relay凭据轮换；M5与Spark隧道旧钥401、新钥认证通过。LaunchAgent使用私有文件加载token。维护前在途7块均成功，次数、预算和available不变。
- 已完成：[PR907](https://github.com/niuroumiantt/InResearch.ai/pull/907) 支持有界gzip响应、截断同请求重试、显式可信manifest读取入口。最终head `11417a4c` 的2599项单元及23项完整CI通过，合并提交 `90b100f8`。
- Spark唯一原发布服务固定在 `11417a4c`，`READER_PUBLISH_INCREMENTAL=1`；正式域名读未压缩的小manifest请求，origin写gzip delta。未增设发布者，原候选发布timer已恢复。
- 实测首轮更新7份，ACK北京时间21:51:06；原timer自动轮次更新21份，ACK22:09:05。22:11采样网页与Spark时点一致且未过期；候选身份仍44801，无新增/删除，首轮其余44794份哈希不变。两轮更新数可能重叠，本任务新增正式采用为0。
- 网站后来已部署独立的[PR908](https://github.com/niuroumiantt/InResearch.ai/pull/908)（初筛年份规则，基准.122）；不把该任务的输出修复计入本任务。接续应核实际启动路径与当前规则，不把本文件中的历史安装SHA冒充永远最新版本。

## 保留事项与下一步

1. 本阶段已完成。若有新故障，先读现行入口及下面私有回执；不要恢复旧审批、重置队列或扩大重试预算。
2. 部署后21:14—22:11记录129次模型调用成功、3次暂态网络失败；正文与凭据未持久化为诊断。仍有一次写入后只读清单采集耗尽预算，失败实测保留，不宣称所有跨网读取均已根治。
3. 22:11网页本批为2887/7778完成，仍1失败；17份报告保留18个缺页。原件/全文/候选/C3/普通来源登记继续分别计量。
4. `inresearch-ai` 汇报automation仍为PAUSED，原配置SHA未变。恢复时间没有授权。

## 待用户决定

无；下一阶段新需求或恢复汇报由用户明确提出。

## 入口与私有证据

- m5：`~/.local/state/inresearch.ai/relay-hardening-20261013T203535+0800/`，含CI、轮换、部署、模型窗口、网站/Spark和保留性回执；其中备份含已撤销旧钥，保持私有，勿打印。
- Spark：`~/.local/state/inresearch.ai/relay-rotation-20261013T2045/`；实际验收目录由 `active-acceptance.json` 指向，逐批ACK、前清单和timer恢复记录均保留。
- 新发布源码：`~/.local/state/inresearch.ai/research-publisher/releases/11417a4c/`；最后的私有systemd drop-in为 `zzzzzz-candidate-transport-20261013.conf`，原source与drop-in保留。
- [网站资料进度](https://inresearch.ai/admin/inresearchrepo.html) 与 `/api/admin/material-flow` 已用实际管理员会话返回200；会话与同步密钥未写入本文件。
