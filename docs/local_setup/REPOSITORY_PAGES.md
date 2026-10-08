# 仓库架构页维护

现行地址与权限以 `framework/05_interface_system.md` 为准。总入口为
`https://inresearch.ai/admin/repos.html`；四页使用 `inresearchrepo.html`、
`inewsrepo.html`、`fetchspecrepo.html`、`infrarepo.html`。

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

脚本只读邻接源码，不连生产、不部署；源文件缺失或生成失败直接退出。
输出在 `web/pages/admin/`，同步日期和来源完整 SHA-256 在
`web/pages/admin/repo-content/manifest.json`。流程变化后重跑并审阅差异，随研究站正常代码发布。
`--check` 使用已保存的同步日期，跨日检查不会仅因日期变化而误报。
源仓库更新不会自动改变研究站已发布快照；在架构相关 PR 中执行同步是当前更新责任。

服务端在归一化路径后校验真实 admin 会话，GET/HEAD、旧 Fetchspec 地址及原始内嵌页都受保护。
本地 `HUB_AUTH=0` 也不关闭这些页面的登录要求。无账号时用既有 `manage.py users add` 交互入口创建，
不要把密码放在源码、命令参数或快照里。响应标记 `private, no-store`。
旧 `/admin/fetchspec/reporg.html` 经认证后跳到 `/admin/fetchspecrepo.html`。

Tailscale 运维仪表盘继续提供运行状态；这里不代理其管理操作、不转发研究站 cookie 给其他域名。
新增仓库先接入真实架构来源，再登记路由、页面清单、同步脚本和权限测试；不提前创建空页面。

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
