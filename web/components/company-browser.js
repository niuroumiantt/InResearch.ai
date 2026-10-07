/* Company -> category -> model. Lists never fetch or auto-select a model detail. */
(()=>{'use strict';
const $=id=>document.getElementById(id), cid='supermicro', api='/api/product-catalog/'+cid;
const observedDate=v=>{if(!v)return '未登记';if(!/[TZ+-].*[0-9]/.test(v)||v.length<=10)return v;const d=new Date(v);return Number.isNaN(d.valueOf())?v:new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'';}catch{return '';}};
const rich=v=>esc(v).replace(/\^\{([^{}]*)\}/g,'<sup>$1</sup>').replace(/_\{([^{}]*)\}/g,'<sub>$1</sub>');
const kindLabel={named_product:'具体型号',family_or_directory:'系列 / 平台 / 目录',software_service:'软件 / 服务'};
let state=new URLSearchParams(location.search), generation=0, comparisonGeneration=0, controller, timer, browse;
const compared=new Set();
try{JSON.parse(sessionStorage.getItem('supermicro-compared')||'[]').slice(0,4).forEach(id=>compared.add(id));}catch{}
const pageUrl=(fields={})=>{
 const p=new URLSearchParams({c:cid,view:'categories'});
 for(const [k,v] of Object.entries(fields)){if(v!==''&&v!=null)p.set(k,String(v));else p.delete(k);}
 return '/product-catalog.html?'+p;
};
const fields=()=>Object.fromEntries(['category','line','q','kind','with_specs','offset'].filter(k=>state.has(k)).map(k=>[k,state.get(k)]));
const categoryUrl=id=>pageUrl({category:id});
const productUrl=id=>pageUrl({...fields(),view:'products',product_id:id});
const external=(url,label)=>safe(url)?`<a href="${esc(safe(url))}" target="_blank" rel="noopener">${esc(label)} ↗</a>`:'';
async function read(url,signal){const r=await fetch(url,{cache:'no-store',signal});if(!r.ok)throw Error(r.status===404?'这项资料暂时不可用。':'产品资料读取失败，请重试。');return r.json();}
function comparisonTools(){
 $('comparison-tools').hidden=!compared.size;
 $('open-comparison').textContent='对比 '+compared.size+' 个型号';
 try{sessionStorage.setItem('supermicro-compared',JSON.stringify([...compared]));}catch{}
}
function toggle(id,input){
 if(compared.has(id))compared.delete(id);
 else if(compared.size<4)compared.add(id);
 else{if(input)input.checked=false;$('status').textContent='最多对比 4 项，请先移出一个型号。';return;}
 comparisonTools();
 if($('compare'))$('compare').textContent=compared.has(id)?'移出对比':'加入对比';
}
function breadcrumb(chain=[],product=''){
 $('browser-breadcrumbs').innerHTML=`<a href="${pageUrl({view:''})}">公司首页</a><a href="${pageUrl()}">产品分类</a>`+
 chain.map(n=>`<a href="${esc(categoryUrl(n.id))}">${esc(n.label)}</a>`).join('')+(product?`<span>${esc(product)}</span>`:'');
}
function specTables(p,prefix='spec'){
 return (p.tables||[]).map((t,i)=>{
 const refs=t.source_refs||[];
 return `<article class="spec-card" id="${esc(prefix)}-${i}"><h3>${rich(t.section||'官方表格 '+t.index)}</h3><div class="spec-scroll" tabindex="0" role="region" aria-label="${esc(t.section||'官方表格')}"><table><tbody>${t.rows.map(row=>`<tr>${row.map(c=>{const tag=c.header?'th':'td';return `<${tag} colspan="${Number(c.colspan)||1}" rowspan="${Number(c.rowspan)||1}">${rich(c.text)}</${tag}>`;}).join('')}</tr>`).join('')}</tbody></table></div>${t.notes?`<p class="spec-note">${rich(t.notes)}</p>`:''}${refs.length?`<footer class="spec-source">${refs.map(r=>external(r.url,'表格原始来源')).join(' · ')}<details><summary>来源身份</summary>${refs.map(r=>`<p><code>${esc(r.sha256)}</code></p>`).join('')}</details></footer>`:''}</article>`;
 }).join('');
}
function sourceRecord(p){
 const pages=(p.official_pages||[]).filter(v=>v.url!==p.source_url), attachments=p.attachments||[], resources=p.official_resources||[];
 return `<details class="source-record"><summary>来源、获取记录与附件${attachments.length?' · '+attachments.length+' 份':''}</summary><p>原厂分类原文：${esc(p.category||'未提供')}</p><p>原厂分类路径：${esc((p.taxonomy||[]).map(v=>v.name||v.slug).join(' › ')||'未交付；上方为本站浏览分类')}</p><p>观察时间：${esc(p.observed_at)} · 官网在售状态：${esc(p.official_status||'未核实')}</p><p>${external(p.source_url,'官方产品页')} · 原文快照 SHA-256：<code>${esc(p.source_sha256)}</code></p>${pages.length?`<ul>${pages.map(v=>`<li>${external(v.url,'其他语言官方页面')} · <code>${esc(v.sha256)}</code></li>`).join('')}</ul>`:''}${attachments.length||resources.length?`<ul>${[...attachments,...resources].map(v=>`<li>${external(v.url,v.label||'官方附件')} ${esc(v.access_status||'')}</li>`).join('')}</ul>`:''}<p>规格保留官方配置、合并单元格与脚注；已收录不代表当前在售或正式研究采用。</p></details>`;
}
async function renderDetail(id,current,signal){
 $('company-browser').classList.add('model-mode');$('browse-body').hidden=true;$('detail').hidden=false;
 $('detail').innerHTML='<p>正在读取这一型号的官方规格…</p>';
 const data=await read(api+'?'+new URLSearchParams({product_id:id}),signal);
 if(current!==generation)return;
 const p=data.product;
 if(!p)throw Error('此型号未在当前接收库中找到。');
 breadcrumb(p.browse_path||[],p.name);
 $('catalog-title').textContent='超微 · 产品规格';document.title=p.name+' · Supermicro';
 $('status').textContent='已收录资料 · '+(p.tables?.length||0)+' 张官方原表 · 原始观察 '+observedDate(p.observed_at);
 $('detail').innerHTML=`<header class="detail-heading"><div><h2>${esc(p.name)}</h2><p class="detail-meta">${esc(kindLabel[p.kind]||p.kind)} · ${esc((p.browse_path||[]).map(v=>v.label).join(' / '))}</p></div><div class="detail-actions">${external(p.source_url,'官方产品页')}<button id="compare" type="button">${compared.has(id)?'移出对比':'加入对比'}</button><a href="${esc(pageUrl(fields()))}">返回分类 / 结果</a></div></header>`+
 ((p.parameters||[]).length?`<dl class="detail-highlights">${p.parameters.slice(0,9).map(v=>`<div><dt>${esc(v.label)}</dt><dd>${rich(v.value)}</dd></div>`).join('')}</dl>`:'')+
 `<header class="specifications-heading"><h3>完整规格</h3><span>官方原文 · 保留配置与适用条件</span></header>`+
 ((p.tables||[]).length?`<nav class="spec-section-links" aria-label="规格分组">${p.tables.map((t,i)=>`<a href="#spec-${i}">${esc(t.section||'表格 '+t.index)}</a>`).join('')}</nav><div class="spec-grid">${specTables(p)}</div>`:'<p class="browser-empty">此条目尚无已提取规格；可从官方产品页查看原文。</p>')+sourceRecord(p);
 $('compare').onclick=()=>toggle(id);
}
function preview(parameters,pattern){
 const values=(parameters||[]).filter(p=>pattern.test(p.label)).slice(0,2);
 return values.length?values.map(v=>`<p title="${esc(v.label+': '+v.value)}">${esc(v.value)}</p>`).join(''):'<small>查看原表</small>';
}
async function renderBrowse(current,signal){
 const p=new URLSearchParams({view:'browse',...fields()});
 const data=await read(api+'?'+p,signal);
 if(current!==generation)return;
 browse=data;$('company-browser').classList.remove('model-mode');$('browse-body').hidden=false;$('detail').hidden=true;$('detail').replaceChildren();
 $('catalog-title').textContent='超微 · 产品分类';document.title='Supermicro · 产品分类';
 breadcrumb(data.breadcrumb||[]);
 const title=state.get('q')?'搜索结果':data.breadcrumb?.at(-1)?.label||'全部产品分类';
 $('category-title').textContent=title;
 $('category-tree').innerHTML=(data.roots||[]).map(n=>`<a href="${esc(categoryUrl(n.id))}" ${data.category===n.id?'aria-current="page"':''}><span>${esc(n.label)}</span><small>${n.entities}</small></a>`+
 (data.category?.startsWith(n.id+'/')?(data.breadcrumb||[]).filter(x=>x.id!==n.id).map(x=>`<a class="child-category" href="${esc(categoryUrl(x.id))}" ${data.category===x.id?'aria-current="page"':''}><span>${esc(x.label)}</span><small>${x.entities}</small></a>`).join(''):'')).join('');
 const children=state.get('q')?[]:(data.children||[]);
 const max=Math.max(1,...children.map(n=>n.entities));
 $('category-children').innerHTML=children.map(n=>`<a class="category-card" href="${esc(categoryUrl(n.id))}"><strong>${esc(n.label)} →</strong><small>${n.entities} 个条目 · ${n.named_products} 个型号</small><i style="width:${Math.max(3,n.entities/max*100)}%" aria-hidden="true"></i></a>`).join('');
 $('matches').textContent=data.matched+' 个匹配条目';
 $('status').textContent=data.available?'数据来自已接收产品数据库 · 浏览分类按官方路径与明确原表字段整理':'等待首次产品资料交付。';
 $('result-context').textContent=state.get('q')?'搜索 “'+state.get('q')+'” · 型号名称与原表字段':'选择子分类浏览，或直接点击型号查看规格';
 for(const mode of ['products','specs'])$('export-'+mode).href=api+'?'+new URLSearchParams({...fields(),export:mode,scope:'all'});
 $('browse-rows').innerHTML=(data.items||[]).map(p=>`<tr><td><input type="checkbox" data-compare="${esc(p.id)}" aria-label="对比 ${esc(p.name)}" ${compared.has(p.id)?'checked':''}></td><td><a class="model-link" href="${esc(productUrl(p.id))}">${esc(p.name)}</a><small>${esc(kindLabel[p.kind]||p.kind)}</small></td><td>${preview(p.parameters,/processor|\bcpu|^gpus?$|^supported gpu/i)}</td><td>${preview(p.parameters,/memory|capacity|storage/i)}</td><td>${esc(p.browse_path.slice(1).map(n=>n.label).join(' / ')||p.browse_path[0].label)}</td><td>${p.table_count?`${p.table_count} 张`:'待补齐'}</td></tr>`).join('')||'<tr><td colspan="6">没有符合筛选条件的资料。</td></tr>';
 $('browse-rows').querySelectorAll('[data-compare]').forEach(el=>el.onchange=()=>toggle(el.dataset.compare,el));
 $('previous').disabled=data.offset===0;$('next').disabled=data.offset+data.limit>=data.matched;
 $('page-caption').textContent=data.matched?`${data.offset+1}–${Math.min(data.offset+data.limit,data.matched)} / ${data.matched}`:'0 个条目';
}
async function load(){
 const current=++generation;++comparisonGeneration;if(controller)controller.abort();controller=new AbortController();
 const timeout=setTimeout(()=>controller.abort(),15000);
 $('status').textContent='正在读取产品资料…';$('browser-comparison').hidden=true;
 try{
  if(state.get('product_id'))await renderDetail(state.get('product_id'),current,controller.signal);
  else await renderBrowse(current,controller.signal);
 }catch(e){if(current===generation){$('status').textContent=e.name==='AbortError'?'产品资料读取超时。':e.message;
  const target=state.get('product_id')?$('detail'):$('browse-rows');
  target.innerHTML=state.get('product_id')?'<p class="browser-empty">规格读取失败。<button id="retry-detail">重试规格</button></p>':'<tr><td colspan="6">分类资料读取失败。<button id="retry-browse">重试</button></td></tr>';
  const button=$('retry-detail')||$('retry-browse');if(button)button.onclick=load;
 }}finally{clearTimeout(timeout);}
}
function change(values){
 state=new URLSearchParams({c:cid,view:'categories',...fields(),...values});
 for(const [k,v] of [...state])if(v==='')state.delete(k);
 history.replaceState(null,'',pageUrl(Object.fromEntries(state)));
 load();
}
function search(){change({q:$('query').value.trim(),kind:$('kind').value,with_specs:$('with-specs').checked?'1':'',offset:'',product_id:''});}
async function comparison(){
 const current=++comparisonGeneration, ids=[...compared];
 const panel=$('browser-comparison');panel.hidden=false;panel.textContent='正在读取所选型号…';
 try{
  const values=await Promise.all(ids.map(async id=>(await read(api+'?'+new URLSearchParams({product_id:id}),AbortSignal.timeout(15000))).product));
  if(current!==comparisonGeneration)return;
  if(values.some(p=>!p))throw Error('部分所选型号已不可用，请重新选择。');
  const maps=values.map(p=>new Map((p.parameters||[]).map(v=>[v.label,v.value])));
  const keys=[...new Set(maps.flatMap(m=>[...m.keys()]))].slice(0,12);
  panel.innerHTML=`<h2>所选型号参数</h2><p class="browser-basis">按原文参数名逐项展示，不合并不同配置、单位与测试条件。</p><div class="comparison-scroll"><table><thead><tr><th>官方参数</th>${values.map(p=>`<th>${esc(p.name)}</th>`).join('')}</tr></thead><tbody>${keys.map(k=>`<tr><th>${esc(k)}</th>${maps.map(m=>`<td>${rich(m.get(k)||'— / 查看原表')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${values.map(p=>`<details class="source-record"><summary>${esc(p.name)} · 完整原表</summary><div class="spec-grid">${specTables(p,p.id)}</div>${sourceRecord(p)}</details>`).join('')}`;
  panel.scrollIntoView({block:'start',behavior:'smooth'});
 }catch(e){if(current!==comparisonGeneration)return;panel.innerHTML=`<p>${esc(e.message)}</p><button id="retry-comparison">重试对比</button>`;$('retry-comparison').onclick=comparison;}
}
$('query').value=state.get('q')||'';$('kind').value=state.get('kind')||'';$('with-specs').checked=state.get('with_specs')==='1';
$('browser-search').onsubmit=e=>{e.preventDefault();clearTimeout(timer);search();};
$('query').oninput=()=>{clearTimeout(timer);timer=setTimeout(search,300);};
$('kind').onchange=search;$('with-specs').onchange=search;$('retry').onclick=load;
$('previous').onclick=()=>change({offset:String(Math.max(0,browse.offset-browse.limit))});
$('next').onclick=()=>change({offset:String(browse.offset+browse.limit)});
$('open-comparison').onclick=comparison;$('clear-comparison').onclick=()=>{++comparisonGeneration;compared.clear();comparisonTools();$('browser-comparison').hidden=true;document.querySelectorAll('[data-compare]').forEach(el=>el.checked=false);if($('compare'))$('compare').textContent='加入对比';};
comparisonTools();load();
read('/api/company-window?c='+cid,AbortSignal.timeout(12000)).then(d=>{const s=d.catalog?.summary;$('browser-summary').textContent=s?`${s.named_products.toLocaleString()} 个型号 · ${s.specification_tables.toLocaleString()} 张原表 · ${(d.catalog.material_count||0).toLocaleString()} 份资料索引`:'尚未收录产品资料';}).catch(()=>{$('browser-summary').textContent='公司摘要暂不可用，产品资料可独立浏览。';});
})();
