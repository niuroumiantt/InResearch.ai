import {systemIllustrations} from './system-atlas.js?v=20261010.16';
/* Adopted illustrations enrich the category dossier; the live 3D inspector stays interactive. */
const illustrations = {
  coldplate: {
    id: 'TA-10', title: '冷板与接头 · 内部液路与快接',
    image: '/assets/technical-atlas/coldplate-v1.svg', preview: '/assets/technical-atlas/coldplate-v1-preview.svg',
    master: '/assets/technical-atlas/coldplate-v1.png',
    alt: '暖白一体冷板局部剖视：封合层虚拟剖开露出内部液路和两端集流区，两个示例接口各接一根软管，右下放大同类快接的插头与插座配合端。',
    note: '通用冷板局部剖视；双端口、内部液路及材料仅为示例。右下为同类快接两半放大，非额外回路；虚拟剖开不表示可拆维护或热插拔，结构与性能以选定型号为准。',
    labels: ['封合层与虚拟剖口：展示内部液体通路，不表示维护时开盖', '内部液路与两端集流区：通用微通道示例，非外露空气散热鳍片', '导热基底：热源接触面位于下方，不指定芯片或导热材料', '两处示例接口与柔性软管：液体连接数量和方向按具体产品核对', '快接插头与插座：右下为同类配合端的重复放大，不是新回路', '选型边界：材料、流量、压力、冷却液、密封和兼容性以产品资料为准，不承诺无滴漏或热插拔'],
  },
  'server-fan': {
    id: 'TA-09', title: '服务器风扇墙 · 模组与安装位',
    image: '/assets/technical-atlas/fan-wall-v1.svg', preview: '/assets/technical-atlas/fan-wall-v1-preview.svg',
    master: '/assets/technical-atlas/fan-wall-v1.png',
    alt: '暖白金属风扇笼：三只带防护格栅的风扇模组就位，第四只沿相应空位上提，显示底部连接端与对应连接座、提拉部和释放卡扣。',
    note: '通用四位风扇笼装配示意：三就位、一上提，唯一空位对应上提模组。数量、结构、接口和气流以选定型号为准；上提关系不表示气流或热插拔条件。',
    labels: ['风扇模组与防护格栅：展示叶轮和外部保护结构', '四位示例：三个就位、一个上提，不指定真实产品数量', '提拉部与释放卡扣：展示可拆模组的机械类别', '安装导向与金属承载框：对应风扇笼上的独立安装位', '模组连接端与对应连接座：解释同一空位的装配关系，不指定引脚或兼容性', '产品差异：气流、转速、风量、电压、冗余和更换条件以选定型号资料为准'],
  },
  psu: {
    id: 'TA-08', title: '服务器电源模块 · 接口与抽拉结构',
    image: '/assets/technical-atlas/psu-v1.svg', preview: '/assets/technical-atlas/psu-v1-preview.svg',
    master: '/assets/technical-atlas/psu-v1.png',
    alt: '暖白长条服务器电源模块：金属外壳、交流输入插口、风扇格栅、抽拉把手与释放锁扣，相反端是输出板边接点；左上为同类接点局部放大。',
    note: '通用服务器 AC–DC 电源模块外观示意；左上为同类输出接点放大。型号、额定功率、效率、尺寸及装配兼容性以产品资料为准。',
    labels: ['交流输入插口：位于外部供电端', '输出板边接点：位于相反端，展示与系统的连接位置', '风扇与防护格栅：展示电源模块上的散热部件', '抽拉把手与释放锁扣：展示可拆模块的机械结构', '金属壳体、折边与通风开孔：解释外部结构，内部电路另查型号资料', '产品差异：接口、额定值、兼容性与更换条件按选定型号资料确定'],
  },
  nic: {
    id: 'TA-07', title: '网卡 · PCIe 与网络接口',
    image: '/assets/technical-atlas/nic-v1.svg', preview: '/assets/technical-atlas/nic-v1-preview.svg',
    master: '/assets/technical-atlas/nic-v1.png',
    alt: '暖白 PCIe 网卡：双 QSFP 类端口、金属挡板、定位缺口与金手指、板级元件和网络控制器，上方为分离鳍片散热器，左上为端口笼局部放大。',
    note: '通用 PCIe 网卡结构示意；双端口与分离散热器为图示示例，左上是端口笼放大。型号、端口代际、速率与装配以产品资料为准，不概括所有 DPU 架构。',
    labels: ['网络端口：双 QSFP 类端口仅为类别示例，左上为同类端口笼放大', 'PCIe 金手指：与主机连接，定位缺口区分连接边', '金属挡板：展示扩展卡的安装部件', '网络控制器与鳍片散热器：展示板上器件与散热装配关系', '电路板与供电元件：细节解释部件类别，不指定走线、引脚或功耗', '产品差异：实际型号、接口代际和速率另查产品资料；图示不代表所有 DPU 的内部设计'],
  },
  cpu: {
    id: 'TA-06', title: '服务器主板 · CPU 与 DIMM 装配',
    image: '/assets/technical-atlas/motherboard-v1.svg', preview: '/assets/technical-atlas/motherboard-v1-preview.svg',
    master: '/assets/technical-atlas/motherboard-v1.png',
    alt: '暖白单路服务器主板：中央 CPU 插槽与固定框、两组各四条 RDIMM、供电元件、PCIe 插槽及板边连接器；左上为内存模组局部放大。',
    note: '通用单路主板装配示意；两组四条 RDIMM 为图示示例，左上为同类模组放大。布局、插槽及兼容性以选定型号为准，不代表 MRDIMM 配置。',
    labels: ['CPU 与固定框：展示主板上的插槽装配位置', 'RDIMM 与插槽：两组已安装模组，左上仅为同类模组局部放大', '内存芯片与金手指：展示模组器件及连接边，不指定容量、速度或代际', '供电元件与连接器：展示板级供电部件类别', 'PCIe 扩展插槽与后部 I/O：展示扩展及外部连接位置', '共用装配图：CPU 与服务器内存入口查看同一主板关系，不新增骨架对象；精确走线与机械结构未知'],
  },
  hbm: {
    id: 'TA-05', title: 'GPU 与 HBM · 封装层次',
    image: '/assets/technical-atlas/hbm-package-v1.svg', preview: '/assets/technical-atlas/hbm-package-v1-preview.svg',
    master: '/assets/technical-atlas/hbm-package-v1.png',
    alt: '暖白 GPU 与 HBM 封装图：逻辑裸片与四个 HBM 堆栈并排在硅中介层上，下面是分离封装基板和焊球，左侧剖开堆栈显示 DRAM 层与硅内 TSV。',
    note: '通用硅中介层封装示意；四堆栈、DRAM 层数、TSV 和连接数量仅为图示，布局、比例与代际以选定型号资料为准。',
    labels: ['GPU 逻辑裸片与 HBM：在中介层上并排放置', 'HBM 堆栈：垂直叠放的 DRAM 层', 'TSV：剖口显示硅内垂直连接，数量与粗细经示意放大', '堆栈底层：展示层叠接口关系，不指定代际内部设计', '硅中介层：此图为硅中介层方案示意，不概括所有 CoWoS 方案', '封装基板与底部焊球：展示封装层次，与整块 GPU 基板模组另图区分'],
  },
  gpu: {
    id: 'TA-04', title: 'GPU 加速基板 · 模组装配',
    image: '/assets/technical-atlas/gpu-board-v1.svg', preview: '/assets/technical-atlas/gpu-board-v1-preview.svg',
    master: '/assets/technical-atlas/gpu-board-v1.png',
    alt: '暖白多 GPU 基板装配图：已安装模组、分离模组与金属接触盖、对应空插槽、互联芯片、供电元件和板边连接器。',
    note: '通用多 GPU 模组与基板装配示意；布局、连接端与散热接触结构以选定型号资料为准。',
    labels: ['GPU 模组：独立电路板承载 GPU 封装与供电元件', '接触盖：展示模组上方金属件的分离关系', '模组插槽：对应被抬起的单个模组', '已安装模组：展示基板上的装配位置', '互联芯片：展示多 GPU 基板上的互联部件类别', '供电元件与板边连接器：展示基板的元件与连接位置'],
  },
  server: {
    id: 'TA-11', title: '加速器服务器 · 整机剖视与安装位置',
    image: '/assets/technical-atlas/server-v1.svg', preview: '/assets/technical-atlas/server-v1-preview.svg',
    master: '/assets/technical-atlas/server-v1.png',
    alt: '暖白风冷加速器服务器整机：前置存储载盘与风扇行、双加速卡和 riser 支承、后区 CPU 与 DIMM 主板、后置电源与内部配电接口；右上为同类加速卡与插槽放大。',
    note: '通用风冷 PCIe 加速器服务器虚拟剖视；双 CPU、八 DIMM、两加速卡、四风扇、八载盘和双电源仅为示例。右上同类插接放大非新增卡，虚拟剖开非拆修步骤；型号、尺寸、走线、性能及兼容性以产品资料为准。',
    labels: ['机箱与安装位置：按前置存储、风扇行、中部加速卡和后部主板/电源解释通用分区', 'CPU 散热器与 DIMM：在主板上各有对应安装和插槽位置，数量仅为示意', 'PCIe 加速卡与 riser：卡边接点对应插槽，卡笼和固定结构承载；右上是同类插接放大', '后置电源：外部交流输入朝后侧，内部配电接口与内部线束分开，不指定针脚或额定值', '后部 I/O：外部开口朝机箱后壁，当前内视角看见金属背壳', '前置载盘与风扇：8 载盘和 4 风扇不表示真实产品数量、气流或热插拔', '通用示意：虚拟剖开与交互拆解帮助理解位置，不替代具体型号的安全维护流程'],
    related: [{id: 'TA-03', title: '机箱子装配 · TA-03', image: '/assets/technical-atlas/chassis-v1.svg'}, {id: 'TA-12', title: '正交平面 · TA-12', image: '/server-plan.html'}],
  },
  'rack-frame': {
    id: 'TA-39', title: '机柜与结构 · 柜架、柜门和侧板',
    image: '/assets/technical-atlas/rack-frame-v1.svg', preview: '/assets/technical-atlas/rack-frame-v1-preview.svg',
    master: '/assets/technical-atlas/rack-frame-v1.png',
    alt: '暖白机柜结构爆炸图：空柜架与安装导轨、分离网孔柜门、侧板、顶盖及底部脚轮支脚。',
    note: '通用机柜类别结构示意；具体尺寸、孔位、承载能力与装配以选定型号资料为准。',
    labels: ['柜架：立柱与横梁构成支撑结构', '安装导轨：展示设备安装位置', '网孔柜门：展示门板与柜架关系', '侧板和顶盖：对应柜体侧面与顶部', '脚轮：移动支撑示意', '调平支脚：落地支撑示意'],
  },
  security: {
    id: 'TA-38', title: '安防 · 周界、门禁与视频监控',
    image: '/assets/technical-atlas/security-v1.svg', preview: '/assets/technical-atlas/security-v1-preview.svg',
    master: '/assets/technical-atlas/security-v1.png',
    alt: '暖白设施安防剖面：围栏、车辆道闸、摄像机、人员门禁、值守监控室与机房入口。',
    note: '通用物理安防层次示意；设备数量、位置与覆盖范围以项目方案为准。',
    labels: ['周界围栏：解释场地边界', '车辆道闸：展示车辆出入口', '视频监控设备：展示室外和室内观察位置', '人员入口门禁：展示身份查验入口', '监控值守位置：展示视频管理场景', '机房入口门禁：展示内部区域的访问控制'],
  },
  fire: {
    id: 'TA-37', title: '消防 · 探测与灭火设备',
    image: '/assets/technical-atlas/fire-v1.svg', preview: '/assets/technical-atlas/fire-v1-preview.svg',
    master: '/assets/technical-atlas/fire-v1.png',
    alt: '机房消防剖面：烟雾采样与探测器、火灾报警控制器、气体灭火瓶组和独立辅助区喷淋。',
    note: '通用消防设备与分区示意；图示管网分别独立，实际选型、覆盖和联动按项目设计确定。',
    labels: ['抽气式采样管与探测器：从保护区域采集空气用于烟雾探测', '火灾报警控制器：展示报警管理设备位置', '声光报警装置：用于现场报警提示', '气体灭火瓶组：展示储存与输送设施', '气体输送管与喷嘴：与探测采样及喷淋管路分开', '喷淋管与喷头：辅助区域示意，配置不作为现场设计要求'],
  },
  shell: {
    id: 'TA-36', title: '土地与建筑 · 建筑剖面',
    image: '/assets/technical-atlas/shell-v1.svg', preview: '/assets/technical-atlas/shell-v1-preview.svg',
    master: '/assets/technical-atlas/shell-v1.png',
    alt: '暖白建筑剖面：屋面揭开、承重结构、机房空间、楼板、基础与地基及场坪道路。',
    note: '通用建筑剖面示意；布局与数量不代表具体项目，尺寸、基础设计和施工要求以项目资料为准。',
    labels: ['场坪与道路：展示建筑所在场地及通行空间', '基础与地基：剖开显示建筑支撑关系', '承重结构：柱、梁与屋面支撑示意', '屋面与外墙：展示围护及局部揭开关系', '室内地坪与楼板：承载内部空间', '机房空间：机柜布局仅作场景解释'],
  },
  ssd: {
    id: 'TA-01',
    title: 'SSD 结构拆解',
    image: '/assets/technical-atlas/ssd-v1.svg',
    preview: '/assets/technical-atlas/ssd-v1-preview.svg',
    master: '/assets/technical-atlas/ssd-v1.png',
    note: '通用有壳 SSD 结构示意；芯片数量、布局与接口外形不代表某个厂商型号。',
    labels: [
      'NAND 闪存：存放数据',
      '控制器：管理数据读写',
      '上盖与紧固件：对应底壳装配位置',
      '导热接触层：示意位置随设计而异',
      '电路板：承载芯片与电子元件',
      '底壳与连接端：提供支撑和连接位置',
    ],
  },
};

