/* One dossier owns its DOM; the scene supplies data and its inspector. */
import {latest, sparkline} from './series-summary.js';
import {mountNodeResearch, safeURL} from './research-graph.js';
import {mountTechnicalAtlas} from './technical-atlas.js?v=20261008.15';

export function dossierNode(tag, text, className) {
  const actual = document.createElement(tag);
  if (text !== undefined) actual.textContent = text;
  if (className) actual.className = className;
  return actual;
}
function dossierLink(text, href) {
  const a = dossierNode("a", text, "chip");
  const valid = safeURL(href);
  if (valid) a.href = valid;
  return a;
}
let targetSnapshot;
function mountTargetSummary(host, node) {
  const section = dossierNode('section', undefined, 'sec dossier-targets');
  section.append(dossierNode('h3', '采集需求 · 只读目标摘要'));
  const content = dossierNode('div', '正在读取目标表…', 'meta'); section.append(content); host.append(section);
  if (!targetSnapshot) targetSnapshot = fetch('/framework/tco_targets.json', {cache:'no-store'})
    .then(response => { if (!response.ok) throw Error('targets unavailable'); return response.json(); })
    .then(doc => { if (!Array.isArray(doc.targets)) throw Error('invalid targets'); return doc; })
    .catch(error => { targetSnapshot = undefined; throw error; });
  targetSnapshot.then(doc => {
    const rows = doc.targets.filter(row => row.request?.node === node ||
      (row.part_id && 'part:' + row.part_id === node) || (row.site_right_id && 'site:' + row.site_right_id === node));
    content.replaceChildren();
    if (!rows.length) content.append(dossierNode('p', '此节点尚无目标行；不能据此认定数据齐全。'));
    for (const row of rows) {
      const line = dossierNode('p'); line.dataset.targetId = row.id;
      line.append(dossierLink(row.id, '/supply.html?' + new URLSearchParams({node, col:row.variable_class}) + '#targets'));
      line.append(dossierNode('span', ' · ' + row.team + (row.team_state === 'connected' ? '（已接通）' : '（未接通）') +
        ' · ' + (doc.mechanisms?.[row.mechanism] || row.mechanism) + ' · ' + (doc.statuses?.[row.status] || row.status)));
      content.append(line);
    }
    content.append(dossierNode('p', '目标表 ' + doc.version + ' · ' + doc.updated + '；交付与正式采用分别验收。'));
  }).catch(() => { content.textContent = '目标表暂不可读取；请从采集页重试，缺失状态不计为零。'; });
}
export function createPartDossier({el, view, BOM, companies: CN,
  prices, indicators: INDS, statusNames: SN, statusColors: SBADGE, inspector, atlasHost = el, atlasViewFor = () => null, researchNodeFor = p => "part:" + p.id}) {
return function showDossier(p) {
  inspector.hide();
  el.replaceChildren();
  if (atlasHost !== el) atlasHost.replaceChildren();
  el.dataset.partId = p.id;
  const close = dossierNode("button", "✕", "close");
  close.type = "button"; close.setAttribute("aria-label", "关闭部件档案");
  close.addEventListener("click", () => { el.style.display = "none"; inspector.hide(); });
  el.append(close, dossierNode("h2", p.name));
  const sceneExport = document.getElementById('atlas-export');
  if (sceneExport) {
    const exportButton = dossierNode('button','导出当前图册','chip');
    exportButton.type = 'button'; exportButton.addEventListener('click',()=>sceneExport.click());
    el.append(exportButton);
  }
  const sys = BOM.systems?.[p.system]; const sysName = sys ? (sys.name || sys) : (p.system || "");
  const meta = dossierNode("div", [sysName, p.chain ? p.chain + " 第 " + p.chain_order + " 位" : "", p.scale ? [p.scale, BOM.scales.find(l => l.id === p.scale)?.name || ""].join(" ") : (BOM.kinds?.[p.kind] || p.kind || "")].filter(Boolean).join(" · "), "meta");
  const badge = dossierNode("span", "产业状态：" + (SN[p.status] || "未知"), "badge");
  badge.style.background = SBADGE[p.status] || "#64748b";
  meta.append(" · ", badge); el.append(meta);
  el.append(dossierNode("p", "概念示意 · 类别级研究锚点。形状、数量、尺寸不代表真实现场配置。", "rg-concept-note"));
  const research = document.createElement("div"); el.append(research);
  mountNodeResearch(research, researchNodeFor(p));
  const slot = dossierNode("div", undefined, "insp");
  slot.id = "inspSlot"; slot.style.display = "none";
  slot.append(dossierNode("div", "独立三维预览 · 拖动旋转；可放大与单独导出", "ihint")); el.append(slot);
  el.append(dossierNode("div", p.desc || "说明待补充"));
  const hasAtlas = mountTechnicalAtlas(atlasHost, p.id, {view:atlasViewFor(p)});
  if (atlasHost !== el) atlasHost.hidden = !hasAtlas;
  const links = dossierNode("div", undefined, "sec");
  links.append(dossierNode("h3", "参考研究与结构"));
  links.append(dossierLink("节点页：五列与目标", "node.html?id=" + encodeURIComponent(researchNodeFor(p))));
  links.append(dossierLink("采集：这个部件的目标行", "supply.html?" + new URLSearchParams({ node: researchNodeFor(p) }) + "#targets"));
  if (view !== "bom") links.append(dossierLink("爆炸图档案", "bom.html#" + encodeURIComponent(p.id)));
  if (view === "campus" && ["S4", "S5"].includes(p.scale))
    links.append(dossierLink("继续拆解机柜 →", "rack3d.html?x=100&node=" + encodeURIComponent(researchNodeFor(p)) + "#" + encodeURIComponent(p.id)));
  if (view === "rack")
    links.append(dossierLink("返回园区定位", "bom3d.html?" + new URLSearchParams({ p: p.id, node: "part:" + p.id })));
  el.append(links);
  mountTargetSummary(el, researchNodeFor(p));
  if (p.upstream?.length) {
    const upstream = dossierNode("div", undefined, "sec"); upstream.append(dossierNode("h3", "上游研究主题"));
    p.upstream.forEach(u => upstream.append(dossierNode("span", u, "chip"))); el.append(upstream);
  }
  if (p.companies?.length) {
    const companies = dossierNode("div", undefined, "sec"); companies.append(dossierNode("h3", "类别关联公司 · 不代表现场供应商"));
    p.companies.forEach(c => companies.append(dossierLink(CN[c] || c, "product-catalog.html?c=" + encodeURIComponent(c)))); el.append(companies);
  }
  const metrics = dossierNode("div", undefined, "sec"); metrics.append(dossierNode("h3", "类别数据与指标 · 按原记录时点"));
  let n = 0;
  (p.series || []).forEach(sid => {
    const sp = sparkline(prices, sid);
    if (sp) { const wrap = document.createElement("div"); wrap.innerHTML = sp; metrics.append(wrap); n++; return; }
    const r = latest(prices, sid); if (!r) return;
    const row = dossierNode("div", undefined, "kv");
    row.append(dossierNode("span", sid + (r.as_of ? " · " + r.as_of : "")), dossierNode("b", r.value == null ? "未知" : String(r.value) + " " + (r.unit || "")));
    metrics.append(row); n++;
  });
  (p.indicators || []).forEach(iid => {
    const i = INDS[iid]; if (!i) return;
    const row = dossierNode("div", undefined, "kv");
    row.append(dossierNode("span", i.name + (i.as_of ? " · " + i.as_of : "")), dossierNode("b", i.value == null ? "未披露 / 待核实" : String(i.value) + " " + (i.unit || "")));
    metrics.append(row); n++;
  });
  if (!n) metrics.append(dossierNode("div", "当前没有量化数据。非数字陈述与未知见节点研究。", "meta"));
  el.append(metrics);
  if (inspector.show(p.id)) { slot.style.display = "block"; slot.insertBefore(inspector.canvas, slot.firstChild); if (inspector.controls) slot.append(inspector.controls); }
  el.style.display = "block";
}

}
