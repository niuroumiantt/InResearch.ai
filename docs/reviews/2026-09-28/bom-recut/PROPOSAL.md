# 部件重切提案：46 个部件 → 按"自己的价格、供应商、交期"重切

2026-09-28｜状态：**已采用**（同日用户批复第 7 节八问，执行结果见 docs/DECISIONS.md 同日条目；实际为 61 条物理部件：58 条加 BMC、CXL 内存、通用服务器三项批复新增）。原文如下。用户已于 2026-09-28 采纳骨架方向（生态为根、主题为列、目标由因子生成），并定下切分规则；本稿是该方向的第 2 步——部件对照表，交用户逐条审定。审定前不改 `framework/bom.json`、`research_graph.json`、`tco_factors.json`、`tco_targets.json`；供应商一栏只引用现有档案或标"待补"，不构成核验证据。

## 0. 一页结论

- 根是数据中心本身；第一层按**系统**分：设施、电力、冷却、IT（计算、内存、存储、网络）、控制与软件。现有八个生态入口就是这五个系统的叶子，逻辑不变，只把层级摆正。
- 部件按一条规则切：**拆到有自己的价格、自己的供应商名单、自己的交期为止；普通紧固件合并，关键稀缺件不合并。**
- 按这条规则，现有 46 条变成 **58 条物理部件 + 1 条软件条目 + 6 条站点权利 + 1 条设施基型**。变化最大的是电力（11 → 18）和冷却（11 → 15），因为交期和供应商集中度最高的东西——变压器、燃气轮机、开关柜、快接头——原来都捆在别的条目里。
- 三类东西从部件表里移出去：权利（土地、水权、电力配额、燃气接入、网络接入、许可）、软件（DCIM/BMS）、交付形态（微模块/预制化）。它们仍然有价格、有主体、有目标，只是不是"东西"。
- `bom.json` 的 L1–L5 是"装在哪"的五个**尺度**，改名后只作部件的一个属性，不再叫层。

## 1. 切分规则

一个条目要单独成行，三个判据至少满足两个：

| 判据 | 问法 | 例子 |
|---|---|---|
| 自己的价格 | 有独立报价、造价指数或单价序列吗？ | 变压器 $/MVA；燃气轮机 $/kW；快接头单价 |
| 自己的供应商名单 | 采购时面对的是另一批厂商吗？ | 冷水机组（江森/特灵/开利）和干冷器（Munters/Evapco）不是同一批 |
| 自己的交期 | 它的交期会独立地卡住项目吗？ | 变压器 2–4 年；燃机 3–5 年；开关柜 40–60 周 |

合并规则：只满足零或一个判据的，并入它所属的装配（紧固件、线槽、支架并入机柜或土建）。不合并规则：交期或供应商集中度是行业瓶颈的，即使单价低也单列（快接头、BMC 是两个边界案例，见第 7 节）。

不进部件表的三类，各有去处：

| 类别 | 去处 | 为什么 |
|---|---|---|
| 权利与配额（土地、水权、电力配额与并网、燃气接入、网络接入、许可） | 站点权利表，`kind: right` | 有价格、有主体、有时间（排队年限），但不是可采购的物件；进主体类与时间类事实 |
| 软件（DCIM、BMS/EPMS、固件） | 控制与软件系统下的软件条目，`kind: software`，不进 3D | 可采购、有订阅价与供应商，但没有物理位置 |
| 交付形态（微模块、预制化） | 设施基型 / 配置模板 | 它是同一批部件的另一种包装方式，不是零件 |

合同（PPA、租约、算力合同、融资）都不是部件也不是权利，是主体类事实，按现行规则进观测数据或材料档案。

## 2. 根与第一层：系统树

