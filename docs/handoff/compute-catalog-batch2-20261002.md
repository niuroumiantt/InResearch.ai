# 第二批计算目录交接（2026-10-02 启动）

当前为发布前本地验收；代码合并和生产发布尚未完成，不能以此视为已上架。

| 公司 | 新增实体 | 合并后实体 | 具体命名型号 | 有规格的具体型号 |
|---|---:|---:|---:|---:|
| AMD | 43 | 43 | 43 | 43 |
| Intel | 35 | 37 | 37 | 36 |
| 兆芯 | 12 | 12 | 0 | 0 |
| 摩尔线程 | 2 | 5 | 5 | 3 |
| 壁仞 | 1 | 4 | 3 | 3 |
| Supermicro | 5 | 5 | 5 | 5 |
| SK hynix | 5 | 5 | 2 | 2 |

净新增103个实体，七家合并后111项。系列不计型号；只有身份而无规格表的芯片不算有规格型号。Intel保留Gaudi 3 HL-338，摩尔线程保留S80，壁仞保留166三款。NVIDIA、Micron和其他第一批公司不在本轮写入范围。

## 证据与形态

- AMD EPYC 27款来自官方9005发布原表，按单元格换行对齐型号，共享核数保留；Instinct 16款/显存变体来自ROCm官方表。MI300A按APU记录，不据GPU表外推CPU参数。MI350X/MI355X为OAM模组，MI350P为PCIe板卡。
- S4000→QY102AA-800、S5000→PH100是两条官方明示关系。S4000卡有曲院GPU表述，不据此给QY102AA-800芯片补架构；PH100有平湖架构原文。芯片实体不继承卡的显存/功耗。
- Intel GPU的Xe-HPG/Xe-HPC来自ARK原表；未明示底层芯片对应，关系留空。
- 壁仞166L/166M按原文独立为模组，166C为板卡。BR100仅计有发布原文的系列。
- Supermicro保持服务器类别；SK hynix的两款SSD与三项内存系列保持存储/内存类别，不混入计算芯片，不收入Solidigm品牌型号。

## 未完成

- AMD主站robots超时；EPYC其他代际、Intel全系列未穷尽，Intel PDF主机robots403。
- 兆芯12项均为CPU系列；工艺空白保留空白，Admin下载入口robots禁止，没有独立SKU证据就不拆型号。
- 燧原robots403；海光官网组件仅取得CPU型号，DCU Z100/K100缺厂家逐型号和架构证据，不从软件兼容信息补值。
- BR100/BR104独立型号规格及架构原件仍缺；166系列不与BR100/BR104猜测关联。
- S5000本批只有正文精度与OAM形态等部分规格；官网及文档sitemap没有检出完整硬件数值表，对标脚注和集群吞吐不当作单卡规格。
- SK hynix产品门户robots500；新闻站根robots合法跳到同站/en/robots.txt后404，按既有404/410无规则策略处理，403/5xx仍封闭。新闻原文不冒充完整数据表；内存系列没有料号，不算具体SKU。

## 数据与重跑

- 原件、来源回执、ProductStore、导出：`~/.local/share/fetchspec/compute-catalog-batch2-20261002/`。旧原件按SHA核验后复制必要引用，原位置保留。
- 生产基线与验收：`~/.local/share/inresearch.ai/compute-catalog-batch2-20261002/`。`changed-company-baseline-v2.json`是修改公司的有效只读基线。最初全库传输被SSH中断的`production-baseline.json`不是完整JSON，不用作基线。
- 重跑：`PYTHONPATH=src python3 -m fetchspec.catalog_batch2 --root <原件根> --company <公司> --baseline <changed-company-baseline-v2.json>`；`config/catalog_batch2.json`固定经审阅SHA。
- 复用既有schema1接收和发布凭据；逐公司回执须匹配规范化包SHA，发布前核对基线run_id仍一致。
- 本批不操作Spark。

## 验收与发布

本地七家原件SHA、分类及芯片关系契约、真实接收和保留既有ID检查通过。回归、CI、合并和生产回执待填。

## Concrete models and series

