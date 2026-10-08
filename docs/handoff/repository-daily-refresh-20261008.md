# 十一仓库系统每日组织图交接（2026-10-08，m5）

## 目标与已定规则
用户已授权每日北京时间0:00更新组织图和真实检测，并明确系统自行运行、不依赖对话/人工在线。用户从GitHub删除suanming与identiry，现行注册表及入口11仓库；本地资料/历史快照不删除，infra身份服务配置仍属infra，不据仓库删除停服务。

## 系统运行
- macmini hermes的launchd：ai.inresearch.repository-pages，每日00:00，RunAtLoad及每小时补试；当日完成后跳过重复检查。对话automation-3已PAUSED，不再执行。
- 独立Python入口：/Users/hermes/.local/share/inresearch.ai/repository-refresh/runner.py；源为scripts/repository_pages_daemon.py，安装参数--install。无需Codex/app/模型；需要macmini开机、常驻用户launchd和网络。
- 私有日志/锁/状态：/Users/hermes/.local/state/inresearch.ai/repository-refresh/{job.log,status.json,job.lock}。
- 每次从已合并main归档当前生成器到系统临时目录，daily_repository_pages.py归档11仓库main，infra daily_check只读检测（不带--issue），构建17个完整载体。工作区不reset/switch/stash，临时源码不当本机资料删除。
- AWS：/srv/inresearch.ai/data/raw/repository-pages/releases/<id>与current原子指针，status.json独立记录最近运行与上次成功。publish_repository_pages.py核对登记文件、来源及本地/远程SHA才激活。失败保留旧current，按小时重试。无每日PR/源码提交/数据库写入，不重启reader或产品服务。
- /admin/repos.html及十一页和/admin/repo-content/job-status.json全部真实admin门禁，private/no-store；/data/raw不公开。源码镜像更新不覆盖持久投影。网页显示更新/检测/原图观察分别的时间及系统失败/过期提示。

## 验收与剩余条件
单元：不完整/软链不替换上一版，越界不读，私有运行页及状态GET/HEAD权限；检测失败/无CI不变通过；11页+总览桌面/手机明暗。原图业务声明与实际检测分开，公网入口和已有CI不等于业务验收。
部署后实际核对launchd已加载、首轮Python完成/云端SHA及持久projection、AWS镜像/健康和管理员资源；首次实机回执保留在本机state。未取得回执前不写已上线。

## 待用户决定
无。
