# 私有订阅正文库页面目录

这是统一仓库中私有订阅采集器生成的页面目录；公开时间线页面由根目录的
`web/` 与 `src/server.js` 提供。

产出全部是静态 HTML，分别落在 `out/<SITE>/`，由 `tools/publish.sh` rsync 到服务器
`/srv/rawarticle/<site>`，对外挂在 `https://inews.today/rawarticle/<site>/` 下。

| 页面 | 路径 | 生成函数（`inews/render.py`） | 说明 |
| --- | --- | --- | --- |
| 清单（对外门面） | `index.html` | `render_index` | 累积库全量清单：顶部三条带（原文库 / 本轮 / 最近 5 轮），浏览器内筛选与分页 |
| 统一后台 | `../DASHBOARD/index.html` | `render_unified_dashboard` | 各库总览、健康状态、正文覆盖、失败原因、召回效率、架构和关键词趋势 |
| 正文页 | `p/<年月>/<uuid>.html` | `render_article` | 每篇一页；读不到时间的在 `p/undated/` |
| 样式 | `site.css` | `layout.py` | 与主站 `sd-ui-kit.css` 同源的 Signal Desk 设计语言 |

`out/<SITE>/data/`（台账 / 跑批记录 / 正文正本）是抓取的内部状态，**发布时不上传**。

导航已与主站统一：每页页眉在时间线、FT、Bloomberg、CNBC、WSJ、Reuters、Axios
清单和统一后台之间切换。各来源的清单和正文始终分开，只有 Dashboard 汇总各自的
运行事实。
