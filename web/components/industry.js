/* Industry entry, filtered drilldowns and source-backed project details. */
(() => {
'use strict';
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
const num=v=>Number(v).toLocaleString('en-US',{maximumFractionDigits:2}), gw=v=>num(v/1000), money=v=>v>=1000?'$'+num(v/1000)+'T':'$'+num(v)+'B';
const path=location.pathname, isProject=path==='/project.html', isMarket=path==='/market.html', isList=path==='/projects.html', isRegions=path==='/regions.html', isCompany=path==='/industry.html';
const isHome=['/','/index.html'].includes(path);
// These aliases share the reader shell and its optional cached font reuse.
const isReader=isHome||isProject||isMarket||isList||isRegions||isCompany;
if(isHome)document.body.classList.add('industry-home');
let params=new URLSearchParams(location.search), data=null, geo=null, news=null, request=null, view=[0,0,1000,490];
let detailGeo=null;
const adminTiles=new Map(),detailLoads=new Map(),detailFailures=new Set();
let highlightedCompany='', selectedSite='', pinned=false, newsFailed=false, mapSignature='';
const keys=['c','region','stage','relation','scope','role','site','country','province','city','address','q'];
let fontCacheQueued=false,fontCacheStarted=false;
function useCachedFonts(){
 const link=$('home-fonts');
 if(!isReader||!link||fontCacheStarted)return;
 if(!link.sheet){
  link.addEventListener('load',useCachedFonts,{once:true});
  link.addEventListener('error',()=>{link.dataset.fonts='fallback';},{once:true});
  return;
 }
 fontCacheStarted=true;
 // Match the operations page: inactive shared CSS supplies descriptors only.
 // Cold cache misses never download font files or compete with public data.
 Promise.all(Array.from(link.sheet.cssRules).filter(r=>r.type===CSSRule.FONT_FACE_RULE).map(async rule=>{
  try{
   const source=rule.style.getPropertyValue('src').match(/url\(["']?(\.\/[a-z0-9-]+\.woff2)["']?\)/i);
   if(!source)return false;
   const response=await fetch(new URL(source[1],link.href),{cache:'only-if-cached',mode:'same-origin'});
   if(!response.ok)return false;
   const face=new FontFace(rule.style.getPropertyValue('font-family').replace(/^["']|["']$/g,''),await response.arrayBuffer(),{
    weight:rule.style.getPropertyValue('font-weight'),style:rule.style.getPropertyValue('font-style'),
    unicodeRange:rule.style.getPropertyValue('unicode-range')||'U+0-10FFFF',display:'swap'
   });
   await face.load();document.fonts.add(face);return true;
  }catch(e){return false;}
 })).then(results=>{link.dataset.fonts=results.some(Boolean)?'cached':'fallback';if(isHome)resizeUpdates();});
}
function queueCachedFonts(){
 if(!isReader||fontCacheQueued||!data||(isHome&&(!geo||!news&&!newsFailed)))return;
 fontCacheQueued=true;
 // Reader content is already rendered; font reuse remains optional work.
 if(window.requestIdleCallback)requestIdleCallback(useCachedFonts);else setTimeout(useCachedFonts,0);
}
function url(page, changes={}) {const q=new URLSearchParams(params);for(const [k,v] of Object.entries(changes))v?q.set(k,v):q.delete(k);return page+(q.size?'?'+q:'');}
function name(id){const c=data?.companies.find(c=>c.company_id===id);return c?.name_cn||c?.name||id;}
function companyLink(id){return `<a href="${esc(url('/industry.html',{c:id,site:'',stage:''}))}">${esc(name(id))}</a>`;}
function participantProfiles(p){
 const ids=[...new Set([...p.developer,...p.tenant])];
 const profiles=ids.map(id=>{const c=data.companies.find(c=>c.company_id===id);return c?.profile?`<p>${companyLink(id)}：${esc(c.profile)}</p>`:'';}).filter(Boolean);
 return profiles.length?`<h3>参与主体的业务</h3>${profiles.join('')}<p class="basis">公司业务与本园区角色分别核验；业务说明不证明资产所有权或已签租约。</p>`:'';
}
function countryName(code){
 try{return code?new Intl.DisplayNames(['zh-CN'],{type:'region'}).of(code):'';}catch{return code||'';}
}
function projectGeography(p){
 const g=p.geography||{};
 return [countryName(p.country),g.province,g.regional_address||p.location].filter(Boolean).map(esc).join(' · ');
}
function participantRoles(p){
 return (p.participants||[]).map(r=>`<div><span class="basis">${esc(r.label)}：</span>${r.company_ids.map(companyLink).join('、')}</div>`).join('')||'角色待核实';
}
function plannedCapacity(p){
 const planned=p.capacity_register?.planned?.quantity;
 if(planned!=null)return quantityText(planned);
 const legacy=stageCapacity(p,'planning');
 return legacy;
}
let tableNotes=[];
function tableNote(body,label,marker='注'){
 const number=tableNotes.push({body,label});
 return `<button type="button" class="table-note" data-note="${number-1}" aria-label="${esc(label)}"><sup>${esc(marker)}</sup></button>`;
}
function tableParticipant(p,roles){
 const known=(p.participants||[]).filter(r=>roles.includes(r.role)).flatMap(r=>r.company_ids.filter(id=>id!=='multiple').map(id=>({id,label:r.label})));
 if(!known.length)return '';
 const first=known[0];
 const extra=new Set(known.map(r=>r.id)).size-1;
 return `${companyLink(first.id)}${tableNote(participantRoles(p),`${p.name}的主体与角色${extra?'，另有其他主体':''}`,extra?'+'+extra:'注')}<small>${esc(first.label)}</small>`;
}
function tableCapacity(p,kind){
 const value=kind==='planned'?plannedCapacity(p):stageCapacity(p,'operating');
 const boundary=kind==='planned'&&p.capacity_register?.planned?.quantity==null&&value!=='未披露'
  ?'<p>此值是已登记规划分期，园区规划总量尚待核实；不与投运容量相加或相减。</p>':'';
 return esc(value)+tableNote(boundary+capacityProvenance(p)+(p.capacity_estimated?capacityEstimate(p):''),`${p.name}的${kind==='planned'?'规划':'投运'}容量依据`);
}
function tableInformationTime(p){
 const values=[...new Set(Object.values(p.capacity_register||{}).map(r=>r.effective_at).filter(Boolean))];
 return values.map(esc).join('<br>')+tableNote(capacityProvenance(p),`${p.name}的信息时间、来源与披露备注`);
}
function capacityProvenance(p){
 const register=p.capacity_register||{};
 return [['planned','规划'],['operating','投运']].map(([key,label])=>{
  const r=register[key]||{},sources=r.sources||[];
  const published=[...new Set((r.source_versions||[]).map(s=>s.published_at).filter(Boolean))];
  return `<div><strong>${label}</strong><br>信息时间：${esc(r.effective_at||'未知')}<br>披露时间：${esc(published.join('、')||'未知')}<br>${sources.map(s=>sourceLink(s.url,s.note||'原始来源')+(s.date?' · 来源标注日期 '+esc(s.date):'')).join('<br>')||'来源待补'}</div>`;
 }).join('');
}
function capacityReviewDate(p){
 const dates=Object.values(p.capacity_register||{}).map(r=>r.reviewed_at).filter(Boolean).sort();
 return dates.length?dates.at(-1).slice(0,10):'未登记';
}
function resourceMetrics(p){
 const rows=Object.entries(p.resource_metrics||{});
 return rows.length?`<section class="detail-card"><h2>其他信息 · 水与电</h2>${rows.map(([key,value])=>`<p>${esc(resourceMetricLabels[key]||key)}：${esc(resourceMetricText(value))}</p>`).join('')}<p class="basis">按各自期间及边界记录；缺少水电数据不影响园区登记。</p></section>`:'';
}
function quantityText(value){
 if(value==null)return '未披露';
 if(typeof value==='number')return num(value)+' MW';
 if(Array.isArray(value.value_range))return value.value_range.map(num).join('–')+' '+value.unit;
 if(typeof value.value==='number')return num(value.value)+' '+value.unit;
 return '未披露';
}
function capacityText(p){
 const ranges=p.capacity_ranges||[],parts=[];
 if(p.capacity_known)parts.push(`${p.capacity_estimated?'约 ':''}${num(p.total_mw)} MW${ranges.length?' 已知值合计':'（各阶段合计）'}`);
 if(ranges.length)parts.push(ranges.map(r=>`${data.stages[r.stage]||'IT 容量'} ${quantityText(r)}`).join(' / '));
 return parts.join('；')||'IT 容量未披露';
}
function stageCapacity(p,stage){
 const ranges=(p.capacity_ranges||[]).filter(r=>r.stage===stage),parts=[];
 if((p.phases||[]).some(phase=>phase.stage===stage))parts.push(num(p.capacity[stage])+' MW');
 parts.push(...ranges.map(quantityText));return parts.join(' + ')||'未披露';
}
function rangeNotes(p){return (p.capacity_ranges||[]).map(r=>`<p class="basis">区间依据：${esc([r.basis,...r.assumptions||[]].filter(Boolean).join('；'))}</p>`).join('');}
function capacityEstimate(p){
 const a=p.capacity_assessment||{};
 if(!p.capacity_estimated)return '';
 const stages=[['operating','运营'],['construction','建设中'],['planning','筹备']].map(([stage,label])=>{const amount=stageCapacity(p,stage);return label+(amount==='未披露'?amount:'约 '+amount+' IT');}).join(' / ');
 return `<section class="detail-card" id="capacity-estimate"><h2>参考估算 · 持续更新</h2>${p.capacity_ranged?`<p>${esc(capacityText(p))} IT</p>${rangeNotes(p)}`:`<p>${esc(stages)}</p>`}<p>${esc(a.basis_note||'估算方法待补')}</p><p>有效时点：${esc(a.as_of||'待补')} · 记录日期：${esc(a.recorded_at||'待补')} · 状态：${a.status==='reviewed'?'已审估算':'暂估待细化'}</p><p>待补：${(a.missing_conditions||[]).map(esc).join('；')||'无已登记缺项'}</p></section>`;
}
function projectDossier(p){
 const pending='待查；未登记不表示不存在';
 const actors=(p.developer||[]).map(id=>`<a href="/product-catalog.html?c=${encodeURIComponent(id)}">${esc(name(id))}</a>`).join('、');
 const users=(p.tenant||[]).map(id=>`<a href="/product-catalog.html?c=${encodeURIComponent(id)}">${esc(name(id))}</a>`).join('、');
 const rows=[
  ['物理地点与边界',projectGeography(p),'地块编号、红线、占地面积、建筑及各分期边界待核实；同城不自动合并'],
  ['主体与角色',participantRoles(p),'土地权利人、资产所有者、开发方、设计方、EPC／总包、运营方、直接承租方及最终使用者分别记录；辖区政府不自动视为地主，不从公司类型推断角色'],
  ['开发、建设与运营',actors||'待查','同一公司可兼任多个角色；自建须分别有开发和使用关系的依据'],
  ['使用方与租赁',users||'待查','此处为已登记使用关系；自建、整租、托管、租约容量及最终工作负载另待核实'],
  ['电源、输配电与接入',esc(p.power_status||p.utility||pending),'发电方、售电／PPA方、电网方、接电合同主体与实际送电分开；既有 utility 标签不是角色核验'],
  ['水源、供水与冷却','待查','原水／再生水、水务运营方、取水及排放配额、冷却方案分别核验'],
  ['网络连接','待查','运营商、光纤路线、接入权、带宽及实际交付待核实'],
  ['审批与约束',esc(p.stage_label),'阶段是当前登记摘要；用地、规划、环评、建设、电水审批机关与批准范围分别待核实'],
  ['规划与投运',`规划：${esc(plannedCapacity(p))}<br>投运：${esc(stageCapacity(p,'operating'))}`,'IT、设施功率、接电额度、发电 MW 分开。规划为明确披露的园区总量；规划分期不冒充总量。未投运不等于在建，暂停及取消单独记录'],
  ['设备与系统','待查','设施、电力、冷却、IT、控制与软件按现行骨架登记现场配置，不套用通用 BOM'],
  ['投资、融资与合同',(p.participants||[]).filter(r=>['investor','lender','borrower','guarantor','lessor'].includes(r.role)).map(r=>`${esc(r.label)}：${r.company_ids.map(companyLink).join('、')}`).join('<br>')||'待查','股权出资不自动等于资产所有权；贷款方、借款主体、担保方、租约对手及实际支付分别核验'],
  ['时间、运行与证据',capacityProvenance(p)+`<p>容量最后核实：${esc(capacityReviewDate(p))}</p>`,'观测有效时间、来源披露时间、首次接收时间及人工核实时间分开；核实日期不冒充事实日期']
 ];
 return `<section class="detail-card" id="project-dossier"><h2>完整园区档案 · 逐项补齐</h2><p>消息先登记到事件线索，逐项核验后补充本档案。一个主体可承担多个角色，各角色可由不同主体承担；缺项保留待查。下列是园区档案的字段展示，可交叉引用同一观察；通用研究与园区共用的可扩展覆盖检查见<a href="/tasks.html#observation-coverage">现行观察清单</a>。</p><div class="table-wrap"><table><thead><tr><th>档案字段主题</th><th>已有登记</th><th>需要继续核实</th></tr></thead><tbody>${rows.map(([label,value,gap])=>`<tr><th>${label}</th><td>${value}</td><td>${gap}</td></tr>`).join('')}</tbody></table></div><p><a href="${esc(url('/projects.html',{view:'pipeline'}))}">查看相关消息与待核验线索 →</a></p></section>`;
}
function sourceLink(source,label){const href=safe(source);return href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`:esc(label);}
function selection(){return {company:params.get('c')||'',region:params.get('region')||'',country:data?.filters?.country||'',province:data?.filters?.province||'',address:data?.filters?.address||'',city:data?.filters?.city||'',q:data?.filters?.q||'',site:params.get('site')||'',scope:params.get('scope')||'',relation:params.get('relation')||'',role:params.get('role')||'',siteIds:data?.rows.filter(p=>!p.portfolio).map(p=>p.site_id)||[]};}
function select(changes){for(const [k,v] of Object.entries(changes))v?params.set(k,v):params.delete(k);history.pushState(null,'',url(path));load();}
window.addEventListener('popstate',()=>{params=new URLSearchParams(location.search);load();});
$('filters')?.addEventListener('submit',e=>e.preventDefault());
$('filters')?.addEventListener('change',e=>select({[e.target.name]:e.target.value,site:''}));
if($('stage-filter'))$('stage-filter').onchange=e=>select({stage:e.target.value});
if($('lead-state'))$('lead-state').onchange=renderPipeline;
window.addEventListener('inresearch:news-data',e=>{news=e.detail;newsFailed=false;renderPipeline();renderDaily();renderMap();});
window.addEventListener('inresearch:news-state',e=>{newsFailed=e.detail.status==='failed';renderPipeline();renderDaily();queueCachedFonts();});
window.addEventListener('inresearch:locate-news',e=>{const row=rawRecords().find(r=>r.id===e.detail.id);if(!validCoordinates(row?.coordinates))return;selectedSite='raw:'+row.id;pinned=false;view=[0,0,1000,490];setView();renderPopup();highlightMap();svg.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
if($('news-selection'))$('news-selection').onchange=e=>{document.querySelector('[data-datacenter-news]').dataset.newsSelection=e.target.value;window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:{...selection(),redraw:true}}));};
function filters(){
 if(!$('filters'))return;
 if((isList||isRegions)&&!$('geographic-filters')){
  const form=document.createElement('form');form.id='geographic-filters';form.className='geographic-filters';
  form.innerHTML=[['country','国家'],['province','省／州'],['city','城市'],['address','区域地址']].map(([key,label])=>`<label>${label}<select name="${key}" aria-label="${label}"></select></label>`).join('');
  form.onsubmit=e=>e.preventDefault();
  form.onchange=e=>select({[e.target.name]:e.target.value,site:'',...(e.target.name==='country'?{province:'',city:'',address:''}:e.target.name==='province'?{city:'',address:''}:{})});
  (isRegions?$('regions-detail'):$('project-rows')).before(form);
 }
 if(isList||isRegions){
  const facets=data.geographic_filters||{};
  for(const [key,values] of [['country',facets.countries],['province',facets.provinces],['city',facets.cities],['address',facets.addresses]]){
   const el=$('geographic-filters').elements[key];
   el.innerHTML='<option value="">全部</option>'+(values||[]).map(v=>`<option value="${esc(v)}">${esc(key==='country'?countryName(v):v)}</option>`).join('');
   el.value=params.get(key)||'';
  }
 }
 for(const key of ['region','c']){
  const element=$('filters').elements[key], values=key==='region'?data.regions.map(r=>[r.id,r.name]):data.companies.map(c=>[c.company_id,c.name_cn||c.name]);
  element.innerHTML=`<option value="">${key==='region'?'全球':'所有主体'}</option>`+values.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');
 }
 for(const key of ['region','scope','role','relation','c'])$('filters').elements[key].value=params.get(key)||'';
 $('stage-filter').value=params.get('stage')||'';
}
function renderStats(){
 if(!$('stats'))return;
 const noDisclosures=data.totals.sites>0&&data.totals.sites===data.totals.unknown,hasRanges=!!data.totals.ranged_sites;
 const labels={operating:'样本 · 已投运',construction:'样本 · 建设中',planning:'样本 · 筹备机会',unknown:'样本 · 容量未披露'};
 $('stats').innerHTML=Object.entries(labels).map(([s,label])=>`<a class="stat-link ${params.get('stage')===s?'active':''}" href="${esc(url('/projects.html',{stage:s,site:'',view:''}))}"><span>${label} ↗${s!=='unknown'&&data.totals.estimated?.[s]?` · 含参考估算 ${gw(data.totals.estimated[s])} GW`:''}</span><strong>${s==='unknown'?data.totals.unknown:noDisclosures||hasRanges&&!data.totals[s]?'—':gw(data.totals[s])}<small>${s==='unknown'?'项':'GW'}</small></strong><span>${s==='planning'?'含官宣、选址、电力与审批阶段':s==='unknown'?'仍在地图与明细中保留':s==='operating'?'已通电 / 满载，按分期计量':'已有开工 / 机电施工记录'}${s!=='unknown'&&data.totals.estimated?.[s]?` · 其中参考估算 ${gw(data.totals.estimated[s])} GW`:''}</span></a>`).join('');
 $('basis').textContent=`地图样本 ${data.totals.sites} 条项目记录，非全球总量 · 已知值合计：建设 + 筹备 ${gw(data.totals.construction+data.totals.planning)} GW${hasRanges?`；另有 ${data.totals.ranged_sites} 项容量以区间披露，见地图与明细，未计入确定值合计`:""} · 来源核对日期 ${data.coverage.oldest_verified}—${data.coverage.latest_verified}，非统一年末存量。点击数字查看明细与来源。`;
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
function validCoordinates(c){return Array.isArray(c)&&c.length===2&&c.every(Number.isFinite)&&Math.abs(c[0])<=90&&Math.abs(c[1])<=180;}
function rawRecords(){
 const f=selection();return (news?.raw_atlas?.records||[]).filter(r=>safe(r.url)&&(!f.company||(r.company_ids||[]).includes(f.company))&&(!f.site||r.site_id===f.site)&&(!f.region||r.region===f.region||f.siteIds.includes(r.site_id))&&(!(f.scope||f.role||f.relation)||f.siteIds.includes(r.site_id)));
}
function countryGroups(){
 const groups=new Map();for(const r of rawRecords().filter(r=>r.origin==='research_publication'&&r.location_precision==='country')){
  const key=r.country_code||r.country_mentions?.[0]?.code||r.location||r.id;
  if(!groups.has(key))groups.set(key,{key,coordinates:r.coordinates,items:[]});groups.get(key).items.push(r);
 }
 const labels=new Map((news?.raw_atlas?.country_groups||[]).map(g=>[g.country_code,g.country_name]));
 for(const g of groups.values()){g.name=labels.get(g.key)||g.items[0].location||g.key;try{if(/^[A-Z]{2}$/.test(g.key)&&!labels.has(g.key))g.name=new Intl.DisplayNames(['zh-CN'],{type:'region'}).of(g.key);}catch{}}
 return [...groups.values()].sort((a,b)=>b.items.length-a.items.length);
}
function renderResearch(){
 if(!isHome||!$('research-arrivals'))return;
 const rows=rawRecords().filter(r=>r.origin==='research_publication'),groups=countryGroups(),count=news?.raw_atlas?.research_total??rows.length;
 $('research-summary').textContent=news?`${num(count)} 条文章提取记录 · 当前筛选 ${rows.length} 条 · ${groups.length} 个国家级位置。容量、主体关系与来源日期保留原文；报道值与项目容量分别展示。`:'正在读取研究资料台账…';
 $('research-countries').innerHTML=groups.map(g=>validCoordinates(g.coordinates)?`<button type="button" data-research-country="${esc(g.key)}">${esc(g.name)} <strong>${g.items.length}</strong></button>`:`<a href="/research/data-centers-2026-projects.html">${esc(g.name)} <strong>${g.items.length}</strong> · 未定位</a>`).join('');
 for(const b of $('research-countries').querySelectorAll('button'))b.onclick=()=>{const group=countryGroups().find(g=>g.key===b.dataset.researchCountry);if(group)window.dispatchEvent(new CustomEvent('inresearch:locate-news',{detail:{id:group.items[0].id}}));};
}
function renderDaily(){
 if(isHome)queueCachedFonts();
}
function renderMap(){
 if(!geo)return;
 hideTooltip();
 if(!svg.querySelector('#map-land-layer')){
  svg.innerHTML='<g id="map-land-layer"></g><g id="map-news-layer"></g><g id="map-sites-layer"></g><g id="map-raw-layer"></g>';
  renderLand();
 }
 if(!data)return;
 const stage=params.get('stage'), rows=data.rows.filter(p=>!p.portfolio&&validCoordinates(p.coordinates));
 const signature=JSON.stringify([stage,rows]);
 if(signature!==mapSignature){
  mapSignature=signature;
  $('map-sites-layer').innerHTML=rows.map(p=>{
   const [x,y]=xy(p.coordinates[1],p.coordinates[0]),v=stage&&stage!=='unknown'?p.capacity[stage]:p.total_mw,r=p.capacity_known?Math.max(2.5,Math.sqrt(v)*.28):4;
   const main=stage&&stage!=='unknown'?stage:p.capacity_ranged?(p.capacity_ranges[0]?.stage||'planning'):Object.keys(data.stages).reduce((a,b)=>p.capacity[a]>=p.capacity[b]?a:b,'operating');
   const color={operating:'var(--ui-green)',construction:'var(--ui-yellow)',planning:'var(--ui-muted)'}[main];
   const shape=p.capacity_ranged?`<rect x="-5" y="-5" width="10" height="10" fill="${color}"/>`:p.capacity_known?`<circle cx="0" cy="0" r="${r}" fill="${color}"/>`:`<path d="M0,-4l4,4 -4,4 -4,-4Z" fill="var(--ui-surface)" stroke="var(--ui-muted)"/>`;
   return `<g class="site-point ${p.lifecycle&&p.lifecycle!=='active'?'inactive':''} ${p.capacity_ranged?'range-point':''}" data-x="${x}" data-y="${y}" transform="translate(${x} ${y}) scale(${view[2]/1000})" tabindex="0" role="button" aria-label="${esc(p.name)}：${esc(capacityText(p))}" data-id="${esc(p.site_id)}"><title>${esc(p.name)} · ${esc(p.location)} · ${esc(capacityText(p))}</title>${shape}</g>`;
  }).join('');
 }
 const leads=(news?.pipeline?.records||[]).filter(r=>r.site_id&&!['paused','cancelled'].includes(r.state)&&(!params.get('c')||(r.company_ids||[]).includes(params.get('c'))));
 const raw=rawRecords(),located=raw.filter(r=>validCoordinates(r.coordinates)),countries=countryGroups();
 $('map-news-layer').innerHTML=rows.filter(p=>leads.some(r=>r.site_id===p.site_id)||raw.some(r=>r.site_id===p.site_id)).map(p=>{const [x,y]=xy(p.coordinates[1],p.coordinates[0]);return `<g class="map-marker" data-x="${x}" data-y="${y}" transform="translate(${x} ${y}) scale(${view[2]/1000})"><circle class="news-ring" cx="0" cy="0" r="${Math.max(7,Math.sqrt(p.total_mw)*.28+4)}"/></g>`;}).join('');
 $('map-raw-layer').innerHTML=located.filter(r=>r.verification_status!=='project_adopted'&&!(r.origin==='research_publication'&&r.location_precision==='country')).map(r=>{const [x,y]=xy(r.coordinates[1],r.coordinates[0]);return `<g class="raw-point" data-raw-id="${esc(r.id)}" data-x="${x}" data-y="${y}" transform="translate(${x} ${y}) scale(${view[2]/1000})" tabindex="0" role="button" aria-label="新闻地点：${esc(r.title)}，待核验"><title>${esc(r.title)} · ${esc(r.location||r.location_precision||'报道地点')} · 待核验</title><path d="M0,-7 2,-2 7,0 2,2 0,7 -2,2 -7,0 -2,-2Z"/></g>`;}).join('')+countries.filter(g=>validCoordinates(g.coordinates)).map(g=>{const [x,y]=xy(g.coordinates[1],g.coordinates[0]);return `<g class="raw-point country-point" data-raw-id="${esc(g.items[0].id)}" data-country="${esc(g.key)}" data-x="${x}" data-y="${y}" transform="translate(${x} ${y}) scale(${view[2]/1000})" tabindex="0" role="button" aria-label="${esc(g.name)}：${g.items.length} 条文章资料，国家示意位置"><title>${esc(g.name)} · ${g.items.length} 条文章提取记录 · 国家示意，非园区坐标</title><circle r="11"/><text text-anchor="middle" dy="3.5">${g.items.length}</text></g>`;}).join('');
 if($('map-summary'))$('map-summary').textContent=`${rows.length} 条项目记录已定位 · ${data.rows.filter(p=>!p.portfolio&&!validCoordinates(p.coordinates)).length} 个项目未定位 · 当前新闻快照 ${located.length} 条有地点、${raw.length-located.length} 条未定位${news?.raw_atlas?.truncated?'（有界展示）':''}；新闻地点精度见浮窗。`;
 $('layout-link').href=url('/projects.html',{site:''});$('map-title').textContent=data.company?`${name(data.company.company_id)} · 全球布局`:'全球项目布局';
 for(const el of svg.querySelectorAll('[data-id],[data-raw-id]')){
  const id=el.dataset.id||'raw:'+el.dataset.rawId;
  const activate=()=>{if(pinned&&selectedSite!==id)return;selectedSite=id;renderPopup();highlightMap();};
  if(isHome){
   const title=el.querySelector('title');el.dataset.tooltip=title?.textContent||el.dataset.tooltip||el.getAttribute('aria-label');title?.remove();
   el.onpointerenter=el.onpointermove=e=>{if(e.pointerType==='mouse'&&!drag)showTooltip(el,e);};
   el.onpointerleave=hideTooltip;el.onfocus=()=>{if(!restoringFocus)showTooltip(el);};el.onblur=hideTooltip;
  }else{
   el.onpointerenter=e=>{if(e.pointerType==='mouse'&&!drag){clearTimeout(hoverTimer);hovering=true;activate();}};
   el.onpointerleave=()=>scheduleHoverClose();el.onfocus=()=>{if(restoringFocus)return;clearTimeout(hoverTimer);hovering=true;activate();};
   el.onblur=e=>{if(!popup.contains(e.relatedTarget)){hovering=true;scheduleHoverClose();}};
  }
  el.onclick=()=>{hideTooltip();hovering=false;clearTimeout(hoverTimer);activate();};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();hideTooltip();hovering=false;clearTimeout(hoverTimer);activate();}};
 }
 highlightMap();renderPopup();queueCachedFonts();
}
function renderLand(){
 const source=detailGeo||geo;if(!source)return;
 const path=(line,closed)=>line.map(([lo,la],i)=>`${i?'L':'M'}${xy(lo,la).map(n=>n.toFixed(detailGeo?3:1)).join(',')}`).join('')+(closed?'Z':'');
 let land='',boundaries='';
 for(const f of [...source.features,...[...adminTiles.values()].flatMap(tile=>tile.features)]){
  const g=f.geometry;if(!g)continue;
  if(['Polygon','MultiPolygon'].includes(g.type)){
   const polygons=g.type==='Polygon'?[g.coordinates]:g.coordinates;
   land+=`<path class="land" fill-rule="evenodd" d="${polygons.map(p=>p.map(r=>path(r,true)).join('')).join('')}"/>`;
  }else if(f.properties?.layer==='admin1'&&['LineString','MultiLineString'].includes(g.type)){
   boundaries+=(g.type==='LineString'?[g.coordinates]:g.coordinates).map(r=>path(r,false)).join('');
  }
 }
 svg.querySelector('#map-land-layer').innerHTML=land+(boundaries?`<path class="admin1-boundaries" d="${boundaries}"/>`:'')+atlasBackdrop();
 svg.dataset.detail=detailGeo?'true':'false';syncMapDetail();
}
function requiredMapParts(){
 if(view[2]>650)return [];
 const parts=['world'];
 if(view[2]<=500){
  const first=Math.max(0,Math.min(11,Math.floor(view[0]/1000*12))),last=Math.max(0,Math.min(11,Math.floor((view[0]+view[2])/1000*12)));
  for(let i=first;i<=last;i++)parts.push(String(i));
 }
 return parts;
}
function mapPartReady(key){return key==='world'?!!detailGeo:adminTiles.has(key);}
function mapDetailStatus(){
 const parts=requiredMapParts(),missing=parts.filter(key=>!mapPartReady(key));
 let status=$('map-detail-status');
 if(!missing.length){if(status)status.hidden=true;return;}
 if(!status){status=document.createElement('button');status.id='map-detail-status';status.type='button';status.setAttribute('aria-live','polite');status.onclick=()=>{for(const key of requiredMapParts())detailFailures.delete(key);syncMapDetail();};svg.parentElement.append(status);}
 const loading=missing.some(key=>detailLoads.has(key));
 status.hidden=false;status.disabled=loading;status.textContent=loading?'正在加载精细底图…':'精细底图暂不可用 · 点击重试';
}
function syncMapDetail(){
 svg.classList.toggle('show-admin1',view[2]<=500);
 for(const key of requiredMapParts()){
  if(mapPartReady(key)||detailLoads.has(key)||detailFailures.has(key))continue;
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
  const url=key==='world'?'/assets/world-detail.geo.json':`/assets/map-admin1-${key}.geo.json`;
  detailLoads.set(key,fetch(url,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(value=>{
   if(value.type!=='FeatureCollection'||!Array.isArray(value.features)||!value.features.every(f=>f.geometry&&f.properties?.layer===(key==='world'?'country':'admin1'))||(key==='world'&&!value.features.length))throw Error();
   if(key==='world')detailGeo=value;else adminTiles.set(key,value);
   detailFailures.delete(key);renderLand();
  }).catch(()=>detailFailures.add(key)).finally(()=>{clearTimeout(timer);detailLoads.delete(key);mapDetailStatus();}));
 }
 mapDetailStatus();
}
function atlasBackdrop(){
 const lines=[];
 for(let lon=-180;lon<=180;lon+=30){const x=xy(lon,0)[0];lines.push(`<path d="M${x} 0V490"/><text x="${x+4}" y="16">${Math.abs(lon)}°${lon<0?'W':lon>0?'E':''}</text>`);}
 for(let lat=-60;lat<=60;lat+=30){const y=xy(0,lat)[1];lines.push(`<path d="M0 ${y}H1000"/><text x="6" y="${y-5}">${Math.abs(lat)}°${lat<0?'S':lat>0?'N':''}</text>`);}
 return `<g class="atlas-grid" aria-hidden="true">${lines.join('')}</g>`;
}
const svg=$('world-map');function setView(){hideTooltip();svg.setAttribute('viewBox',view.join(' '));for(const el of svg.querySelectorAll('[data-x]'))el.setAttribute('transform',`translate(${el.dataset.x} ${el.dataset.y}) scale(${view[2]/1000})`);positionPopup();syncMapDetail();}function zoom(f){const w=Math.max(140,Math.min(1000,view[2]*f)),h=w*.49;view=[view[0]+(view[2]-w)/2,view[1]+(view[3]-h)/2,w,h];setView();}
$('zoom-in').onclick=()=>zoom(.65);$('zoom-out').onclick=()=>zoom(1/.65);$('zoom-reset').onclick=()=>{view=[0,0,1000,490];setView();};
let drag;svg.addEventListener('pointerdown',e=>{hideTooltip();if(e.target.closest('[data-id],[data-raw-id]'))return;drag={x:e.clientX,y:e.clientY,view:[...view]};svg.setPointerCapture(e.pointerId);});
svg.addEventListener('pointermove',e=>{if(!drag)return;const k=view[2]/svg.getBoundingClientRect().width;view=[drag.view[0]-(e.clientX-drag.x)*k,drag.view[1]-(e.clientY-drag.y)*k,view[2],view[3]];setView();});
svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);
const popup=document.createElement('section');
popup.id='map-popup';popup.className='map-popup';popup.hidden=true;popup.setAttribute('role','dialog');popup.setAttribute('aria-label','园区信息');
svg.parentElement.append(popup);
const tooltip=isHome?document.createElement('div'):null;
if(tooltip){tooltip.id='map-tooltip';tooltip.className='map-tooltip';tooltip.hidden=true;tooltip.setAttribute('role','tooltip');svg.parentElement.append(tooltip);}
let tooltipAnchor=null;
function hideTooltip(){if(!tooltip)return;tooltip.hidden=true;tooltipAnchor?.removeAttribute('aria-describedby');tooltipAnchor=null;}
function showTooltip(point,event){
 if(!tooltip||!popup.hidden)return;
 if(tooltipAnchor!==point)hideTooltip();tooltipAnchor=point;
 tooltip.textContent=point.dataset.tooltip;tooltip.hidden=false;point.setAttribute('aria-describedby',tooltip.id);
 const frame=svg.parentElement,box=frame.getBoundingClientRect(),anchor=point.getBoundingClientRect();
 const x=(Number.isFinite(event?.clientX)?event.clientX:(anchor.left+anchor.right)/2)-box.left-frame.clientLeft;
 const y=(Number.isFinite(event?.clientY)?event.clientY:(anchor.top+anchor.bottom)/2)-box.top-frame.clientTop;
 const width=tooltip.offsetWidth,height=tooltip.offsetHeight;
 const left=x+12+width<=frame.clientWidth-8?x+12:x-width-12;
 const top=y+12+height<=frame.clientHeight-8?y+12:y-height-12;
 tooltip.style.left=Math.max(8,Math.min(frame.clientWidth-width-8,left))+'px';
 tooltip.style.top=Math.max(8,Math.min(frame.clientHeight-height-8,top))+'px';
}
let hoverTimer,hovering=false,restoringFocus=false;
function scheduleHoverClose(){clearTimeout(hoverTimer);if(hovering&&!pinned)hoverTimer=setTimeout(()=>closePopup(),200);}
popup.onpointerenter=()=>clearTimeout(hoverTimer);popup.onpointerleave=scheduleHoverClose;popup.onfocusin=()=>clearTimeout(hoverTimer);popup.onfocusout=e=>{if(!popup.contains(e.relatedTarget))scheduleHoverClose();};
function closePopup(focus=false){hideTooltip();clearTimeout(hoverTimer);hovering=false;const id=selectedSite;selectedSite='';pinned=false;popup.hidden=true;highlightMap();if(focus){restoringFocus=true;[...svg.querySelectorAll('[data-id],[data-raw-id]')].find(p=>p.dataset.id===id||'raw:'+p.dataset.rawId===id)?.focus();restoringFocus=false;}}
function positionPopup(){
 if(popup.hidden)return;
 const raw=rawRecords().find(r=>'raw:'+r.id===selectedSite),group=raw?.origin==='research_publication'&&raw.location_precision==='country'?countryGroups().find(g=>g.items.some(r=>r.id===raw.id)):null;
 const point=[...svg.querySelectorAll('[data-id],[data-raw-id]')].find(p=>p.dataset.id===selectedSite||'raw:'+p.dataset.rawId===selectedSite||group&&p.dataset.country===group.key);if(!point)return;
 const frame=svg.parentElement.getBoundingClientRect(),r=point.getBoundingClientRect();
 const right=r.right-frame.left+12,left=r.left-frame.left-popup.offsetWidth-12;
 const x=right+popup.offsetWidth<=frame.width-8?right:left>=8?left:Math.max(8,Math.min(frame.width-popup.offsetWidth-8,right));
 const overlaps=x<r.right-frame.left&&x+popup.offsetWidth>r.left-frame.left;
 const y=overlaps?(r.bottom-frame.top+12+popup.offsetHeight<=frame.height-8?r.bottom-frame.top+12:r.top-frame.top-popup.offsetHeight-12):r.top-frame.top;
 popup.style.left=x+'px';popup.style.top=Math.max(8,Math.min(frame.height-popup.offsetHeight-8,y))+'px';
}
function renderPopup(){
 if(!selectedSite)return;
 hideTooltip();
 const raw=selectedSite.startsWith('raw:')?rawRecords().find(r=>r.id===selectedSite.slice(4)):null;
 if(selectedSite.startsWith('raw:')){
  if(!raw){closePopup();return;}
  const group=raw.origin==='research_publication'&&raw.location_precision==='country'?countryGroups().find(g=>g.items.some(r=>r.id===raw.id)):null;
  const capacities=(raw.capacity_observations||[]).slice(0,3).map(o=>`${esc(o.quoted_value||num(o.mw)+' MW')} · ${o.basis==='it'?'IT 报道值':o.basis==='facility_or_grid'?'设施 / 电网口径':'口径待核验'}`).join('<br>');
  popup.innerHTML=`<div class="popup-actions"><button id="pin-site" type="button" aria-pressed="${pinned}">${pinned?'取消固定':'固定浮窗'}</button><button id="close-site" type="button" aria-label="关闭园区信息">×</button></div><strong>${esc(group?group.name+' · '+group.items.length+' 条文章提取记录':raw.title)}</strong><p class="raw-badge">${raw.origin==='research_publication'?'研究资料中的项目 · 来源报道口径':'新闻观察 · 来源报道口径'}</p><p>${esc(raw.location||'报道地点')} · ${raw.location_precision==='country'?'国家级示意，非城市或园区位置':raw.location_precision==='site'?'关联项目登记坐标':esc(raw.location_precision||'位置精度待补充')}</p>${group?`<p>${group.items.slice(0,4).map(r=>esc(r.title)+(r.capacity_text?'：'+esc(r.capacity_text):'')).join('<br>')}</p><p><a href="/research/data-centers-2026-projects.html">查看文章项目台账与来源 →</a></p>`:''}<p>${capacities||esc(raw.capacity_text)||'容量未披露'}<br>报道数字不并入项目 IT 容量。</p><p>${(raw.company_ids||[]).map(name).map(esc).join('、')||'主体待关联'}</p><a href="${esc(safe(raw.url))}" target="_blank" rel="noopener noreferrer">阅读原始报道 →</a>${raw.site_id?`<p><a href="${esc(url('/project.html',{site:raw.site_id}))}">查看关联项目 →</a></p>`:''}`;
  popup.hidden=false;$('pin-site').onclick=()=>{pinned=!pinned;renderPopup();};$('close-site').onclick=()=>closePopup(true);positionPopup();return;
 }
 const p=data.rows.find(p=>p.site_id===selectedSite);if(!p){closePopup();return;}
 const focused=popup.contains(document.activeElement)?document.activeElement.id:null;
 popup.innerHTML=`<div class="popup-actions"><button id="pin-site" type="button" aria-pressed="${pinned}">${pinned?'取消固定':'固定浮窗'}</button><button id="close-site" type="button" aria-label="关闭园区信息">×</button></div><strong>${esc(p.name)}</strong><p>${esc(p.location)} · ${esc(p.stage_label)}</p><p>${esc(capacityText(p))}</p>${p.capacity_estimated?`<p>参考估算 · 观测时点 ${esc(p.capacity_assessment?.as_of||'待补')}<br>${esc(p.capacity_assessment?.basis_note||'估算方法见项目明细')}</p>`:''}<p>开发：${p.developer.map(name).map(esc).join('、')||'未登记'}<br>使用：${p.tenant.map(name).map(esc).join('、')||'未登记'}</p><p>来源核对 ${esc(p.verified_date||'日期未登记')}<br>分期按来源口径${p.capacity_ranged?'；区间未取中点':''}</p><a href="${esc(siteURL(p))}">查看项目与来源 →</a>`;
 popup.hidden=false;$('pin-site').onclick=()=>{pinned=!pinned;renderPopup();};$('close-site').onclick=()=>closePopup(true);
 if(focused)$(focused)?.focus();positionPopup();
}
function highlightMap(){
 let count=0,unlocated=0;
 for(const el of svg.querySelectorAll('[data-raw-id]')){const r=rawRecords().find(r=>r.id===el.dataset.rawId),group=el.dataset.country?countryGroups().find(g=>g.key===el.dataset.country):null,matched=highlightedCompany&&(group?group.items.some(r=>(r.company_ids||[]).includes(highlightedCompany)):(r?.company_ids||[]).includes(highlightedCompany));el.classList.toggle('highlighted',!!matched);el.classList.toggle('dimmed',!!highlightedCompany&&!matched);el.classList.toggle('selected',selectedSite==='raw:'+el.dataset.rawId);}
 for(const p of data?.rows||[])if(!p.portfolio&&highlightedCompany&&[...p.developer,...p.tenant].includes(highlightedCompany)){if(p.coordinates)count++;else unlocated++;}
 for(const el of svg.querySelectorAll('[data-id]')){const p=data.rows.find(p=>p.site_id===el.dataset.id),matched=highlightedCompany&&[...p.developer,...p.tenant].includes(highlightedCompany);el.classList.toggle('highlighted',!!matched);el.classList.toggle('dimmed',!!highlightedCompany&&!matched);el.classList.toggle('selected',selectedSite===p.site_id);el.setAttribute('aria-pressed',String(selectedSite===p.site_id));}
 if(isHome){
  document.querySelectorAll('#company-chips [data-company],#leaders [data-company]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.company===highlightedCompany)));
  $('map-selection').textContent=highlightedCompany?`${name(highlightedCompany)} · ${count} 个已定位项目${unlocated?' · '+unlocated+' 项未定位':''} · ${rawRecords().filter(r=>(r.company_ids||[]).includes(highlightedCompany)).length} 条资料提及`:'悬停看简要信息 · 点击查看详情';
 }
}
function highlightCompany(id){highlightedCompany=highlightedCompany===id?'':id;highlightMap();}
document.addEventListener('pointerdown',e=>{if(!pinned&&!popup.contains(e.target)&&!e.target.closest('[data-id],[data-raw-id]'))closePopup();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(tooltip&&!tooltip.hidden){e.preventDefault();hideTooltip();}if(!popup.hidden){e.preventDefault();closePopup(true);}}});
window.addEventListener('resize',()=>{hideTooltip();positionPopup();});
function renderCompanies(){
 const ids=[...new Set(['amazon','microsoft','alphabet-google','meta','oracle','bytedance','alibaba',...data.leaders.map(c=>c.company_id)])].filter(id=>data.companies.some(c=>c.company_id===id)).slice(0,isHome?7:10);
 $('company-chips').innerHTML=`<button type="button" data-company="" aria-pressed="${!(isHome?highlightedCompany:params.get('c'))}">${isHome?'清除高亮':'全部'}</button>`+ids.map(id=>`<button type="button" data-company="${esc(id)}" aria-pressed="${(isHome?highlightedCompany:params.get('c'))===id}">${esc(id==='amazon'?'Amazon / AWS':id==='bytedance'?'ByteDance / TikTok':id==='alibaba'?'Alibaba / 阿里云':name(id))}</button>`).join('');
 $('company-chips').querySelectorAll('button').forEach(b=>b.onclick=()=>isHome?highlightCompany(b.dataset.company):select({c:b.dataset.company,site:''}));
 const featured=['amazon','microsoft','alphabet-google','meta','oracle','bytedance','alibaba'];
 const leaders=[...data.leaders].sort((a,b)=>{const ai=featured.indexOf(a.company_id),bi=featured.indexOf(b.company_id);return (ai<0?99:ai)-(bi<0?99:bi);});
 if($('leaders'))$('leaders').innerHTML=leaders.slice(0,isHome?7:4).map(c=>`<${isHome?'button type="button" data-company="'+esc(c.company_id)+'" aria-pressed="'+(highlightedCompany===c.company_id)+'"':'a href="'+esc(url('/industry.html',{c:c.company_id,stage:'',site:''}))+'"'} class="leader"><strong>${esc(name(c.company_id))}${isHome?'':' ↗'}</strong><p>已登记的相关园区容量（含估算）</p><p class="leader-size">${c.totals.unknown===c.totals.sites?'容量未披露':c.totals.ranged_sites&&!c.totals.operating&&!c.totals.construction&&!c.totals.planning?'容量以区间披露':gw(c.totals.operating+c.totals.construction+c.totals.planning)+' GW'+(c.totals.ranged_sites?' + 区间':'')}</p><p>${c.totals.sites} 条相关项目 · ${c.totals.unknown} 项容量未披露${c.totals.ranged_sites?` · ${c.totals.ranged_sites} 项容量区间单列`:""}${c.totals.estimated_sites?` · 含参考估算 ${gw(Object.values(c.totals.estimated||{}).reduce((a,b)=>a+b,0))} GW`:''}</p><p>${c.totals.unknown===c.totals.sites?'已登记布局，容量有待来源补充。':`投运 ${gw(c.totals.operating)} / 建设 ${gw(c.totals.construction)} / 筹备 ${gw(c.totals.planning)} GW`}</p></${isHome?'button':'a'}>`).join('')||'<p class="empty">当前筛选下没有登记的主体关系。</p>';
 if(isHome&&$('company-coverage'))$('company-coverage').textContent='快捷查看 AWS、Microsoft、Google、Meta、Oracle、TikTok、Alibaba；样本有缺口，未登记不表示没有项目。';
 $('leaders')?.querySelectorAll('button').forEach(b=>b.onclick=()=>highlightCompany(b.dataset.company));
}
function renderTable(){
 if(!isList)return;
 const stage=params.get('stage'),rows=data.rows;
 tableNotes=[];
 $('list-title').textContent=`${data.stages[stage]|| (stage==='unknown'?'容量未披露':'项目明细')} · ${rows.length} 条记录`;
 const sorted=[...rows].sort((a,b)=>[a.country,a.geography?.province,a.geography?.regional_address,a.name].join('\u001f').localeCompare([b.country,b.geography?.province,b.geography?.regional_address,b.name].join('\u001f'),'zh-CN'));
 const body=sorted.map(p=>{
  const g=p.geography||{};
  const siteNotes=[p.stage_label,g.identity_scope==='cluster'?'集群记录，尚未拆到唯一地块':'',p.portfolio?'组合记录，不计总量':'',p.duplicate_of?'重复记录，不计总量':'',!p.coordinates?'未精确定位':'',p.disputed?'来源有争议':''].filter(Boolean).map(esc).join('；');
  return `<tr><td>${esc(countryName(p.country))}</td><td>${esc(g.province)}</td><td>${esc(g.regional_address||p.location)}</td><td><a href="${esc(siteURL(p))}">${esc(p.name)}</a>${g.identity_scope==='cluster'?'<small>跨园区集群</small>':p.portfolio?'<small>组合计划，不计地点容量</small>':'<small>地点登记，边界待逐项核实</small>'}${tableNote(`<p>${siteNotes}</p>`,`${p.name}的状态与地点边界`)}</td><td>${tableParticipant(p,['developer','builder','designer','owner','land_owner'])}</td><td>${tableParticipant(p,['tenant','end_user','operator'])}</td><td class="num">${tableCapacity(p,'planned')}</td><td class="num">${tableCapacity(p,'operating')}</td><td>${tableInformationTime(p)}</td><td>${esc(capacityReviewDate(p))}</td></tr>`;
 }).join('');
 $('project-rows').innerHTML=rows.length?`<div class="table-wrap"><table><thead><tr><th>国家</th><th>省／州</th><th>区域地址</th><th>园区</th><th>开发／建设</th><th>运营／使用</th><th class="num">规划 IT 容量</th><th class="num">已投运 IT 容量</th><th>信息时间</th><th>最后核实日期</th></tr></thead><tbody>${body}</tbody></table></div><dialog id="project-note"><button type="button" class="note-close" aria-label="关闭备注">×</button><h3></h3><div class="note-body"></div></dialog>`:'<p class="empty">没有匹配的项目。可放宽筛选；容量缺失不代表没有项目。</p>';
 const dialog=$('project-note');
 if(dialog){
  dialog.querySelector('.note-close').onclick=()=>dialog.close();
  $('project-rows').querySelectorAll('[data-note]').forEach(button=>button.onclick=()=>{
   const note=tableNotes[Number(button.dataset.note)];
   dialog.querySelector('h3').textContent=note.label;
   dialog.querySelector('.note-body').innerHTML=note.body;
   dialog.showModal();
  });
  dialog.onclick=e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}};
 }
}
function siteBridge(p,kind){
 const b=p.model_bridge;if(!b)return p.model_bridge_error?'<p>'+esc(p.model_bridge_error)+'</p>':'';
 const claims=kind==='equipment'?b.configurations:b.economic_candidates;
 const rows=claims.map(c=>`<tr><td>${esc(c.label)}</td><td>${esc(c.content||String(c.value)+' '+c.unit)}${c.quantity?'<br>'+esc(c.quantity.value+' '+c.quantity.unit):''}</td><td>候选 · ${esc(({reported:'来源描述',estimated:'第三方估算'})[c.measurement_kind])}<br>时间：${esc(c.effective_at||'待核对')}<br>范围：${esc(c.scope==='source_scope_not_aligned'?'与所选情景范围待对齐':c.scope)}</td><td>${sourceLink(c.source_url,'来源：'+c.locator)}<br>${esc(c.missing.join('；'))}<br>${esc(c.evidence_ids.join('；'))}${c.note?'<br>'+esc(c.note):''}${c.node?'<br><a href="/node.html?node='+encodeURIComponent(c.node)+'&col=1">通用构成说明 →</a>':''}</td></tr>`).join('');
 const coverage=b.coverage.map(c=>`<li>${esc(c.angle)} · ${esc(c.item)}：${esc(({adopted:'已有资料',candidate:'候选',excluded:'本情景排除',unknown:'未知',not_checked:'未检查'})[c.state])}；${esc(c.reason)}</li>`).join('');
 return `<h3>${kind==='equipment'?'现场配置映射':'园区情景与参数预览'}</h3><p>${esc(b.scope.label)} · ${esc(b.scope.accounting_basis)}。包含：${esc(b.scope.included)}；排除：${esc(b.scope.excluded)}。</p><p>已有资料：${esc(b.expected_it_mw)}MW第三方容量估算（${esc(b.capacity_source.effective_at)}），不代表实测负载。该规模与GPU数量共用配置假设，不是独立证据。以下候选尚未取得现场配置或模型采用资格。</p><div class="table-wrap"><table><thead><tr><th>内容</th><th>来源信息</th><th>状态与范围</th><th>依据与缺项</th></tr></thead><tbody>${rows}</tbody></table></div>${kind==='equipment'?'<details><summary>来源信息覆盖与去向</summary><ul>'+coverage+'</ul></details>':''}<p>${esc(b.dependency_notice.summary)} ${esc(b.dependency_notice.version_limit)}</p><details><summary>复核异常与推导关系</summary>${b.blockers.map(x=>'<p>'+esc(x.label)+'：'+esc(x.reason)+'（不自动填参）</p>').join('')}${b.review.derivations.map(x=>'<p>'+esc(x.id)+'：'+esc(x.input_item_ids.join(' + '))+' → '+esc(x.output_item_id)+'（候选）；'+esc(x.assumptions.join('；'))+'</p>').join('')}<p>${esc(b.review.limitations.join(' '))}</p></details>${kind==='equipment'?'<details><summary>设计、许可与图纸原件核对（'+b.document_checks.length+'项，可人工复核）</summary>'+b.document_checks.map(d=>'<h4>'+esc(d.label)+'</h4><p>'+esc(d.statement)+'</p><p>'+esc(d.boundary)+'</p>'+sourceLink(b.review.sources.find(x=>x.id===d.source_id).url,d.locator)).join('')+'<p>代理原件内容核对，不是人类批准、现场确认或模型认证。</p></details>':''}<p>未知：${esc(b.unknowns.join('；'))}。</p><a href="/ledger.html?view=basis&site=${encodeURIComponent(p.site_id)}&scope=${encodeURIComponent(b.scope.id)}">预览模型参数 →</a><p>确认后生成情景；候选不会自动填参，地区参考和用户假设分别标明。</p>`;
}
function renderDetail(){
 const p=data.detail;if(!isProject)return;
 const related=$('pipeline-section');if(related)$('detail').before(related);
 if(!p){$('page-title').textContent='园区详情';$('detail').innerHTML='<p class="empty">请从 <a href="/projects.html">园区名录</a> 选择一个登记对象。</p>';return;}
 const scope=p.geography?.identity_scope||'registered_site';
 const scopeLabel=scope==='portfolio'?'组合计划（不计地点容量）':scope==='cluster'?'跨园区集群（不等于一个物理园区）':'地点登记（物理边界仍须逐项核实）';
 const module=(id,title,body)=>`<section class="detail-card campus-module" id="campus-${id}" data-campus-module="${id}"><h2>${title}</h2>${body}</section>`;
 $('page-title').textContent=p.name;
 $('page-description').textContent=`${p.location||'位置待补'} · ${p.stage_label} · ${p.registration_status==='unverified'?'基础登记待查':'核验 '+(p.verified_date||'日期未登记')}`;
 const aliases=(p.aliases||[]).map(esc).join('、')||'未登记';
 const duplicate=p.duplicate_of?`<p>重复记录，已退出聚合。<a href="/project.html?site=${encodeURIComponent(p.duplicate_of)}">查看主记录 →</a><br>${esc(p.deduplication_note)}</p>`:'';
 const retained=(p.duplicate_records||[]).map(a=>`<p>${esc(a.note)} <a href="/project.html?site=${encodeURIComponent(a.site_id)}">查看保留记录 →</a></p>`).join('');
 const adopted=p.adoption?`<details open><summary>本批材料已用于此项目</summary><p>${esc(p.adoption.scope)}</p><p>已采用字段：${esc(p.adoption.fields.join('、'))}</p>${p.adoption.assertions.filter(x=>x.value!=null).map(x=>`<p>${num(x.value)} ${esc(x.unit)} · ${esc(({it:'IT容量',grid:'供电容量',facility:'设施功率'})[x.basis]||x.basis)} · ${esc(x.phase)}</p><blockquote>${esc(x.quote)}</blockquote>`).join('')}</details>`:'';
 const sections=[
 module('overview','园区概况与位置',`<dl><dt>稳定ID</dt><dd>${esc(p.site_id)}</dd><dt>登记范围</dt><dd>${esc(scopeLabel)}</dd><dt>别名</dt><dd>${aliases}</dd><dt>国家 / 区域 / 地点</dt><dd>${projectGeography(p)||'未登记'}</dd><dt>位置</dt><dd>${p.coordinates?esc(p.coordinates.join(', '))+'（登记坐标）':'仅有地区信息，未落精确坐标'}</dd><dt>坐标依据与精度</dt><dd>${esc(p.geography?.coordinate_source?.precision||'未登记精度；不据坐标推定园区边界')}</dd></dl>${duplicate}${retained}<p>${esc(p.notes||'')}</p>${p.disputed?'<p>此项目有来源争议，请对照历史与原始依据。</p>':''}`),
 module('phases','分期、楼栋与容量',`<h3>项目与分期</h3><dl><dt>规划 IT 容量</dt><dd>${esc(plannedCapacity(p))}</dd><dt>已投运 IT 容量</dt><dd>${esc(stageCapacity(p,'operating'))}</dd><dt>IT 容量</dt><dd>${esc(capacityText(p))}</dd><dt>设施总功率</dt><dd>${p.quantity_fields?.capacity_facility_mw!=null?esc(quantityText(p.quantity_fields.capacity_facility_mw))+'（不与 IT 容量相加）':p.capacity_facility_mw?num(p.capacity_facility_mw)+' MW（不与 IT 容量相加）':'未披露'}</dd></dl>${p.phases.map(x=>`<p><span class="badge">${esc(x.label)}</span>${num(x.mw)} MW</p>`).join('')}${rangeNotes(p)}${capacityEstimate(p)}<p class="basis">阶段容量不是楼栋清单。未披露的分期／楼栋边界留空；规划总量与分期、IT与接电容量不重复相加。</p>`),
 module('participants','参与主体与关系',`${participantRoles(p)}${participantProfiles(p)}<p>企业资料：${[...new Set((p.participants||[]).flatMap(r=>r.company_ids))].filter(id=>id!=='multiple').map(id=>`<a href="/product-catalog.html?c=${encodeURIComponent(id)}">${esc(name(id))}</a>`).join('、')||'主体待补'}</p><p class="basis">土地与产权、开发、设计、总包、运营、直接租户与最终使用方分别登记；同一公司可兼多职，未知的范围与期限不推断。企业详情与园区关系分别维护。</p>`),
 module('resources','电、水、网络与许可',`<dl><dt>电力进展</dt><dd>${esc(p.power_status||p.utility||'未登记')}</dd><dt>水源与冷却</dt><dd>按已披露水电指标查看；供应主体、许可与现场方案待逐项补齐。</dd><dt>网络连接</dt><dd>未披露的运营商、路线、合同与带宽保持未知。</dd><dt>许可与约束</dt><dd>建设阶段不证明审批齐备；批准机关、容量、适用分期与期限须有独立来源。</dd></dl>${resourceMetrics(p)}<p class="basis">发电、PPA、接入申请、接电合同与实际送电分别记录。</p>`),
 module('equipment','设备配置与运行',`${siteBridge(p,'equipment')}<p>现场设备型号、数量和工况尚未形成完整配置映射；不从通用图册补造现场安装。</p><nav class="local-nav"><a href="/node.html?col=1">了解通用组成 →</a><a href="/node.html?col=2">了解运行机制 →</a><a href="/bom.html">通用技术图册 →</a></nav><p class="basis">以上为通用知识入口，不表示本园区使用这些配置。</p>`),
 module('economics','投资与经济分析',`${siteBridge(p,'economics')}<p>${(p.participants||[]).filter(r=>['investor','lender','borrower','guarantor','lessor'].includes(r.role)).map(r=>esc(r.label)+'：'+r.company_ids.map(companyLink).join('、')).join('<br>')||'投资、融资与合同金额尚未登记完整。'}</p><p>分析前确定业主／运营商／租户、分期和时间边界。集团投资不向本园区摊分；未披露价格与运行数据保持未知。</p><a href="/ledger.html?view=basis">进入统一成本与收益模型 →</a><p class="basis">此通用入口不携带园区参数；园区情景请先预览并确认。本园区可行性尚未核验。</p>`),
 module('history','变化历史与来源',`<p><a href="#site-observation-timeline">查看观测与来源 →</a></p><div id="campus-linked-news"></div><h3>进展时间线</h3><ol class="timeline">${p.history.map(h=>`<li><time>${esc(h.date)}</time>${sourceLink(h.source_url,h.status+' · 查看当时来源')}</li>`).join('')||'<li>尚无已登记的历史事件。</li>'}</ol><h3>来源与核验</h3>${p.sources.map(x=>`<p>${sourceLink(x.url,x.note||(safe(x.url)?new URL(x.url).hostname:'归档来源 · 链接未登记'))}<br><span class="basis">${esc(x.grade)} · ${esc(x.date||'日期未登记')}</span></p>`).join('')||'<p>暂无可公开的来源链接。</p>'}${capacityProvenance(p)}${adopted}<details><summary>十二角度检查清单与待补项</summary>${projectDossier(p)}</details>`)
 ];
 $('detail').innerHTML=`<p><a href="${esc(url('/projects.html',{site:''}))}">← 返回同条件园区名录</a></p><nav class="local-nav" aria-label="园区档案章节">${['overview','phases','participants','resources','equipment','economics','history'].map((id,i)=>`<a href="#campus-${id}">${['概况','分期容量','主体关系','资源许可','设备运行','经济分析','历史来源'][i]}</a>`).join('')}</nav><div class="campus-dossier">${sections.join('')}</div>`;
}
function renderTrends(){
 if(isHome)return;
 const rows=[...data.regional].sort((a,b)=>(b.totals.planning+b.totals.construction)-(a.totals.planning+a.totals.construction)),max=Math.max(...rows.map(r=>r.totals.planning+r.totals.construction),1);
 $('trends').innerHTML=rows.slice(0,5).map(r=>`<a class="region-chart" href="${esc(url('/projects.html',{region:r.id,stage:''}))}"><span>${esc(r.name)}</span><strong>${gw(r.totals.planning+r.totals.construction)} <small>GW</small></strong><div class="bar-track"><div class="bar-fill" style="width:${(r.totals.planning+r.totals.construction)/max*100}%"></div></div></a>`).join('')+'<p class="basis">地图样本 · 建设中 + 筹备</p>';
}
function renderPipeline(){
 if(!data||isHome)return;
 if(!news){
  $('pipeline-summary').innerHTML='<a href="/projects.html?view=pipeline">建设机会 · 等待新闻同步 →</a>';
  $('pipeline-rows').innerHTML=newsFailed?'<p class="empty">项目新闻暂时无法同步，已登记项目仍可查看。</p><button type="button" id="retry-pipeline-news">重试新闻同步</button>':'<p>正在读取项目线索…</p>';
  const retry=$('retry-pipeline-news');if(retry)retry.onclick=()=>window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:{...selection(),force:true}}));
  return;
 }
 const stages={reported:'消息称',announced:'已官宣',construction:'报道已开工',operating:'报道已投运',reviewing:'重新评审',paused:'暂停',cancelled:'取消'};
 const labels={lead:'新闻线索',reviewing:'重新评审',paused:'暂停',cancelled:'取消',linked:'已关联项目'},filter=selection();
 let rows=news.pipeline?.records||[];
 rows=rows.filter(r=>(!filter.company||(r.company_ids||[]).includes(filter.company))&&(!filter.site||r.site_id===filter.site)&&(!(filter.region||filter.scope||filter.role||filter.relation||filter.country||filter.province||filter.city||filter.address||filter.q)||filter.siteIds.includes(r.site_id))&&($('lead-state').value==='all'||(!['paused','cancelled'].includes(r.state))));
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
const observationFields={name:'名称',developer:'开发方',tenant:'使用方',owner:'业主',operator:'运营方',builder:'建设方',status:'建设阶段',lifecycle:'运行状态',capacity_planned_it_mw:'规划IT容量',capacity_it_mw:'IT容量',capacity_it_mw_by_status:'分期IT容量',capacity_facility_mw:'设施功率',power_status:'供电进展',utility:'电网',notes:'说明',capacity_assessment:'估算依据'};
const observationKinds={disclosed:'披露',reported:'报道',estimated:'估算',derived:'推导',forecast:'预测'};
const resourceMetricLabels={electricity_consumption_mwh:'电耗',water_consumption_m3:'耗水量',water_withdrawal_m3:'取水量',water_use_m3_per_day:'日用水量',pue:'PUE',wue_l_per_kwh_it:'WUE'};
function resourceMetricText(value){
 if(value==null)return '未披露';
 const amount=value.value_range?value.value_range.join('–'):value.value;
 return `${amount} ${value.unit} · ${value.period_start||'起期未知'} 至 ${value.period_end||'止期未知'} · ${value.boundary}`;
}
function observationValues(item){
 return Object.entries(item.fields||{}).filter(([k])=>k!=='capacity_assessment').map(([k,v])=>{
  const value=v==null?'未披露':resourceMetricLabels[k]?resourceMetricText(v):k==='capacity_it_mw_by_status'?Object.entries(v).map(([stage,mw])=>`${stage} ${quantityText(mw)}`).join(' / ')||'无分期值':k.startsWith('capacity_')?quantityText(v):Array.isArray(v)?v.map(name).join('、')||'无':String(v);
  return esc(resourceMetricLabels[k]||observationFields[k]||k)+'：'+esc(value);
 });
}
function timelineItem(item){
 const sourceVersions=item.source_versions||[];
 const published=[...new Set(sourceVersions.map(s=>s.published_at||s.publication_date).filter(Boolean))];
 return `<li><time>${esc(item.effective_at||'观测时间未明确')}${item.valid_until?' 至 '+esc(item.valid_until):''}</time><div><span class="badge">${esc(observationKinds[item.kind]||item.kind)}</span>${item.registration_status==='unverified'?'<span class="badge">基础登记待查</span>':''}${item.scope&&item.scope!=='whole_site'?`<span class="badge">分期 ${esc(item.scope.slice(6))}</span>`:''}${item.revision?`<span class="badge">${item.revision.action==='withdraw'?'来源观测已撤回':'来源观测已修订'}</span>`:''}<p>${observationValues(item).join('<br>')}</p><p>${esc(item.basis)}</p>${item.assumptions?.length?`<p class="basis">${item.assumptions.map(esc).join('；')}</p>`:''}${(item.source_reading||[]).filter(r=>r.mode==='targeted').map(r=>`<p class="basis">局部证据已核验 · 选取 ${esc(r.pages_read)}／${esc(r.pages_total)} 页 · 未作全文阅读</p>`).join('')}${published.length?`<span class="basis">来源发表 ${published.map(esc).join('、')}</span> `:''}${(item.sources||[]).map(s=>sourceLink(s.url,'来源 ↗')).join(' · ')}</div></li>`;
}
function objectObservationRows(rows){
 const labels={Capacity:'容量',Interface:'接口／吞吐',Density:'容量',Technology:'存储技术','Module Version':'外形／模块版本','Product Name':'产品系列','Bus Width':'总线宽度','CAS Latency':'CAS延迟','Operating Temp':'工作温度',Speed:'频率',industrial_electricity_price_ytd:'工业电价（年初至当月）',manufacturer_catalogue_model:'厂商目录型号',cooling_capacity:'制冷量',height:'高度',width:'宽度',depth:'深度',power_rating:'额定功率',operating_temperature:'工作温度',input_voltage:'输入电压',output_voltage:'输出电压',weight:'重量',efficiency:'效率',rack_count:'机柜数',rack_units:'机架高度',rated_current:'额定电流',outlet_configuration:'插座配置',airflow:'风量'};
 return rows.map(r=>`<li><time>${esc(r.effective_at||'信息时间未明确')}</time><div><strong>${esc(labels[r.metric]||labels[r.metric.split('.').pop()]||r.metric)}</strong> · ${esc(typeof r.value==='object'?r.value.value_range.join('–'):r.value)} ${esc(r.unit==='native'?'':r.unit)}${r.conflict?'<span class="badge">同口径分歧待核</span>':''}${r.revision?'<span class="badge">历史修订</span>':''}<p>${r.period_start||r.period_end?'统计期间：'+esc(r.period_start||'未知')+'—'+esc(r.period_end||'未知')+' · ':''}${r.registration_status==='unverified'?'基础登记待查':'核实：'+esc((r.reviewed_at||'').slice(0,10))}${r.source.published_at?' · 披露：'+esc(r.source.published_at):''}</p><details class="observation-note"><summary>口径与条件</summary><p>${esc(r.basis)}</p><p>${Object.entries(r.scope).map(([k,v])=>esc(k)+': '+esc(v)).join(' · ')}</p></details>${r.source.url?sourceLink(r.source.url,'原始来源 ↗'):'<span class="basis">归档资料 · 未提供公开原文链接</span>'}</div></li>`).join('');
}
function renderObjectUpdates(){
 const panel=$('object-changes');if(!(isHome||isCompany)||!panel)return;
 const updates=data.research_updates||{},groups=new Map();
 for(const row of updates.changes||[]){if(!groups.has(row.object_id))groups.set(row.object_id,[]);groups.get(row.object_id).push(row);}
 $('object-update-count').textContent=`${updates.total||0} 项有来源信息 · ${updates.objects||0} 个对象；按最近补充排列，历史补录不代表今日发生。`;
 panel.innerHTML=[...groups.values()].map(rows=>{const o=rows[0].object;return `<details class="project-change" data-object="${esc(o.id)}"><summary><strong>${esc(o.name)}</strong><span class="badge">${esc(({company:'公司',product:'产品',statistic:'统计',quote:'报价'})[o.type]||o.type)}</span><span class="change-preview">近期信息</span><span class="change-open">展开全部信息与来源</span></summary><p class="object-load-status" role="status"></p><ol class="timeline">${objectObservationRows(rows)}</ol></details>`}).join('')||'<p class="empty">暂无已采用的公司、产品、统计或报价更新。</p>';
 for(const item of panel.querySelectorAll('details[data-object]'))item.addEventListener('toggle',async()=>{
  if(!item.open||item.dataset.loaded||item.dataset.loading)return;
  item.dataset.loading='1';const status=item.querySelector('.object-load-status');status.textContent='正在读取全部信息…';
  try{const response=await fetch('/api/observations?object='+encodeURIComponent(item.dataset.object)+'&limit=100');if(!response.ok)throw Error('unavailable');const result=await response.json();item.querySelector('.timeline').innerHTML=objectObservationRows(result.records);status.textContent=`${result.total} 项有来源信息${result.next_offset!=null?'（当前显示前100项）':''}`;item.dataset.loaded='1';}
  catch{status.textContent='全部信息暂不可用，保留近期摘要；重新展开可重试。';}
  finally{delete item.dataset.loading;}
 });
}
function renderTracking(){
 const t=data.tracking||{},panel=$('project-changes');
 if(isHome&&panel){
  const changes=(t.changes||[]).filter(item=>(item.sources||[]).some(s=>safe(s.url))).slice(0,6);
  panel.innerHTML=changes.map(item=>`<details class="project-change"><summary><span class="change-date">${esc(item.effective_at||'观测时间未明确')}</span><strong>${esc(item.name)}</strong><span class="badge">${esc(observationKinds[item.kind]||item.kind)}</span>${item.registration_status==='unverified'?'<span class="badge">基础登记待查</span>':''}${item.scope&&item.scope!=='whole_site'?`<span class="badge">分期 ${esc(item.scope.slice(6))}</span>`:''}<span class="change-preview">${observationValues(item).join(' · ')}</span><span class="change-open">展开依据与历史</span></summary><ol class="timeline">${timelineItem(item)}</ol><p><a href="/project.html?site=${encodeURIComponent(item.site_id)}#site-observation-timeline">查看项目现状与完整历史 →</a></p></details>`).join('')||'<p class="empty">暂无有独立来源的项目观测动态。可从地图查看现有项目状态与历史来源。</p>';
  $('daily-freshness').textContent='按最近补充排列，标注信息发生时间；历史补录不代表今日发生，估算与预测分别标明。';
 }
 if(isProject&&data.detail){const p=data.detail;
  ($('campus-history')||$('detail')).insertAdjacentHTML('beforeend',`<section class="detail-card" id="site-observation-timeline"><h2>站点观测时间线</h2><p>物理站点 ${esc(p.site_id)} · 运行状态 ${esc(({active:'活跃',paused:'暂停',cancelled:'取消',closed:'关闭'})[p.lifecycle]||p.lifecycle)}</p>${p.tracking?.conflicts?.length?'<p role="status">同口径记录存在分歧，历史与来源均保留；基础登记按时间展示当前参考，不表示争议已解决。</p>':''}<ol class="timeline">${(p.observations||[]).map(timelineItem).join('')||'<li>尚未登记有有效时点的独立观测；上方保留历史登记。</li>'}</ol></section>`);
 }
}
let updateSignature='';
function updateDate(stamp){
 if(!stamp)return {label:'更新时间未登记',sort:''};
 if(/^\d{4}(?:-\d{2}(?:-\d{2})?)?$/.test(stamp))return {label:stamp,sort:stamp};
 const date=new Date(stamp);if(!Number.isFinite(date.getTime()))return {label:'更新时间未登记',sort:''};
 return {label:new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(date),sort:date.toISOString()};
}
function renderUpdates(){
 if(!isHome)return;
 const entries=[];
 for(const item of data.research_updates?.changes||[]){
  const sourceHref=safe(item.source?.url);
  if(item.source?.url&&!sourceHref)continue;
  const date=updateDate(item.recorded_at),key=item.metric.split('.').pop();
  const metric=({Capacity:'容量',Interface:'接口',Density:'容量',Technology:'技术',Speed:'频率',cooling_capacity:'制冷量',power_rating:'额定功率',industrial_electricity_price_ytd:'工业电价',manufacturer_catalogue_model:'目录型号'})[key]||key.replace(/_/g,' ');
  const value=typeof item.value==='object'?item.value.value_range.join('–'):item.value;
  const qualifiers=[item.registration_status==='unverified'?'基础登记待查':null,({estimated:'估算',calculated:'推导',forecast:'预测'})[item.kind],item.conflict?'同口径分歧':null,item.revision?(item.revision.action==='withdraw'?'已撤回':'修订'):null].filter(Boolean);
  const label=`${item.object.name} · ${qualifiers.length?qualifiers.join(' · ')+' · ':''}${metric} ${value}${item.unit==='native'?'':' '+item.unit}`;
  entries.push({kind:'research',date,label,effective:item.effective_at,href:sourceHref||'#research-observation',observation:sourceHref?null:item.id});
 }
 for(const item of data.tracking?.changes||[]){
  const previewFields=Object.fromEntries(Object.entries(item.fields||{}).filter(([key])=>!['name','notes'].includes(key)));
  const preview=document.createElement('span');preview.innerHTML=observationValues({...item,fields:previewFields}).join(' · ');
  entries.push({kind:'project',date:updateDate(item.recorded_at),label:[item.name,observationKinds[item.kind]||item.kind,item.scope&&item.scope!=='whole_site'?'分期 '+item.scope.slice(6):'',item.revision?(item.revision.action==='withdraw'?'已撤回':'修订'):'',preview.textContent].filter(Boolean).join(' · '),effective:item.effective_at,href:'/project.html?site='+encodeURIComponent(item.site_id)+'#site-observation-timeline'});
 }
 entries.sort((a,b)=>b.date.sort.localeCompare(a.date.sort));
 const content=entries.slice(0,40).map(item=>`<a class="update-item" data-update-kind="${item.kind}" data-effective-at="${esc(item.effective||'')}" href="${esc(item.href)}"${item.observation?' data-observation="'+esc(item.observation)+'"':item.kind==='research'?' target="_blank" rel="noopener noreferrer"':''} title="${esc(item.date.label)} 补充 · 信息发生时间：${esc(item.effective||'未明确')} · 北京时间"><time${/^\d{4}-\d{2}-\d{2}/.test(item.date.sort)?' datetime="'+esc(item.date.sort)+'"':''} aria-label="${esc(item.date.label)} 更新"><span class="update-date-full">${esc(item.date.label)} 更新</span><span class="update-date-short" aria-hidden="true">${esc(item.date.label.replace(/^\d{4}-(?=\d{2}-\d{2})/,''))}</span></time><span>${esc(item.label)}</span></a>`).join('')||'<span class="update-empty">暂无已登记的研究与项目更新</span>';
 if(content===updateSignature)return;updateSignature=content;
 $('update-track').innerHTML='<div class="update-items">'+content+'</div>';
 const original=$('update-track').firstElementChild;
 if(entries.length){const clone=original.cloneNode(true);clone.setAttribute('aria-hidden','true');clone.inert=true;for(const link of clone.querySelectorAll('a'))link.tabIndex=-1;$('update-track').append(clone);}
 resizeUpdates();
}
function resizeUpdates(){
 const track=$('update-track');if(!track?.firstElementChild)return;
 const width=track.firstElementChild.getBoundingClientRect().width;
 track.style.setProperty('--update-distance',-width+'px');track.style.setProperty('--update-duration',Math.max(25,width/42)+'s');
}
if(isHome){
 $('update-toggle').onclick=()=>{const paused=$('home-updates').classList.toggle('paused');$('update-toggle').setAttribute('aria-pressed',String(paused));$('update-toggle').setAttribute('aria-label',paused?'继续更新播报':'暂停更新播报');$('update-toggle').textContent=paused?'▷':'Ⅱ';};
 $('home-updates').addEventListener('click',event=>{
  const link=event.target.closest('[data-observation]');if(!link)return;
  event.preventDefault();
  const row=(data.research_updates?.changes||[]).find(r=>r.id===link.dataset.observation);if(!row)return;
  let dialog=$('research-observation');
  if(!dialog){dialog=document.createElement('dialog');dialog.id='research-observation';dialog.setAttribute('aria-label','研究信息');document.body.append(dialog);}
  dialog.innerHTML='<form method="dialog"><button aria-label="关闭研究信息">关闭</button></form><h3>'+esc(row.object.name)+'</h3><ol class="timeline">'+objectObservationRows([row])+'</ol>';
  dialog.showModal();
 });
 $('home-updates').addEventListener('focusin',e=>{if(e.target.closest('.update-item'))requestAnimationFrame(()=>e.target.scrollIntoView({block:'nearest',inline:'nearest'}));});
 $('home-updates').addEventListener('focusout',()=>requestAnimationFrame(()=>{if(!$('home-updates').matches(':focus-within'))$('update-viewport').scrollLeft=0;}));
 window.addEventListener('resize',resizeUpdates);
}
function renderCampusViews(){
 if(!$('regions-detail'))return;
 $('regions-detail').hidden=!isRegions;
 if(isRegions){
  const analysis=data.geographic_analysis||{},level=params.get('level')||'country';
  const labels={region:'区域',country:'国家',province:'省／州',city:'城市'};
  const groups=(analysis.groups||[]).filter(g=>g.level===level);
  const value=(g,stage)=>g.known_records?num(g.totals[stage])+' MW':'未披露确定值';
  $('regions-detail').innerHTML=`<h2>同口径地区比较</h2><p>${esc(analysis.basis||'地区数据尚未取得')}</p><p>${analysis.place_records??'—'} 条地点记录 · ${analysis.cluster_records??'—'} 条集群 · ${analysis.portfolio_records??'—'} 条组合计划 · ${analysis.unlocated_records??'—'} 条地点记录未定位。登记范围不代表全球完整覆盖。</p><label>比较层级 <select id="region-level">${Object.entries(labels).map(([k,v])=>`<option value="${k}" ${k===level?'selected':''}>${v}</option>`).join('')}</select></label><div class="table-wrap"><table id="region-comparison"><thead><tr><th>地区 / 登记范围</th><th>地点记录</th><th>已投运确定值</th><th>在建确定值</th><th>筹备确定值</th><th>区间 / 未知记录</th><th>集群 / 组合</th><th>来源状态</th></tr></thead><tbody>${groups.map(g=>`<tr data-region="${esc(JSON.stringify(g.filters))}"><th><a href="${esc(url('/projects.html',{...g.filters,view:'',site:''}))}">${esc(Object.entries(g.filters).map(([k,v])=>k==='country'?countryName(v):v).join(' · '))}</a></th><td>${g.totals.sites}</td><td>${value(g,'operating')}</td><td>${value(g,'construction')}</td><td>${value(g,'planning')}</td><td>${g.totals.ranged_sites} / ${g.totals.unknown}</td><td>${g.cluster_records} / ${g.portfolio_records}</td><td>${g.unverified_records} 条基础登记待查；${g.totals.estimated_sites} 条含估算</td></tr>`).join('')||'<tr><td colspan="8">该范围没有此层级的明确地点，未推测补齐。</td></tr>'}</tbody></table></div><details id="regional-ranges"><summary>容量区间原值与对应对象</summary>${groups.flatMap(g=>g.ranges||[]).map(r=>`<p><a href="/project.html?site=${encodeURIComponent(r.site_id)}">${esc(r.name)}</a> · ${esc(data.stages[r.stage]||r.stage)} · ${esc(quantityText(r))} · ${esc((r.assumptions||[]).join('；'))}</p>`).join('')||'<p>当前范围没有登记的容量区间。</p>'}</details><p class="basis">同一层级横向比较；不同层级不能再相加。统计只使用本站已登记对象，机构全球估算另见<a href="/market.html">市场规模</a>。</p>`;
  $('region-level').onchange=e=>select({level:e.target.value});
 }
 if(isList){
  const tools=$('campus-directory-tools');tools.hidden=false;
  tools.innerHTML=`<nav class="local-nav" aria-label="名录视图"><a href="${esc(url(path,{view:''}))}" ${!params.get('view')?'aria-current="page"':''}>列表</a><a href="${esc(url(path,{view:'map'}))}" ${params.get('view')==='map'?'aria-current="page"':''}>地图</a><a href="${esc(url(path,{view:'pipeline'}))}">项目线索</a><a href="${esc(url('/regions.html',{view:'',site:''}))}">地区分析 →</a></nav><form id="campus-search" role="search"><label>园区名称、别名或ID <input name="q" maxlength="160" value="${esc(params.get('q')||'')}"></label><button>查找</button></form><p class="basis">名录包括地点与明确集群；组合计划和新闻线索不能当作唯一园区。保留原始ID和边界，未知不补零。</p>`;
  $('atlas-tools').before(tools);$('campus-search').onsubmit=e=>{e.preventDefault();select({q:new FormData(e.target).get('q'),site:''});};
  $('atlas-layout').hidden=params.get('view')!=='map';$('project-list').hidden=['pipeline','map'].includes(params.get('view'));
 }
 const overview=isCompany&&!keys.some(k=>params.get(k));
 $('industry-entry').hidden=!overview;
 if(overview){
  for(const id of ['atlas-tools','pipeline-summary','project-list','leaders-section','trends-section'])$(id).hidden=true;
  $('atlas-layout').hidden=false;$('atlas-layout').classList.add('industry-summary');$('atlas-layout').querySelector('.atlas-panel').hidden=true;
  $('research-updates').hidden=false;
 }
 if(isRegions){for(const id of ['atlas-layout','project-list','leaders-section','trends-section','market-band','pipeline-summary','pipeline-section','research-updates'])$(id).hidden=true;}
 if(isProject){
  const section=$('pipeline-section');section.hidden=false;section.querySelector('h2').textContent='关联园区消息与线索';
  ($('campus-linked-news')||$('campus-history')).append(section);
 }
}
function render(){
 filters();renderStats();renderMarket();renderCompanies();renderTable();renderTrends();renderMap();renderDetail();renderPipeline();renderDaily();renderTracking();renderObjectUpdates();renderUpdates();
 if(!isProject){$('page-title').textContent=isMarket?'数据中心市场规模':data.company?name(data.company.company_id)+' · 全球布局':isRegions?'地区分析':isList?'园区名录':isHome?'全球数据中心':'行业总览';$('page-description').textContent=data.company?'追踪相关园区、建设进度和新闻变化。园区容量不代表公司的持有或租用份额。':'全球布局、项目规模与有来源的最新动态。';}
 if($('coverage'))$('coverage').textContent=`${data.totals.sites} 条已追踪项目记录 · 含园区与集群，非全球普查\n核验日期 ${data.coverage.oldest_verified||'—'} — ${data.coverage.latest_verified||'—'}`;
 const hidden=isProject||isMarket||isRegions;
 for(const id of ['daily-pulse','research-arrivals'])if($(id))$(id).hidden=!isHome;
 for(const id of ['atlas-tools','atlas-layout','project-list','leaders-section','trends-section'])if($(id))$(id).hidden=hidden;
 if($('detail'))$('detail').hidden=!isProject;if($('market-detail'))$('market-detail').hidden=!isMarket;$('market-band').hidden=isProject;if($('pipeline-section'))$('pipeline-section').hidden=!(isList||isProject);if($('project-list'))$('project-list').hidden=!isList||params.get('view')==='pipeline';if($('pipeline-summary'))$('pipeline-summary').hidden=hidden||isList;
 if(isList){$('atlas-layout').hidden=true;$('leaders-section').hidden=true;$('trends-section').hidden=true;$('market-band').hidden=true;}
 if(isCompany&&!keys.some(k=>params.get(k)))$('page-description').textContent='行业规模、机构预测与最新动态；具体园区与地区数据进入全球园区。';
 if(isRegions)$('page-description').textContent='按同一统计边界比较已登记地点；缺失地理、容量与来源范围明确显示。';
 renderCampusViews();
 document.title=$('page-title').textContent+' · inresearch.ai';
 window.industryFilter=selection();window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:selection()}));queueCachedFonts();
}
let loading=false;
async function load({quiet=false}={}){
 if(quiet&&loading)return;
 request?.abort();const current=new AbortController();request=current;loading=true;if(!quiet)$('load-status').textContent='正在读取项目数据…';
 const q=new URLSearchParams();if(isHome)q.set('overview','1');else for(const k of keys)if(params.get(k))q.set(k,params.get(k));
 try{const r=await fetch('/api/industry?'+q,{signal:current.signal});if(!r.ok)throw Error(r.status===404?'未找到对应的项目或主体。':r.status===400?'筛选条件无效，请重置后重试。':'项目数据暂时无法读取。');const value=await r.json();if(request!==current)return;$('load-status').textContent='';if(quiet&&JSON.stringify(value)===JSON.stringify(data))return;data=value;render();}
 catch(e){if(e.name==='AbortError')return;$('load-status').innerHTML=quiet&&data?'状态刷新暂缓，保留上次读取结果。':esc(e.message)+' <a href="/">返回行业总览</a>';}
 finally{if(request===current)loading=false;}
}
fetch('/assets/world.geo.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(value=>{geo=value;renderMap();}).catch(()=>{$('map-selection').textContent='地图底图暂不可用，请点击布局明细查看项目。';});
load();
if(isHome){setInterval(()=>{if(!document.hidden&&!document.activeElement?.closest('form'))load({quiet:true});},60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load({quiet:true});});}
})();

// The shared header has one or two business rows. Fit the entire homepage map
// below its actual top edge, preserving the SVG viewBox and zoom behaviour.
(() => {
 if (!document.body.classList.contains('industry-home')) return;
 const map = document.getElementById('world-map');
 const fit = () => {
  if (innerWidth <= 1000) { map.style.removeProperty('max-height'); map.style.removeProperty('width'); return; }
  const available = Math.max(220, innerHeight - map.getBoundingClientRect().top - 8);
  const width = Math.min(map.parentElement.clientWidth, available * 1000 / 490);
  map.style.width = Math.floor(width) + 'px';
  map.style.maxHeight = Math.floor(available) + 'px';
 };
 const schedule = () => requestAnimationFrame(fit);
 window.addEventListener('resize', schedule);
 window.addEventListener('inresearch:navigation', schedule);
 if (window.ResizeObserver) new ResizeObserver(schedule).observe(document.querySelector('.industry'));
 schedule();
})();
