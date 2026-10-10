# 仓库架构页维护

现行地址与权限以 `framework/05_interface_system.md` 为准。总入口为
`https://inresearch.ai/admin/repos.html`。现行 11 个仓库都有入口。
`inresearchrepo.html`、`inewsrepo.html`、`fetchspecrepo.html`、`infrarepo.html`
保留专用图；其余仓库从当前源码目录生成组织图。

每个仓库维护自己的事实；研究站保存可审阅的架构快照，研究主页另附只读运行聚合。infra 原 HTML 原样保留，
Fetchspec 调用自身生成器，inews 导出同一份 pipeline-map 架构声明，InResearch 从程序职责说明生成。
源图观察时间、声明状态与同步日期分开；同步不证明生产已部署或原记录已重新核验。
inews 统一页不读生产库，也不把演示库计数带入页面；实时统计仍在新闻站原架构页。

**[Codex 云开发环境 /workspace]** 四仓库并排时，在研究站执行：

```bash
cd /workspace/InResearch.ai
python3 scripts/sync_repo_pages.py --workspace /workspace
python3 scripts/sync_repo_pages.py --workspace /workspace --check
```

默认同步脚本只读邻接源码；`--probe` 只读探测公网入口及 GitHub 当前提交工作流，`--daily-report` 接入 infra 六机检测。源文件缺失或生成失败直接退出。脚本本身不提交、合并或部署。
输出在 `web/pages/admin/`，同步日期和来源完整 SHA-256 在
`web/pages/admin/repo-content/manifest.json`。流程变化后重跑并审阅差异，随研究站正常代码发布。
`--check` 使用已保存的同步日期，跨日检查不会仅因日期变化而误报。
2026-10-08 替代手动同步责任：常驻macmini的系统cron每日北京时间0:00运行Python刷新器，独立于Codex和对话。读取11个当前仓库的最新远程main、只读检测并原子发布AWS私有运行投影；不每日提交PR。其他主工作区不切换、不reset、不stash。

服务端在归一化路径后校验真实 admin 会话，GET/HEAD、旧 Fetchspec 地址及原始内嵌页都受保护。
本地 `HUB_AUTH=0` 也不关闭这些页面的登录要求。无账号时用既有 `manage.py users add` 交互入口创建，
不要把密码放在源码、命令参数或快照里。响应标记 `private, no-store`。
旧 `/admin/fetchspec/reporg.html` 经认证后跳到 `/admin/fetchspecrepo.html`。

Tailscale 运维仪表盘继续提供运行状态；这里不代理其管理操作、不转发研究站 cookie 给其他域名。
新增仓库先接入真实架构来源，再登记路由、页面清单、同步脚本和权限测试；不提前创建空页面。11 仓库列表与 infra 注册表必须一致，新增仓库未审阅时停止生成。

本轮本地权限和浏览器验收记录见 `docs/handoff/repository-pages-20261003.md`。
生产发布及登录验收需在研究站正常发布流程后单独记录。

## 研究站资料关系图（2026-10-08）

`/admin/inresearchrepo.html` 的五个环节可点击展开，数据库和网站包含关系独立显示。
仅重生成这一个仓库页时运行 `python3 scripts/sync_repo_pages.py --repo inresearch`，
随后用相同参数加 `--check` 检查；其他仓库内容与来源登记保持原同步版本。
完整同步仍用 `--workspace`；脚本始终不读取生产资料。

运行指标随既有 `Reader.export_snapshot` 生成、经接收端白名单校验进入 AWS 候选快照；
目录 `du` 低频采样缓存于 Spark 私有 state/material-directory-measurements.json，最多一小时。
目录缓存失败保留上次时间并标陈旧；SQLite 数据库读取 mode=ro，缺库不创建、失败不填零。
只读 API 每分钟短缓存，前端每分钟刷新；候选或正式记录文件改变即失效。
更新网站和 Spark 发布源码后需等待既有发布周期，核对实际接收时间及新字段；
无需重启 Reader、改变队列或新建模型服务。旧发布端缺字段时仍保留关系说明并显示未知。

容量采用十进制 GB/MB，传输计量保留 bytes。库内索引不重复计入文件容量；
目录含副本，登记含派生，二者不可相减推导唯一原件量。候选、证据、当前状态、
正式采用与项目/合同各自明确单位；不得把已核验待发布算作正式上网。
本图不证明原件备份完整、全库语义阅读完毕或 IT GW 改变。生产验收见本次交接记录。

## 每日刷新与检测（2026-10-08）

**[m5 / 本对话执行机]** 在本任务的独立研究站工作树执行：

```bash
python3 scripts/daily_repository_pages.py --workspace /Users/m5/code
python3 scripts/daily_repository_pages.py --workspace /Users/m5/code --check
```

脚本只 fetch 远程 main，将所用提交归档到系统临时目录并记录提交与在册目录，不改变邻接仓库分支、工作文件或暂存区。
复用 infra `daily_check.py` 做六机只读检查，不带 `--issue`，不自动向外发送报告。
工作流结果只是已存在的该提交运行记录，公网入口只检查 HTTP/TLS；未取得不填绿，CI 失败如实展示。
infra 整份运行报告留在本机私有 state；页面快照只保存容器/服务、连接状态、变化数量及告警，过滤私有仓库路径和变化前后原值。

定时执行与发布步骤见 `docs/handoff/repository-daily-refresh-20261008.md`。系统日更只拉已合并的源码并写运行投影，验证17个完整载体和内容摘要后原子切换current；旧release和失败回执保留。生成器实现、规范或在册测试变化仍走PR/CI与实际复审，不自动重签摘要。
对话heartbeat已停用。Python刷新器在macmini后台运行，每天0:00检查，每小时补试尚未成功的一天；本机状态在~/.local/state/inresearch.ai/repository-refresh，AWS投影与状态在/srv/inresearch.ai/data/raw/repository-pages。网页从私有job-status显示实际完成/失败和过期；失败不改写上次成功日期。系统无需人工在线、无需打开Codex。macmini开机、系统cron、网络/SSH/GitHub可用性仍是运行条件。

**[macmini]** 通过m5把已合并的Python刷新器放在macmini本地运行目录后安装（实际位置见交接）：

```bash
ssh mini '/Users/hermes/.local/bin/python3 /Users/hermes/.local/share/inresearch.ai/repository-refresh/runner.py --install'
```

启动和安装均使用现有hermes用户权限，与该机器现有采集任务一样由系统cron管理（无需图形界面或用户登录）。云端激活通过既有aws SSH与sudo执行，仅限独立的repository-pages投影目录，不重启研究服务或reader。服务端只允许登记管理员页面读取运行投影，原始/data/raw路径不开放，源码镜像替换不覆盖current投影。

macOS→Linux传输使用COPYFILE_DISABLE=1，关闭BSD tar附带的AppleDouble元数据；云端仍只接受完整17个登记载体，不放宽额外文件/摘要验证。
