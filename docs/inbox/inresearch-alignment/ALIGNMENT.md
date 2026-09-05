# 产品研究目录 ↔ Datacenter Hub 对齐方案

> 来源项目：数据中心上下游产品研究目录（供应链轴：公司→产品线→产品→spec资料）
> 目标项目：Inresearch.ai / Datacenter Hub（研究角度轴 M01–M15 + 物理部件轴 bom.json）
> 日期：2026-08-18　｜　本包内容：ALIGNMENT.md（本文）+ products.json + companies_patch.json + bom_parts_extension.json

## 一、两个项目的分工（不变的约定）

| | 产品研究目录（我方） | Datacenter Hub（对方） |
|---|---|---|
| 主轴 | 供应链9环节 × 公司 × 产品线 × 产品spec | 15研究模块 + 爆炸图五层BOM |
| 负责生产 | 官方产品资料的搜集、建档、spec字段库（library/） | 价格序列、交期指标、研究结论（Finding） |
| 消费对方 | 引用其 status/交期/价格判断（如变压器交期序列） | 爆炸图"部件→厂商→产品→资料"下钻直接引用我方 products.json 与 library/ 路径 |
| 数据格式 | Excel（人读）+ 本包JSON（机器读） | JSON数据层 + Markdown知识层 |

**锚点只有两个**：`company_id`（kebab-case英文名）和 `bom_part_id`（以对方 `framework/bom.json` 为唯一定义源）。两边所有数据通过这两个ID互相引用，其余各自独立演进。

## 二、请对方执行的三个变更（走其框架变更流程）

1. **bom.json 扩充**：按 `bom_parts_extension.json` 新增14个部件节点（dram/ssd/hdd/storage-array/switch-asic/copper-interconnect/cabling/coolant/immersion/fan-vc/leak-detection/modular-dc/fpga/interconnect-chip），并删除被拆分的 `storage` 节点。在 `framework/00_overview.md` 变更日志记一条。
2. **修正现有节点的公司挂接**：`hbm` 节点当前挂 nvidia/amd（是用户不是制造商），应挂 samsung/sk-hynix/micron/cxmt；`ups`/`optics`/`server` 等节点公司不全——以 `products.json` 按 bom_part 聚合后回填 companies 字段。
3. **companies.json 合并**：`companies_patch.json` 160条按 company_id 合并（已存在的公司只追加 roles，不覆盖已核验字段；`verified_date=null` 的进对方核验队列）。

## 三、我方持续交付的内容与节奏

- **products.json**：公司×产品线目录（当前175条），每次目录版本更新随包交付；
- **library/ 索引**：资料落盘路径规范 `library/<环节表名>/<公司>/<产品线>/<型号>/<资料类型>_<版本>_<日期>.pdf`，路径已写入 products.json 每条记录的 `library_path`。爬取完成后交付 `library_index.json`（文件清单+来源URL+采集日期），文件本体过大不进git，走网盘/对象存储，索引进git；
- **节奏**：P0（34条）90天内完成首批建档；此后按季度增量。

## 四、给 Datacenter Hub 项目 Claude 会话的执行指令（复制即用）

```
docs/inbox/ 里有一个 inresearch-alignment 对齐包，请执行：
1. 读 ALIGNMENT.md；
2. 按 bom_parts_extension.json 更新 framework/bom.json（新增14节点、删storage、
   修正hbm等节点的companies挂接），在 00_overview.md 记变更日志；
3. 将 companies_patch.json 按 company_id 合并进 data/companies.json，
   冲突时保留已核验字段，新公司标记待核验；
4. 将 products.json 存为 data/products.json，并建立对应 schema
   （data/schema/products.schema.json），字段以现有文件为准；
5. 跑 pipeline 校验，汇报合并结果与冲突清单。
```

## 五、映射速查（9环节 → BOM层 → 模块）

| 我方环节表 | BOM层 | 主要部件ID | 模块 |
|---|---|---|---|
| 3-算力芯片与核心器件 | L5 | cpu, gpu, fpga※, interconnect-chip※ | M06 |
| 4-服务器与整机 | L4 | server, rack-frame | M06 |
| 5-存储介质与部件 | L5 | dram※, hbm, ssd※, hdd※ | M06 |
| 6-存储系统与数据管理 | L4 | storage-array※ | M06 |
| 7-网络与光互联 | L4/L5 | network-switch, switch-asic※, nic, optics, copper-interconnect※ | M07 |
| 8-供配电 | L1/L3/L4 | prime-power, substation, backup-power, bess, ups, power-dist, power-shelf, psu | M09（园区电源M04） |
| 9-散热与液冷 | L1/L3/L4/L5 | cdu, immersion※, room-cooling, heat-reject, water, manifold, coolant※, coldplate, fan-vc※ | M08 |
| 10-机柜布线与物理设施 | L2/L3/L4 | rack-frame, modular-dc※, cabling※, fire | M10 |
| 11-DCIM与运维配套 | L3 | dcim, leak-detection※ | M13 |

※ = 本次建议新增的节点。供需状态口径与 bom.json 一致：mature / tight / transition / emerging。
