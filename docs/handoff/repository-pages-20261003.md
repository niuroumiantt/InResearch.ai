# 仓库架构统一入口交接（2026-10-03，Codex 云环境）

## 本轮范围

用户要求四个协作仓库的架构页集中到研究站，infra 组织图也需登录访问。
使用既有域名 inresearch.ai，统一 `/admin/repos.html` 与
`/admin/inresearchrepo.html`、`/admin/inewsrepo.html`、
`/admin/fetchspecrepo.html`、`/admin/infrarepo.html`。

管理页已增加总览链接。所有统一页、内嵌原图及来源清单由服务端检查真实 admin 会话；
本地免登录不豁免，member/intern 不可读，私有响应禁止缓存。
旧 Fetchspec 地址认证后转到新入口；旧源码仅留迁移说明。

来源分别为研究站程序职责说明、inews pipeline-map 架构声明、Fetchspec 自有生成器、
infra 自有组织图。同步脚本保存日期和完整内容 SHA-256，infra 图字节保持不变。
新闻统一页没有实时计数，明确标注并链接原站统计；不读取或复制演示库、生产库、密钥、会话。
Tailscale 仪表盘的运行数据与管理入口继续留在原处。

## 已验证

- InResearch Python 全量：1,662 项通过。
- inews Node 全量：699 项通过；新增导出测试确认没有创建数据库、实时计数为 null。
- Fetchspec 架构生成器：5 项通过，已生成页 `--check` 通过。
- 完整外观套件已用真实临时管理员账号复测23页；修正管理页用户表在手机上的横溢，未放宽登录权限。
- 统一同步脚本：8 个页面/来源产物 `--check` 通过。
- 治理基准 2026.10.03.4 检查通过（1,073 个在册文件）；严格数据校验 0 warnings，registry 344 对象/458 问题有效。
- 新浏览器套件：真实临时账号登录/退出、5 页 × 桌面/手机 × 明暗共20种视图、无横向溢出、
  原图 SVG 加载、旧地址跳转、页面错误0；人工查看截图并修正主题初始化。
- 权限测试覆盖 GET/HEAD、编码与路径归一化、匿名/member/intern/admin、本地 AUTH_OFF、原图和清单。

日志与截图在云环境 `/workspace/.onboarding/logs/repo-*` 和
`/workspace/.onboarding/repo-screenshots/`；不包含真实用户凭据。
本轮未运行全站全部浏览器套件、容器部署及生产真实账号验收。

## 发布状态与下一步

用户已授权本轮上线。先前 GitHub API Forbidden 已解除：2026-10-03 云环境复测仓库 API 与
研究站 healthz 均为200；现有 GitHub 身份可写仓库。四仓库 origin/main 与本地开发基线一致。
提交本记录时准备 PR 与 CI，尚未合并或部署；不能据本地测试推定公网新地址已可用。
研究站沿用 `inresearch-only-deploy` 正式发布器，timer 每两分钟检查 main，不另建发布通道。
云环境无 SSH 配置；线上公开健康和匿名权限可直接验证，真实管理员验收仍需研究站既有登录身份。

按既有 PR/CI/正式发布流程推进研究站后，验证匿名与非管理员拒绝、真实管理员访问所有入口及原图、
退出后不可读取、反向代理未缓存私有响应。四仓库改动应分别审阅；运行页面已随研究站保存快照，
无需生产容器访问旁边三个 Git checkout。其他仓库更新架构后要显式同步并重新发布研究站。
