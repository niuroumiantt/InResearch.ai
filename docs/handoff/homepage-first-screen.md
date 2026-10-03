# 首页首屏排版交接（2026-10-03，m5）

> 发布验收已完成：PR #309 合并与网站实际功能版本 `084d65597cc7a908a2c19121fb1710f9879b716f`。以下首轮「不部署」仅记录当时范围，已被文末后续授权与实际发布替代。

## 目标与已定范围

三个指定桌面视口首屏同时看到全球规模大数字和完整世界地图；手机地图、新闻纵排。仅修改代码、本地验收和提交 PR，本轮不合并、不部署。

原工作区 `/Users/m5/code/inresearch.ai` 保持 `catalog-series-browser-test` 分支及原状态；本轮从远程 `main` 的 `3d4ad3d` 建立独立工作树 `~/.worktrees/inresearch.ai/homepage-first-screen`，分支 `homepage-first-screen`。

## 已完成

- 标题、说明和局部导航紧凑排版，大数字后直接放完整地图；筛选、主体标签、样本统计及核验日期移至地图下方。
- 首页移除两类机会区块和明细表；原始数据、新闻采集、持久线索、主体地图和项目明细继续保留。首页点园区进项目来源页，点主体进主体布局页，数字分别进市场口径或同条件项目明细。
- 保留全球估算/预测年份和来源，年度 IT 资本开支不称 TAM；地图统计明确标样本。新闻计数取当前接口快照实际可展示的精选/线索，注明范围，空缺显示「—」。
- 05 界面规范直接替代旧首页顺序，基准与验收映射升至 `2026.10.03.2`，保留原替代链与 Git 历史。

## 浏览器验收

Chromium / Playwright 1.62.1，100% 页面缩放，等待字体加载后取实际 DOM 边界；截图阶段取消新闻测试拦截，使用真实本地 API。完整 `viewBox="0 0 1000 490"`，地图比例不变，桌面大数字 42px、元信息至少 13px。

| 视口 | 地图下边缘（px） | 横向溢出 | 结果 |
|---|---:|---:|---|
| 1366×768 | 722.12 | 0 | 大数字与完整地图同屏 |
| 1440×900 | 758.39 | 0 | 大数字与完整地图同屏 |
| 1920×1080 | 797.58 | 0 | 大数字与完整地图同屏 |
| 390×844 | 793.58 | 0 | 地图后接新闻，页面自然滚动 |
| 320×740 | 799.08 | 0 | 地图后接新闻，页面自然滚动 |

实际截图及 `layout.json` 在 m5 的 `~/.local/state/inresearch.ai/homepage-first-screen/`，文件名 `homepage-<宽>x<高>.png`；桌面图是首屏，手机图为整页。运行产物不进 Git。三个桌面截图和手机截图已查看；新闻本地未连接 reader，截图如实显示「—」和未连接状态。测试夹具只验证精选计数、过滤与交互，不冒充真实新闻内容。

- `tests/industry.cjs`：上述视口、无首页表格/机会块、Microsoft/Meta 切换、五项筛选与 API 对账、样本/市场/地图/主体下钻、返回、键盘、缩放拖动、新闻精选/全部/空/503、明暗，通过。
- `tests/datacenter_news.cjs`：共享新闻、安全链接、时区、旧响应拒写、失败恢复/延迟/未连接，通过。
- `tests/ui_skin.cjs`：全站明暗、字体、窄屏、表单与偏好回归，通过。
- `manage.py validate --strict`：通过，0 warnings；`manage.py registry`：344 objects / 458 questions，引用有效。
- `manage.py governance --refresh` 与 `--check`：通过（1057 个在册文件）；全量单测 1657 项全部通过（38.632s）。初轮源码不变断言受并行清单刷新干扰，已在冻结源码后完整重跑通过。

复现截图：设置 `UI_QA_DIR` 为仓库外目录，运行 `NODE_PATH=<Playwright依赖目录> node tests/run_browser.cjs industry datacenter_news ui_skin`。测试运行器自建隔离本地服务；核心运行无新增依赖。

## 未完成与下一步

本轮部署按用户要求不执行。真实生产新闻内容、reader 接入、其他浏览器引擎和真实手机触屏不在本地验收证明范围。PR 评审后再依后续授权处理上线，无待用户决定的实现项。可 `/clear` 或开新会话后读取本交接继续。

## 后续发布授权（2026-10-03）

