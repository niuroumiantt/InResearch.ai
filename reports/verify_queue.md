# 核验队列

生成时间：2026-08-14 ｜ P1（必须处理）1 条 ｜ P2（补强来源）7 条

流程：打开来源链接核对 → 有变化改数据+来源，无变化只改 verified_date → `python3 pipeline/validate.py`

## P1

- [ ] **prices / transformer-lead-time@2026-06-30** — 价格点已 45 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.woodmac.com/

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

