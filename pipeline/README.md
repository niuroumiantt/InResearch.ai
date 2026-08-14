# pipeline — 采集与校验

零依赖 Python（与 news 项目同基因）。所有脚本从仓库根目录运行。

## 现有脚本

| 脚本 | 档位 | 作用 |
|---|---|---|
| `validate.py` | — | 按口径手册校验六张表：主键、枚举、引用、保鲜度。**任何提交前先跑它** |
| `fetch_sec.py` | 自动 | 拉取公司库中有 CIK 公司的 EDGAR 文件清单，原始数据存 `data/raw/sec/` |

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