const serverPlan = {
  id: 'TA-12', title: '服务器正交平面图 · 同一通用整机布局',
  image: '/assets/technical-atlas/server-plan-v1.svg', preview: '/assets/technical-atlas/server-plan-v1-preview.svg',
  master: '/assets/technical-atlas/server-plan-v1.png',
  alt: '正交俯视的服务器布局示意：前置载盘在下，四风扇框架居前中，两个加速卡示例顶罩居中，双CPU散热器与八DIMM位于后部主板，右后是双电源，左后是I/O背壳。',
  note: '同一通用服务器布局的正交俯视示意，前在下、后在上；省略顶盖。双CPU、八DIMM、两加速卡、四风扇、八载盘、双电源及一网卡仅为示例。上层四盘可见、下层四盘遮挡；加速卡区显示程序几何的示例顶罩。非CAD、非实际尺寸图，不能据此施工或拆修。',
  labels: ['前后方向：前置存储在图下，外部I/O与交流输入朝后壁；俯视看到背壳与顶部框架，不虚构外部开口', '主板区：双CPU散热器与两组共八条DIMM的位置来自同一通用几何，不是原厂精确板图', '加速卡区：两个示例顶罩保持原安装位置；TA-11虚拟剖视母图露出的鳍片与当前几何罩体有表现差异', '风扇区：四模组顶部框架可见，竖直叶轮正面在俯视中被遮挡，不表示气流方向', '存储区：四列上下两层共八载盘，当前只见上层四盘，存储背板位于载盘后方', '电源区：后侧外部交流接口与内侧配电接口分开，未知引脚、额定值和更换条件不补造', '图示边界：真实尺寸、U高度、功率、容量、兼容性与维护要求按具体型号资料核对'],
  related: [{id: 'TA-11', title: '整机剖视与部件档案 · TA-11', image: '/bom.html#server'}, {id: 'TA-11-3D', title: '旋转、拾取与装配交互', image: '/rack3d.html?view=server&x=55&node=part:server'}],
};

