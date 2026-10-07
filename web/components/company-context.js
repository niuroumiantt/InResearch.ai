
(() => {
async function get(p) {
  const r = await fetch(p + (p.includes("?") ? "&" : "?") + "t=" + Date.now(), { cache: "no-store", signal: AbortSignal.timeout(12000) });
  if (!r.ok) throw new Error(p + " → HTTP " + r.status);
  return r.json();
}
const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
const fmtMW = n => n >= 10000 ? (n / 1000).toFixed(1) + " GW" : Math.round(n).toLocaleString() + " MW";
function capBuckets(p) {
  let op = 0, bu = 0, pl = 0;
  const put = (l, v) => { const n = +l.slice(1); if (n >= 8) op += v; else if (n >= 6) bu += v; else pl += v; };
  if (p.capacity_it_mw) put(p.status, p.capacity_it_mw);
  for (const [k, v] of Object.entries(p.capacity_it_mw_by_status || {})) put(k, v);
  return [op, bu, pl];
}
const SC = l => +l.slice(1) >= 8 ? "var(--green)" : +l.slice(1) >= 6 ? "var(--yellow)" : "var(--gray)";
const SUP = { tight: "紧缺", transition: "技术切换中", mature: "成熟", emerging: "新兴" };

/* 已登记产品：Git 内事件卡（data/event_cards.json）里属于这家公司的交付。Fetchspec 的产品 ID 是「公司-20位哈希」，
   两家的公司 ID 与公司表不同名，在此对照。一张卡是一条目标行；同一来源页面交付到多行时合成一个产品。 */
const FETCHSPEC_COMPANY = { asteralabs: "astera-labs", delta: "delta-electronics" };
function cardCompanies(card) {
  const ids = (card.parameters || []).map(p => p.product_id);
  const m = /products ([^;]+)/.exec(card.note || "");
  if (m) ids.push(...m[1].split(","));
  return new Set(ids.map(id => String(id).trim().replace(/-[0-9a-f]{20}$/, "")).map(co => FETCHSPEC_COMPANY[co] || co));
}
function registeredProducts(cards, cid) {
  const byPage = new Map();
  for (const c of cards) {
    if (c.team !== "fetchspec" || !cardCompanies(c).has(cid)) continue;
    const p = byPage.get(c.origin_pointer) || { url: c.origin_pointer, kind: c.pointer_kind, at: c.delivered_at, targets: [], parameters: [] };
    p.targets.push(c.target_id);
    for (const v of c.parameters || []) p.parameters.push({ ...v, target_id: c.target_id });
    if ((c.delivered_at || "") > (p.at || "")) p.at = c.delivered_at;
    byPage.set(c.origin_pointer, p);
  }
  return [...byPage.values()].sort((a, b) => a.targets[0].localeCompare(b.targets[0]));
}
function productHtml(p) {
  let host = p.url, label = p.url;
  try { const u = new URL(p.url); host = u.hostname.replace(/^www\./, ""); label = decodeURIComponent(u.pathname.split("/").filter(Boolean).pop() || host); } catch (e) {}
  const link = p.kind === "url" ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(label)} ↗</a>` : `<code>${esc(p.url)}</code>`;
  const many = p.targets.length > 1;   // name the row only when one page delivers to several
  const rows = p.parameters.map(v => `<tr><td><code>${esc(v.parameter_name)}</code>${many ? `<div style="font-size:10.5px;color:var(--gray)">${esc(v.target_id)}</div>` : ""}</td>
      <td>${esc(v.value)}${v.unit ? ` <span style="color:var(--muted)">[${esc(v.unit)}]</span>` : ""}${v.condition ? `<div style="font-size:11px;color:var(--muted)">${esc(v.condition)}</div>` : ""}</td></tr>`).join("");
  return `<div class="sec registered-product" style="margin-bottom:14px"><h3>${link} <span style="font-size:11px;color:var(--muted)">${esc(host)} · ${esc(p.at || "")}</span></h3>
    <div>${p.targets.map(t => `<a class="chip" href="supply.html?q=${encodeURIComponent(t)}#targets">${esc(t)}</a>`).join("")}</div>
    ${rows ? `<div class="ui-table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><th>参数</th><th>原文值 [单位] · 条件</th></tr>${rows}</table></div>` : '<div class="note">这次交付只登记了原件指针，没有随附参数。</div>'}</div>`;
}

const STATUS_LABEL = { delivered: "已交付", needed: "缺", sourced: "已有", assumed: "假设" };
/* 需求：目标表里实例点名这家公司的 Fetchspec 行（有目录时用接口算好的对照，否则在本页按名称匹配）。 */
function demandRows(targets, c, cat, registered) {
  const names = [c.name.split("/")[0].trim(), c.company_id].map(s => s.toLowerCase()).filter(s => s.length >= 3);
  const byId = Object.fromEntries(targets.map(t => [t.id, t]));
  const ids = cat && cat.research_alignment ? cat.research_alignment.target_ids
    : targets.filter(t => t.team === "fetchspec" && (t.instances || []).some(i => names.some(n => String(i).toLowerCase().includes(n)))).map(t => t.id);
  return ids.filter(id => byId[id]).map(id => ({ row: byId[id], products: registered.filter(p => p.targets.includes(id)) }));
}
function demandRow(d) {
  const r = d.row, products = d.products.map(p => {
    let label = p.url; try { label = decodeURIComponent(new URL(p.url).pathname.split("/").filter(Boolean).pop()); } catch (e) {}
    const n = p.parameters.filter(v => v.target_id === r.id).length;
    return `<a href="#registered">${esc(label)}</a>${n ? ` <span class="note">${n} 个参数</span>` : ""}`; }).join("<br>");
  return `<tr><td><a href="supply.html?q=${encodeURIComponent(r.id)}#targets"><code>${esc(r.id)}</code></a><div class="note" style="margin:0">${esc(r.notes || "")}</div></td>
    <td class="st-${esc(r.status)}">${esc(STATUS_LABEL[r.status] || r.status)}</td><td>${products || '<span class="note">—</span>'}</td></tr>`;
}

/* 主体档案从节点页第五列进入；对象类型 actor 与第五类变量分开。 */
function ecosystemHtml(records, projects, cname) {
  const adopted = records.filter(r => r.adoption?.review?.decision === 'adopted' && (r.capacity_observations || []).some(x => x.basis === 'generation'));
  if (!adopted.length) return '';
  const actor = id => `<a href="product-catalog.html?c=${encodeURIComponent(id)}">${esc(cname[id] || id)}</a>`;
  const safeLink = (value, label) => {
    try { const u = new URL(value); if (['http:', 'https:'].includes(u.protocol) && !u.username && !u.password) return `<a href="${esc(u.href)}" target="_blank" rel="noopener">${esc(label)}</a>`; } catch {}
    return esc(label);
  };
  const provinces = [...new Set(adopted.flatMap(r => (r.geographies || []).map(g => g.province)).filter(Boolean))];
  const shortState = { Illinois: 'IL', Pennsylvania: 'PA', 'New Jersey': 'NJ' };
  const inState = (p, state) => p.country === 'US' && (p.province === state || new RegExp(`^(?:${state}|${shortState[state] || state})(?:[, ·]|$)`, 'i').test(p.location || ''));
  const geography = provinces.length ? `<h3>地域对照 · 已披露省州</h3><div class="ui-table-scroll" tabindex="0" role="region" aria-label="地域对照"><table><tr><th>省州</th><th>电源信息</th><th>本站登记的数据中心</th><th>土地与接电关系</th></tr>${provinces.map(state => {
    const sites = projects.filter(p => inState(p, state) && !p.duplicate_of && !p.site_id.includes('portfolio'));
    return `<tr><td>${esc(state)}</td><td>所在电源组合已登记；本州具体电厂、机组及 MW 分配待核实</td><td>${sites.map(p => `<a href="project.html?site=${encodeURIComponent(p.site_id)}">${esc(p.name)}</a>`).join('<br>') || '尚未按明确州名匹配到登记项目；待查'}</td><td>地主、供地交易、审批机关、受电园区及电网接入均待核实</td></tr>`;
  }).join('')}</table></div><p class="note">这里只对照已有登记的明确州名，覆盖并不完整；同州不证明供电关系。组合容量不向各州分摊，也不据此推断数据中心土地批复。</p>` : '';
  return `<section class="board b12" id="ecosystem"><div class="bh"><h2>生态关系与已采用信息</h2><a class="go" href="supply.html#matching">查看日报交付 →</a></div>
    <p>电源 → 电网与接入 → 园区 → 使用方，按实际关系逐项连接。供电、土地和审批的主体分别登记；未确认的连接保留待查。</p>
    ${adopted.map(r => `<article class="sec"><h3>${esc(r.summary)}</h3><p>${(r.relationships || []).map(x => actor(x.actor_id) + '：' + esc(x.role)).join('；')}</p>
      <p>${(r.capacity_observations || []).map(x => `${esc(x.value)} ${esc(x.unit)} · ${esc(x.basis === 'generation' ? '发电口径' : x.basis)} · ${esc(x.nature === 'forecast' ? '新增计划' : '既有电源协议')} · ${esc(x.scope)}`).join('<br>')} · 协议 ${esc(r.term_years)} 年</p>
      <p>${(r.object_ids || []).filter(x => !x.startsWith('actor:')).map(id => `<a class="chip" href="node.html?id=${encodeURIComponent(id)}">${esc(({ 'system:power': '电力系统', 'chain:power/3': '发电与储能', 'site:grid': '电力配额与并网' })[id] || id)}</a>`).join('')}</p>
      <p class="note">待补：${esc((r.gaps || []).join('；'))}</p><p>${(r.sources || []).map((s, i) => safeLink(s.url, (new URL(s.url).hostname.replace(/^www\./, '')) + ' 原始来源 ↗')).join(' · ')} · 核验 ${esc(r.verified_date)} · <a href="supply.html?event=${encodeURIComponent(r.adoption.event_id)}#matching">对应日报证据 →</a></p>
    </article>`).join('')}
    <p class="note">采用范围是双方公告所述协议与角色；完整合同和监管批准仍待取得。新增发电计划与既有电源供给分别登记，均不增加数据中心 IT GW。</p>${geography}</section>`;
}
let loaded = false;
document.querySelector("#research-details").addEventListener("toggle", async event => {
if (!event.target.open || event.target.hidden || loaded) return;
loaded = true;
try {
  const cid = new URLSearchParams(location.search).get("c") || "nvidia";
  const [companies, bom, rights, products, projectsDoc, contracts, cardsDoc] = await Promise.all([
    get("data/companies.json"), get("framework/bom.json"), get("framework/site_rights.json"),
    get("data/products.json"), get("data/projects.json"), get("data/contracts.json"),
    get("data/event_cards.json")]);
  const [catalog, targetsDoc] = await Promise.all([
    get("api/product-catalog/" + encodeURIComponent(cid) + "?view=summary").catch(() => null),
    get("framework/tco_targets.json")]);
  const c = companies.records.find(x => x.company_id === cid);
  if (!c) throw new Error("公司不存在: " + cid);

  const cname = Object.fromEntries(companies.records.map(x => [x.company_id, x.name_cn || x.name]));
  const pri = r => r.includes("hyperscaler") ? 0 : r.includes("ai-lab") ? 1 : r.includes("neocloud") ? 2 : r.includes("colo") ? 3 : 4;


  const systems = bom.systems;
  const sysName = sid => { const s = systems[sid] || {}; const top = s.parent ? systems[s.parent] : s; return (top.name || sid) + (s.parent ? " · " + String(s.name || sid).replace("IT · ", "") : ""); };
  const supplied = bom.parts.filter(p => (p.companies || []).includes(cid));
  const bySystem = {};
  supplied.forEach(p => (bySystem[p.system] ||= []).push(p));
  const held = (rights.rights || []).filter(r => (r.companies || []).includes(cid));
  const lines = (products.records || []).filter(r => r.company_id === cid);
  const mine = projectsDoc.records.filter(p => (p.developer || []).includes(cid) || (p.tenant || []).includes(cid));
  const myContracts = contracts.records.filter(x => (x.parties || []).includes(cid));
  const registered = registeredProducts(cardsDoc.records || [], cid);
  const demand = demandRows(targetsDoc.targets || [], c, catalog, registered);

  const supplyHtml = Object.keys(bySystem).length ? Object.entries(bySystem).map(([sid, parts]) => `<div class="sec"><h3>${esc(sysName(sid))}</h3>${parts.sort((a, b) => (a.chain_order || 0) - (b.chain_order || 0)).map(p =>
      `<a class="chip" href="node.html?id=part:${encodeURIComponent(p.id)}&col=5" title="${esc(p.chain || "")} 第 ${p.chain_order || "?"} 位 · ${SUP[p.status] || p.status}">${esc(p.name)}</a>`).join("")}</div>`).join("")
    : '<div class="note">骨架里没有登记这家公司供应的部件（登记数，不代表现场供应商）。</div>';
  const rightsHtml = held.length ? held.map(r => `<a class="chip" href="node.html?id=site:${encodeURIComponent(r.id)}&col=5">${esc(r.name)}</a>`).join("") : '<div class="note">没有登记持有的站点权利。</div>';
  const linesHtml = lines.length ? `<div class="ui-table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><th>产品线</th><th>部件</th><th>系统 · 链路</th><th>状态</th><th>资料</th></tr>${lines.map(l =>
      `<tr><td>${esc(l.product_line)}<div style="font-size:10.5px;color:var(--gray)">${esc(l.representative_models || "")}</div></td><td>${(l.bom_parts || []).map(pid => `<a href="node.html?id=part:${encodeURIComponent(pid)}">${esc(pid)}</a>`).join("、")}</td><td>${esc(l.system ? sysName(l.system) : "")}${l.chain ? " · " + esc(l.chain) : ""}</td><td>${esc(SUP[l.status] || l.status || "")}</td><td>${l.library_path ? `<a href="product-catalog.html?c=${encodeURIComponent(c.company_id)}">规格库</a>` : ""}</td></tr>`).join("")}</table></div>`
    : '<div class="note">产品库没有这家公司的产品线。</div>';
  const projRows = mine.sort((a, b) => { const ca = capBuckets(a), cb = capBuckets(b); return (cb[0] + cb[1] + cb[2]) - (ca[0] + ca[1] + ca[2]); }).map(p => {
    const [o, b, l] = capBuckets(p), tot = o + b + l;
    return `<tr><td><a href="project.html?site=${encodeURIComponent(p.site_id)}">${esc(p.name)}</a><div style="font-size:10.5px;color:var(--gray)">${esc(p.location || "")}</div></td>
      <td><span class="badge" style="background:${SC(p.status)}">${esc(p.status)}</span></td>
      <td>${tot ? fmtMW(tot) : "<span style='color:var(--gray)'>未披露</span>"}</td>
      <td>${(p.developer || []).includes(cid) ? "自建/开发" : "租户"}</td>
      <td style="font-size:11px">${esc(p.verified_date || "")}</td>
      <td>${(p.sources || [])[0] ? `<a href="${esc(p.sources[0].url)}" target="_blank" rel="noopener">源</a>` : ""}</td></tr>`;
  }).join("");

  document.getElementById("root").innerHTML = `
    <div class="grid">
      ${ecosystemHtml(myContracts, projectsDoc.records, cname)}
      <div class="board b12" id="demand"><div class="bh"><h2>需求与交付对照（${demand.length} 条目标行）</h2><a class="go" href="supply.html#targets">目标表 →</a></div>
        ${demand.length ? `<div class="ui-table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><th>目标行</th><th>状态</th><th>已交付的产品</th></tr>${demand.map(demandRow).join("")}</table></div>`
          : '<div class="note">目标表里没有点名这家公司的行。</div>'}
        <div class="note">inresearch.ai 的采集需求只来自目标表：这里列出实例点名这家公司的行，及 Fetchspec 已交付到每行的产品与参数原文。</div></div>
      <div class="board b6"><div class="bh"><h2>供应的部件（${supplied.length}）</h2><a class="go" href="bom.html">爆炸图 →</a></div>${supplyHtml}
        <div class="note">来自骨架登记（bom.json 的 companies）：类别关联，不代表现场供应商；点部件进节点页第五列。</div></div>
      <div class="board b6"><div class="bh"><h2>持有的站点权利（${held.length}）</h2><a class="go" href="node.html?id=site">六条权利 →</a></div>${rightsHtml}
        <div class="note">登记数：只说明登记过持有关系，事件卡与合同是证据。</div>
        <div class="bh" style="margin-top:14px"><h2>产品线（${lines.length}）</h2><a class="go" href="product-catalog.html?c=${encodeURIComponent(c.company_id)}">规格库 →</a></div>${linesHtml}</div>
      <div class="board b12" id="registered"><div class="bh"><h2>已登记产品（Fetchspec 交付 · ${registered.length}）</h2><a class="go" href="supply.html#targets">目标表 →</a></div>
        ${registered.length ? registered.map(productHtml).join("") : '<div class="note">尚未登记到研究目标；产品目录交付情况见上方总览。</div>'}
        <div class="note">厂商官网原文值（不换算），随交付登记到目标行；单位与条件照审阅过的映射。是候选资料，不是序列，正式采用另走研究流程。</div></div>
      <div class="board b12"><div class="bh"><h2>关联园区（附表 · ${mine.length}）</h2></div>
        <div class="ui-table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><th>园区</th><th>状态</th><th>合计容量</th><th>关系</th><th>核验</th><th>来源</th></tr>${projRows || "<tr><td colspan=6>暂无关联园区</td></tr>"}</table></div>
        <div class="note">容量口径：IT 负载 MW；未披露 ≠ 不存在。</div></div>
      <div class="board b12"><div class="bh"><h2>关联合同（附表 · ${myContracts.length}）</h2></div>
        ${myContracts.length ? `<div class="ui-table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><th>合同</th><th>类型</th><th>$B</th><th>循环</th></tr>` +
          myContracts.map(x => `<tr><td>${esc(x.contract_id)}<div style="font-size:10px;color:var(--gray)">${(x.parties || []).map(p => esc(cname[p] || p)).join(" ↔ ")}</div></td>
          <td>${esc(x.type)}</td><td>${x.value_usd_b ?? "—"}</td><td>${x.circular_flag ? "⚠️" : "—"}</td></tr>`).join("") + "</table></div>" : '<div class="note">暂无</div>'}</div>
    </div>`;
  if(location.hash)document.getElementById(location.hash.slice(1))?.scrollIntoView();
} catch (e) {
  const error = document.createElement("div");
  error.className = "err";
  loaded = false;
  error.textContent = `研究关联读取失败：${e.message}。收起后重新展开可重试。`;
  document.getElementById("root").replaceChildren(error);
}
});
})();
