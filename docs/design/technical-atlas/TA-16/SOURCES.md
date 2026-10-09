# TA16 类别来源与制图边界

当前44个详细候选的来源索引，尚未代表整项网页验收或发布。来源用于确认设备类别及可见结构背景，不能把通用示例认证为来源厂商的具体产品、型号、尺寸或额定值；封装外观不能证明芯片内部功能。原生图片、实际工具输入、源坐标、显示变换、编辑/拒绝记录分别见categories中的generation.json与prompt.txt。

## transformer

通用类别示意；三个套管为选定端子示例，非完整接线图。未指定型号、额定值、绕组、油路或装配尺寸。

- [官方类别资料](https://www.hitachienergy.com/products-and-solutions/transformers/power-transformers)：power transformer category and external liquid-filled family; not selected model geometry
- [官方类别资料](https://www.hitachienergy.com/products-and-solutions/insulation-and-components/transformer-insulation-components/transformer-bushings/bushings-for-ac-applications)：transformer bushing category; no terminal/winding arrangement established

尚未核实：model/manufacturer；terminal completeness, phase and winding scheme；oil circulation network or thermal rating；internal windings, insulation and hidden circuit；physical dimensions and assembly compatibility。

## quick-disconnect

两半接头沿同一水平配合轴分离；间隙是装配关系示意，不表示液体流向。 通用金属外形；未指定型号、尺寸、标准或互换性，未绘阀芯，也不据此承诺热插拔、无滴漏或介质兼容。

- [官方类别资料](https://www.cpcworldwide.com/liquid-cooling)：liquid cooling coupling categories including metal; product-dependent termination, valve, seal, material selection; not this exact model

尚未核实：precise bore/tolerance；valve internals；standard/interchangeability；working pressure/temperature/flow；sealing or hot-plug performance；material and coolant compatibility。

## cdu

四个管口为选定接口示例；内部泵组、换热器和供回拓扑未作产品设计。 通用类别外形；未指定型号、工质、流量、功率、尺寸、冗余或接口标准。

- [官方类别资料](https://www.vertiv.com/en-us/solutions/learn-about/liquid-cooling-options-for-data-centers/?Advocacy-Region=na)：CDU separates facility and IT-side cooling interfaces in selected liquid cooling architecture; drawing is external selected configuration, no verified topology

尚未核实：manufacturer/model；internal liquid circuit；port role and direction；pumps and heat exchanger configuration；coolant compatibility；operating ratings/redundancy；dimensions/installation。

## general-server

前脸八个载盘位置是选定外形示例，不证明已安装八盘；内部 CPU、内存与其他配置未指定。 通用机架式外形；不据此确认 OEM、机箱 U 高、尺寸、接口、功率或导轨兼容性。

- [官方类别资料](https://www.hpe.com/us/en/products/compute/proliant.html)：general-purpose server category with rack form factors; drawing not HPE model/configuration

尚未核实：manufacturer/model；internal components and device quantities；populated drive count；chassis U height/dimensions；mounting rail compatibility；electrical or protocol ratings。

## hv-switchyard

选定封闭设备外形；可见金属壳体与支承，不表示已核实内部相别、母线、电气回路或气体介质。 部件数量、型号、电压、绝缘、安装与操作要求以具体产品及项目资料为准。

- [官方类别资料](https://www.hitachienergy.com/us/en/products-and-solutions/high-voltage-switchgear-and-breakers/gas-insulated-switchgear/gis-service)：category exterior only; not exact configuration

尚未核实：exact electrical circuit/phase configuration；gas medium；ratings；manufacturer/model；installation and operating procedures。

## mv-switchgear

封闭金属柜的控制面、门与下部盖板示例；图中不展示内部相别、一次接线或已核实的电缆布置。 两柜分隔为选定外形；型号、电压、绝缘、额定值和操作要求以产品与项目资料为准。

- [官方类别资料](https://www.eaton.com/content/dam/eaton/markets/data-center/eaton-data-center-linecard.pdf)：category exterior only; not exact configuration

尚未核实：internal primary circuit；cable routing；electrical insulation；ratings；model；operating procedures。

## lv-switchgear

选定模块化功能面与封闭盖板示例；指示灯颜色为外形元素，不是设备当前运行状态。 具体内部电路、型号、电压、额定值和柜内分隔形式以产品资料为准；不作为施工或操作图。

- [官方类别资料](https://www.eaton.com/content/dam/eaton/markets/data-center/eaton-data-center-linecard.pdf)：category exterior only; not exact configuration

尚未核实：electrical circuit；ratings；electrical separation form；manufacturer/model；installation or operating steps。

## ups

四个模块位置为选定示例；内部整流、逆变、旁路与接线未绘制，外形不认证配置或性能。 通用柜式外形；型号、模块数、容量、电压、冗余、安装与操作要求以产品及项目资料为准。

- [官方类别资料](https://www.eaton.com/content/dam/eaton/products/backup-power-ups-surge-it-power-distribution/eaton-critical-power-distributed-IT-line-overview-br153163en.pdf)：category/form exterior only; not exact selected device or rating

尚未核实：internal topology；rectifier/inverter/bypass selection；modules/ratings/redundancy；OEM/model；installation or operation。

## ups-battery

柜内画出十个封闭模块面，仅为选定外形；未指定电芯化学、串并联、容量或电压。 内部电芯与接线未绘制；型号、模块数量、环境及安装要求以产品与项目资料为准。

- [官方类别资料](https://www.eaton.com/content/dam/eaton/products/backup-power-ups-surge-it-power-distribution/eaton-critical-power-distributed-IT-line-overview-br153163en.pdf)：category/form exterior only; not exact selected device or rating

尚未核实：cell chemistry and construction；series/parallel circuit；voltage/capacity；module actual count；OEM/model；operating conditions。

## busway

一段封闭母线槽、转向段和两个插接箱的外形示例；不展示内部导体或已核实现场回路。 支吊件与连接外形不是施工图；相别、电压、额定值、接口、安装和操作要求以具体资料为准。

- [官方类别资料](https://www.eaton.com/us/en-us/catalog/low-voltage-power-distribution-controls-systems/eaton-pdi-busway.html)：category/form exterior only; not exact selected device or rating

尚未核实：conductor/bus topology；electrical connections inside tap-offs；phase/voltage/ratings；site routing；support load/installation；OEM/model。

## gas-turbine

通用示意，非 OEM / CAD；进气段、封闭机罩、排气外部构件与底座可辨。 内部透平/燃烧/发电结构、燃料系统、并网方案与功率未核实；图不作安装或维护指引。

- [官方类别资料](https://www.solarturbines.com/en_US/products/oil-and-gas-power-generation-packages.index.html)：category external terminology only; not this drawn OEM/model/configuration

尚未核实：internal turbine/compressor/generator layout；model/rating/fuel and grid system；site installation/maintenance。

## gas-engine

示意散热器、发动机外形、联轴壳与发电机的相邻连接；非 OEM / CAD。 缸数、燃气处理、燃料与并网方案、额定功率未指定；外部结构不代表完整现场系统。

- [官方类别资料](https://www.cummins.com/en-apac/generators)：category external terminology only; not this drawn OEM/model/configuration

尚未核实：cylinder count/fuel train；rating/model/grid scheme；internal engine/generator geometry。

## fuel-cell

选定柜体形态示例，非 OEM / CAD；封闭外壳不能确认燃料电池的技术路线。 电堆、化学体系、燃料路径、端口分工与功率未核实；接口仅示意可见外部形态。

- [官方类别资料](https://www.bloomenergy.com/technology/)：category external terminology only; not this drawn OEM/model/configuration

尚未核实：SOFC/PEM or other chemistry；stack/fuel processor/pipe topology；port assignment/model/rating。

## backup-power

通用选定外形，非 OEM / CAD；仅示意机罩、外部消声排气、监控与共同底座。 发动机、发电机、油路及ATS/并网配套未绘；功率、排放许可和现场安装配置未知。

- [官方类别资料](https://www.cummins.com/en-apac/generators)：category external terminology only; not drawn OEM/configuration

尚未核实：hidden engine/alternator/fuel circuit；ATS/grid and emissions approval；model/rating/site installation。

## fuel-storage

选定储罐外形，非 OEM / CAD；罐顶接口、法兰、鞍座与底架仅示意可见结构。 容量、油位、接口分工与合规配置未知；日用箱、加注物流及现场管路未绘制。

- [官方类别资料](https://incal.cummins.com/www/literature/applicationmanuals/t-030_p115-132.pdf)：diesel bulk/day tank category; not this tank geometry/capacity/compliance

尚未核实：tank capacity/fuel level/port assignment；containment/compliance/site piping；complete logistics/day tank/fill system。

## bess

两类封闭柜体的选定外形，非 OEM / CAD；图中位置不代表接线或完整现场系统。 内部电芯/PCS电路、化学体系、容量、电压与二者连接未知；两柜角色仅为类别示意。

- [官方类别资料](https://www.eaton.com/us/en-us/catalog/energy-storage/xstorage-battery-energy-storage-system.html)：battery cabinets and PCS category; not this drawn OEM/configuration/connection

尚未核实：internal batteries and converter circuitry；chemistry/capacity/voltage/model；electrical connections/site configuration。

## pdu

两种选定外形并列，非同尺寸 / 接线图，非 OEM / CAD；柜内导体与现场接线未绘。 8个操作手柄、6个插座面为图例数量；插座标准、相别、电压、容量与配置未核实。

- [官方类别资料](https://www.eaton.com/content/dam/eaton/products/backup-power-ups-surge-it-power-distribution/eaton-critical-power-distributed-IT-line-overview-br153163en.pdf)：facility/rack distribution category only; not drawn product rating/pinout

尚未核实：plug standard/pinout/phases/rating；internal distribution circuit/site wiring；true/common scale/configuration。

## power-shelf

6个封闭模块与共同托架为选定图例，非 OEM / CAD；数量不代表实际采购配置。 电压、800V/HVDC、接口、额定值、供应者及储能功能均未核实；内部接线未绘。

- [官方类别资料](https://www.opencompute.org/projects/rack-and-power/)：rack-level conversion/shelves category only; not this six-module rating/topology

尚未核实：actual configuration count/rating/model；800V/HVDC or battery-storage applicability；rear pinout/internal power topology。

## bbu

选定封闭模块，非 OEM / CAD；拉手、保持机构、开孔与金属壳仅示意可见结构。 内部电芯、化学体系、串并联、容量、电压及接口未核实；不作为安装或热插拔指引。

- [官方类别资料](https://www.opencompute.org/projects/rack-and-power/)：rack battery-backup category only; not drawn chemistry/capacity/pinout

尚未核实：cell chemistry/arrangement/capacity；voltage/pinout/model；installation/hot-swap procedure。

## vrm

通用元件外形示例，非 OEM / CAD / 电路图；4个电感不认证实际相数或拓扑。 电压、电流、器件型号与电路连接未核实；示意位置和走线不得作为可制造板图。

- [官方类别资料](https://www.ti.com/product-category/power-management/multiphase.html)：controller/power-stage multiphase component category only; not schematic or exact layout

尚未核实：schematic/connectivity/phase count；device identification/rating；fabrication layout。

## smr

选定轻水堆技术家族的封闭圆柱容器概念；非完整电站、非所有SMR、非厂家模型或CAD。 内部堆芯/燃料/换热器未画；功率、尺寸、许可、价格、交期与可采购性均不由本图证明。

- [官方类别资料](https://www.nuscalepower.com/products/nuscale-power-module)：Specific integral light-water family documents cylindrical containment vessel; only external-form category context, not drawn dimensions/OEM geometry or generic SMR universality.
- [官方类别资料](https://www.energy.gov/ne/articles/what-should-i-do-if-small-modular-reactor-loses-site-power)：US DOE describes a steel reactor vessel within steel containment for one SMR design; no interiors are inferred or drawn.

尚未核实：SpecificOEMgeometry；AllSMRtypes；Core/fuel/internalcircuits；Dimensions/rating/licensing/procurement。

## rack-system

复用TA13原生母图：2交换机、8托盘×8载盘、2电源架×6模块仅本图选择；前门/左壳虚拟省略。 附件未接线；协议、各托盘内部配置、电压、功率、尺寸与冷却回路未知，非OEM实际配置或维修步骤。

- [官方类别资料](https://iportal.se.com/Contents/docs/UPS-AR3104.PDF)：Prior TA13 actual reviewed rack structure/mounting/covers category source; no dimensions/ratings adopted.
- [官方类别资料](https://www.opencompute.org/projects/rack-and-power/)：Rack infrastructure and rack power categories only; no ORV3 product or specific voltage/configuration inferred.

尚未核实：Newsystemcategorymapping_notyetpageverified；ActualOEMconfiguration；Voltage/HVDC/storage；Connectedfluid/electricalroutes。

## optics

双光口、散热壳与电接点是选定通用外形；内部激光器/接收器/芯片不补画。 光口标准、波长、协议、速率、功耗、型号与兼容性未核实；本图不是厂家器件图。

- [官方类别资料](https://www.nvidia.com/en-us/networking/ethernet/optical-transceivers/)：Optical transceiver category and distinction from DAC/active copper; selected external two-aperture form is generic and not certified OEM geometry/speed.

尚未核实：OEMgeometry；Connectorstandard；Wavelength/protocol/rate。

## copper-interconnect

两端金属电插头与外护套连续；选择铜缆类别，不以外观验证内部导体或电路。 有源/无源、接口标准、速率、线长、针脚与互配性未知；非施工布线或可采购型号。

- [官方类别资料](https://enterprise-support.nvidia.com/s/article/introduction-to-linkx-dac-cables)：Primary category definition of DAC twinax direct electrical cable between rack systems; selected illustrated external form not certified product/protocol/rate.
- [官方类别资料](https://www.nvidia.com/en-us/networking/ethernet/optical-transceivers/)：Separate copper DAC family from optical transceivers.

尚未核实：Active/passive；Internaltwinaxpairs；Standard/rate/length/pinout/compatibility。

## cabling

4根可追踪外护套与两端连接器仅为选定示例；外护套数不等于差分对、通道或针脚数。 内部屏蔽/导体、协议、带宽、长度、互配性与真实设备布线路径未知。

- [官方类别资料](https://www.molex.com/en-us/products/connectors/high-speed-internal-io/cx2-connectors-cable-assemblies)：Near-chip internal twinax connectors/cable assemblies and mechanical retention; chosen four-jacket form does not certify actual Molex design or signal pairs.

尚未核实：Signals/pairs/pinout；ExactOEMform；Bandwidth/standard/realrouting。

## connector

通用线端插头与板端座的封闭已配合外形；可见外壳、保持件与板上固定脚。 内部触点、针数、脚位、额定值、实际互配标准与配合尺寸未知；非安装步骤或厂家模型。

- [官方类别资料](https://www.molex.com/en-us/products/connectors/high-speed-internal-io/cx2-connectors-cable-assemblies)：Cable plug/socket pair, protected interface and retention category; illustrated mate/pin counts/geometry not an actual product specification.

尚未核实：Internalcontacts/pinout；Matingcompatibility；Voltage/current/standard；Installation。

## retimer

仅画封装外表与示意BGA接点；重定时功能来自类别资料，不能由外观识别或证明。 内部电路、球数、脚位、尺寸、工艺、代际、速率与型号未知；非特定器件版图。

- [官方类别资料](https://docs.broadcom.com/doc/85668-PB101)：Specific primary retimer datasheet documents BGA packaging and retimer function; generic closed package intentionally does not reproduce product dimensions/ball count/pinout.

尚未核实：Functionfromappearance；Ballcount/pinout/dimensions；Process/generation/rate/model。

## pcie-switch

封闭封装与底部接点仅为外形示例；交换功能来自类别资料，不能由外观识别。 内部电路、版图、球数、通道数、脚位、代际、速率、尺寸与型号均未核实。

- [官方类别资料](https://www.broadcom.com/products/pcie-switches-retimers)：Primary distinction between PCIe switches and retimers; only category context.
- [官方类别资料](https://www.broadcom.com/products/pcie-switches-retimers/pcie-switches/pex8617)：A specific older switch is offered in PBGA, supports selected generic package family only, not its obsolete model as current recommendation or drawn geometry.

尚未核实：Functionfromappearance；Ballcount/lanes/pinout；Process/generation/rate/dimensions/model。

## ai-asic

通用封装外形示意；不能凭外观认证 AI ASIC 功能或厂商型号。 不绘制内部计算阵列或 HBM；尺寸、焊球、引脚与性能均未指定。

- [官方类别资料](https://docs.cloud.google.com/tpu/docs/system-architecture-tpu-vm)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：封闭通用BGA封装外观；不认证AI ASIC功能/实际TPU型号/内部电路/HBM/尺寸/性能。

## fpga

带盖封装为外形示例；仅凭外观不能认证 FPGA 功能或厂商型号。 不绘制内部逻辑阵列；焊球数量、尺寸、引脚、电路与性能均未指定。

- [官方类别资料](https://docs.altera.com/r/docs/683481/current/an-114-board-design-guidelines-for-altera-programmable-device-packages/overview-of-bga-packages)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：内部fabric/LUT/型号/pinout/封装尺寸/性能均未认证。

## bmc

选定通用封装：外表不能认证 BMC 功能、厂商型号、固件或电路。 底面焊球仅局部可见；数量、尺寸、引脚定义及性能均未指定。

- [官方类别资料](https://www.aspeedtech.com/server/)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：实际BMC功能/型号/固件/IO定义/性能与封装精确尺寸未认证。

## cxl-memory

仅示意封闭模组与可见部位，不按具体产品或标准尺寸复刻。 不能凭外观确认 CXL 协议、内部存储器、容量、引脚定义或性能。

- [官方类别资料](https://investors.micron.com/news/press-release/2023/Micron-Launches-Memory-Expansion-Module-Portfolio-to-Accelerate-CXL-2-0-Adoption-08-07-2023/default.aspx)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：仅选定封闭模组示意；生成比例不作E3.S标准尺寸/具体CZ120产品复刻认证；外观不能认证CXL协议/内部DRAM或控制器/容量/型号/性能；连接器触点非pinout。

## storage-array

图中两排各四个托架为选定示意布局，不代表具体型号或实装数量。 不展示内部控制器或磁盘；不能据外观推断 RAID、容量、功率或性能。

- [官方类别资料](https://support.hpe.com/hpesc/public/docDisplay?docId=psg000246aen_us&docLocale=en_US&page=GUID-AC67DA7D-35D5-4C4C-AC0E-05E8465FF811.html)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：通用机架式存储阵列8托架外形示意；不是HPE特定型号复刻；内部控制器/磁盘装配/RAID/容量/功率均未认证。

## hdd

解释性开盖示意：只绘一张可见盘片，不断言整盘盘片或磁头总数。 盘轴与执行臂支点分离；不认证实际间隙、尺寸、容量或具体型号。

- [官方类别资料](https://www.seagate.com/support/disc/manuals/ata/1621pma.pdf)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：选定开盖解释示意；仅一张可见盘片，不认证总盘片/总磁头数、飞行间隙、尺寸或容量；pivot与spindle分离，原生图自查连接关系。

## network-switch

八个端口笼为选定示意布局，不代表具体商业型号、协议或端口速率。 不绘制后侧供电及风扇；机箱外观不能证明内部交换结构或性能。

- [官方类别资料](https://networking-docs.nvidia.com/sn2000hw/latest/introduction)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：8端口笼仅选定外形示意，不认证具体型号/协议/速率/实际端口数/后侧PSU或风扇；封闭外部。

## switch-asic

通用封装外形示意；不能凭外观认证交换功能、协议或厂商型号。 不绘制内部交换结构；尺寸、焊球、引脚、端口数与性能均未指定。

- [官方类别资料](https://investors.broadcom.com/news-releases/news-release-details/broadcom-ships-tomahawk-5-industrys-highest-bandwidth-switch)：类别背景；不据此复刻或认证本图具体规格。

尚未核实：通用封装外形，不认证交换功能/Ethernet协议/型号/端口数/内部结构/性能；不绘floorplan/pinout。

## dry-cooler

选定风扇—翅片盘管外形；四风扇为本图示例，不表示设备标准数量。 不展示内部水路或蒸发冷却附件；接口角色、容量及实际项目配置未知。

- [官方类别资料](https://guntner.com/products/dry-coolers/high-density-dc)：Category only: fan deck and finned heat exchanger, industrial frame. Source describes adiabatic product; drawn generic dry-only V-coil example does not reproduce its product, water system or performance.

尚未核实：Generic selected external V-coil form, not actual OEM geometry；Hidden header-to-coil route not validated; no fluid direction；No dimensions, capacity, pressure, wet/adiabatic module or installation claim。

## water-treatment

本图只选择过滤壳体、隔离阀与连接短管；不代表完整项目水处理工艺。 过滤精度、水质、流量、压力与消毒配置未知；不展示内部滤篮或操作步骤。

- [官方类别资料](https://www.eaton.com/us/en-us/catalog/filters-strainers/model-72-basket-strainer.html)：Category only: industrial closed basket strainer, lid, flanged connections, drain and mounting feet. Drawing does not reproduce Model72 geometry or rating.
- [官方类别资料](https://www.xylem.com/siteassets/brand/lowara/resources/data-centrecbs-brochure_a4---final_lowres2.pdf)：Data-center water distribution/treatment category context only; not evidence of depicted skid layout.

尚未核实：Selected closed basket-filter exterior only；Not entire supply/softening/RO/disinfection process；No filter grade/water quality/operating rating or instructions。

## chiller

本图选择封闭风冷机外形；三风扇为所选示例，不表示型号或标准数量。 压缩机、蒸发器及冷媒回路未展示；容量、接口流向和项目配置未知。

- [官方类别资料](https://www.vertiv.com/49d8ee/globalassets/documents/white-papers/vertiv-liquid-cooling-wp-en-na-sl-70807-web_332687_0.pdf)：Chiller category within cooling infrastructure; no support for drawn OEM internals or capacity.

尚未核实：Closed air-cooled chiller selected external example；Hidden compressor/evaporator/refrigerant circuit not validated；Unknown capacity/performance/port role/OEM dimensions。

## chilled-water-loop

两条平行管段分别示出阀门、法兰与保温；不是完整水力循环或现场施工图。 未指定供回水角色、流向、口径、压力和泵配置；不将两管互连成短路。

- [官方类别资料](https://www.xylem.com/siteassets/brand/lowara/resources/data-centrecbs-brochure_a4---final_lowres2.pdf)：Hydronic distribution/pipe context; no exact drawn valve topology or performance.

尚未核实：Selected independent paired pipe segments; not complete loop；Flow roles/direction, temperature, pressure, pipe size unknown；No pump or full site hydraulic topology。

## room-cooling

封闭柜体仅表达百叶、屏幕与检修面板；不推断内部风机、盘管或压缩机布置。 不据此区分 CRAC / CRAH 的介质与实际能力；气流方向、容量和项目配置未知。

- [官方类别资料](https://www.vertiv.com/en-us/solutions/learn-about/liquid-cooling-options-for-data-centers/?Advocacy-Region=na)：Air-cooling equipment category coexists with liquid cooling; does not establish drawn cabinet internals/medium.

尚未核实：Closed precision room cooling cabinet exterior only；Not certified CRAC/CRAH medium or internal cooling design；Unknown airflow direction/capacity/interfaces/OEM。

## immersion

四个通用承载框浸于示意液面下，手柄上露；数量与内部配置仅为本图选择。 不指定液体化学、温度、相态、能力或操作步骤；封闭外壳不展示完整散热回路。

- [官方类别资料](https://www.vertiv.com/en-us/solutions/learn-about/liquid-cooling-options-for-data-centers/?Advocacy-Region=na)：Category: servers submerged in dielectric fluid. No exact tank geometry, fluid chemistry, performance or operating method.

尚未核实：Single-bath external example; submerged carriers generic, not installed OEM server configuration；No fluid chemistry/temperature/phase/performance claim；No full circulation/hotplug/maintenance procedure。

## sidecar-hx

本条选择后门式换热框外形；不同时代表侧挂式 Sidecar，也不构成整柜液路。 接口方向、安装兼容和容量未知；底部小支撑仅为独立示意摆放，不表示安装脚件。

- [官方类别资料](https://www.vertiv.com/en-us/solutions/learn-about/liquid-cooling-options-for-data-centers/?Advocacy-Region=na)：Category: rack rear-door liquid-to-air heat exchanger. Not exact depicted OEM geometry or port arrangement.

尚未核实：Selected rear-door frame, not combined rear-door+sidecar design；Not complete rack liquid/air circuit; hidden channels and flow unknown；Temporary display supports do not prove installation hardware；Unknown capacity/OEM compatibility/pipe standards。

## manifold

八个支路接头为本图选定外形，不表示机柜标准数量；主管不展示内部流道。 供回角色、流向、接口标准、阀门功能与压力未知；不是完整冷却循环或安装图。

- [官方类别资料](https://www.coolitsystems.com/products-services/server-products/rack-manifolds/)：Rack manifold category and stainless external distribution assemblies; not eight-port standard or exact OEM connector design.

尚未核实：Eight branches are selected example, not universal quantity；No role/flow/port standard/pressure compatibility；No unseen full circuit or quick-disconnect internal mechanism。


## heatsink-vc

选定板翅散热器外形，非 OEM / CAD；鳍片与封闭底板只示意可见外部。 底板内部、材料、热设计与额定散热能力未核；不以外形认证均热板内部结构。

- [官方类别资料](https://www.boydcorp.com/thermal/air-cooling/heat-sinks/bonded-brazed-fin-heat-sink-assemblies.html)

尚未核实：Sources support category; selected rendered exterior is not OEM geometry, verified VC internals or performance。

## coolant

容器仅为工质类别图例，不表示已选包装、成分或容积；不展示内部液体。 配方、浓度、温度、压力、材料相容性及系统适用性，须按具体产品资料另核。

- [官方类别资料](https://www.cpcworldwide.com/Thermal-Campaigns/Liquid-Cooling-and-Chemical-Compatibility)：Coolants contact wetted system materials; coolant/material interaction and operating conditions require product-specific compatibility evaluation (official page paragraphs around lines18–21 and59).

尚未核实：Generic external packaging example; no actual coolant fill or selected OEM container；Opaque exterior cannot certify liquid chemistry, concentration, color, volume or polymer identity；No thermal/pressure/temperature/compatibility/performance rating or complete cooling loop。

## leak-detection

选定漏液检测绳与封闭模块外形；检测类别由资料支持，灰色编织外观不证明传感结构或型号。 引线、接头与末端仅示意机械连接；长度、端接电路、供电、报警、精度与覆盖未知，非安装图。

- [官方类别资料](https://rletech.com/wp-content/uploads/2014/01/SensingCable_Datasheet.pdf)：Primary sensing-cable category and mating end connectors; a cable category used with controllers for conductive-fluid detection.
- [官方类别资料](https://rletech.com/wp-content/uploads/2014/01/LD300_Datasheet.pdf)：Primary example of a sensing-cable controller with separate leader cable and end accessory; supports category relationship only.
- [官方类别资料](https://parameter-tech.com/product/conductive-fluid-sensing-cable/)：Current primary category page distinguishes conductive-fluid sensing cable; intended fluids cannot be inferred from appearance.

尚未核实：OEM model/geometry；internal sensing conductors or circuitry；controller electronics；terminal/EOL circuit；pin count or connector standard；length/dimensions；power and alarm state；accuracy/sensitivity；rack or room coverage；installation or procurement suitability。