const campusPlan={
 id:'TA-20',title:'园区与机房正交平面图 · 同一八柜示例布局',
 image:'/assets/technical-atlas/campus-plan-v1.svg',preview:'/assets/technical-atlas/campus-plan-v1-preview.svg',master:'/assets/technical-atlas/campus-plan-v1.png',
 alt:'严格正交俯视的通用园区：机房内两行各四个机柜顶面、五室内冷却、三CDU和一组UPS；室外三双风扇冷机、两变压器、三备用发电和两储能柜，浅灰虚线投影已有上方桥架。',
 note:'同一通用布局严格正上方示意，所有设备保持原位；屋面、上部钢架和实体桥架虚拟省略。10柱脚轮廓和4上方桥架矩形只是投影，灰虚线不表示完整电缆/水路。UPS只见顶面，不展示正面柜门或柜内配置；设备数量、朝向与比例是画法选择。无北向、比例尺或真实尺寸，非OEM/CAD、施工或维护图。',
 labels:['机柜区：2行×4柜保留原位置与朝向，只见闭合顶面，不虚构柜内盘面或冷热通道规则',
 '室内冷却：5个顶部风管短节和3CDU局部接口来自同一源几何，未连接成完整供回液路',
 'UPS分区：一组UPS顶面与保留分隔墙可见；四个正面柜门属于TA18侧视示例，不在俯视中冒称可见',
 '室外机电：3双风扇冷机、2变压器、3备用发电与2储能柜为示例外形和数量，未知型号及额定值不补造',
 '投影说明：10柱脚轮廓与4桥架矩形是同源位置的非物理线，桥架不代表完整电力、网络或流体连接',
 '围护与地坪：保留墙顶轮廓和UPS分隔墙；基础轮廓不是地块边界，图上方向不是地理北向',
 '交互入口：原园区装配和分层仍可旋转、逐实例点选与导出；本页静态图可放大、下载标注SVG与无字原生PNG'],
 related:[{id:'TA-18',title:'园区旋转与设备拾取 · TA-18',image:'/bom3d.html'},{id:'TA-19',title:'园区分层交互 · TA-19',image:'/bom3d.html?x=70'}],
};