用户已明确授权继续 PR #309 的检查、修复、合并与现有网站发布，并要求线上验收新闻、布局及下钻；取代上文首轮不部署的任务边界。无关 Spark 服务不动。原四项 GitHub CI 成功、无审查线程；整合 #308 新生产记录解决 DECISIONS 与生成清单冲突，保留双方记录后重新治理校验及 CI。发布仅调用 AWS 现有 `inresearch-only-deploy.service`，不绕过发布锁、健康检查或持久数据边界。线上验收回执保存在 m5 `~/.local/state/inresearch.ai/homepage-release-20261003/`，发布版本以成功回执与实际容器一致为准。

## 线上发布与验收回执（2026-10-03 01:15–01:18 UTC）

- PR #309 首次 CI 通过后，整合 #308 解决两处记录/清单冲突；最终头提交 `3f4632cb633fbb76007c06bdf7bdb3881c7bdc57` 的 validate、browser(core)、browser(model_assets)、storage-container 全部通过，无审查线程/待解决意见。CI run `37085071288`。
- 01:14:58 UTC squash 合并为 `084d65597cc7a908a2c19121fb1710f9879b716f`。通过 AWS 已安装的 `inresearch-only-deploy.service` 正式发布，未旁路锁或直接替换容器，未修改持久数据。
- 发布状态 `HEALTHY: 084d65597cc7a908a2c19121fb1710f9879b716f`；applied 镜像与实际容器一致：`sha256:c3f3a46cae46b2811e6d77ff41e3a15a2c6e99a0006b14319eea75aa2bccd82f`。容器 01:15:32.695 UTC 启动、health=healthy、发布服务退出码 0；公网 `/healthz` 成功。公网 industry.js SHA256 与代码一致：`5c43363337084a5d00d7e76fb7d306d059efa51ef2a6e29eaecea1a7531de8d3`。
- 实际地址：https://inresearch.ai/ 。匿名浏览器检查五个视口通过，地图下边缘与上表一致，横溢均 0。三档桌面大数字与完整世界地图同屏，390/320 手机新闻在地图面板下方。真实截图不拦截 API、不填入测试新闻。
- 五项筛选与当前 `/api/industry` 对账：APAC 15、AI 11、operator 29、tenant 118、Microsoft 19 个样本园区；Microsoft→Meta 切换、Meta 建设中→Gallatin 项目来源、地图→Abilene 详情、市场卡→market.html#capacity 均成功，页面错误为 0。这些数仅是验收时本站样本。

### 生产新闻：成功、空结果与失败分开

- `/api/news` HTTP 200，feed.status=success；快照 80 条，其中 33 条有中文标题且 editorial_pick=true。默认精选 33 条的标题、链接逐条等于 API 合法可展示集合，标注「本次快照 · 当前筛选精选 33 条」。全部线索仍显示 33 条，因为其余 47 条无可展示中文标题；不是 inews 全量，也不是 80 条全部已翻译。
- 验收快照 exported_at=2026-10-03T01:01:36.609948+00:00，received_at=2026-10-03T01:11:31.975395+00:00，stale=false。同期 upstream `https://inews.today/api/feeds/datacenter?limit=100` 成功；与网站快照重合的 59 条精选标记全部一致。上游分页窗口与网站最近 80 条范围不同，不拿两者总数直接对比。
- 真空结果：按 alphabet-google 筛选，接口仍 200/success，但当前集合无匹配中文新闻；显示「—」及「当前范围暂无已整理的中文新闻」。另外仅在验收浏览器内模拟请求失败，页面显示「新闻暂时无法同步，请稍后重试。」及「—」，不会显示暂无新闻。模拟不修改服务、不用于实际截图。
- reader 汇总 status=degraded 来自已有阅读/OCR 失败码（model_output_invalid、model_output_truncated、ocr_gap_pages_exceed_limit、parked_derived_artifact、scanned_page_requires_ocr），不是新闻连接失败；新闻同步 status=success/error_code=null。Spark 仅只读检查：源码 d24b60a，reader 服务 active/running，发布与新闻 timer active，最近 oneshot 退出码 0；快照 release 标签仍为 780b314，未将该旧标签冒充 Spark 实际代码。未更新、重启或改动 Spark 服务。

### 证据位置与范围

m5：`~/.local/state/inresearch.ai/homepage-release-20261003/` 保存 `deployment-receipt.txt`、`pr-checks.json`、`live-verification.json`、公共新闻快照、浏览器验收脚本与 `live-<宽>x<高>.png`。桌面为真实首屏，手机为整页；截图已人工查看。运行产物不进 Git。本文作为发布后的文档回执提交，不改变功能源码；后续仅文档发布的实际容器 SHA 仍以部署回执为准。

没有发布阻塞。真实手机触屏硬件、其他浏览器引擎未验；Spark 历史阅读失败和 release 标签偏差是本轮未改动的既有状态。原主工作区保持原分支，未覆盖其内容。