- amd: AMD Instinct MI355X, AMD Instinct MI350X, AMD Instinct MI350P, AMD Instinct MI325X, AMD Instinct MI300X, AMD Instinct MI300A, AMD Instinct MI250X, AMD Instinct MI250, AMD Instinct MI210, AMD Instinct MI100, AMD Instinct MI60, AMD Instinct MI50 (32GB), AMD Instinct MI50 (16GB), AMD Instinct MI25, AMD Instinct MI8, AMD Instinct MI6, AMD EPYC 9965, AMD EPYC 9845, AMD EPYC 9825, AMD EPYC 9755, AMD EPYC 9745, AMD EPYC 9655, AMD EPYC 9655P, AMD EPYC 9645, AMD EPYC 9565, AMD EPYC 9575F, AMD EPYC 9555, AMD EPYC 9555P, AMD EPYC 9535, AMD EPYC 9475F, AMD EPYC 9455, AMD EPYC 9455P, AMD EPYC 9365, AMD EPYC 9375F, AMD EPYC 9355, AMD EPYC 9355P, AMD EPYC 9335, AMD EPYC 9275F, AMD EPYC 9255, AMD EPYC 9175F, AMD EPYC 9135, AMD EPYC 9115, AMD EPYC 9015
- biren: 壁砺™ 166L, 壁砺™ 166M, 壁砺™ 166C, BR100系列
- intel: Intel Gaudi 3 PCIe HL-338, Intel® Xeon® 6980P Processor, Intel® Data Center GPU Flex 140, Intel® Data Center GPU Flex 170, Intel® Data Center GPU Flex 170V, Intel® Data Center GPU Max 1550, Intel® Data Center GPU Max 1100, Intel® Xeon® 6788P Processor (336M Cache, 2.00 GHz), Intel® Xeon® 6787P Processor (336M Cache, 2.00 GHz), Intel® Xeon® 6768P-B Processor (256M Cache, 2.20 GHz), Intel® Xeon® 6767P Processor (336M Cache, 2.40 GHz), Intel® Xeon® 6760P Processor (320M Cache, 2.20 GHz), Intel® Xeon® 6747P Processor (288M Cache, 2.70 GHz), Intel® Xeon® 6745P Processor (336M Cache, 3.10 GHz), Intel® Xeon® 6740P Processor (288M Cache, 2.10 GHz), Intel® Xeon® 6738P Processor (144M Cache, 2.90 GHz), Intel® Xeon® 6737P Processor (144M Cache, 2.90 GHz), Intel® Xeon® 6736P Processor (144M Cache, 2.00 GHz), Intel® Xeon® 6730P Processor (288M Cache, 2.50 GHz), Intel® Xeon® 6728P Processor (144M Cache, 2.70 GHz), Intel® Xeon® 6724P Processor (72M Cache, 3.60 GHz), Intel® Xeon® 6714P Processor (48M Cache, 4.00 GHz), Intel® Xeon® 6530P Processor (144M Cache, 2.30 GHz), Intel® Xeon® 6527P Processor (144M Cache, 3.00 GHz), Intel® Xeon® 6520P Processor (144M Cache, 2.40 GHz), Intel® Xeon® 6517P Processor (72M Cache, 3.20 GHz), Intel® Xeon® 6515P Processor (72M Cache, 2.30 GHz), Intel® Xeon® 6507P Processor (48M Cache, 3.50 GHz), Intel® Xeon® 6505P Processor (48M Cache, 2.20 GHz), Intel® Xeon® 6369P Processor (24M Cache, 3.30 GHz), Intel® Xeon® 6357P Processor (24M Cache, 3.00 GHz), Intel® Xeon® 6353P Processor (24M Cache, 2.70 GHz), Intel® Xeon® 6349P Processor (18M Cache, 3.60 GHz), Intel® Xeon® 6337P Processor (18M Cache, 3.50 GHz), Intel® Xeon® 6333P Processor (18M Cache, 3.10 GHz), Intel® Xeon® 6325P Processor (12M Cache, 3.50 GHz), Intel® Xeon® 6315P Processor (12M Cache, 2.80 GHz)
- moore-threads: MTT S5000, MTT S4000, MTT S80, QY102AA-800, PH100
- sk-hynix: PEB110, PS1012 U.2, HBM3E 12-layer, DDR5 RDIMM, DDR5 MRDIMM
- supermicro: SYS-821GE-TNHR, SYS-442B-NR, SYS-222H-TN, SYS-621C-TN12R, SYS-212GB-FNR
- zhaoxin: 开先® KX-7000系列处理器, 开先® KX-6900系列处理器, 开先® KX-6000G系列处理器, 开先® KX-6000系列处理器, 开先® KX-5000系列处理器, 开先® ZX-C+系列处理器, 开先® ZX-C系列处理器, 开胜® KH-50000系列处理器, 开胜® KH-40000系列处理器, 开胜® KH-30000系列处理器, 开胜® KH-20000系列处理器, 开胜® ZX-C+FC-1080/1081系列处理器