const facilityDomain={
 id:'TA-21',title:'设施与站点权利 · 同一八柜空间示例',
 image:'/assets/technical-atlas/facility-domain-v1.svg',preview:'/assets/technical-atlas/facility-domain-v1-preview.svg',master:'/assets/technical-atlas/facility-domain-v1.png',
 alt:'八个闭合机柜位于同源建筑梁柱、保留屋面和基础内；右侧消防、安防为独立类别图，本八柜场景未建模；底部六类站点权利为非物理文字入口。',
 note:'同源建筑四实例组与八柜保持原位置；其他机电只在本母图隐藏。消防与安防采用独立已验类别图，不共用比例、不是本布局局部放大，也不证明安装、覆盖或合规。土地、取用水、电网、燃料、通信和许可是六类非物理证据入口，地面与设备不证明权利成立。微模块是交付模板，DCIM归控制软件；比例、数量与现场适用未知，非OEM/CAD或施工图。',
 labels:['建筑与机柜：保留屋面、围护、梁柱、基础和八柜来自同一组实际程序几何；空间包含不是能量流',
 '消防与安防：八柜三维场景未造实体，独立类别图与研究入口保留，未认证位置、覆盖或合规',
 '六站点入口：site:land、site:water-rights、site:grid、site:gas-supply、site:network-access、site:permits；权属/配额/许可均需证据',
 '非物理边界：modular-dc为配置交付模板，dcim为控制软件，不造额外设备或以建筑轮廓代替权利',
 '研究关系：系统与链路是研究提纲，公司与产品属于类别；无现场证据不补供应者、权利人或有向连接',
 '实际交互：设施领域保留旋转、逐实例拾取、类别档案、显式适配和当前视角导出；六权利独立档案无三维物理件'],
 related:[{id:'TA-21-3D',title:'设施领域旋转与独立档案',image:'/bom3d.html?d=facility'},{id:'TA-37',title:'消防独立类别图',image:'/bom.html#fire'},{id:'TA-38',title:'安防独立类别图',image:'/bom.html#security'},{id:'TA-20',title:'同一园区严格俯视',image:'/campus-plan.html'}],
};

const powerDomain={
 id:'TA-22',title:'电力链路 · 选定功能与替代末端',
 image:'/assets/technical-atlas/power-domain-v1.svg',preview:'/assets/technical-atlas/power-domain-v1-preview.svg',master:'/assets/technical-atlas/power-domain-v1.png',
 alt:'暖白电力领域图：交流接入、变压、双变换UPS、分配、服务器PSU与板级稳压；UPS电池与静态旁路独立支路，共享电源架为另一方案。',
 note:'通用功能示例A采用服务器独立AC–DC PSU；共享电源架与BBU是另一种末端方案B，不再串第二套服务器AC–DC。UPS电池、条件旁路与正常转换各有角色；BESS、备用发电和其它发电候选不强制串/并联。七幅外形图不共实物比例，也不认证内部电路或端口。园区三维仅4电力类别8外形实例，其余15类别明确未建模；功能图不是场景实际接线。电压、功率、保护、接地、冗余、现场权利与适用均未知，非OEM/CAD/施工单线图。',
 labels:['01–02 接入与变压：GIS外形不证明电网接入权利，输入分配/保护按设计；其它负载支路未展开',
 '03 UPS：本图选双变换功能；正常整流→逆变，电池向DC节点供能，静态旁路绕过转换链。充电管理、切换和隔离未展开，不能作为操作步骤',
 '04 分配：机房/行PDU与机柜rPDU分层；中低压柜、母线槽按方案选，类别次序不是电路',
 '05–06 服务器PSU输出进入DC分配、按需中间转换和板级VRM；不从外观推定额定值或实际接线',
 '替代方案B：共享AC–DC电源架、DC分配及BBU备份；UPS是否保留和BBU控制按具体方案，不硬串第二套AC–DC',
 '候选与未知：燃料储运仅属燃料支路，BESS/UPS电池/BBU不互换；其它发电技术是候选，不证明可用安装或现场并存'],
 related:[{id:'TA-22-3D',title:'电力领域 · 4类外形与15未建模入口',image:'/bom3d.html?d=power'},{id:'TA-16',title:'19类独立部件图',image:'/bom.html#system-power'},{id:'TA-18',title:'园区通用外形全景',image:'/bom3d.html'}],
};