| 系统 | 子系统（按流向） | 对应现有生态入口 | 现有部件数 → 重切后 |
|---|---|---|---|
| 设施 | 土地与建筑；消防与安防；机柜结构 | 设施与机柜 | 5 → 4（土地、微模块移出；消防安防拆二） |
| 电力 | 电网接入 → 变电 → 发电与储能 → UPS → 配电 → 机柜与板级供电 | 电力与供配电 | 11 → 18 |
| 冷却 | 排热 → 冷冻水与 CDU → 机房与机柜 → 芯片级 → 工质与安全 | 冷却与热管理 | 11 → 15 |
| IT · 计算 | 整机柜、服务器、加速器、CPU、管理芯片 | 计算与加速 | 4 → 7 |
| IT · 内存 | HBM、服务器内存模组 | 内存生态 | 2 → 2 |
| IT · 存储 | 企业级 SSD、近线 HDD、存储系统 | 存储生态 | 3 → 3 |
| IT · 网络 | 交换、网卡、光与铜、连接器、布线、互联芯片 | 网络与互联 | 9 → 9 |
| 控制与软件 | DCIM/BMS/EPMS | 控制与运维 | 1 → 0 部件 + 1 软件条目 |

八个平铺还是五加四，是展示问题。`research_graph.json` 的 `hardware_domains` 已经把 46 个部件无重叠地分进这八个入口，重切后只改叶子，不改分法。

## 3. 对照表：46 → 重切后

列说明：**处理** = 保留 / 改名 / 拆分 / 移出 / 并入；**判据** = 价 · 商 · 期，写出满足的项；**档案公司** = 现有 `bom.json` 已登记的公司 ID（示例，未核验），"待补"= 现有档案没有；**把握** = 确定（规则下没有别的切法）/ 建议（有取舍）/ 待定（请用户决定，见第 7 节）。

### 3.1 设施

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| land 土地与选址 | 移出 → 权利 | `site:land` 土地（地价、租金、区划） | 价 · 主体 | — | 园区 | 确定 |
| shell 楼宇结构与土建 | 保留 | `shell` 建筑与土建（含场坪、基础、外墙屋面、机房装修与承重地板） | 价（每平方英尺造价指数）· 商（总包）· 期（建设历时） | 待补总包档案 | 建筑 | 确定 |
| fire 消防与安防 | 拆分 | `fire-suppression` 消防（探测、气体灭火、喷淋） | 价 · 商 | vesda | 建筑 | 建议 |
| | | `security` 安防（门禁、视频、周界） | 价 · 商（另一批厂商） | cn-security-group；待补 | 建筑 | 建议 |
| rack-frame 机柜与结构（ORV3） | 保留 | `rack-frame` 机柜与结构 | 价 · 商 · 期 | celestica, delta-electronics, rittal, legrand, panduit, cn-rack-group | 机柜 | 确定 |
| modular-dc 微模块/预制化 | 移出 → 设施基型 | 配置模板"预制化交付" | 不是零件 | schneider-electric-apc, kehua, kstar（转到基型档案） | — | 建议 |

