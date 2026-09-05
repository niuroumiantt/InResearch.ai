# 页面目录（inews.today 全站）

inews.today 现在由**一个仓库**承载完整产品：

| 仓库 | 负责什么 | 部署方式 |
| --- | --- | --- |
| [inews.today](https://github.com/niuroumiantt/inews.today) | Node 快讯时间线 + Python FT/Bloomberg/CNBC/WSJ/Reuters/Axios 六个独立原文库 | Node 由 push/autopull 部署；静态原文产出 rsync 到 `/srv/rawarticle/` |

**对外的门面只有一个：快讯时间线**（9-02 站长裁决：「让这些文章暂时不对外，
对外的只有快讯」）。原文库整体不对外 —— 页眉入口只有登录后的 staff 看得到，
页面本身由本站的 `requireStaff` 鉴权。其余一切分析/管理入口都收在页眉右上角
的「管理」菜单里，未登录不可见。

## 一、对外页面（公开）

| 页面 | 地址 | 来源 | 说明 |
| --- | --- | --- | --- |
| 快讯时间线 | `https://inews.today/` | 本仓库 `web/index.html` + `web/app.js` | 按发布时间倒序的 AI 快讯，标题中文呈现、原文可展开。公开（除非 `INEWS_REQUIRE_LOGIN=1`）。 |

## 一之二、原文库（暂不对外：入口 staff 可见，页面需登录）

这是只供站长学习的私有原文归档，其中 FT、Bloomberg 与 WSJ 正文使用站长个人
订阅登录态；9-02 起连**入口**也收进登录 —— 页眉的 FT / Bloomberg / CNBC / WSJ /
Reuters / Axios 原文库入口挂 `data-staff`，未登录不渲染。每页顶部印着自己的抓取规则。

| 页面 | 地址 | 来源 | 说明 |
| --- | --- | --- | --- |
| FT 原文清单 | `https://inews.today/rawarticle/ft/index.html` | `inews.render` | 累积库全量清单，浏览器内筛选 + 分页，标题中文、带评分、低分折叠。 |
| FT 正文页 | `https://inews.today/rawarticle/ft/p/<年月>/<uuid>.html` | `inews.render` | 每篇一页，按年月分层；读不到时间的在 `p/undated/`。 |
| Bloomberg 原文清单 | `https://inews.today/rawarticle/bloomberg/index.html` | `inews.render` | 同一套渲染、同一套评分；召回只走官方 AI 栏目页，无关键词。 |
| Bloomberg 正文页 | `https://inews.today/rawarticle/bloomberg/p/<年月>/<日期-slug>.html` | `inews.render` | 文章号是站方地址里的「日期-slug」，不是 uuid。 |
| CNBC 原文清单 | `https://inews.today/rawarticle/cnbc/index.html` | `inews.render` | 只走官方 AI 专题并完整展开 Load More；视频、会员稿和非 AI 噪音在正文前剔除。 |
| CNBC 正文页 | `https://inews.today/rawarticle/cnbc/p/<年月>/<日期-slug>.html` | `inews.render` | 只保存通过复核的公开文字稿；正文内嵌视频不影响文字稿准入。 |
| WSJ 原文清单 | `https://inews.today/rawarticle/wsj/index.html` | `inews.render` | 只走官方 AI 栏目；过滤视频、旁栏和非 AI 噪音，正文使用站长的订阅登录态。 |
| WSJ 正文页 | `https://inews.today/rawarticle/wsj/p/<年月>/<article_id>.html` | `inews.render` | 与其他原文库共用正文页、评分和存档结构。 |
| Reuters 原文清单 | `https://inews.today/rawarticle/reuters/index.html` | `inews.render` | B 路线：只走官方 Artificial Intelligence 专题并展开 Load More；过滤视频、AI Weekly、活动、Opinion/Breakingviews、市场口水和非核心 AI 内容。列表页经专用可见 Chrome 获取。 |
| Reuters 正文页 | `https://inews.today/rawarticle/reuters/p/<年月>/<日期-slug>.html` | `inews.render` | 只保存通过复核的 Reuters 公开文字正稿；DataDome/挑战页会明确记为失败。 |
| Axios 原文清单 | `https://inews.today/rawarticle/axios/index.html` | `inews.render` | A 路线：固定搜索 `artificial intelligence`、选择 Latest，并展开 Show 10 more results；政治口水、地方新闻、股票融资、视频和外围应用不入库。搜索页经专用可见 Chrome 获取。 |
| Axios 正文页 | `https://inews.today/rawarticle/axios/p/<年月>/<日期-slug>.html` | `inews.render` | 保存通过复核的公开 Smart Brevity 文字稿；短视频说明和空壳摘要不能过正文门槛。 |

导航仍是一条：原文库侧的 tab 栏「时间线 / 清单 / 姊妹库 / 后台」，第一项链回
本站，姊妹库互链。一个 repo、一个项目、一条导航 —— 只是这条导航的原文库段
现在要先登录。

## 二、后台页面（需 staff / admin，收在「管理」菜单）

| 页面 | 地址 | 来源 | 内容 |
| --- | --- | --- | --- |
| 分析 | `https://inews.today/`（SPA 内 `dashboard` 面板） | `web/app.js` | ⓪ 流水线（抓取规则与 24h 实测）① 内容 ② 来源（域名审核工作台）③ 抓取 ④ 车道（规则自演化，含人工锁定）。页内导航末尾链到原文库后台。 |
| 账号 | `https://inews.today/`（SPA 内 `admin` 面板） | `web/app.js` | 用户列表（改角色/停用）、翻译进度、审计流水。 |
| 统一原文库 Dashboard | `https://inews.today/rawarticle/dashboard/` | `inews.render` | 汇总 FT/Bloomberg/CNBC/WSJ/Reuters/Axios 六个来源的总量、正文覆盖率、失败原因、积压、运行时间与趋势；不合并各库清单或正文页。 |

「补译标题」是「管理」菜单里的一个动作按钮，不是独立页面。统一原文库
Dashboard 在页眉与「管理」菜单各有入口。

「规则演化」已并进「分析」页的 ④ 车道一节，不再是独立 tab。

## 三、API（本仓库 `src/server.js`）

| 端点 | 权限 | 用途 |
| --- | --- | --- |
| `GET /api/timeline` | 公开¹ | 时间线数据（瘦身行，不含 url） |
| `GET /api/filters` | 公开¹ | 筛选项元数据 |
| `GET /api/cluster?id=` | 公开¹ | 展开同一故事的全部转载 |
| `GET /api/version` | 永远公开 | 区分「缓存旧了」和「部署旧了」 |
| `GET /r/:id` | 公开 | 302 跳到文章真实地址 |
| `GET /api/stats` `GET /api/throttle` `GET /api/domains` `GET /api/rules` | staff | 分析页数据 |
| `POST /api/translate` `POST /api/pin` `POST /api/domain-status` `POST /api/classify` | staff + CSRF | 补译 / 锁车道 / 域名处置 / 价值精化 |
| `/api/auth/*` `/api/admin/*` | 见 `src/auth/routes.js` | 登录 / 注册 / 验证码 / 账号管理 |

¹ `INEWS_REQUIRE_LOGIN=1` 时也要登录。

## 四、不部署的页面（仓库内部）

| 位置 | 是什么 |
| --- | --- |
| `design/reference/*.html`、`SIGNAL_DESK_UI_GUIDE.md` | 设计参考与评审存档，不上服务器 |
| `web/brand/` | favicon / 页眉标记 / og:image（随站点发布，但不是「页面」） |
| `out/<SITE>/data/` | 台账 / 跑批记录 / 正文正本，**发布时不上传** |

## 访问控制(2026-09-03 起:全站一道门,本站自己的)

登录是各站自己的事(infra `docs/auth-standard.md` v3),Caddy 对本站只做反代与 TLS。

- **时间线等本站路径**:鉴权在 `src/auth/`,时间线默认公开(`INEWS_REQUIRE_LOGIN=1` 可整站要登录)。
- **`/rawarticle/*`(各原文库)**:本仓库 Python 采集器生成后 rsync 到服务器 `/srv/rawarticle`,
  infra 把它**只读挂进本容器**的 `/rawarticle`(`RAWARTICLE_DIR` 可改),由本站用
  `requireStaff` 挡门后直接读文件——正文来自站长个人订阅,只有 staff 能看。
  此前(09-02 至 09-03)它由 Caddy 用运维后台那组 basic_auth 挡门,两套登录互不相认,
  且 inresearch.ai 的运维密码顺带成了本站的门,违反各站自管——已撤。用例见 `test/rawarticle.test.js`。