const thermalDomain={
 id:'TA-23',title:'冷却链路 · 两个流体域与热传递',
 image:'/assets/technical-atlas/thermal-domain-v1.svg',preview:'/assets/technical-atlas/thermal-domain-v1-preview.svg',master:'/assets/technical-atlas/thermal-domain-v1.png',
 alt:'暖白冷却领域图：冷板虚拟剖口及同类快接放大、歧管、封闭CDU、设施管路和风冷冷水机；蓝TCS与绿FWS各自供回，棕色热箭头跨隔离换热壁。',
 note:'选定冷板液冷+液—液CDU+风冷冷水机功能示例。TCS与FWS各自循环，换热器只传热、不混液；功能节点不认证上方照片内部或端口分工。冷板虚拟剖口/快接同类放大沿用TA10原件，五图不共实物比例。其它冷源、液—气CDU、浸没和后门换热器另列，非全部串接。三维仅3类别11外形实例，其余12未建模，不证明八柜实际接管。温压/流量/流体兼容、泵阀/制冷剂内部、冗余、现场与水权未知，非OEM/CAD/施工管线图；残余空气冷却占比未知。',
 labels:['01–02 冷板虚拟剖口解释液路，热源接触面在下方；右下为同类快接重复放大，非额外回路或维修步骤',
 '03 歧管：单根八支路外形只是示例；下方供回功能节点不认证照片具体端口分工或连接数量',
 '04 CDU：本例为液—液；TCS和FWS由换热器隔开，热量跨壁，液体分别循环，内部泵阀/控制未展开',
 '05–06 设施供回与风冷冷水机：所选冷源向室外空气排热；制冷剂和泵阀回路未展开，不硬加冷却塔或冷凝水回路',
 '颜色与箭头：蓝TCS/绿FWS是各自液体循环，棕色只示热流；细蓝引线是设备定位，不是管道',
 '方案边界：干冷器、液—气CDU、浸没、后门换热器是其它方案；水处理、冷却液和泄漏检测按系统核，不把空气负荷或全部热量入水比例补成事实'],
 related:[{id:'TA-23-3D',title:'冷却领域 · 3类外形与12未建模入口',image:'/bom3d.html?d=thermal'},{id:'TA-16',title:'15类独立部件图',image:'/bom.html#system-thermal'},{id:'TA-10',title:'冷板与同类快接详细图',image:'/bom.html#coldplate'},{id:'TA-22',title:'电力功能路径',image:'/power-atlas.html'}],
};

const computeDomain={
 id:'TA-24',title:'IT计算 · 整合范围与计算/管理角色',
 image:'/assets/technical-atlas/compute-domain-v1.svg',preview:'/assets/technical-atlas/compute-domain-v1-preview.svg',master:'/assets/technical-atlas/compute-domain-v1.png',
 alt:'暖白计算领域图：上层整柜、加速器服务器、封闭通用CPU节点；下层主板CPU装配、GPU基板、可选AI ASIC和FPGA封装、独立BMC管理芯片。',
 note:'通用分类与功能角色示意，八图不共比例，不证明同一系统安装。CPU本身计算；GPU/AI ASIC/FPGA按任务和系统设计选择，不强制三者并装或串联。BMC是物理管理控制器，不是主机CPU或AI加速器。主板和GPU基板沿用独立装配图，封闭芯片不推导内部版图。园区仅facility rack-frame八柜，计算八类均未建模；独立服务器与整柜三维示例不证明已安装。型号、配置、协议/引脚、性能、功耗、兼容性及现场拓扑未知，非OEM/CAD。',
 labels:['01 整柜系统：整合范围示例，2交换/8托盘/2电源架沿TA13画法，不是NVL72或本园区配置',
 '02–03 服务器：加速器整机沿TA11双CPU/双加速卡示例，右上同类卡/插槽是重复局部；另一通用CPU节点只展示封闭外形，内部配置未知',
 '04 CPU：沿TA06完整主板装配，包含DIMM同类局部；CPU可执行通用计算与控制，不改称独立裸片',
 '05–07 可选加速：GPU基板沿TA04多模组示例；AI ASIC与FPGA闭合封装是不同类别，不靠外形认证内部或强制共同安装',
 '08 BMC：独立管理角色的物理芯片；固件、针脚和管理链路按具体实现核，不塞入AI执行流水线',
 '领域与独立示例：八类均本场景未建模，类别档案保留；TA11服务器、TA13整柜及TA15封装是独立通用三维示例，不证明共同配置'],
 related:[{id:'TA-24-3D',title:'计算领域 · 八类未建模档案',image:'/bom3d.html?d=compute'},{id:'TA-11',title:'独立服务器装配三维',image:'/rack3d.html?view=server&x=55&node=part:server'},{id:'TA-13',title:'独立整柜结构三维',image:'/rack3d.html?view=rack&x=0&node=part:rack-frame'},{id:'TA-15',title:'独立四HBM封装示例',image:'/rack3d.html?view=chip&x=90&node=part:gpu'}],
};

