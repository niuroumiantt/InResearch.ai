# 公开仓库后 Actions 与发布恢复交接（2026-10-09，m5）

用户已改仓库为public，要求尽快修复。GitHub API确认PUBLIC；原任务因Actions budget被拒绝，steps为空。已重跑旧预算失败及当时main检查，实际数据/存储/网页测试均恢复执行。

原#482有冲突且无CI；原#476被仓库暂时disabled的403阻塞。暂停M5发布器维护journal，复验封存包SHA、现行上下文、原head和干净独占工作树后更新基线，不改审核原件。#476后来因研究上下文变化按既有协议重排C3并关闭旧PR。用户随后截图中的#485/#488也在原封存包不变、精确旧head一致的复验中发现现行上下文过期，按同一协议关闭旧PR并重排。

新#487和原#461已合并，但观察到新head推送后的检查仍运行时就发生合并；不能把先前成功追认给新head。发现旧发布器从PR汇总读检查，推送窗口可能读到上一版。修复为按精确审核SHA读取全部分页check runs，每项head_sha及check_run_id入journal；空检查、运行中、异SHA均拒绝准入。四项必需及全部额外检查仍需实际成功。已合并包按既有精确head恢复及真实网站支持闭包规则，不重合并或伪造CI。

#482两条与#484六条现行复验通过，按严格稳定ID追加汇总本发布，所有29份旧文档、193条旧证据、185条旧陈述保持原值和顺序；新增10条证据/8条陈述、无答案变更。每批原包/审核head/原PR头记录于私有consolidated-batches.json，正式发布仍等本PR精确head全部CI和真实HTTPS/Spark验收。

#485实际company_catalog_map测试在导航DOM尚未出现时读null.textContent。此次将等待谓词改为先等DOM出现，1U/2U/3U、型号、搜索和导出断言不变；实际本地浏览器通过。原失败保留并重跑失败检查，不冒充原CI通过。

工作源码：~/.worktrees/inresearch.ai/public-actions-release-20261009。原主工作区未跟踪电力专题原样保留。私有审计：~/.local/state/inresearch.ai/public-actions-recovery-20261009/，含原journal快照、完整单元测试与最终CI/合并/网站证明（以实际存在的最终证明为准）。运行专用工作树research-publisher-runtime-20261009有服务引用，不可清理。

用户明确授权的15分钟合并协调已通知「spark 阅读并提交」，该聊天确认暂缓；原Reader/relay/独立审核不停止。本发布验收后需恢复M5 LaunchAgent并通知该聊天恢复；最终状态以私有final-proof.json和逐批journal为准，不把这里的CI等待时点当长期状态。

## Final acceptance (2026-10-09T08:43:14+00:00)

PR489 merged as e968b66cdaf58fb49bb60662c29bd747fa852e39. All seven checks on exact reviewed SHA ef2fa23c204fc8ec51410799efb937c5e1018e8c succeeded. The merge occurred before the last check completed; preserve that ordering rather than claiming all checks preceded merge. The eight unchanged statements from PR482/484 passed real HTTPS text/adoption/quotation/source coverage acceptance and both batches are published on Spark. Original PR485/488 were closed with context revalidation or existing split-context children preserved; all four old screenshot PRs are CLOSED. PR461/487 also passed exact-head checks and real live acceptance.

M5 runtime, Spark and the actual healthy AWS image all match e968b66c. Spark Reader and review services are active. Publisher was reloaded after the runtime fast-forward and is running PID18897. An older process had been restored elsewhere during maintenance; disk revision alone was not treated as loaded code. Reader/relay were not restarted. The authorized coordination pause ended and the Spark chat was notified to resume. New PR490/491/492 are normal new-head CI work, not the original blocked PRs.

Infra PR335 is already MERGED. Its rerun still has zero executed steps and the private Actions budget rejection; making InResearch public did not remove that separate restriction. Final raw proofs: private final-proof.json, ci-proof.json, merge-proof.json and accepted-proofs.json. No pending user decision.
