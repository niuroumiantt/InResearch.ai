# fetchdata 仓库启动说明（2026-09-28）

供创建 `niuroumiantt/fetchdata` 的会话直接接手。本文只写边界与骨架，不写实现细节；正式规则在 [06 采集规范](../../framework/06_acquisition.md)，任务来源在 [五层目标清单](../../framework/tco_targets.json)。

## 为什么一个仓库承载四队

fetchstat、fetchfilings、fetchreports、fetchquotes 属于同一形态族：按日历从 API、EDGAR、IR 站或 PDF 地址取文件，哈希，打包，交付。差别在适配器，不在仓库。失败隔离靠各队独立的 runner 入口与定时器，限速身份靠各队配置。出现不同协议（中文分队的巨潮与集采平台）、不同运行依赖（fetchquotes 的浏览器采集变重）或大体量索引（EDGAR 全文）时再拆。

## 目录骨架

```text
fetchdata/
  core/            条件请求（ETag）、按主机限速、SHA256、包构建（manifest + SHA256SUMS + files/）、运行台账、交付上传
  registry/        来源登记表 sources.json：source_id → 队、主执行机、机制、日历、目标清单 target_id、最近 as_of、下次到期
  teams/
    fetchstat/     sources/*.json + adapters（EIA、BLS、Eurostat、FRED、费率 PDF、县级 PDF）
    fetchfilings/  EDGAR submissions/XBRL/全文检索、IR 站、可持续报告；迁入 inresearch 退役的 sec 采集器作种子
    fetchreports/  免费 PDF、arXiv/Epoch API；注册下载由 macmini 任务执行
    fetchquotes/   价目 API 与价目页快照；迁入 inresearch 退役的 gpu（Vast.ai）采集器作种子
  deploy/          AWS systemd timer 每队一个；macmini 辅助队列
```

## 三条硬规则

1. 一个来源只属一个队、一台主执行机、一个日历；换主机即结束旧任务、开新任务。登记表是唯一归属记录，变更进 Git。
2. 交付只走供应中心一个入口，包格式与 `framework/supply_contract.json` 的 delivery_contract 一致；接收端按 SHA 与来源身份去重，不信任包内指令。
3. 每个来源只抓目标清单点名的披露类型；公司是实例栏，可替换；数字带 as_of 进观测数据，规格进参照数据，文本进材料档案。

## sec 与 gpu 种子的来源

inresearch 于 2026-09-28 删除 `src/inresearch/adapters/acquisition.py` 中的 `fetch`、`sec`、`summarize_offers`、`gpu`，退役前版本在该提交的父提交可查（`git log -- src/inresearch/adapters/acquisition.py`）。迁入时保留：EDGAR 身份 User-Agent 与 10 次/秒上限、文件间隔 0.6 秒、修订件独立身份、不覆盖历史原件；Vast.ai 报价只是低价样本不是成交价，缺 `VAST_API_KEY` 时明确报缺凭据。凭据只放采集机私有环境文件。

## 第一批任务

按目标清单 `team` 列筛选：fetchstat 先做 `L3.power_price.state_industrial`、`L3.demand_charge.tariff`、`L3.wages.bls`、`L3.escalation.eci_cpi`、`L5.tax.rates`；fetchfilings 先做 `L4.useful_life.notes`、`L5.debt.terms`、`L2.pue_wue.operator_disclosure`；fetchreports 先做 `L3.capex.cost_index`、`L2.pue.survey`；fetchquotes 先做 `L3.gpu_hour.index`、`L3.gpu.used_and_rack`。

## 验收

每个 runner 交付一包到供应中心并取得回执；目标清单对应行的 `status` 与 `next_due` 据回执更新；`python3 manage.py governance --check` 与 `tests/unit/test_tco_targets.py` 通过。
