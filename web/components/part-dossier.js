/* One dossier owns its DOM; the scene supplies data and its inspector. */
import {latest, sparkline} from './series-summary.js';
import {mountNodeResearch, safeURL} from './research-graph.js';

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
export function createPartDossier({el, view, BOM, moduleNames: MODNAME, companies: CN,
  prices, indicators: INDS, statusNames: SN, statusColors: SBADGE, inspector}) {
return function showDossier(p) {
  el.replaceChildren();
  const close = dossierNode("button", "✕", "close");
  close.type = "button"; close.setAttribute("aria-label", "关闭部件档案");
  close.addEventListener("click", () => { el.style.display = "none"; inspector.hide(); });
  el.append(close, dossierNode("h2", p.name));
  const meta = dossierNode("div", [p.layer, BOM.layers.find(l => l.id === p.layer)?.name || ""].join(" "), "meta");
  const badge = dossierNode("span", "产业状态：" + (SN[p.status] || "未知"), "badge");
  badge.style.background = SBADGE[p.status] || "#64748b";
  meta.append(" · ", badge); el.append(meta);
  el.append(dossierNode("p", "概念示意 · 类别级研究锚点。形状、数量、尺寸不代表真实现场配置。", "rg-concept-note"));
  const research = document.createElement("div"); el.append(research);
  mountNodeResearch(research, "part:" + p.id);
  const slot = dossierNode("div", undefined, "insp");
  slot.id = "inspSlot"; slot.style.display = "none";
  slot.append(dossierNode("div", "概念部件预览 · 拖动旋转", "ihint")); el.append(slot);
  el.append(dossierNode("div", p.desc || "说明待补充"));
  const links = dossierNode("div", undefined, "sec");
  links.append(dossierNode("h3", "参考研究与结构"));
  links.append(dossierLink("研究模块 " + p.module + " " + (MODNAME[p.module] || ""), "report.html#ch-" + encodeURIComponent(p.module)));
  links.append(dossierLink("模块原文", "doc.html?f=" + encodeURIComponent("research/" + p.module + ".md")));
  if (view === "campus" && ["rack-frame", "server", "network-switch", "power-shelf", "manifold", "gpu", "cpu", "hbm", "dram", "nic", "psu", "coldplate", "ssd"].includes(p.id))
    links.append(dossierLink("继续拆解机柜 →", "rack3d.html?x=100&node=" + encodeURIComponent("part:" + p.id) + "#" + encodeURIComponent(p.id)));
  if (view === "rack")
    links.append(dossierLink("返回园区定位", "bom3d.html?" + new URLSearchParams({ p: p.id, node: "part:" + p.id })));
  el.append(links);
  if (p.upstream?.length) {
    const upstream = dossierNode("div", undefined, "sec"); upstream.append(dossierNode("h3", "上游研究主题"));
    p.upstream.forEach(u => upstream.append(dossierNode("span", u, "chip"))); el.append(upstream);
  }
  if (p.companies?.length) {
    const companies = dossierNode("div", undefined, "sec"); companies.append(dossierNode("h3", "类别关联公司 · 不代表现场供应商"));
    p.companies.forEach(c => companies.append(dossierLink(CN[c] || c, "company.html?c=" + encodeURIComponent(c)))); el.append(companies);
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
  if (inspector.show(p.id)) { slot.style.display = "block"; slot.insertBefore(inspector.canvas, slot.firstChild); }
  el.style.display = "block";
}

}
