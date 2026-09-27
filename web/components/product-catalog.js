(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const kinds = {named_product:'具体型号页 · 待身份复核',family_or_directory:'系列 / 平台 / 目录',software_service:'软件 / 服务'};
  let catalog = {products:[]}, selected = '', generation = 0;
  const compared = new Set();
  function tableHtml(table) {
    const rich=s=>esc(s).replace(/\^\{([^{}]*)\}/g,'<sup>$1</sup>').replace(/_\{([^{}]*)\}/g,'<sub>$1</sub>');
    return `<h3>${rich(table.section || `官方表格 ${table.index}`)}</h3><div class="table-wrap"><table aria-label="${esc(table.section)}"><tbody>${table.rows.map(row=>`<tr>${row.map(c=>{const tag=c.header?'th':'td';return `<${tag} colspan="${Number(c.colspan)||1}" rowspan="${Number(c.rowspan)||1}">${rich(c.text)}</${tag}>`;}).join('')}</tr>`).join('')}</tbody></table></div>${table.notes?`<p class="notes">${rich(table.notes)}</p>`:''}`;
  }
  function details(p, compact = false) {
    return `<h2>${esc(p.name)}</h2><p>${esc(p.category)} · ${esc(kinds[p.kind])}</p><p class="muted">在售状态：待核对 · 获取于 ${esc(p.observed_at)}</p>${compact?'':`<button id="compare">${compared.has(p.id)?'移出并排核查':'加入并排核查（最多 4 项）'}</button>`}${p.tables.length?p.tables.map(tableHtml).join(''):'<p class="notice">已发现官方产品入口，具体规格仍待寻找或提取。这里不以相邻产品参数补值。</p>'}<p class="source"><a href="${esc(p.source_url)}" target="_blank" rel="noopener">查看官方来源</a> · 原文快照 SHA-256：${esc(p.source_sha256)}</p>${p.attachments.length?`<details><summary>关联附件（${p.attachments.length}）</summary><ul>${p.attachments.map(a=>`<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url.split('/').pop())}</a></li>`).join('')}</ul></details>`:''}`;
  }
  function select(id) {
    selected=id;
    const p=catalog.products.find(p=>p.id===id);
    if(!p)return;
    $('#detail').innerHTML=details(p);
    document.querySelectorAll('.product').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===id)));
    $('#compare').onclick=()=>{
      if(compared.has(id))compared.delete(id);else if(compared.size<4)compared.add(id);else {$('#status').textContent='最多并排核查 4 项，请先移出一项。';return;}
      $('#comparison').hidden=!compared.size;
      $('#comparison-items').innerHTML=catalog.products.filter(p=>compared.has(p.id)).map(p=>`<article>${details(p,true)}</article>`).join('');
      select(id);
    };
  }
  function filter() {
    const q=$('#query').value.trim().toLowerCase(), kind=$('#kind').value;
    const products=catalog.products.filter(p=>(!kind||p.kind===kind)&&(!$('#with-specs').checked||p.tables.length)&&(p.name+' '+p.category).toLowerCase().includes(q));
    $('#products').innerHTML=products.map(p=>`<button class="product" data-id="${esc(p.id)}" aria-pressed="${p.id===selected}"><strong>${esc(p.name)}</strong><small>${esc(p.category)} · ${p.tables.length?`${p.tables.length} 张官方规格表`:'待提取规格'}</small></button>`).join('')||'<p>没有符合筛选条件的产品。</p>';
    $('#matches').textContent=`${products.length} 项`;
    for(const mode of ['products','specs'])$('#export-'+mode).href='/api/product-catalog/nvidia?'+new URLSearchParams({export:mode,q,kind,with_specs:$('#with-specs').checked?'1':''});
    document.querySelectorAll('.product').forEach(b=>b.onclick=()=>select(b.dataset.id));
    if(products.length&&!products.some(p=>p.id===selected))select(products[0].id);
    if(!products.length)$('#detail').textContent='没有符合筛选条件的产品。';
  }
  async function load() {
    const current=++generation;
    $('#status').textContent='正在读取产品清单…';
    try {
      const response=await fetch('/api/product-catalog/nvidia',{cache:'no-store'});
      if(!response.ok)throw Error('产品数据库暂时不可用，请刷新重试。');
      const data=await response.json();if(current!==generation)return;
      catalog=data;
      if(!data.available){$('#status').textContent='等待 M5 首次交付产品清单。';return;}
      const c=data.coverage;
      $('#status').textContent=`更新于 ${data.generated_at} · 官方清单整理中，尚未确认全公司产品总数`;
      $('#metrics').innerHTML=[['官方目录入口',c.directory_entries],['已识别型号页',c.entity_counts.named_product||0],['有规格表的条目',c.with_spec_tables],['待访问页面',c.pending_pages],['访问失败',c.failed_pages]].map(([label,n])=>`<div class="metric"><strong>${esc(n)}</strong>${esc(label)}</div>`).join('');
      $('#limitations').innerHTML=c.limitations.map(v=>`<li>${esc(v)}</li>`).join('');filter();
    } catch(e) {if(current===generation)$('#status').textContent=e.message;}
  }
  $('#query').oninput=filter;$('#kind').onchange=filter;$('#with-specs').onchange=filter;$('#retry').onclick=load;load();
})();
