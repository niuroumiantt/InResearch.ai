/* Adopted illustrations enrich the category dossier; the live 3D inspector stays interactive. */
const illustrations = {
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