const memoryDomain={
 "id": "TA-25",
 "title": "IT内存 · 三种实现与访问关系",
 "image": "/assets/technical-atlas/memory-domain-v1.svg",
 "preview": "/assets/technical-atlas/memory-domain-v1-preview.svg",
 "master": "/assets/technical-atlas/memory-domain-v1.png",
 "alt": "暖白内存领域图：同封装四HBM与同类剖层重复，完整主板CPU与RDIMM，封闭CXL扩展模组；三种访问关系独立。",
 "note": "通用内存功能示意，三图不共比例。HBM是堆叠DRAM，服务器dram类别专指RDIMM/MRDIMM模组，CXL是内存接入与扩展方式，不是三级串联。四HBM、层数与TSV沿TA05画法；主板只示RDIMM，CPU属于计算上下文，不新增内存类。封闭模组外形不认证CXL协议、介质或控制器。园区三类均未建模，独立封装/主板与三维示例不证明八柜安装。型号、容量、通道、代际、性能、兼容平台和现场配置未知，非OEM/CAD。",
 "labels": [
  "01 HBM：同一封装内逻辑裸片旁的四堆栈沿TA05示例；堆栈本身是DRAM，不是服务器DIMM之后一级",
  "02 同类剖开重复放大：层叠DRAM与TSV只为结构解释，不增加第五组、不给层数/代际规格",
  "03 服务器模组：沿TA06完整主板与同类RDIMM局部；这里只示RDIMM，不据外形认证MRDIMM或八条真实配置",
  "04 CPU上下文：锚点属于compute的cpu，源图取主板装配，非新增内存ID或已核控制器电路",
  "05 CXL扩展：封闭E3.S式模组外形只示壳体/触点；支持CXL主机与扩展设备的功能关系不认证照片协议或内部介质",
  "三种关系：逻辑↔HBM、CPU内存控制器↔RDIMM、支持CXL主机↔扩展设备分别表达，不能HBM→DIMM→CXL串联；园区三类均未建模"
 ],
 "related": [
  {
   "id": "TA-25-3D",
   "title": "内存领域 · 三类未建模档案",
   "image": "/bom3d.html?d=memory"
  },
  {
   "id": "TA-15",
   "title": "独立四HBM封装三维",
   "image": "/rack3d.html?view=chip&x=90&node=part:hbm"
  },
  {
   "id": "TA-06",
   "title": "CPU与RDIMM装配原图",
   "image": "/bom.html#dram"
  },
  {
   "id": "TA-24",
   "title": "计算与管理角色",
   "image": "/compute-atlas.html"
  }
 ]
};

const storageDomain={
 "id": "TA-26",
 "title": "IT存储 · 系统与整盘、本地或网络访问",
 "image": "/assets/technical-atlas/storage-domain-v1.svg",
 "preview": "/assets/technical-atlas/storage-domain-v1-preview.svg",
 "master": "/assets/technical-atlas/storage-domain-v1.png",
 "alt": "暖白存储领域图：八前托架机架盒、SSD虚拟分层及同类芯片局部、虚拟开盖HDD；本地和网络访问分别表达。",
 "note": "通用功能示意，非OEM/CAD，三图不共比例。系统类别也含软件与服务，机架盒只代表一种实体外形；八个前托架不证明已装盘、内部控制器或RAID。SSD同类芯片重复不增加整盘，HDD只画可见盘片、不认证内部总数，虚拟剖开不是维护步骤。本地/网络是访问选项，SSD/HDD是介质选项，不把目录顺序当数据路径。接口协议、容量、寿命、性能、数据保护、兼容性和现场配置未知。园区三类均未建模，八设施柜不证明存储已安装。",
 "labels": [
  "01 存储系统：封闭机架盒为选定外形，八外托架不证明介质已装、内部控制器或RAID；类别亦含软件/服务",
  "02 企业SSD：沿TA01虚拟分层，上盖、PCB和底壳保留；连接器外形不认证NVMe/SATA/SAS",
  "03 同类芯片重复局部：沿原图上下两个芯片解释，不新增整盘或物理ID",
  "04 近线HDD：虚拟开盖锚点在整盘可见主轴面，盘片/磁头内部总数未知，不作维修步骤",
  "05 盘片与磁头臂：引线指向真实可见臂结构，只取结构关系，不认证型号/转速/性能",
  "本地直连SSD/HDD与主机经网络访问系统分别表达，系统按设计选用介质，不能强制串联；园区三类均未建模"
 ],
 "related": [
  {
   "id": "TA-26-3D",
   "title": "存储领域 · 三类未建模档案",
   "image": "/bom3d.html?d=storage"
  },
  {
   "id": "TA-01",
   "title": "独立SSD结构详图",
   "image": "/bom.html#ssd"
  },
  {
   "id": "TA-16-HDD",
   "title": "HDD独立类别图",
   "image": "/bom.html#hdd"
  },
  {
   "id": "TA-25",
   "title": "内存访问关系",
   "image": "/memory-atlas.html"
  }
 ]
};

const networkDomain={
 "id": "TA-27",
 "title": "IT网络 · 机外互联、配接与PCIe接入角色",
 "image": "/assets/technical-atlas/network-domain-v1.svg",
 "preview": "/assets/technical-atlas/network-domain-v1-preview.svg",
 "master": "/assets/technical-atlas/network-domain-v1.png",
 "alt": "暖白网络领域九类别图：双口NIC、可插拔光模块、八口交换机、铜互联、交换ASIC、四护套机内线束、配接连接器、Retimer和PCIe交换封装；按角色区分，非九级串联。",
 "note": "通用功能示意，非OEM/CAD，各图不共比例。八前口、NIC双主口与同类重复局部、四外护套沿已验图例，不认证规格。光/铜是匹配链路方案，交换ASIC为设备内部角色，不是外部一跳。Retimer与PCIe交换分别做信号调理/接入分支，不能按目录拼九级路径；PCIe也非绝对限于机箱内。可插拔光模块不是CPO，CPO仅关联集成方案无新增实体。园区已有cabling架空桥架1实例，其余八类未建模；桥架不等于四护套线束，不认证介质或网络已安装。协议、速率、端口、针脚、lane、内部电路、兼容性和现场配置未知。",
 "labels": [
  "01 NIC主机接入：原TA07一张板卡/两个主端口与一个同类端口重复，不认证全部DPU或每GPU配比",
  "02 可插拔光模块：电光接入的选定外形，非CPO布局；协议与互配另核",
  "03 网络交换整机：八前口为图例，封闭箱体不认证以太网/InfiniBand、速率或内部ASIC",
  "04 铜互联：两端一缆外形不判断有源/无源，光与铜方案不强制串接",
  "05 交换ASIC：内部功能类别，封装不展示内部阵列，也不是新增外部网络一跳",
  "06 机内线束：四外护套与两端外形，不认证光纤、通道或针脚；现有园区桥架是另一示例",
  "07 连接器：配接外形与锁扣，不能据图确认其它器件互配标准或电气定义",
  "08 Retimer：按通道设计选择的时钟/数据恢复功能，不等于分组路由，外形不认证代际",
  "09 PCIe交换：主机/I/O接入分支功能，外形不认证PCIe/CXL或现场拓扑；园区仅1组cabling桥架，其余八类未建模"
 ],
 "related": [
  {
   "id": "TA-27-3D",
   "title": "网络领域 · 一组桥架与八类未建模档案",
   "image": "/bom3d.html?d=network"
  },
  {
   "id": "TA-07",
   "title": "独立NIC结构详图",
   "image": "/bom.html#nic"
  },
  {
   "id": "TA-16-CABLING",
   "title": "线束类别图",
   "image": "/bom.html#cabling"
  },
  {
   "id": "TA-26",
   "title": "本地与网络存储访问",
   "image": "/storage-atlas.html"
  }
 ]
};

