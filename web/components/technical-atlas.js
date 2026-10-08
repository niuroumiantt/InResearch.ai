/* Adopted illustrations enrich the category dossier; the live 3D inspector stays interactive. */
const illustrations = {
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
  full.setAttribute('aria-label', '放大 SSD 结构拆解图（新窗口）');
  const image = document.createElement('img');
  image.src = item.preview; image.alt = '暖白底 SSD 爆炸图：上盖、导热接触层、电路板和底壳，左侧放大 NAND 与控制器。';
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
