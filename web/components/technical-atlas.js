/* Adopted illustrations enrich the category dossier; the live 3D inspector stays interactive. */
const illustrations = {
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
    id: 'TA-03', title: '服务器机箱 · 盖板与壳体',
    image: '/assets/technical-atlas/chassis-v1.svg', preview: '/assets/technical-atlas/chassis-v1-preview.svg',
    master: '/assets/technical-atlas/chassis-v1.png',
    alt: '暖白服务器机箱子装配爆炸图：分离金属上盖、通风开孔、盖板锁扣、折边空壳、内部横梁和安装支柱。',
    note: '通用机箱子装配示意；孔位、紧固件与锁扣形式以选定型号资料为准。整机内部部件另图展示。',
    labels: ['上盖与紧固件：展示盖板和壳体的分离关系', '通风开孔与锁扣：展示盖板局部结构', '后部开孔：示意接口和扩展位置', '折边壳体、底板与横梁：展示机箱支撑结构', '安装支柱：示意板卡安装位置', '机架安装耳与把手：展示机箱前部结构'],
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

export function atlasPreviewTitle(partId) {
  return illustrations[partId]?.title || '';
}

export function atlasPreview(partId) {
  return illustrations[partId]?.preview || null;
}

export function mountTechnicalAtlas(parent, partId) {
  const item = illustrations[partId];
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
  section.append(heading, figure, detail, actions); parent.append(section);
  return true;
}