### 3.2 电力（按电流流向）

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| grid 电网接入与并网 | 拆分 | `site:grid-capacity` 电力配额与并网（排队年限、并网协议）→ 权利 | 主体 · 时间 | aep, constellation-energy（转到权利档案） | 园区 | 确定 |
| | | `hv-switchyard` 高压开关站/GIS（园区侧） | 价 · 商 · 期 | 待补（现有 substation 档案里的 hitachi-energy、siemens-energy 可复用） | 园区 | 建议 |
| substation 变电站与大型变压器 | 拆分 | `transformer` 大型电力变压器 | 价（$/MVA）· 商 · 期（2–4 年，全行业最紧） | hitachi-energy, siemens-energy, hyosung, ge-vernova；已有序列 transformer-lead-time | 园区 | 确定 |
| | | `mv-switchgear` 中压开关柜 | 价 · 商 · 期 | abb, schneider-electric, eaton, siemens（现在登记在 ups/power-dist 下） | 园区 | 建议 |
| prime-power 主用自备电源 | 拆分 | `gas-turbine` 燃气轮机 | 价（$/kW）· 商 · 期（3–5 年） | ge-vernova, siemens-energy, mitsubishi-power | 园区 | 确定 |
| | | `gas-engine` 燃气往复式机组 | 价 · 商（另一批）· 期（1–2 年） | wartsila；待补 caterpillar/cummins/innio | 园区 | 建议 |
| | | `fuel-cell` 燃料电池 | 价 · 商 · 期（月级，桥接方案） | bloom-energy | 园区 | 确定 |
| | | 小型堆/核电 | 尚不可采购 | — | — | 待定 |
| backup-power 备用电源（柴发） | 改名 | `diesel-genset` 柴油发电机组 | 价 · 商 · 期 | caterpillar, cummins, rolls-royce, kohler, cn-genset-group | 园区 | 确定 |
| bess 储能/BESS | 保留 | `bess` 储能系统 | 价（$/kWh）· 商 · 期 | tesla-energy-catl-fluence | 园区 | 确定 |
| fuel-supply 燃料供给 | 拆分 | `site:gas-supply` 天然气管道接入（容量、合同）→ 权利 | 主体 · 时间 | 待补管线公司 | 园区 | 建议 |
| | | `fuel-storage` 柴油储运（储罐、日用箱、加注） | 价 · 商 | 待补 | 园区 | 建议 |
| ups UPS 与短时储能 | 拆分 | `ups` UPS 系统（整流、逆变、静态开关） | 价（$/kW）· 商 · 期 | schneider-electric, eaton, vertiv, abb, delta-electronics, siemens, huawei-digital-power, east | 机房 | 确定 |
| | | `ups-battery` UPS 电池（锂电/铅酸） | 价（随电芯价格独立波动）· 商（电芯厂） | smartli-vertiv；待补电芯厂 | 机房 | 建议 |
| power-dist 配电（母线/PDU/开关柜） | 拆分 | `lv-switchgear` 低压开关柜 | 价 · 商 · 期（40–60 周） | abb, schneider-electric, eaton, siemens, zhongheng-electric | 机房 | 确定 |
| | | `busway` 母线槽 | 价 · 商（另一批）· 期 | 待补 | 机房 | 建议 |
| | | `pdu` 机房配电柜/PDU/RPP（含机柜配电条，是否再拆见第 7 节） | 价 · 商 | vertiv, eaton, schneider-electric | 机房 | 建议 |
| power-shelf 机柜电源（Power Shelf/BBU） | 拆分 | `power-shelf` 机柜电源架（AC-DC / HVDC 整流） | 价 · 商 · 期 | delta-electronics, liteon-advanced-energy | 机柜 | 确定 |
| | | `bbu` 机柜电池备份单元 | 价 · 商（电芯） | delta-electronics, liteon-advanced-energy；待补电芯厂 | 机柜 | 建议 |
| psu 电源模块 | 保留 | `psu` 服务器电源模块 | 价（$/W）· 商 | delta-electronics, liteon-advanced-energy | 部件 | 确定 |
| vrm 板级供电 | 保留 | `vrm` 板级供电（VRM/Power Stage） | 价 · 商 · 期 | infineon-mps-renesas-adi-ti, delta-electronics | 部件 | 确定 |

### 3.3 冷却（按热量流向反向）

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| heat-reject 冷机与室外排热 | 拆分 | `chiller` 冷水机组 | 价（$/冷吨）· 商 · 期 | johnson-controls, trane, carrier | 机房 | 确定 |
| | | `dry-cooler` 干冷器/冷却塔/蒸发冷 | 价 · 商（另一批）· 期 | munters, modine-airedale；待补 evapco/bac | 园区 | 建议 |
| （新增） | 新增 | `chilled-water-loop` 冷冻水泵、管路与阀门 | 价 · 商（机电分包）· 期 | 待补 | 机房 | 建议 |
| water 水源与水权 | 拆分 | `site:water-rights` 水权与取水许可 → 权利 | 主体 · 时间 | — | 园区 | 建议 |
| | | `water-treatment` 水处理与供水（泵站、过滤、软化） | 价 · 商 | ecolab, ecolab-veolia | 园区 | 建议 |
| room-cooling 机房空气系统 | 改名 | `room-air-cooling` 机房空气冷却（CRAH/CRAC/风墙） | 价 · 商 · 期 | vertiv, munters, johnson-controls, modine-airedale, stulz | 机房 | 确定 |
| cdu CDU 与液冷分配 | 保留 | `cdu` CDU | 价（$/kW）· 商 · 期 | coolit-systems, vertiv, schneider-electric, motivair-by-schneider, boyd, nvent, envicool, shenling, goaland | 机房 | 确定 |
| manifold 歧管与快接 | 拆分 | `manifold` 机柜歧管与管路 | 价 · 商 | coolit-systems, vertiv | 机柜 | 确定 |
| | | `quick-disconnect` 快接头 | 商（集中度高）· 期（认证周期） | staubli-cpc-parker-danfoss | 机柜 | 建议 |
| coldplate 冷板 | 保留 | `coldplate` 冷板 | 价 · 商 · 期（GPU/OEM 认证） | coolit-systems, motivair, zutacore, accelsius | 部件 | 确定 |
| coolant 冷却液/工质 | 保留 | `coolant` 冷却液与工质 | 价（每升）· 商 | chemours；待补 | 机柜 | 确定 |
| immersion 浸没式液冷 | 改名（技术路线 → 设备） | `immersion-tank` 浸没式液冷槽/系统 | 价 · 商 · 期 | liquidstack-submer-grc, sugon-dcu | 机房 | 建议 |
| sidecar-hx Sidecar/后门热交换器 | 改名 | `rear-door-hx` 机柜级液-气换热器（RDHx/Sidecar） | 价 · 商 · 期 | nvent, motivair, coolit-systems, boyd | 机柜 | 确定 |
| fan-vc 风扇/VC/散热模组 | 拆分 | `server-fan` 服务器风扇 | 价 · 商 | nidec-ebm-papst-avc-auras（拆开登记） | 部件 | 建议 |
| | | `heatsink-vc` 均热板与散热器 | 价 · 商（另一批） | 同上拆开 | 部件 | 建议 |
| leak-detection 漏液检测 | 保留 | `leak-detection` 漏液检测 | 商 · 期（认证） | ttk-rle-nvent | 机房 | 确定 |