const rackOverview = {
  id:'TA-13', title:'机柜整柜 · 安装分区与结构',
  image:'/assets/technical-atlas/rack-overview-v1.svg', preview:'/assets/technical-atlas/rack-overview-v1-preview.svg',
  master:'/assets/technical-atlas/rack-overview-v1.png',
  alt:'暖白整柜虚拟剖视：前门和左侧柜壳省略，外框柱、独立安装立柱和支撑、顶部两交换机、中部八托盘每台八载盘、底部两电源架各六模块。左侧可选铜色长条与竖管未接线。',
  note:'通用整柜示意；2交换机、8托盘×8载盘、2电源架×6模块为图示选择，非通用标配、OEM型号或额定配置。前门/左侧为虚拟剖口，非维修步骤。侧部铜排和管道只作可选附件，接线与回路未知；比例、U高度、承载、功率和冷却性能未知。',
  labels:['框架与安装：外框柱、内安装立柱、横向支撑和设备导轨各有位置，深部精密连接不由静态图证明',
    '设备分区：底部电源架、中部计算托盘和顶部交换机仅为本图配置示例，设备保持安装位置',
    '前脸细节：载盘、模块、端口与把手用于区分类别；孔距、端口协议、可维护性与热插拔不作推定',
    '服务槽：铜色长条和灰色竖管是未接线的可选附件，不证明完整电连接或流体回路，不连接风冷服务器',
    '柜壳与支撑：右侧板、顶板、底框和调平脚保持整柜关系，前门/左侧虚拟剖开不表示安装操作',
    '交互对应：整柜可旋转点选及分区观察；程序几何保持同一分区/数量，端口细节为独立通用表达，不是原厂数字孪生'],
  related:[{id:'TA-39',title:'柜架类别结构 · TA-39',image:'/assets/technical-atlas/rack-frame-v1.svg'},
    {id:'TA-11',title:'独立服务器 · TA-11',image:'/rack3d.html?view=server&x=55&node=part:server'}],
};

const rackExploded={
  id:'TA-14',title:'机柜分层 · 虚拟装配对应',
  image:'/assets/technical-atlas/rack-exploded-v1.svg',preview:'/assets/technical-atlas/rack-exploded-v1-preview.svg',master:'/assets/technical-atlas/rack-exploded-v1.png',
  alt:'同一通用机柜的分层对应：网孔门向前、左侧板向侧、顶盖向上，三个代表设备沿共同前轴平移，各有空位。总计2交换机、8计算托盘各8载盘、2电源架各6模块；局部放大重复现有盘位、模块和导轨。',
  note:'独立原生1536×1024程序几何母图。门、侧板和顶盖为虚拟拆出壳件；每类只抽一个代表设备，对应空位保留。2交换机、8托盘各8载盘、2电源架各6模块仅为示例；三个局部放大重复现有对象。比例、U高度、承载、电压、功率、协议和连接未知；平移关系非安装、拆修或热插拔程序。',
  labels:['共同前轴：代表交换机、计算托盘和电源架保持原朝向，沿同一前轴平移；其余实例保持安装位置',
    '柜壳对应：门沿前轴、左侧板沿侧轴、顶盖沿竖轴；此处虚拟补画TA13省略的门和侧板',
    '计算前脸：每个示例托盘8载盘，左上是同一代表托盘的正面放大，不新增托盘',
    '电源前脸：每个示例电源架6模块，左侧是同一代表电源架的正面放大，不指定电气方案',
    '导轨对应：外轨和前后支承固定在柜架，内轨随机箱；右侧放大显示同一计算位安装位置的单侧轨道，省略外壳便于观察',
    '未知边界：服务槽铜色长条与灰管未连接，研究链接属于类别；图中平移不能作为维护、热插拔或载荷依据'],
  related:[{id:'TA-13',title:'同一整柜安装分区 · TA-13',image:'/rack-atlas.html'},{id:'TA-14-3D',title:'分层旋转、拾取与装配对应',image:'/rack3d.html?x=35&node=part:rack-frame'}],
};

