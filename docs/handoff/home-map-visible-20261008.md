# 首页地图交付补齐（2026-10-08，macmini / hermes）

## 目标与规则
用户反馈旧会话声称完成的地图更新未显示。补齐技术图册、鼠标悬停与缩放固定点位尺寸；保留来源、点击/键盘、固定浮窗、Escape 与筛选。不再要求重复授权。

## 进度
- GitHub 无法找到旧回复的 `2f9182f` 或对应地图 PR，检查时生产和 main 为 `06f96964`，旧地图源码仍只有点击交互。
- 实际交付 PR： https://github.com/niuroumiantt/InResearch.ai/pull/395 。点位/新闻环按登记坐标 translate，尺寸按 viewBox 宽度反向 scale；右边界浮窗优先置于点位左侧，避免阻挡悬停点。
- 已通过：industry 16项单元、validate --strict（0 warnings）、registry、governance、JS语法与diff检查；真实本地五视口浏览器回归覆盖悬停离开、固定/Escape、缩放尺寸/锚定、手机、明暗与截图。
- 实际发布：PR #395 已合并为 `0b75aff0`，AWS status 为 `HEALTHY: 0b75aff069e6e8dfccb0aff5a36d8c745fd8cf77`、同 SHA 镜像与容器 healthy 已核对。CI validate、model_assets、storage-container 已通过，core 回归仍运行；不冒称全站CI完成。公网浏览器回执见PR描述与本会话输出 `map-live-verification.json`，不得以本地截图代替上线。

## 入口与后续核对
- 实现：web/components/industry.js、web/themes/industry.css、web/pages/index.html；规范：framework/05_interface_system.md；回归：tests/industry.cjs。
- 首页加载 `/assets/industry.js?v=20261008-map2`，CSS 同版本；经纬索引/网格是装饰，不新增研究数据。
- 生产状态：`ssh aws 'sudo cat /var/lib/inresearch-ops/inresearch-only/status'`；容器应 healthy，公网地图应出现 `.atlas-grid`，悬停显示、离开关闭，放大两次尺寸误差小于0.1px。
- 独立工作树：~/.worktrees/inresearch.ai/home-map-visible-20261008。未覆盖主工作区、未改Spark运行服务。

## 待用户决定
无。