### 3.4 IT · 计算

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| server AI 服务器/整机 | 拆分 | `rack-system` 整机柜系统（NVL72 类，按柜计价；含 NVLink 交换托盘与背板） | 价（$/柜）· 商 · 期 | nvidia（设计）；foxconn-industrial-internet, quanta-qct, wiwynn, dell-technologies, supermicro（制造） | 机柜 | 建议 |
| | | `server` 服务器整机（通用与加速节点） | 价 · 商 · 期 | 现有全部 21 家 | 机柜 | 确定 |
| gpu GPU/AI ASIC | 拆分 | `gpu` GPU 加速器 | 价 · 商 · 期 | nvidia, amd, intel-gaudi, huawei-ascend, cambricon, hygon-dcu, biren, moore-threads, metax, iluvatar-corex, enflame | 部件 | 确定 |
| | | `ai-asic` 定制 AI ASIC | 价（自研/代工）· 商（另一批：Broadcom、Marvell、Alchip 与云厂商） | broadcom, alphabet-google, amazon, google-tpu-aws-trainium-ms-maia-meta-mtia | 部件 | 确定 |
| cpu CPU | 保留 | `cpu` | 价 · 商 | 现有 10 家 | 部件 | 确定 |
| fpga FPGA/异构加速 | 保留 | `fpga` | 商 | amd-xilinx-alveo-altera-agilex | 部件 | 确定 |
| interconnect-chip 的 BMC 部分 | 拆出 | `bmc` 基板管理控制器 | 商（aspeed 近乎单一来源） | aspeed | 部件 | 待定 |

### 3.5 IT · 内存

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| hbm HBM/内存 | 保留（收紧命名） | `hbm` HBM | 价 · 商 · 期 | samsung, sk-hynix, micron, cxmt | 部件 | 确定 |
| dram DRAM 模组 | 保留 | `dram-module` 服务器内存模组（RDIMM/MRDIMM） | 价（与 HBM 周期不同步）· 商 | samsung, sk-hynix, micron, cxmt | 部件 | 确定 |
| dram 的 CXL 部分 | 待定 | `cxl-memory` CXL 内存扩展 | 商（控制器厂另一批）· 新兴 | samsung-cmm-micron-cz120-mxc-smart-modular | 部件 | 待定 |

`hbm` 现挂的指标 `cowos_capacity_wpm` 属于 GPU 上游（先进封装），应随 `gpu.upstream` 走，不再挂在 HBM 上。

### 3.6 IT · 存储

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| ssd SSD 固态硬盘 | 改名 | `enterprise-ssd` 企业级 SSD（NAND、控制器为上游，研究图谱已分开） | 价 · 商 · 期 | 现有 12 家 | 部件 | 确定 |
| hdd 近线 HDD | 改名 | `nearline-hdd` | 价 · 商 · 期 | seagate, western-digital, toshiba-electronic-devices | 部件 | 确定 |
| storage-array 存储系统/阵列 | 改名 | `storage-system` 存储系统 | 价 · 商 | 现有 21 家 | 机柜 | 确定 |

