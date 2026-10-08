# 十二仓库每日组织图交接（2026-10-08，m5）

## 目标与已定规则
用户已授权每日北京时间0:00刷新组织框架、最新检测和结果并上站。按infra注册表覆盖12仓库，研究站admin集中入口/admin/repos.html；八个新增图以源码模块和原架构文件为依据，不杜撰流水线。四个专用源图保留，infra附加六机实测图。更新、检测与原图观察时间分别标示；未知、失败和业务未验收不混为通过。

## 实现与入口
- scripts/daily_repository_pages.py：只fetch canonical远程main，将源码归档到系统临时目录，不改变活跃checkout。复用infra daily_check（不带--issue），然后同步与检测。
- scripts/sync_repo_pages.py：12页+总览+来源/检查清单；--probe为公网HTTP/TLS与已有GitHub工作流，--daily-report为六机报告，--source-roots支持隔离快照。
- 原始运行报告在~/.local/state/infra/daily/；页面快照过滤仓库私有路径/变化前后原值，仅保留连接、容器、服务、变化数及告警。源码状态不代表业务验收。
- 每日任务为本对话Codex heartbeat「十二仓库组织图每日零点更新」，Asia/Shanghai 0:00。依赖m5 app/网络可用；正常更新保持安静，变化异常才通知。

## 每日继续
从最新origin/main独立工作树恢复同日工作；运行daily_repository_pages及--check，审阅差异。受审文件改变须实际审阅规范映射和未覆盖项，不自动重签。刷新治理、严格数据、registry、相关单元/浏览器验证，通过当前HEAD全部PR CI后合并。核对AWS实际镜像/健康/admin资源与检测时间；源图或服务变动不触发其他产品、Spark reader的部署或重启。

## 本轮检测与验收
当前公网登记入口全部响应符合预期；suanming当前提交工作流失败；aliyun SSH不可达，机器事实未知。报告如实保存，不因此把整站功能判通过或无故修改其他仓库。
单元权限和检测回归、13页手机/桌面明暗浏览器已通过；生产发布回执在本对话完成后记录，未取得不写已上线。

## 待用户决定
无。新仓库注册变动先核对真实来源与权限，缺来源不发布空图。
