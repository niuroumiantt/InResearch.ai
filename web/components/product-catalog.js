(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const kinds = {named_product:'具体型号页 · 待身份复核',family_or_directory:'系列 / 平台 / 目录',software_service:'软件 / 服务'};
  let catalog = {products:[]}, selected = '', generation = 0;
  let group = 'datacenter', family = '', scope = 'catalog', page = 0;
  const pageSize = 15;
  const compared = new Set();
  const specificationGaps = {
    official_specification_source_unavailable: {
      label: '官网规格来源不可用',
      detail: '官网型号专属规格页已删除或不可用；产品与来源记录已保留，不以相邻型号或非官方参数补值。'
    },
    official_specification_not_published_on_observed_page: {
      label: '官网未发布型号规格',
      detail: '已核对的官网产品页未发布型号专属规格表或附件；产品与来源记录已保留，不以相邻型号或非官方参数补值。'
    }
  };
  function gap(p) {
    return specificationGaps[p.extraction_status] || {
      label: '规格待补齐',
      detail: '已发现官方产品入口，具体规格仍待寻找或提取。这里不以相邻产品参数补值。'
    };
  }
  function tableHtml(table) {
    const rich=s=>esc(s).replace(/\^\{([^{}]*)\}/g,'<sup>$1</sup>').replace(/_\{([^{}]*)\}/g,'<sub>$1</sub>');
    const refs=table.source_refs||[];
    const evidence=refs.length?`<p class="source">表格来源：${refs.map(r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener">查看原始附件</a> · SHA-256：${esc(r.sha256)}`).join('；')}</p>`:'';
    return `<h3>${rich(table.section || `官方表格 ${table.index}`)}</h3><div class="table-wrap"><table aria-label="${esc(table.section)}"><tbody>${table.rows.map(row=>`<tr>${row.map(c=>{const tag=c.header?'th':'td';return `<${tag} colspan="${Number(c.colspan)||1}" rowspan="${Number(c.rowspan)||1}">${rich(c.text)}</${tag}>`;}).join('')}</tr>`).join('')}</tbody></table></div>${table.notes?`<p class="notes">${rich(table.notes)}</p>`:''}${evidence}`;
  }
  function details(p, compact = false) {
    const parent=p.parent_id?catalog.products.find(x=>x.id===p.parent_id):null;
    const resources=p.official_resources||[];
    const sm=p.website_sitemap||{};
    const localized=(p.official_pages||[]).filter(x=>x.url!==p.source_url);
    return `<h2>${esc(p.name)}</h2><p>${esc(p.navigation?.family_label)} · ${esc(kinds[p.kind])}${parent?` · 所属平台：${esc(parent.name)}`:''}</p><details><summary>官方原始分类与获取记录</summary><p>${esc(p.category)}</p><p class="muted">在售状态：待核对 · 产品地图：${esc(p.map_change_status||'已登记')} · 来源出现在官方语言 sitemap：${sm.matched?'是（'+esc((sm.roles||[]).join('、'))+'）':'否 / 尚未匹配'} · 获取于 ${esc(p.observed_at)}</p></details>${compact?'':`<button id="compare">${compared.has(p.id)?'移出并排核查':'加入并排核查（最多 4 项）'}</button>`}${p.tables.length?p.tables.map(tableHtml).join(''):`<p class="notice"><strong>${esc(gap(p).label)}</strong><br>${esc(gap(p).detail)}</p>`}<p class="source"><a href="${esc(p.source_url)}" target="_blank" rel="noopener">查看官方来源</a> · 原文快照 SHA-256：${esc(p.source_sha256)}</p>${localized.length?`<details><summary>其他语言官方来源（${localized.length}）</summary><ul>${localized.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">查看官方页面</a> · SHA-256：${esc(s.sha256)}</li>`).join('')}</ul></details>`:''}${resources.length?`<details open><summary>官方规格资料入口（${resources.length}，尚未确认文件可直接下载）</summary><ul>${resources.map(a=>`<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url)}</a> · ${esc(a.access_status||'待核实')}</li>`).join('')}</ul></details>`:''}${p.attachments.length?`<details><summary>关联附件（${p.attachments.length}）</summary><ul>${p.attachments.map(a=>`<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url.split('/').pop())}</a></li>`).join('')}</ul></details>`:''}`;
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
  function navigation() {
    const items=catalog.products.filter(p=>p.navigation.role==='catalog');
    $('#groups').innerHTML=catalog.navigation.groups.map(g=>`<button data-group="${esc(g.id)}" aria-pressed="${scope==='catalog'&&group===g.id&&!$('#query').value}"><strong>${esc(g.label)}</strong><small>${items.filter(p=>p.navigation.group===g.id).length} 个产品 / 系列条目</small></button>`).join('');
    $('#auxiliary').textContent=`辅助资料 / 待归类（${catalog.products.length-items.length}）`;
    $('#auxiliary').setAttribute('aria-pressed',String(scope==='auxiliary'));
    $('#groups').querySelectorAll('button').forEach(b=>b.onclick=()=>{group=b.dataset.group;family='';scope='catalog';page=0;$('#query').value='';filter();});
    const families=new Map();
    items.filter(p=>p.navigation.group===group).forEach(p=>families.set(p.navigation.family,p.navigation.family_label));
    const choices=[...families].sort((a,b)=>a[1].localeCompare(b[1],'zh-CN'));
    if(!family||!families.has(family))family=choices.some(([id])=>id==='accelerators')?'accelerators':choices[0]?.[0]||'';
    $('#families').innerHTML=choices.map(([id,label])=>`<button data-family="${esc(id)}" aria-pressed="${family===id}">${esc(label)} <small>${items.filter(p=>p.navigation.group===group&&p.navigation.family===id).length}</small></button>`).join('');
    $('#families').hidden=scope!=='catalog'||!!$('#query').value;
    $('#families').querySelectorAll('button').forEach(b=>b.onclick=()=>{family=b.dataset.family;page=0;filter();});
  }
  function filter() {
    if(!catalog.navigation)return;
    navigation();
    const q=$('#query').value.trim().toLowerCase(), kind=$('#kind').value;
    const activeGroup=q||scope!=='catalog'?'':group, activeFamily=q||scope!=='catalog'?'':family;
    const products=catalog.products.filter(p=>(scope==='catalog'?p.navigation.role==='catalog':p.navigation.role!=='catalog')&&(!activeGroup||p.navigation.group===activeGroup)&&(!activeFamily||p.navigation.family===activeFamily)&&(!kind||p.kind===kind)&&(!$('#with-specs').checked||p.tables.length)&&(p.name+' '+p.category).toLowerCase().includes(q)).sort((a,b)=>Number(b.kind==='named_product')-Number(a.kind==='named_product')||Number(!!b.tables.length)-Number(!!a.tables.length)||a.name.localeCompare(b.name,'en',{numeric:true}));
    page=Math.min(page,Math.max(0,Math.ceil(products.length/pageSize)-1));
    const shown=products.slice(page*pageSize,(page+1)*pageSize);
    $('#products').innerHTML=shown.map(p=>`<button class="product" data-id="${esc(p.id)}" aria-pressed="${p.id===selected}"><strong>${esc(p.name)}</strong><small>${p.tables.length?`${p.tables.length} 张规格表`:gap(p).label} · ${p.kind==='named_product'?'具体型号':p.kind==='software_service'?'软件 / 服务':'系列 / 目录'}</small></button>`).join('')||'<p>没有符合筛选条件的条目。</p>';
    $('#matches').textContent=`${products.length} 项 · 当前显示 ${products.length?page*pageSize+1:0}–${Math.min(products.length,(page+1)*pageSize)}`;
    $('#breadcrumb').textContent=scope!=='catalog'?'辅助资料 / 待归类（不计作具体产品）':q?'跨大类搜索结果':`${catalog.navigation.groups.find(g=>g.id===group)?.label||''} › ${catalog.products.find(p=>p.navigation.family===family)?.navigation.family_label||''}`;
    $('#previous').disabled=page===0;$('#next').disabled=(page+1)*pageSize>=products.length;
    for(const mode of ['products','map','specs'])$('#export-'+mode).href='/api/product-catalog/nvidia?'+new URLSearchParams({export:mode,q,kind,with_specs:$('#with-specs').checked?'1':'',group:activeGroup,family:activeFamily,scope});
    document.querySelectorAll('.product').forEach(b=>b.onclick=()=>select(b.dataset.id));
    if(shown.length)select(shown.some(p=>p.id===selected)?selected:shown[0].id);
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
      const pm=c.product_map||{};
      const delta=Object.entries(pm.changes||{}).map(([k,v])=>`${k} ${v}`).join(' / ');
      const sm=c.website_sitemap||{};
      const named=data.products.filter(p=>p.kind==='named_product');
      const namedWithSpecs=named.filter(p=>p.tables.length);
      const explicitGaps=named.filter(p=>specificationGaps[p.extraction_status]);
      $('#status').textContent=`更新于 ${data.generated_at} · 具体型号规格 ${namedWithSpecs.length} / ${named.length} · 产品地图 ${pm.entries||data.products.length} 项${delta?` · 本次 ${delta}`:''} · 官方 sitemap 候选 ${sm.candidate_urls??'尚未同步'} · 尚未确认全公司产品总数`;
      $('#metrics').innerHTML=[['产品目录入口',c.directory_entries],['目录实体',pm.entries||data.products.length],['具体型号规格覆盖',`${namedWithSpecs.length} / ${named.length}`],['官网明确规格缺口',explicitGaps.length],['有规格表的全部条目',c.with_spec_tables],['官方 sitemap 候选 URL',sm.candidate_urls??'—'],['已核对产品 URL',`${sm.product_path_observed??0} / ${sm.product_path_candidates??'—'}`],['产品来源命中 sitemap',sm.matched_catalog_sources??'—'],['待访问页面',c.pending_pages],['访问失败（可重试）',c.failed_pages],['官网已删除旧页',c.unavailable_pages??0],['策略阻止跳转',c.policy_blocked_pages??0]].map(([label,n])=>`<div class="metric"><strong>${esc(n)}</strong>${esc(label)}</div>`).join('');
      $('#limitations').innerHTML=c.limitations.map(v=>`<li>${esc(v)}</li>`).join('');filter();
    } catch(e) {if(current===generation)$('#status').textContent=e.message;}
  }
  $('#query').oninput=()=>{page=0;filter();};$('#kind').onchange=()=>{page=0;filter();};$('#with-specs').onchange=()=>{page=0;filter();};$('#retry').onclick=load;
  $('#auxiliary').onclick=()=>{scope=scope==='auxiliary'?'catalog':'auxiliary';page=0;$('#query').value='';filter();};
  $('#previous').onclick=()=>{page--;filter();};$('#next').onclick=()=>{page++;filter();};load();
})();