### 3.7 IT · 网络

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| network-switch 交换机与互联 | 保留 | `network-switch` 交换机（scale-out 以太网/IB；scale-up 交换托盘归 rack-system） | 价（每端口）· 商 · 期 | 现有 12 家 | 机柜 | 确定 |
| switch-asic 交换芯片 | 保留 | `switch-asic` | 价 · 商（集中） | broadcom, marvell, centec | 部件 | 确定 |
| nic NIC/DPU | 改名 | `nic-dpu` | 价 · 商 | nvidia, broadcom, amd-pensando, intel-ethernet, cn-dpu-group | 部件 | 确定 |
| optics 光模块/CPO | 改名 | `optical-transceiver` 光模块（CPO 为新兴子条目） | 价（800G 单价序列）· 商 · 期 | 现有 10 家 | 部件 | 确定 |
| copper-interconnect 高速铜互联 | 改名 | `copper-cable` 高速铜缆（DAC/AEC；背板归 rack-system） | 价 · 商 | credo, amphenol-luxshare-molex-te-connectivity | 机柜 | 确定 |
| connector 高速连接器 | 改名 | `high-speed-connector` | 价 · 商 · 期（随速率代际） | amphenol-luxshare-molex-te-connectivity | 部件 | 确定 |
| cabling 结构化布线与光纤 | 改名 | `structured-cabling` | 价 · 商 | corning, commscope, yofc | 机房 | 确定 |
| interconnect-chip 互联与接口芯片 | 拆分 | `retimer` 重定时器 / AEC 芯片 | 价 · 商（集中） | astera-labs, montage, broadcom, marvell | 部件 | 建议 |
| | | `pcie-switch` PCIe/CXL 交换芯片 | 价 · 商 | broadcom, microchip | 部件 | 建议 |
| network-access 园区网络接入 | 移出 → 权利 | `site:network-access` 网络接入（暗光纤、运营商、IXP） | 主体 · 价 | 待补运营商档案 | 园区 | 建议 |

### 3.8 控制与软件

| 现有条目 | 处理 | 新条目 | 判据 | 档案公司 | 尺度 | 把握 |
|---|---|---|---|---|---|---|
| dcim DCIM 与运维软件 | 移出 → 软件条目 | `software:dcim-bms` DCIM / BMS / EPMS（监控、运维、电力监控） | 价（订阅）· 商 | schneider-ecostruxure-it, vertiv-environet, sunbird-dctrack-nlyte, neteco | — | 建议 |

### 3.9 站点权利与配额（新表，`kind: right`）

| 条目 | 来自 | 主要变量类 | 说明 |
|---|---|---|---|
| `site:land` 土地 | land | 价格、主体 | 地价与租金序列；区划 |
| `site:water-rights` 水权与取水许可 | water | 主体、时间 | 取水量、许可期限 |
| `site:grid-capacity` 电力配额与并网 | grid | 时间、主体 | 排队年限、并网协议、谁付升级费 |
| `site:gas-supply` 天然气接入 | fuel-supply | 主体、时间 | 管道容量、供气合同 |
| `site:network-access` 网络接入 | network-access | 主体、价格 | 暗光纤租约、运营商 |
| `site:permits` 许可（区划、环评、排放、建设） | 新增（9-06 评审清单） | 时间、主体 | 审批时长、暂停令 |

## 4. 汇总

| 类别 | 现有 | 重切后 |
|---|---|---|
| 物理部件 | 46 | 58（含 1 条待定的 bmc；不含待定的 cxl-memory） |
| 软件条目 | 0（dcim 混在部件里） | 1 |
| 站点权利 | 0（混在部件里） | 6 |
| 设施基型 | 0（modular-dc 混在部件里） | 1 |

按系统：设施 4、电力 18、冷却 15、计算 7、内存 2、存储 3、网络 9。

## 5. 覆盖核对

对照 2026-09-06 物理架构评审第 4 节的覆盖清单：

