# 首页整体图景与日更交接（更新于2026-10-11，机器m5）

## 目标
首页显示全球登记布局、来源项目、重点公司与每日新闻容量，并降低首屏载荷。

## 已定规则
- CDN由用户另行配置；代码侧采用有界摘要、gzip、缓存失效、复用地图与非阻塞新闻。
- raw与正式库并行；来源MW不自动累计正式IT GW。登记、部分字段采用、报道待核分别标识。
- 168条专题台账已公开但未正式入库，国家落点是示意；无坐标保持未定位。缺运行快照显示未知。
- 主工作区与另一活跃会话保持独立；#686已由原会话合并，本分支保留其估算修正。#622旧实现已被现行控制室替代。

## 进度
- 已完成：改造前9个公开载体完整SHA与线上部署核对；前后端/模型边界/治理更新；初版完整2,209项、接入#686后最终性能版完整2,224项及专项/浏览器回归。
- 首版PR690最终head4506698的21项CI均成功，正常合并ec8b4c32；AWS容器/公网与Spark增量同步核实，真实桌面/手机/暗色/地图新闻与七公司交互通过。
- 连续更新修复候选：codex/homepage-news-stability-20261011，整合基线3fda295a，框架.87。发现旧接收源/控制分时切换及180秒服务/120秒网络超时；改完整pair预生成与prepared精确恢复，网络240/服务420秒有界预算，首页输入不变复用投影、重算stale并与研究构建隔离。专项44项、完整单元2,237项（85.827秒）和industry浏览器通过，治理/严格校验/registry/事件卡与资产检查通过；整合#694/#695后补齐IT容量束拒绝assessment-only的回归；最终冻结完整2,250项单元通过（85.840秒），合并后industry浏览器及55项数据专项通过；最终GitHub CI与新生产ACK待本PR核验。

## 下一步
1. 连续更新修复最终head的validate和browser(core)及全部所选作业通过，再走保护合并；不重复合并首版。
2. 等AWS现行inresearch-only-deploy.timer完成构建/健康门禁；核源码与实际容器SHA、框架、HTTPS接口及桌面/手机。
3. 核Spark安全增量同步后新oneshot真实exit0与publish-status新ACK（旧ACK为02:45:37Z）；420临时drop-in已daemon-reload，未重启/新启任务。不得启动第二发布器或把源码已同步当运行升级。补齐全球覆盖、精确位置和正式采用需独立研究。

## 待用户决定
当前实现无需重复确认；正式入库的字段数门槛尚未指定，不自动发明阈值。

## 入口
framework/CURRENT.md、current_state.json、01_data_standards.md、05_interface_system.md；docs/reviews/2026-10-11/homepage-global-daily/README.md；manage.py governance/validate/registry；tests/unit/test_homepage_raw_atlas.py、tests/industry.cjs。