const chipPackage={
 id:'TA-15',title:'芯片封装 · 独立近景与虚拟分层',
 image:'/assets/technical-atlas/chip-package-v1.svg',preview:'/assets/technical-atlas/chip-package-v1-preview.svg',master:'/assets/technical-atlas/chip-package-v1.png',
 alt:'暖白一逻辑裸片和四组HBM沿共同竖轴展开，对应硅中介层接触面、封装基板和底部焊球；左侧三张原生局部重复同一HBM的剖口、接触点与同一基板底面。',
 note:'独立原生1536×1024程序几何母图，与交互近景使用同一组位置。一个逻辑裸片、四组HBM、八层DRAM与TSV/微凸点/焊球数量为图示选择；左侧三处局部重复现有对象，不增加器件。此图只解释通用硅中介层封装，非OEM/CAD、特定逻辑版图、制造或拆修步骤；工艺、尺寸、容量、带宽、功率和供应者未知。',
 labels:['逻辑裸片与四组HBM：并排结合在同一硅中介层，五个顶部器件沿同一竖轴虚拟分开，接触面保持对应',
 'HBM层次与TSV：八DRAM层和六铜柱为放大示意，剖口暴露硅内垂直连接，不是外置金属引脚',
 '微凸点：左中是同一HBM的侧面原生放大，显示底部接触点，不增加一组HBM',
 '中介层：对应接触pad和刻蚀路径仅解释连接层，不作为已核实布线、pitch或所有CoWoS方案',
 '封装基板与BGA：左下重复同一基板的底部视角，层数、焊球数量和材料不构成产品规格',
 '实际交互：x90独立主对象可旋转、展开、逐实例点选和查看完整封装，用户手动镜头不因阶段或迟到加载被夺回'],
 related:[{id:'TA-15-3D',title:'封装旋转与分层对应',image:'/rack3d.html?x=90'},{id:'TA-05',title:'原HBM类别母图 · TA-05',image:'/bom.html#hbm'},{id:'TA-11',title:'服务器装配上下文 · TA-11',image:'/rack3d.html?x=55'}],
};

// Existing CPU and server-memory categories share this one assembly context figure.
illustrations.dram = illustrations.cpu;

export function atlasPreviewTitle(partId, {view} = {}) {
  return (['system','scale'].includes(view) ? systemIllustrations[partId] || illustrations[partId] : illustrations[partId])?.title || '';
}

export function atlasPreview(partId, {view} = {}) {
  const item = ['system','scale'].includes(view) ? systemIllustrations[partId] || illustrations[partId] : illustrations[partId];
  return item?.tile || item?.preview || null;
}

// Explicit system/scale artwork must not certify the category research description as a selected device.
export function atlasCategoryNote(partId, {view} = {}) {
  return ['system','scale'].includes(view) ? systemIllustrations[partId]?.note || '' : '';
}

export function mountTechnicalAtlas(parent, partId, {view} = {}) {
  const item = partId === 'facility-domain' && view === 'domain' ? facilityDomain : partId === 'power-domain' && view === 'domain' ? powerDomain : partId === 'thermal-domain' && view === 'domain' ? thermalDomain : partId === 'compute-domain' && view === 'domain' ? computeDomain : partId === 'network-domain' && view === 'domain' ? networkDomain : partId === 'storage-domain' && view === 'domain' ? storageDomain : partId === 'memory-domain' && view === 'domain' ? memoryDomain : ['system','scale'].includes(view) ? systemIllustrations[partId] || illustrations[partId] : view==='chip' && ['gpu','hbm'].includes(partId) ? chipPackage : partId === 'server' && view === 'plan' ? serverPlan : partId === 'campus-overview' && view === 'plan' ? campusPlan : partId === 'rack-frame' && view === 'exploded' ? rackExploded : partId === 'rack-frame' && view === 'overview' ? rackOverview : illustrations[partId];
  if (!item) return false;
  if (!document.querySelector('link[data-technical-atlas]')) {
    const stylesheet = document.createElement('link');
    stylesheet.rel = 'stylesheet'; stylesheet.href = '/assets/technical-atlas.css';
    stylesheet.dataset.technicalAtlas = ''; document.head.append(stylesheet);
  }
  const section = document.createElement('section');
  section.className = 'technical-atlas'; section.dataset.figure = item.id;
  const heading = document.createElement('h3'); heading.textContent = item.title;
  const figure = document.createElement('figure');
  const full = document.createElement('a'); full.href = item.image;
  full.target = '_blank'; full.rel = 'noopener';
  full.setAttribute('aria-label', `放大 ${item.title}图（新窗口）`);
  const image = document.createElement('img');
  image.src = item.preview; image.alt = item.alt || '暖白底 SSD 爆炸图：上盖、导热接触层、电路板和底壳，左侧放大 NAND 与控制器。';
  image.width = 1536; image.height = 1024; image.loading = 'lazy'; image.decoding = 'async';
  full.append(image); figure.append(full);
  const caption = document.createElement('figcaption'); caption.textContent = item.note;
  figure.append(caption);
  const detail = document.createElement('details');
  const summary = document.createElement('summary'); summary.textContent = '查看部件说明';
  const list = document.createElement('ul');
  for (const label of item.labels) { const li = document.createElement('li'); li.textContent = label; list.append(li); }
  detail.append(summary, list);
  const actions = document.createElement('div'); actions.className = 'technical-atlas-actions';
  for (const [name, url, download] of [
    ['放大查看', item.image, false],
    ['下载标注图', item.image, true],
    ['下载无字底图', item.master, true],
  ]) {
    const link = document.createElement('a'); link.textContent = name; link.href = url;
    if (download) link.download = url.split('/').at(-1);
    else { link.target = '_blank'; link.rel = 'noopener'; }
    actions.append(link);
  }
  for (const related of item.related || []) {
    const link = document.createElement('a'); link.textContent = related.title; link.href = related.image;
    link.dataset.relatedFigure = related.id; link.target = '_blank'; link.rel = 'noopener'; actions.append(link);
  }
  section.append(heading, figure, detail, actions); parent.append(section);
  return true;
}