| 物理范围 | 覆盖情况 |
|---|---|
| 园区与建筑 | shell（含场坪、基础、外墙屋面、机房装修）；权利表覆盖土地与许可 |
| 供配电 | 从 hv-switchyard 到 vrm 十八条完整链；接地防雷、保护计量并入 lv-switchgear 与 shell 的电气工程 |
| 冷却与流体 | 从 dry-cooler/chiller 到 coldplate 完整链；泵、阀、管路在 chilled-water-loop；过滤与水处理在 water-treatment；软管快接在 quick-disconnect |
| 网络与互连 | 交换、网卡、光、铜、连接器、布线、互联芯片九条；逻辑网络不在部件表 |
| 计算与存储装配 | rack-system、server、gpu、ai-asic、cpu、fpga、bmc、内存两条、存储三条；主板/背板/载板作为 server 与 rack-system 的子装配，不单列（不满足独立价格判据） |
| 消防、安防与监控 | fire-suppression、security、leak-detection；传感器与控制器归 software:dcim-bms 的硬件部分 |
| 外部接口与非物理配套 | 站点权利六条；软件一条；合同按主体类事实处理 |

## 6. 对因子树与目标表的影响

- `revenue.gpus.density`：bom_parts 加 `rack-system`（按柜计价的整柜功率与每柜 GPU 数正来自它）。
- `cost.energy.pue`：`room-cooling` → `room-air-cooling`；`heat-reject` → `chiller` + `dry-cooler`；加 `chilled-water-loop`、`coolant`（现在 coolant 未挂因子树，此处挂上）。
- `cost.energy.price`：`grid` → `site:grid-capacity`；`prime-power` → `gas-turbine` + `gas-engine` + `fuel-cell`。
- `cost.other_opex`：`dcim` → `software:dcim-bms`；`fire` → `fire-suppression` + `security`；加 `water-treatment`、`leak-detection`。
- `cost.depreciation.capex.accelerators`：加 `ai-asic`。
- `cost.depreciation.capex.other_it`：加 `rack-system`、`psu`（现在 psu 未挂因子树，此处挂上）、`nic-dpu`、`optical-transceiver`、`dram-module`、`enterprise-ssd`。
- `cost.depreciation.capex.shell`：`substation` → `transformer` + `mv-switchgear` + `hv-switchyard`；`backup-power` → `diesel-genset`；加 `ups`、`ups-battery`、`lv-switchgear`、`busway`、`pdu`、`shell`。
- `cost.depreciation.capex.btm`：`prime-power` → 三条；`fuel-supply` → `fuel-storage`（`site:gas-supply` 作为权利挂主体类）。
- `cost.depreciation.capex.land`：`land` → `site:land`。

挂完之后，因子树对部件的覆盖从 44/46 变为全覆盖；目标表（第 4 步）再从"因子输入 × 部件 × 数据类别"生成。

## 7. 请用户决定

1. `bmc` 是否单列（单一来源，但单价低）。
2. `cxl-memory` 是否单列（新兴，控制器厂另一批）。
3. 机柜配电条（rack PDU）是否从 `pdu` 再拆一条。
4. 小型堆/核电是否登记为 emerging 条目，还是等可采购再登记。
5. 站点权利放在 `bom.json` 内（`kind: right`）还是新文件 `site_rights.json`。
6. 尺度 ID 是否从 L1–L5 改为 S1–S5：改了更清楚，但 web 页面、3D 映射与旧链接都要保留别名。
7. 通用服务器与加速器服务器是否分两行：本稿不分，用 `rack-system` 承接按柜计价的部分。
8. 软件条目是否进目标表：本稿建议进（有订阅价与供应商），不进 3D。

## 8. 采用后的实施顺序

1. `bom.json` 升 2.0：新 ID、`kind`（part / right / software / archetype）、`layer` 键保留并改称尺度、`aliases` 记录旧 ID → 新 ID，web 页面与 3D 的 `mesh.userData.part` 经别名解析。
2. `research_graph.json`：`hardware_domains` 换成新叶子；旧 `part:*` 节点按 03 号规范保留兼容身份。
3. `tco_factors.json`：按第 6 节改 `bom_parts`。
4. 生成目标表（第 4 步），替换手写的 43 行。
5. 测试、`governance --refresh`、登记 DECISIONS。
