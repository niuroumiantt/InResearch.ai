(() => {
  const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const categories={cpu:'CPU',gpu:'GPU',accelerator:'其他计算加速器',unknown:'待核验'};
  const forms={chip:'芯片',board:'板卡',module:'模组',system:'整机 / 平台',series:'系列 / 目录',unknown:'形态待核验'};
  const nonCompute=new Set(['micron','sk-hynix','supermicro']);
  let items=[],filtered=[],companies=[],page=0,generation=0,controller,downloads;
  const pageSize=30;
  function render(){
    const q=$('compute-query').value.trim().toLowerCase(),category=$('compute-category').value,region=$('compute-region').value,company=$('compute-company').value,form=$('compute-form').value;
    filtered=items.filter(p=>(!category||p.compute.category===category)&&(!region||p.company.country===region)&&(!company||p.company.id===company)&&(!form||p.compute.form===form)&&(!$('compute-specs').checked||p.table_count)&&`${p.name} ${p.company.label}`.toLowerCase().includes(q));
    page=Math.min(page,Math.max(0,Math.ceil(filtered.length/pageSize)-1));
    const counts=Object.entries(forms).map(([k,v])=>`${v} ${filtered.filter(p=>p.compute.form===k).length}`).join(' · ');
    $('compute-counts').textContent=`本次已交付条目 ${filtered.length}：${counts}。有原文参数 ${filtered.filter(p=>p.table_count).length}；不是厂商产品总数。`;
    $('compute-products').innerHTML=filtered.slice(page*pageSize,(page+1)*pageSize).map(p=>`<tr><td><a href="/product-catalog.html?${new URLSearchParams({c:p.company.id,product_id:p.id,q:p.name})}">${esc(p.name)}</a><small>${esc((p.taxonomy||[]).map(x=>x.name||x.slug).join(' › ')||p.category)}</small></td><td><a href="/product-catalog.html?c=${encodeURIComponent(p.company.id)}">${esc(p.company.label)}</a>${p.company.parent_company_id?`<small>母公司：<a href="/product-catalog.html?c=${encodeURIComponent(p.company.parent_company_id)}">${esc(p.company.parent_company_id)}</a></small>`:''}</td><td>${esc(categories[p.compute.category]||'待核验')}<small>${esc(forms[p.compute.form]||'形态待核验')}</small></td><td>${esc(p.compute.architecture||'—')}${(p.compute.chip_links||[]).map(l=>`<small>芯片：<a href="/product-catalog.html?${new URLSearchParams({c:p.company.id,product_id:l.product_id})}">${esc(items.find(x=>x.company.id===p.company.id&&x.id===l.product_id)?.name||l.product_id)}</a></small>`).join('')}</td><td>${p.table_count?`${p.table_count} 组原文规格`:'规格待补'}<small>${esc(p.observed_at||'')}</small></td></tr>`).join('')||'<tr><td colspan="5">没有符合条件的已交付产品。</td></tr>';
    $('compute-prev').disabled=page===0;$('compute-next').disabled=(page+1)*pageSize>=filtered.length;
  }
  async function get(url, loadSignal){
    const request=new AbortController(), cancel=()=>request.abort();
    loadSignal.addEventListener('abort',cancel,{once:true});
    if(loadSignal.aborted)cancel();
    const timer=setTimeout(cancel,30000);
    try{
      const r=await fetch(url,{cache:'no-store',signal:request.signal,priority:'high'});
      if(!r.ok)throw Error(`HTTP ${r.status}`);
      return await r.json();
    }finally{clearTimeout(timer);loadSignal.removeEventListener('abort',cancel);}
  }
  async function load(){
    const current=++generation;controller?.abort();controller=new AbortController();const signal=controller.signal;
    items=[];filtered=[];render();$('gaps').innerHTML='';$('compute-status').textContent='正在读取已交付目录…';
    try{
      const first=await get('/api/product-catalog/nvidia?view=index',signal);
      if(current!==generation)return;
      companies=(first.registered_companies||[]).filter(c=>!nonCompute.has(c.id));
      $('compute-company').innerHTML='<option value="">全部厂商</option>'+companies.map(c=>`<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');
      const results=await Promise.allSettled(companies.map(c=>c.id==='nvidia'?first:get(`/api/product-catalog/${encodeURIComponent(c.id)}?view=index`,signal)));
      if(current!==generation)return;
      const gaps=[];let ready=0;
      results.forEach((r,i)=>{const c=companies[i];if(r.status==='rejected'){gaps.push(`${c.label}：读取失败，尚未核对交付状态`);return;}const d=r.value;if(!d.available){gaps.push(`${c.label}：尚未收到目录`);return;}ready++;const ps=d.products.filter(p=>p.compute&&p.compute.category!=='excluded');items.push(...ps.map(p=>({...p,company:c})));gaps.push(`${c.label}：已交付 ${ps.length} 项（具体型号 ${ps.filter(p=>p.kind==='named_product').length}），全目录未穷尽`);});
      items.sort((a,b)=>a.company.label.localeCompare(b.company.label)||a.name.localeCompare(b.name,'en',{numeric:true}));
      $('gaps').innerHTML=gaps.map(t=>`<li>${esc(t)}</li>`).join('');$('compute-status').textContent=`已读取 ${ready} / ${companies.length} 个厂商或产品线目录；只展示已接收的数据。`;render();
    }catch(e){if(current===generation)$('compute-status').textContent='目录读取失败，请重新读取。';}
  }
  for(const id of ['compute-category','compute-region','compute-company','compute-form','compute-query','compute-specs'])$(id).addEventListener('input',()=>{page=0;render();});
  $('compute-prev').onclick=()=>{page--;render();};$('compute-next').onclick=()=>{page++;render();};$('compute-retry').onclick=load;
  $('compute-export').onclick=()=>{const cell=x=>'"'+String(x??'').replace(/^[\s]*([=+@-])/,'\'$1').replace(/"/g,'""')+'"';const rows=[['product_id','name','company_id','parent_company_id','country','compute_category','form','architecture','chip_product_ids','official_category','official_taxonomy','tables','observed_at'],...filtered.map(p=>[p.id,p.name,p.company.id,p.company.parent_company_id,p.company.country,p.compute.category,p.compute.form,p.compute.architecture,(p.compute.chip_links||[]).map(l=>l.product_id).join(' | '),p.category,(p.taxonomy||[]).map(x=>x.name||x.slug).join(' > '),p.table_count,p.observed_at])];if(downloads)URL.revokeObjectURL(downloads);downloads=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=downloads;a.download='compute-catalog.csv';a.click();};
  load();
})();
