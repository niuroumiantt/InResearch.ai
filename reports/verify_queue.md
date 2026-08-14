# 核验队列

生成时间：2026-08-15 ｜ P1（必须处理）9 条 ｜ P2（补强来源）7 条

流程：打开来源链接核对 → 有变化改数据+来源，无变化只改 verified_date → `python3 pipeline/validate.py`

## P1

- [ ] **prices / dc-rent-index-na@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.jll.com/en-us/insights/market-dynamics/north-america-data-centers
- [ ] **prices / transformer-lead-time@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.woodmac.com/
- [ ] **prices / vacancy-rate-na@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.jll.com/en-us/newsroom/data-center-availability-crisis-deepens-as-vacancy-hits-historic-low
- [ ] **research / M02-F7** — 标记 needs-review（Neocloud 把电力、芯片、网络、软件和资本组合成可用算…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M02-F8** — 标记 needs-review（Neocloud 是 Hyperscaler 的弹性层而非简…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M02-F9** — 标记 needs-review（公开信息不足以算出四大厂统一的"自用/出租 MW 比例"，可…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M03-F2** — 标记 needs-review（Anthropic 以 AWS 为主云与训练基础，Googl…）
      动作：复核证据后改回 current 或修订结论（M03.md）
- [ ] **research / M04-F2** — 标记 needs-review（核电分"现役共址/重启/SMR"三条时间表：重启本十年可供数…）
      动作：复核证据后改回 current 或修订结论（M04.md）
- [ ] **research / M15-F7** — 标记 needs-review（单指标会被宣传误导：三色判断要求至少三个同向信号，资本指标识…）
      动作：复核证据后改回 current 或修订结论（M15.md）

## P2

- [ ] **contracts / openai-oracle-2025** — media 级来源
      动作：用财报 RPO/监管文件交叉验证金额与期限
      来源：https://www.wsj.com/
- [ ] **prices / gpu-hourly-h100-spot@2026-07-31** — estimate 级（带假设推算）
      动作：寻找可替代的一手/研究级来源
      来源：https://cloud-gpus.com/
- [ ] **prices / transformer-lead-time@2026-06-30** — estimate 级（带假设推算）
      动作：寻找可替代的一手/研究级来源
      来源：https://www.woodmac.com/
- [ ] **projects / us-mi-saline** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-nm-dona-ana** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-tx-milam** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-wi-port-washington** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand

