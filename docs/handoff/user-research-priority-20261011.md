# 研究优先级交接（2026-10-11，m5）

## 目标
美国数据中心电力研究直接推进；是否排队、插队及事件优先级由用户决定。

## 已定规则
- 用户说普通排队、插队或直接上线，按最新指令执行；不等无关主题清空、不逐批重新请求授权。当前已领取任务保留归属，沿现有单一发布所有者推进。
- 原件、阅读、核验、C3、必过CI与网站回执如实记录；优先级不能被记作这些步骤完成。唯一入口：docs/local_reader/EDITORIAL_DELIVERY.md。

## 已完成
- PR682已正常合并3b9f569e；精确head d92b5c10的21项CI全部成功，56项相关本地测试及治理/strict/registry通过，治理版本2026.10.11.79。保留并行主分支的大快照修复与正式研究，未用ours覆盖源文件。
- Spark与M5两份干净发布运行树已安全快进合并源码；未重启Reader或新建发布worker。正文加入原23来源偏好清单，当前24个文档身份；审核服务实际重读清单。四个未完成当前阅读版本从7提到10，在线事务保存前快照、幂等marker与回执，全部jobs/次数/预算未变，既有失败未重试。
- 本专题属于Spark。M5 research-publish.json已配置Spark上的preferred_sources，实际ready查询返回优先批次。M4发布入口是独立队列，不能复用Spark路径；误加字段已撤回并保留原设置，M4仍由原所有者处理。
- 正文SHA 5a90f85c91aff48a5f6aa1f2241a5709a7297191614cdbdce17c050d91fdda13。网站实际记录complete/authored_analysis、引用52条；真实浏览器搜索《美国数据中心抢电，争的是通电时间》得到65条资料/1份材料，展开原文依据可读。这65条是Reader提取资料，不是原50候选的正式采用数。
- 初次网页资料接口502与大快照运行故障一致；保留主分支PR680修复，实际部署后浏览器重试恢复。官方部署单元是inresearch-only-deploy.service，不能把其它应用的infra-app-deploy模板当研究站发布器。最新镜像/健康与规则HTTP实核记录保存在本轮私有状态目录，不从源码main推断网站版本。

## 后续
1. 仍由现有所有者处理优先批次及真实网站ACK；本次插队不宣称所有原件都读完、原50全部采用或问题闭合。
2. 用户调整事件优先级时更新正确接收机的来源清单，未完成阅读按当前版本提级；无须再问是否授权插队。保留旧配置、原件和审计。

## 入口
- Spark清单：~/.config/inresearch.ai/us-power-preferred-sources-20261009.json；回执：~/.local/state/inresearch.ai/user-priority-20261011/。
- M5回执：~/.local/state/inresearch.ai/user-priority-20261011/；唯一协调器：~/.local/state/inresearch.ai/assist/dcd-publication-queue-20261009/worker.py。该协调器每个子轮重新载入发布配置，保留两接收机身份。
- Spark研究规范及CLI：src/inresearch/workflow/research_review.py；M5发布调用：src/inresearch/workflow/research_publish.py。

## 待用户决定
无。
