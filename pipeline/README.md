# pipeline — 采集与校验

零依赖 Python（与 news 项目同基因）。所有脚本从仓库根目录运行。

## 现有脚本

| 脚本 | 档位 | 作用 |
|---|---|---|
| `validate.py` | — | 按口径手册校验六张表：主键、枚举、引用、保鲜度。**任何提交前先跑它** |
| `verify.py` | — | 生成核验队列 `reports/verify_queue.md`：按 P1/P2/P3 列出该重新查证的记录。**核验工作的固定入口** |
| `fetch_sec.py` | 自动 | 拉取公司库中有 CIK 公司的 EDGAR 文件清单（含 20-F/6-K），原始数据存 `data/raw/sec/` |
| `update_ciks.py` | 自动 | 用 SEC 官方映射表回填美股公司 CIK |
| `fetch_news_signals.py` | 自动 | 消费 news 项目数据，按实体词条匹配出新闻线索 → `data/raw/news_signals/` |
| `export.py` | — | **报告导出器**：从知识层汇编报告（全量/按模块），md + 可选 docx → `reports/output/` |
| `serve.py` | 常驻 | 本地服务器：静态站点 + 管理后台 API（任务白名单执行 / 价格人工录入含校验回滚）|
| `fetch_gpu_prices.py` | 自动 | vast.ai 市场 H100/B200 现货租价中位数 → prices 时间序列（每日幂等）|
| `refresh_indicators.py` | 自动 | 库内可计算指标回填（容量聚合/价格序列直通/合同聚合），collect 每日调用 |
| `output_map.py` | 按需 | Top N 数据中心世界地图 → HTML + PDF（无头 Chrome 渲染）|

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

## 规划中（按路线图第二阶段）

- `fetch_news_signals.py`：消费 news 项目的 `data/*.json`，按公司/项目名匹配出实体相关新闻，
  生成"待核验线索"清单（不直接入库——自动信号，人工核验，才能写库）
- `fetch_gpu_prices.py`：抓取主要 GPU 租赁平台公开报价 → `prices` 表 `gpu-hourly-*` 序列
- `fetch_ir_events.py`：监控重点公司 IR 页面的财报/公告发布
- `refresh_indicators.py`：从六张表计算可自动化的指标（如 L8+ 聚合、建设周期中位数），
  写回 `framework/indicators.json` 的 value/as_of

## 入库纪律

自动脚本**只产生线索和原始存档，不直接改六张表**。
写库的权限属于人（或人确认后的 AI 提取）——每条记录必须过 `validate.py` 且带齐
口径四标签（口径类型、状态、来源级别、核验日期）。
