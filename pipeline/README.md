# pipeline — 采集与校验

零依赖 Python（与 news 项目同基因）。所有脚本从仓库根目录运行。

现行采集、存储和翻译方案见 [06 采集规范](../framework/06_acquisition.md)。采集在 Spark 执行；旧简报日期不能代替采集状态。

## 现有脚本

| 脚本 | 档位 | 作用 |
|---|---|---|
| `acquisition.py` | 第一阶段 | 永久台账、新闻投影、SEC 主文件、GPU 原始快照与候选统计 |
| `launch_acquisition.py` | 只读 | 查询 Spark 采集摘要 |
| `validate.py` | — | 按口径手册校验六张表：主键、枚举、引用、保鲜度。**任何提交前先跑它** |
| `verify.py` | — | 生成核验队列 `reports/verify_queue.md`：按 P1/P2/P3 列出该重新查证的记录。**核验工作的固定入口** |
| `collect.py` | 兼容 | 只汇总历史缓存，不联网；不能代表当前采集状态 |
| `fetch_sec.py` | 兼容 | 转交 Spark acquisition.py；有界抓取主文件并存永久采集台账 |
| `update_ciks.py` | 自动 | 用 SEC 官方映射表回填美股公司 CIK。**仅本机**（同上）|
| `fetch_news_signals.py` | 兼容 | 仅接收 inews 显式新闻投影 --input；旧 news/data 协议退役 |
| `fetch_gpu_prices.py` | 兼容 | Vast 按需报价候选快照；需要私有凭据，不再写 prices.json |
| `refresh_indicators.py` | 自动 | 库内可计算指标回填（容量聚合/价格序列直通/合同聚合），collect 每日调用 |
| `export.py` | — | **报告导出器**：从知识层汇编报告（全量/按模块），md + 可选 docx → `reports/output/` |
| `serve.py` | 常驻 | 服务器：静态站点 + 登录认证（auth.py）+ 管理后台 API（任务白名单执行 / 价格人工录入含校验回滚 / 派工）|
| `auth.py` | 模块 | 登录认证与限速（PBKDF2 + HMAC 会话 cookie），serve.py 与 users.py 共用；非独立命令 |
| `users.py` | 按需 | 用户 CRUD 命令行（加/删/改角色/重置密码），与管理后台 API 同一套规则 |
| `workorder.py` | 按需 | 工单队列 = 声明 − 现状：每个模块下一步该做什么 → `reports/workorders.json` |
| `blindspot.py` | 按需 | 盲区体检：库里有但分类器看不见的材料 |
| `intake.py` | 按需 | 成员投递机检与三档分流（A 人批 / B 模型批抽 10% / C 自动）；`--selftest` 自检 |
| `facts.py` | 按需 | 事实层校验 + 可比性判定；`--public` 对外口径预览 |
| `scan_inbox.py` | 按需 | 扫描收件箱 docs/inbox 新材料 |
| `reading_queue.py` | 按需 | 旧评分账本的迁移队列；只排序，不豁免逐篇深读 |
| `launch_reader.py` | 按需 | 查询 Spark 常驻阅读状态；启动和守护见 SPARK_OPERATIONS.md|
| `output_map.py` | 按需 | Top N 数据中心世界地图 → HTML + PDF。**PDF 仅本机**（无头 Chrome 渲染）|
| `build_library_index.py` | 按需 | 重建研报库索引 docs/LIBRARY_INDEX.md。**仅本机**（库本体不进 git）|
| `fix_stale_paths.py` | 按需 | 修打分表死路径：按文件名在库内重定位，唯一匹配才改写。**仅本机**（同上）|

## 核验闭环（固定路径）

```
① python3 pipeline/verify.py          → 得到今天的核验清单（查什么、开哪个链接、改哪个字段）
② 逐条打开来源核对                     → 有变化：改数据 + status_history + 来源
                                        无变化：只更新 verified_date
③ python3 pipeline/validate.py        → 合规把关
④ git commit                          → 核验历史全部留痕（谁、何时、改了什么）
```

自动信号（fetch_sec / fetch_news_signals）发现的事件是**事件驱动核验**的触发器：
看到相关 8-K/新闻 → 直接对该实体走 ②③④，不必等队列到期。

## 知识层闭环（研究结论的生命周期）

```
信号命中 Finding 的触发器 → 把该 Finding 状态改为 needs-review（verify.py 会列入 P1）
→ 复核证据：结论变 → 修订正文（旧结论重要则 superseded 存档）；没变 → 更新修订日期回 current
→ python3 pipeline/export.py 随时可从最新知识层导出报告
```

## 规划中

- `fetch_ir_events.py`：监控重点公司 IR 页面的财报/公告发布

（2026-08-18 卫生审计：原列此处的 fetch_news_signals / fetch_gpu_prices /
refresh_indicators 三个早已实现，已并入上表。）

## 入库纪律

自动脚本**只产生线索和原始存档，不直接改六张表**。
写库的权限属于人（或人确认后的 AI 提取）——每条记录必须过 `validate.py` 且带齐
口径四标签（口径类型、状态、来源级别、核验日期）。
