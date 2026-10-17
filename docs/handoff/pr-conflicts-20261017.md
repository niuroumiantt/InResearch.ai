# 三个 PR 冲突与 CI 修复（2026-10-17，m5）

## 授权与边界
按 #973 → #939 → #975 修复冲突、CI 后逐个合并。只恢复本项源码工作，其它后台任务保持暂停；不执行生产采集、模型阅读、队列 dispatch/reconcile 或研究发布。保留各任务原件、运行数据和原工作区。

## 已完成
- #973：最终 head 461f9bd0 的 23 项 CI 全部成功，合并 c4f1199c。本地完整 3041 项单元测试与 ui_skin/customer_catalog/scene_delivery 通过；随后纳入新闻修复并通过 datacenter_news。公开仓库固定走 GitHub hosted；只有私有、infra 已登记且显式启用 SPARK_CI_ENABLED 才可走 Spark，系统门禁保持。
- #939：最终 head 9717999c 的 23 项 CI 全部成功，合并 778df624。94 项 collector 相关单元回归及治理/strict/registry/deliveries 通过；保留最新规则，去掉旧冲突处理的无关历史规范回退。未运行生产队列或四旧版本交付。
- main 已恢复 validate 与 browser (core) 两项 GitHub Actions 必过检查，strict=true、enforce_admins=true，无新增人工审批或 bypass。

## #975 修复与验收入口
合入上述 main，保留品牌统一及首页数据裁剪，同时保留 intern 权限、CoreWeave 档案和新闻修复。marketing 进入共享静态页面登记，CoreWeave 独立页排除登记保留。原 core_a/core_b 失败来自客户 403：三款 WOFF2 与明暗 SVG 字标缺少精确访问登记；只补这五个路径，GET/HEAD 真实字节、写请求及未登记/私有资源拒绝由 CustomerHTTPTests 回归，浏览器继续实际验证权限和全部资源。

本 PR 必须以最终 head 完整 GitHub CI 成功后正常合并；未验生产页面或未执行研究不能冒充上线完成。历史品牌测量和失败证据仍在原交接中。

## 本任务暂停核验与后续授权
本任务未启动任何 Spark CI 容器或研究服务。发现 intake timer 再次启用后已停用；日志显示 15:11 停止、15:37 新启动周期后启动、15:57 再启动（触发者未确认）、16:31 本次停止。后续实测 intake/Reader/review inactive+disabled，专用 CI 容器 exited 且 restart=no。机器重启与其它调用的来源不据此推测。

后续只读核对发现，用户在「启动 Spark 27B 研究任务」聊天于本次暂停之后新要求“请开始执行，并每半小时汇报一下进展”，随后要求继续并完成 admin 登录。该聊天恢复 Spark/M5 研究属后来独立授权，本任务不再干预；前述 inactive+disabled 是 16:31 暂停后核验时点，并非当前全局状态。更早 15:37/15:57 的触发者仍未确认。

#975 远端并发增加 ca0bdb17/b7816cf3（三款字体授权）；已合并保留这些提交，再补齐两款字标、真实 HTTP 回归和最新 main，未强推覆盖。最终本地完整 3055 项单元测试、七组浏览器及治理校验通过；远端最终 head 仍须通过完整 CI 方可合并。
