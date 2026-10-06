/* Industry entry, filtered drilldowns and source-backed project details. */
(() => {
'use strict';
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
const num=v=>Number(v).toLocaleString('en-US',{maximumFractionDigits:2}), gw=v=>num(v/1000), money=v=>v>=1000?'$'+num(v/1000)+'T':'$'+num(v)+'B';
const path=location.pathname, isProject=path==='/project.html', isMarket=path==='/market.html', isList=path==='/projects.html', isCompany=path==='/industry.html';
const isHome=['/','/index.html'].includes(path);
if(isHome){document.body.classList.add('industry-home');$('pipeline-summary').remove();$('trends-section').remove();}
let params=new URLSearchParams(location.search), data=null, geo=null, news=null, request=null, view=[0,0,1000,490];
let highlightedCompany='', selectedSite='', pinned=false;
const keys=['c','region','stage','relation','scope','role','site'];
function url(page, changes={}) {const q=new URLSearchParams(params);for(const [k,v] of Object.entries(changes))v?q.set(k,v):q.delete(k);return page+(q.size?'?'+q:'');}
function name(id){const c=data?.companies.find(c=>c.company_id===id);return c?.name_cn||c?.name||id;}
function companyLink(id){return `<a href="${esc(url('/industry.html',{c:id,site:'',stage:''}))}">${esc(name(id))}</a>`;}
function participantProfiles(p){
 const ids=[...new Set([...p.developer,...p.tenant])];
 const profiles=ids.map(id=>{const c=data.companies.find(c=>c.company_id===id);return c?.profile?`<p>${companyLink(id)}：${esc(c.profile)}</p>`:'';}).filter(Boolean);
 return profiles.length?`<h3>参与主体的业务</h3>${profiles.join('')}<p class="basis">公司业务与本园区角色分别核验；业务说明不证明资产所有权或已签租约。</p>`:'';
}
function projectGeography(p){
 let country=p.country||'国家待核验';
 try{if(p.country)country=new Intl.DisplayNames(['zh-CN'],{type:'region'}).of(p.country);}catch{}
 return `${esc(country)} · ${esc(data.regions.find(r=>r.id===p.region)?.name||p.region||'区域待核验')}<br>${esc(p.location||'具体地点待核验')}`;
}
function sourceLink(source,label){const href=safe(source);return href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`:esc(label);}
function selection(){return {company:params.get('c')||'',region:params.get('region')||'',site:params.get('site')||'',scope:params.get('scope')||'',relation:params.get('relation')||'',role:params.get('role')||'',siteIds:data?.rows.filter(p=>!p.portfolio).map(p=>p.site_id)||[]};}
function select(changes){for(const [k,v] of Object.entries(changes))v?params.set(k,v):params.delete(k);history.pushState(null,'',url(path));load();}
window.addEventListener('popstate',()=>{params=new URLSearchParams(location.search);load();});
$('filters').addEventListener('submit',e=>e.preventDefault());
$('filters').addEventListener('change',e=>select({[e.target.name]:e.target.value,site:''}));
$('stage-filter').onchange=e=>select({stage:e.target.value});
$('lead-state').onchange=renderPipeline;
window.addEventListener('inresearch:news-data',e=>{news=e.detail;renderPipeline();renderMap();});
$('news-selection').onchange=e=>{document.querySelector('[data-datacenter-news]').dataset.newsSelection=e.target.value;window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:{...selection(),force:true}}));};
function filters(){
 for(const key of ['region','c']){
  const element=$('filters').elements[key], values=key==='region'?data.regions.map(r=>[r.id,r.name]):data.companies.map(c=>[c.company_id,c.name_cn||c.name]);
  element.innerHTML=`<option value="">${key==='region'?'全球':'所有主体'}</option>`+values.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');
 }
 for(const key of ['region','scope','role','relation','c'])$('filters').elements[key].value=params.get(key)||'';
 $('stage-filter').value=params.get('stage')||'';
}
function renderStats(){
 const noDisclosures=data.totals.sites>0&&data.totals.sites===data.totals.unknown;
 const labels={operating:'样本 · 已投运',construction:'样本 · 建设中',planning:'样本 · 筹备机会',unknown:'样本 · 容量未披露'};
 $('stats').innerHTML=Object.entries(labels).map(([s,label])=>`<a class="stat-link ${params.get('stage')===s?'active':''}" href="${esc(url('/projects.html',{stage:s,site:''}))}"><span>${label} ↗</span><strong>${s==='unknown'?data.totals.unknown:noDisclosures?'—':gw(data.totals[s])}<small>${s==='unknown'?'项':'GW'}</small></strong><span>${s==='planning'?'含官宣、选址、电力与审批阶段':s==='unknown'?'仍在地图与明细中保留':s==='operating'?'已通电 / 满载，按分期计量':'已有开工 / 机电施工记录'}</span></a>`).join('');
 $('basis').textContent=`地图样本 ${data.totals.sites} 条项目记录，非全球总量 · 建设 + 筹备 ${gw(data.totals.construction+data.totals.planning)} GW · 核验 ${data.coverage.oldest_verified}—${data.coverage.latest_verified}，非统一年末存量。点击数字查看明细与来源。`;
}
function renderMarket(){
 const m=data.market, actual=m.series.filter(r=>!r.forecast).at(-1);
 const benchmarks=data.benchmarks||[];
 $('market-band').innerHTML=benchmarks.map(r=>`<a class="macro-card" href="/market.html#capacity"><span>全球 IT 负载 · ${esc(r.as_of.slice(0,4))}${r.caliber.basis==='预测'?' 预测':' 估算'} ↗</span><strong>约 ${num(r.value)}<small>GW</small></strong><small>汇丰 · 2026 年 3 月报告</small></a>`).join('')+(actual?`<a class="macro-card" href="/market.html"><span>全球 IT 年度资本开支 · ${actual.year} ↗</span><strong>${money(actual.value)}</strong><small>Dell’Oro · 2026/07 报告 · 历史值</small></a>`:'')+`<div class="macro-note">全球规模采用机构口径<br>地图展示本站追踪园区<br><a href="/market.html#capacity">来源与统计范围 →</a></div>`;

 if(!isMarket)return;
 const rows=m.series.filter(r=>r.year>='2020'),max=Math.max(...rows.map(r=>r.value),1);
 $('market-detail').innerHTML=`<div class="detail-card"><h2>${esc(m.title)}</h2><p>${esc(m.forecast_note)}</p><p>这是年度 IT 资本开支视角的市场规模。运营收入和设施建设投资需要独立来源，暂不混入本序列。</p><div class="market-bars">${rows.map(r=>`<div class="market-column ${r.forecast?'forecast':''}"><span>${num(r.value)}</span><div class="column" style="height:${r.value/max*170}px"></div><span>${r.year}${r.forecast?'E':''}</span></div>`).join('')}</div><p class="basis">单位：十亿美元（$B）；E = 预测。来源：Dell’Oro，2026 年 7 月版；内部原件未在本站公开。</p><div class="table-wrap"><table><thead><tr><th>年份</th><th class="num">年度投资（$B）</th><th>性质</th><th>来源与口径</th></tr></thead><tbody>${m.series.map(r=>`<tr><td>${r.year}</td><td class="num">${num(r.value)}</td><td>${r.forecast?'预测':'机构历史值'}</td><td>${esc(r.source)}<small>${esc(r.assumptions)}</small></td></tr>`).join('')}</tbody></table></div></div>`;
 $('market-detail').innerHTML+=`<div class="detail-card" id="capacity"><h2>全球容量：机构估算与地图样本</h2><p>首页的全球 IT 负载是机构估算及预测，不是截至今天已投运的普查值。地图样本只覆盖已登记园区，不能用它推算全球总量。全球在建与规划尚无当前、完整且统一口径的统计，暂不填一个伪精确总数。</p>${capacityComparison()}${benchmarks.map(r=>`<h3>${esc(r.as_of)} · 约 ${num(r.value)} ${esc(r.unit)} · ${esc(r.caliber.basis)}</h3><p>${esc(r.source)}</p><blockquote>${esc(r.locator)}</blockquote><p class="basis">${esc(r.caliber.power_scope)} / ${esc(r.caliber.workload)} · ${esc(r.corroboration)} · 内部登记引用 ${esc(r.fact_id)}</p>`).join('')}</div>`;

}
function capacityComparison(){
 const a=data.capacity_audit;
 return `<h3>为什么不能相减或算覆盖率</h3><p>${esc(a.comparability)}</p><dl><dt>年份</dt><dd>全球：2025 年估算 / 2030 年预测，报告发布于 2026-03-25；样本：核验 ${esc(a.oldest_verified)}—${esc(a.latest_verified)}，不是统一的 2025 年存量。</dd><dt>定义</dt><dd>${esc(a.definition)}</dd><dt>去重</dt><dd>${esc(a.deduplication)}</dd><dt>覆盖</dt><dd>${a.sites} 条非组合项目记录（含集群），${a.known} 条有容量，${a.unknown} 条未披露；${a.unlocated} 条未定位；排除 ${a.portfolios_excluded} 条组合及 ${a.duplicates_excluded} 条重复。${esc(a.coverage)}</dd><dt>登记合计</dt><dd>投运 ${num(a.operating/1000)} / 建设 ${num(a.construction/1000)} / 筹备 ${num(a.planning/1000)} GW，仅为现有登记字段合计。</dd><dt>仍待核实</dt><dd>${esc(a.unresolved)}</dd></dl>`;
}
function siteURL(p){return url('/project.html',{site:p.site_id});}
function xy(lon,lat){return [(lon+180)/360*1000,(90-lat)/180*490];}
function renderMap(){
 if(!geo||!data)return;
 let land='';
 for(const f of geo.features){const g=f.geometry;if(!g||!['Polygon','MultiPolygon'].includes(g.type))continue;const polygons=g.type==='Polygon'?[g.coordinates]:g.coordinates;for(const polygon of polygons){let d='';for(const ring of polygon){d+=ring.map(([lo,la],i)=>`${i?'L':'M'}${xy(lo,la).map(n=>n.toFixed(1)).join(',')}`).join('')+'Z';}land+=`<path class="land" d="${d}"/>`;}}
 const stage=params.get('stage'), rows=data.rows.filter(p=>!p.portfolio&&p.coordinates);
 const points=rows.map(p=>{
  const [x,y]=xy(p.coordinates[1],p.coordinates[0]),v=stage&&stage!=='unknown'?p.capacity[stage]:p.total_mw,r=p.capacity_known?Math.max(2.5,Math.sqrt(v)*.28):4;
  const main=stage&&stage!=='unknown'?stage:Object.keys(data.stages).reduce((a,b)=>p.capacity[a]>=p.capacity[b]?a:b,'operating');
  const color={operating:'var(--ui-green)',construction:'var(--ui-yellow)',planning:'var(--ui-muted)'}[main];
  const shape=p.capacity_known?`<circle cx="${x}" cy="${y}" r="${r}" fill="${color}"/>`:`<path d="M${x},${y-4}l4,4 -4,4 -4,-4Z" fill="var(--ui-surface)" stroke="var(--ui-muted)"/>`;
  return `<g class="site-point" tabindex="0" role="button" aria-label="${esc(p.name)}：${p.capacity_known?num(v)+' MW':'容量未披露'}" data-id="${esc(p.site_id)}"><title>${esc(p.name)} · ${esc(p.location)} · ${p.capacity_known?num(p.total_mw)+' MW（各阶段合计）':'容量未披露'}</title>${shape}</g>`;
 }).join('');
 const leads=(news?.pipeline?.records||[]).filter(r=>r.site_id&&!['paused','cancelled'].includes(r.state)&&(!params.get('c')||(r.company_ids||[]).includes(params.get('c'))));
 const overlays=rows.filter(p=>leads.some(r=>r.site_id===p.site_id)).map(p=>{const [x,y]=xy(p.coordinates[1],p.coordinates[0]);return `<circle class="news-ring" cx="${x}" cy="${y}" r="${Math.max(7,Math.sqrt(p.total_mw)*.28+4)}"/>`;}).join('');
 $('world-map').innerHTML=land+overlays+points;
 $('map-summary').textContent=`${rows.length} 条项目记录已定位 · ${data.rows.filter(p=>!p.portfolio&&!p.coordinates).length} 个未定位项目可在明细查看`;
 $('layout-link').href=url('/projects.html',{site:''});
 $('map-title').textContent=data.company?`${name(data.company.company_id)} · 全球布局`:'全球项目布局';
 for(const el of $('world-map').querySelectorAll('[data-id]')){
  const activate=()=>{if(pinned&&selectedSite!==el.dataset.id)return;selectedSite=el.dataset.id;renderPopup();highlightMap();};
  el.onclick=activate;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}};
 }
 highlightMap();renderPopup();
}
const svg=$('world-map');function setView(){svg.setAttribute('viewBox',view.join(' '));positionPopup();}function zoom(f){const w=Math.max(140,Math.min(1000,view[2]*f)),h=w*.49;view=[view[0]+(view[2]-w)/2,view[1]+(view[3]-h)/2,w,h];setView();}
$('zoom-in').onclick=()=>zoom(.65);$('zoom-out').onclick=()=>zoom(1/.65);$('zoom-reset').onclick=()=>{view=[0,0,1000,490];setView();};
let drag;svg.addEventListener('pointerdown',e=>{if(e.target.closest('[data-id]'))return;drag={x:e.clientX,y:e.clientY,view:[...view]};svg.setPointerCapture(e.pointerId);});
svg.addEventListener('pointermove',e=>{if(!drag)return;const k=view[2]/svg.getBoundingClientRect().width;view=[drag.view[0]-(e.clientX-drag.x)*k,drag.view[1]-(e.clientY-drag.y)*k,view[2],view[3]];setView();});
svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);
const popup=document.createElement('section');
popup.id='map-popup';popup.className='map-popup';popup.hidden=true;popup.setAttribute('role','dialog');popup.setAttribute('aria-label','园区信息');
svg.parentElement.append(popup);
function closePopup(focus=false){const id=selectedSite;selectedSite='';pinned=false;popup.hidden=true;highlightMap();if(focus)[...svg.querySelectorAll('[data-id]')].find(p=>p.dataset.id===id)?.focus();}
function positionPopup(){
 if(popup.hidden)return;
 const point=[...svg.querySelectorAll('[data-id]')].find(p=>p.dataset.id===selectedSite);if(!point)return;
 const frame=svg.parentElement.getBoundingClientRect(),r=point.getBoundingClientRect();
 popup.style.left=Math.max(8,Math.min(frame.width-popup.offsetWidth-8,r.right-frame.left+12))+'px';
 popup.style.top=Math.max(8,Math.min(frame.height-popup.offsetHeight-8,r.top-frame.top))+'px';
}
function renderPopup(){
 if(!selectedSite)return;
 const p=data.rows.find(p=>p.site_id===selectedSite);if(!p){closePopup();return;}
 const focused=popup.contains(document.activeElement)?document.activeElement.id:null;
 popup.innerHTML=`<div class="popup-actions"><button id="pin-site" type="button" aria-pressed="${pinned}">${pinned?'取消固定':'固定浮窗'}</button><button id="close-site" type="button" aria-label="关闭园区信息">×</button></div><strong>${esc(p.name)}</strong><p>${esc(p.location)} · ${esc(p.stage_label)}</p><p>${p.capacity_known?`投运 ${num(p.capacity.operating)} / 建设 ${num(p.capacity.construction)} / 筹备 ${num(p.capacity.planning)} MW`:'IT 容量未披露'}</p><p>开发：${p.developer.map(name).map(esc).join('、')||'未登记'}<br>使用：${p.tenant.map(name).map(esc).join('、')||'未登记'}</p><p>核验 ${esc(p.verified_date||'未登记')} · 分期按登记口径</p><a href="${esc(siteURL(p))}">查看项目与来源 →</a>`;
 popup.hidden=false;$('pin-site').onclick=()=>{pinned=!pinned;renderPopup();};$('close-site').onclick=()=>closePopup(true);
 if(focused)$(focused)?.focus();positionPopup();
}
function highlightMap(){
 let count=0,unlocated=0;
 for(const p of data?.rows||[])if(!p.portfolio&&highlightedCompany&&[...p.developer,...p.tenant].includes(highlightedCompany)){if(p.coordinates)count++;else unlocated++;}
 for(const el of svg.querySelectorAll('[data-id]')){const p=data.rows.find(p=>p.site_id===el.dataset.id),matched=highlightedCompany&&[...p.developer,...p.tenant].includes(highlightedCompany);el.classList.toggle('highlighted',!!matched);el.classList.toggle('dimmed',!!highlightedCompany&&!matched);el.classList.toggle('selected',selectedSite===p.site_id);el.setAttribute('aria-pressed',String(selectedSite===p.site_id));}
 if(isHome){
  document.querySelectorAll('#company-chips [data-company],#leaders [data-company]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.company===highlightedCompany)));
  $('map-selection').textContent=highlightedCompany?`${name(highlightedCompany)}：当前筛选内高亮 ${count} 个地图点，另有 ${unlocated} 项未定位。点击园区显示信息，可固定浮窗。`:'点击园区显示信息，可固定浮窗；详情另设链接。支持拖动和缩放。';
 }
}
function highlightCompany(id){highlightedCompany=highlightedCompany===id?'':id;highlightMap();}
document.addEventListener('pointerdown',e=>{if(!pinned&&!popup.contains(e.target)&&!e.target.closest('[data-id]'))closePopup();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!popup.hidden){e.preventDefault();closePopup(true);}});
window.addEventListener('resize',positionPopup);
function renderCompanies(){
 const ids=[...new Set(['microsoft','meta','amazon','alphabet-google','oracle',...data.leaders.map(c=>c.company_id)])].filter(id=>data.companies.some(c=>c.company_id===id)).slice(0,10);
 $('company-chips').innerHTML=`<button type="button" data-company="" aria-pressed="${!(isHome?highlightedCompany:params.get('c'))}">${isHome?'清除高亮':'全部'}</button>`+ids.map(id=>`<button type="button" data-company="${esc(id)}" aria-pressed="${(isHome?highlightedCompany:params.get('c'))===id}">${esc(name(id))}</button>`).join('');
 $('company-chips').querySelectorAll('button').forEach(b=>b.onclick=()=>isHome?highlightCompany(b.dataset.company):select({c:b.dataset.company,site:''}));
 const featured=['microsoft','meta','amazon','alphabet-google'];
 const leaders=[...data.leaders].sort((a,b)=>{const ai=featured.indexOf(a.company_id),bi=featured.indexOf(b.company_id);return (ai<0?99:ai)-(bi<0?99:bi);});
 $('leaders').innerHTML=leaders.slice(0,4).map(c=>`<${isHome?'button type="button" data-company="'+esc(c.company_id)+'" aria-pressed="'+(highlightedCompany===c.company_id)+'"':'a href="'+esc(url('/industry.html',{c:c.company_id,stage:'',site:''}))+'"'} class="leader"><strong>${esc(name(c.company_id))}${isHome?'':' ↗'}</strong><p>已披露的相关园区容量</p><p class="leader-size">${c.totals.unknown===c.totals.sites?'容量未披露':gw(c.totals.operating+c.totals.construction+c.totals.planning)+' GW'}</p><p>${c.totals.sites} 条相关项目 · ${c.totals.unknown} 项容量未披露</p><p>${c.totals.unknown===c.totals.sites?'已登记布局，容量有待来源补充。':`投运 ${gw(c.totals.operating)} / 建设 ${gw(c.totals.construction)} / 筹备 ${gw(c.totals.planning)} GW`}</p></${isHome?'button':'a'}>`).join('')||'<p class="empty">当前筛选下没有登记的主体关系。</p>';
 $('leaders').querySelectorAll('button').forEach(b=>b.onclick=()=>highlightCompany(b.dataset.company));
}
function renderTable(){
 if(!isList)return;
 const stage=params.get('stage'),all=data.rows,rows=(!isList&&!isCompany?all.slice(0,8):all);
 $('list-title').textContent=`${data.stages[stage]|| (stage==='unknown'?'容量未披露':'项目明细')} · ${all.length} 条记录`;
 $('project-rows').innerHTML=rows.length?`<div class="table-wrap"><table><thead><tr><th>园区 / 地区</th><th>参与主体</th><th class="num">已投运 MW</th><th class="num">建设中 MW</th><th class="num">筹备 MW</th><th>最近核验</th></tr></thead><tbody>${rows.map(p=>`<tr><td><a href="${esc(siteURL(p))}">${esc(p.name)}</a><small>${esc(p.location)} · ${esc(p.stage_label)}${p.portfolio?' · 组合记录（不计总量）':''}${!p.coordinates?' · 未定位':''}${p.disputed?' · 有争议':''}</small></td><td>${[...new Set([...p.developer,...p.tenant])].map(companyLink).join('、')||'未登记'}</td>${Object.keys(data.stages).map(s=>`<td class="num">${p.capacity_known?num(p.capacity[s]):'—'}</td>`).join('')}<td>${esc(p.verified_date||'未登记')}</td></tr>`).join('')}</tbody></table></div>`:'<p class="empty">没有匹配的项目。可放宽筛选；容量缺失不代表没有项目。</p>';
 if(rows.length<all.length)$('project-rows').innerHTML+=`<p><a href="${esc(url('/projects.html',{site:''}))}">查看全部 ${all.length} 条记录 →</a></p>`;
}
function renderDetail(){
 const p=data.detail;if(!isProject)return;if(!p){$('page-title').textContent='项目详情';$('detail').innerHTML='<p class="empty">请从 <a href="/projects.html">项目列表</a> 选择一个园区。</p>';return;}
 $('page-title').textContent=p.name;$('page-description').textContent=`${p.location} · ${p.stage_label} · 核验 ${p.verified_date||'日期未登记'}`;
 $('detail').innerHTML=`<p><a href="${esc(url('/projects.html',{site:''}))}">← 返回同条件项目列表</a></p><div class="detail-grid"><div><div class="detail-card"><h2>项目与分期</h2>${p.duplicate_of?`<p>重复记录，已退出聚合。<a href="${esc(url('/project.html',{site:p.duplicate_of}))}">查看主记录 →</a><br>${esc(p.deduplication_note)}</p>`:''}${(p.duplicate_records||[]).map(a=>`<p>${esc(a.note)} <a href="${esc(url('/project.html',{site:a.site_id}))}">查看保留记录 →</a></p>`).join('')}<dl><dt>开发建设</dt><dd>${p.developer.map(companyLink).join('、')||'未登记'}</dd><dt>使用 / 租用</dt><dd>${p.tenant.map(companyLink).join('、')||'待核验（尚未登记）'}</dd><dt>国家 / 区域 / 地点</dt><dd>${projectGeography(p)}</dd><dt>IT 容量</dt><dd>${p.capacity_known?num(p.total_mw)+' MW（各阶段合计）':'未披露'}</dd><dt>设施总功率</dt><dd>${p.capacity_facility_mw?num(p.capacity_facility_mw)+' MW（不与 IT 容量相加）':'未披露'}</dd><dt>电力进展</dt><dd>${esc(p.power_status||'未登记')}</dd><dt>位置</dt><dd>${p.coordinates?esc(p.coordinates.join(', '))+'（登记坐标）':'仅有地区信息，未落精确坐标'}</dd></dl>${participantProfiles(p)}${p.phases.map(x=>`<p><span class="badge">${esc(x.label)}</span>${num(x.mw)} MW</p>`).join('')}<p class="basis">${esc(p.notes||'')}</p>${p.adoption?`<h3>本批材料已用于此项目</h3><p>${esc(p.adoption.scope)}</p><p>已采用字段：${esc(p.adoption.fields.join('、'))}</p><p><a href="/supply.html?event=${encodeURIComponent(p.adoption.event_id)}#matching">查看对应日报事件与原件定位 →</a></p>${p.adoption.assertions.filter(x=>x.value!=null).map(x=>`<p>${num(x.value)} ${esc(x.unit)} · ${esc(({it:'IT容量',grid:'供电容量',facility:'设施功率'})[x.basis]||x.basis)} · ${esc(x.phase)}</p><blockquote>${esc(x.quote)}</blockquote>`).join('')}`:''}${p.disputed?'<p>此项目有来源争议，请对照下列原始依据。</p>':''}${p.portfolio?'<p>组合型记录，仅供参考，不计入园区合计。</p>':''}</div></div><div><div class="detail-card"><h2>进展时间线</h2><ol class="timeline">${p.history.map(h=>`<li><time>${esc(h.date)}</time>${sourceLink(h.source_url,h.status+' · 查看当时来源')}</li>`).join('')||'<li>尚无已登记的历史事件。</li>'}</ol></div><div class="detail-card"><h2>来源与核验</h2>${p.sources.map(s=>`<p>${sourceLink(s.url,s.note||new URL(s.url).hostname)}<br><span class="basis">${esc(s.grade)} · ${esc(s.date||'日期未登记')}</span></p>`).join('')||'<p>暂无可公开的来源链接。</p>'}</div></div></div>`;
}
function renderTrends(){
 if(isHome)return;
 const rows=[...data.regional].sort((a,b)=>(b.totals.planning+b.totals.construction)-(a.totals.planning+a.totals.construction)),max=Math.max(...rows.map(r=>r.totals.planning+r.totals.construction),1);
 $('trends').innerHTML=rows.slice(0,5).map(r=>`<a class="region-chart" href="${esc(url('/projects.html',{region:r.id,stage:''}))}"><span>${esc(r.name)}</span><strong>${gw(r.totals.planning+r.totals.construction)} <small>GW</small></strong><div class="bar-track"><div class="bar-fill" style="width:${(r.totals.planning+r.totals.construction)/max*100}%"></div></div></a>`).join('')+'<p class="basis">地图样本 · 建设中 + 筹备</p>';
}
function renderPipeline(){
 if(!data||isHome)return;
 if(!news){$('pipeline-summary').innerHTML='<a href="/projects.html?view=pipeline">建设机会 · 等待新闻同步 →</a>';return;}
 const stages={reported:'消息称',announced:'已官宣',construction:'报道已开工',operating:'报道已投运',reviewing:'重新评审',paused:'暂停',cancelled:'取消'};
 const labels={lead:'新闻线索',reviewing:'重新评审',paused:'暂停',cancelled:'取消',linked:'已关联项目'},filter=selection();
 let rows=news.pipeline?.records||[];
 rows=rows.filter(r=>(!filter.company||(r.company_ids||[]).includes(filter.company))&&(!filter.site||r.site_id===filter.site)&&(!(filter.region||filter.scope||filter.role||filter.relation)||filter.siteIds.includes(r.site_id))&&($('lead-state').value==='all'||(!['paused','cancelled'].includes(r.state))));
 const groups=['reported','announced','construction','reviewing'];
 $('pipeline-summary').innerHTML=`<div><p class="eyebrow">LIVE PIPELINE</p><h2>新闻里的建设机会</h2><p class="basis">${news.reader?.stale?'快照延迟':'随新闻同步更新'} · ${news.pipeline?.available?(news.pipeline.truncated?'近期快讯与已接收日报事件':'新闻事件组，非唯一园区'):'等待阅读服务快照'}</p></div><div class="pipeline-stages">${groups.map(stage=>`<a href="${esc(url('/projects.html',{view:'pipeline',lead_stage:stage,site:''}))}"><strong>${news.pipeline?.available?rows.filter(r=>(r.reported_stage||'reported')===stage).length:'—'}</strong><span>${stages[stage]} ↗</span></a>`).join('')}</div><a href="${esc(url('/projects.html',{view:'pipeline',site:''}))}">全部动态 →</a>`;
 if(params.get('lead_stage'))rows=rows.filter(r=>(r.reported_stage||'reported')===params.get('lead_stage'));
 $('pipeline-rows').innerHTML=rows.map(r=>`<details class="pipeline-item" ${params.get('lead')===r.id?'open':''}><summary><span class="badge">${esc(['paused','cancelled','reviewing','linked'].includes(r.state)?labels[r.state]:stages[r.reported_stage]||labels[r.state]||'消息称')}</span>${esc(r.title)}</summary><p>${r.origin==='daily_html'?'日报项目动态 · 来源对应已登记 · '+esc(r.report_date)+(r.state==='linked'?' · 已关联正式项目，采用口径见项目明细<br>':' · 未计入正式 GW<br>'):''}首次发现 ${esc(r.first_seen||'未登记')} · 最近同步 ${esc(r.last_seen||'未登记')}</p><p>${(r.company_ids||[]).map(companyLink).join('、')||'主体待关联'}${r.site_id?` · <a href="${esc(url('/project.html',{site:r.site_id}))}">查看关联项目</a>`:' · 项目与地点待核实'}</p><p>${r.match_method==='name_and_actor'?'按园区全名与主体自动关联 · 待核实':''}</p>${r.events.map(e=>`<p><span class="badge">${esc(stages[e.reported_stage]||'消息称')}</span>${sourceLink(e.url,e.title_zh||e.title||'查看原始报道')}${e.reported_capacity?`<br>报道容量 ${esc(e.reported_capacity)} · ${r.state==='linked'?'原文报道口径；正式采用见关联项目':'原文口径，未计入 IT GW'}`:''}</p>`).join('')}${r.review_note?`<p>${esc(r.review_note)}</p>`:''}</details>`).join('')||`<p class="empty">${news.pipeline?.available?'当前筛选下暂无项目线索。地区筛选仅显示已关联园区的线索。':'尚未收到长期项目线索快照；已登记园区仍可正常浏览。'}</p>`;
 const progress=news.pipeline?.progress;
 if(progress && Number.isInteger(progress.leads)){
   const panel=document.createElement('div');panel.className='basis';panel.textContent=`完整档案：${progress.leads} 条线索 / ${progress.events} 个事件 · 当前筛选 ${rows.filter(r=>r.site_id).length} 条关联项目 · ${progress.identity_candidates} 有园区候选 · ${progress.capacity_observations} 个容量观察。水 ${progress.constraints?.water||0} / 电 ${progress.constraints?.power||0} / 审批 ${progress.constraints?.permits||0} 个约束事件。核验与采用单独登记；新闻 MW 不参加容量合计。`;
   $('pipeline-rows').prepend(panel);
 }
 for(const [index,row] of rows.entries()){
   const element=$('pipeline-rows').querySelectorAll('.pipeline-item')[index];if(!element)continue;
   for(const event of row.events||[]){
     const candidates=event.site_candidates||[];
     if(candidates.length){const line=document.createElement('p');line.textContent='园区匹配候选（待核验）：';
       for(const candidate of candidates){const a=document.createElement('a');a.href=url('/project.html',{site:candidate.site_id});a.textContent=candidate.site_id+' · '+candidate.anchor;line.append(a,document.createTextNode('；'));}element.append(line);}
     if(event.constraints?.length){const line=document.createElement('p');line.textContent='约束观察：'+event.constraints.map(x=>({power:'电力',water:'水',permits:'审批',land:'土地',finance:'融资'}[x]||x)).join(' / ');element.append(line);}
     for(const observed of event.capacity_observations||[]){const line=document.createElement('p');line.textContent=`${observed.quoted_value} · ${observed.basis==='it'?'提及 IT，仍待原件核验':observed.basis==='facility_or_grid'?'设施 / 电网 / 发电口径':'功率口径待核验'} · ${observed.locator}；不计入 GW`;element.append(line);}
   }
 }
 if(news.pipeline?.truncated)$('pipeline-rows').innerHTML+='<p class="basis">当前快照展示近期快讯与来源齐全的日报事件，非完整历史。</p>';
}
function render(){
 filters();renderStats();renderMarket();renderCompanies();renderTable();renderTrends();renderMap();renderDetail();renderPipeline();
 if(!isProject){$('page-title').textContent=isMarket?'数据中心市场规模':data.company?name(data.company.company_id)+' · 全球布局':isList?'全球项目与建设机会':'全球数据中心';$('page-description').textContent=data.company?'追踪相关园区、建设进度和新闻变化。园区容量不代表公司的持有或租用份额。':'全球规模与园区布局，追踪算力基础设施的变化。';}
 $('coverage').textContent=`${data.totals.sites} 条已追踪项目记录 · 含园区与集群，非全球普查\n核验日期 ${data.coverage.oldest_verified||'—'} — ${data.coverage.latest_verified||'—'}`;
 const hidden=isProject||isMarket;
 for(const id of ['atlas-tools','atlas-layout','project-list','leaders-section','trends-section'])if($(id))$(id).hidden=hidden;
 $('detail').hidden=!isProject;$('market-detail').hidden=!isMarket;$('market-band').hidden=isProject;$('pipeline-section').hidden=!(isList||isProject);$('project-list').hidden=!isList||params.get('view')==='pipeline';if($('pipeline-summary'))$('pipeline-summary').hidden=hidden||isList;
 if(isList){$('atlas-layout').hidden=true;$('leaders-section').hidden=true;$('trends-section').hidden=true;$('market-band').hidden=true;}
 document.title=$('page-title').textContent+' · inresearch.ai';
 window.industryFilter=selection();window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:selection()}));
}
async function load(){
 request?.abort();const current=new AbortController();request=current;$('load-status').textContent='正在读取项目数据…';
 const q=new URLSearchParams();for(const k of keys)if(params.get(k))q.set(k,params.get(k));
 try{const r=await fetch('/api/industry?'+q,{signal:current.signal});if(!r.ok)throw Error(r.status===404?'未找到对应的项目或主体。':r.status===400?'筛选条件无效，请重置后重试。':'项目数据暂时无法读取。');const value=await r.json();if(request!==current)return;data=value;$('load-status').textContent='';render();}
 catch(e){if(e.name==='AbortError')return;$('load-status').innerHTML=esc(e.message)+' <a href="/">返回行业总览</a>';}
}
fetch('/assets/world.geo.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(value=>{geo=value;if(data)renderMap();}).catch(()=>{$('map-selection').textContent='地图底图暂不可用，请点击布局明细查看项目。';});
load();
})();
