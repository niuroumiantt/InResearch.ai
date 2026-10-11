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
- 发布候选：分支codex/homepage-global-daily-20261011，接入main b3d94502，框架2026.10.11.85。后续完整GitHub CI、合并和生产回执按该分支PR/本聊天记录核实。

## 下一步
1. 确认最终head的validate和browser(core)及全部所选作业通过，再走保护合并。
2. 等AWS现行inresearch-only-deploy.timer完成构建/健康门禁；核源码与实际容器SHA、框架、HTTPS接口及桌面/手机。
3. 核Spark安全增量同步；不得启动第二发布器或把源码已同步当运行升级。补齐全球覆盖、精确位置和正式采用需独立研究。

## 待用户决定
当前实现无需重复确认；正式入库的字段数门槛尚未指定，不自动发明阈值。

## 入口
framework/CURRENT.md、current_state.json、01_data_standards.md、05_interface_system.md；docs/reviews/2026-10-11/homepage-global-daily/README.md；manage.py governance/validate/registry；tests/unit/test_homepage_raw_atlas.py、tests/industry.cjs。
