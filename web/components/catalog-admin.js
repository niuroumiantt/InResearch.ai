/* Internal projection of the same current catalog. No second fact store. */
(() => {
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const query=new URLSearchParams(location.search), company=query.get('c')||'nvidia';
  const api='/api/product-catalog/'+encodeURIComponent(company);
  let generation=0, sourceGeneration=0;
  const safe=value=>{try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
  function preview(product='',series='') {
    const q=new URLSearchParams({c:company,view:'products'});
    if(product)q.set('product_id',product);if(series)q.set('series',series);
    $('reader-preview').href='/product-catalog.html?'+q;
  }
  preview(query.get('product_id'),query.get('series'));
  async function source(id,series=false) {
    const current=++sourceGeneration;
    $('admin-source').replaceChildren();$('source-status').textContent=id?'正在读取来源身份…':'当前目录没有可查看的记录。';
    if(!id)return;
    try{
      const r=await fetch(api+'?'+new URLSearchParams({[series?'series_id':'product_id']:id}),{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!r.ok)throw Error('来源读取失败');const d=await r.json(),p=d.product||d.series;
      if(current!==sourceGeneration)return;if(!p)throw Error('当前目录中没有这条来源记录');
      const fields=[['稳定 ID',p.id],['原文快照 SHA-256',p.source_sha256],['观测日期',p.observed_at],['地图变化',p.map_change_status],['提取状态',p.extraction_status],['官方语言 sitemap',p.website_sitemap?JSON.stringify(p.website_sitemap):null]];
      $('admin-source').innerHTML=`<h3>${esc(p.name)}</h3><dl>${fields.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v??'未提供')}</dd>`).join('')}</dl>${safe(p.source_url)?`<a href="${esc(safe(p.source_url))}" target="_blank" rel="noopener">官方来源 ↗</a>`:''}<h3>表格及多语言来源身份</h3><ul>${[...(p.tables||[]).flatMap(t=>t.source_refs||[]),...(p.official_pages||[])].map(v=>`<li>${safe(v.url)?`<a href="${esc(safe(v.url))}" target="_blank" rel="noopener">${esc(v.url)}</a>`:esc(v.url)} · SHA-256 ${esc(v.sha256??'未提供')}</li>`).join('')||'<li>没有附加来源记录。</li>'}</ul>`;
      $('source-status').textContent='';preview(series?'':id,series?id:'');
    }catch(e){if(current===sourceGeneration)$('source-status').textContent=e.name==='TimeoutError'?'来源读取超时，请重新选择或刷新。':e.message;}
  }
  async function load(){
    const current=++generation;sourceGeneration++;
    $('admin-status').textContent='正在读取当前目录…';
    try{
      const r=await fetch(api+'?view=index',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!r.ok)throw Error('目录状态读取失败');const d=await r.json();if(current!==generation)return;
      const products=d.products||[],c=d.coverage||{},sm=c.website_sitemap||{},map=c.product_map||{};
      const named=products.filter(p=>p.kind==='named_product'&&p.listing!=='obsolete');
      const withSpecs=items=>items.filter(p=>Number(p.table_count??p.tables?.length??0)>0).length;
      const metrics=[['当前目录实体',products.length],['非停产具体型号规格',`${withSpecs(named)} / ${named.length}`],['全部实体有规格',`${withSpecs(products)} / ${products.length}`],['官方 sitemap 候选',sm.candidate_urls??'未提供'],['已核对产品 URL',`${sm.product_path_observed??'未知'} / ${sm.product_path_candidates??'未知'}`],['待访问页面',c.pending_pages??'未知'],['访问失败（可重试）',c.failed_pages??'未知'],['官网已删除旧页',c.unavailable_pages??'未知'],['策略阻止跳转',c.policy_blocked_pages??'未知']];
      $('metrics').innerHTML=d.available?metrics.map(([label,n])=>`<div class="metric"><strong>${esc(n)}</strong>${esc(label)}</div>`).join(''):'<p>尚未收到该公司的产品目录，无法计算覆盖率。</p>';
      $('admin-title').textContent=(d.company?.label||company)+' · 公司后台';
      $('admin-batch').textContent='当前目录生成于 '+(d.generated_at||'未知')+' · schema '+(d.schema??d.schema_version??'未提供');
      $('admin-change').textContent='本次目录变化：'+(Object.entries(map.changes||{}).map(([k,v])=>k+' '+v).join(' / ')||'未提供');
      $('limitations').innerHTML=(c.limitations||[]).map(v=>`<li>${esc(v)}</li>`).join('');
      $('admin-company').innerHTML=(d.registered_companies||[{id:company,label:company}]).map(v=>`<option value="${esc(v.id)}" ${v.id===company?'selected':''}>${esc(v.label)}</option>`).join('');
      $('admin-product').innerHTML=products.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
      const requested=query.get('product_id')||query.get('series');
      if(products.some(p=>p.id===requested))$('admin-product').value=requested;
      $('admin-product').onchange=()=>source($('admin-product').value);
      $('admin-status').textContent='已读取网站当前目录。';
      source($('admin-product').value,!!query.get('series')&&$('admin-product').value===query.get('series'));
    }catch(e){if(current===generation){$('admin-status').textContent=e.name==='TimeoutError'?'状态读取超时，请刷新重试。':'目录状态读取失败，请刷新重试。';$('metrics').replaceChildren();$('admin-batch').textContent='当前版本未知';$('admin-change').textContent='';$('limitations').replaceChildren();$('admin-product').replaceChildren();$('admin-source').replaceChildren();$('source-status').textContent='来源记录未读取。';}}
  }
  $('admin-company').onchange=e=>{location.href='/admin/company.html?'+new URLSearchParams({c:e.target.value});};
  $('admin-retry').onclick=load;load();
})();
