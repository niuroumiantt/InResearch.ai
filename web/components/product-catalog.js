(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const kinds = {named_product:'具体型号页 · 待身份复核',family_or_directory:'系列 / 平台 / 目录',software_service:'软件 / 服务'};
  // One page per registered company: ?c=<company> (default nvidia) reads /api/product-catalog/<company>.
  // NVIDIA keeps its reviewed five display groups; other companies are browsed by the vendor's own product path.
  // The receiver registry also supplies the company switch; no separate browser allowlist.
  const requested = (new URLSearchParams(location.search).get('c') || 'nvidia').toLowerCase();
  const company = requested;
  let companyLabel = company;
  const vendorPath = company !== 'nvidia';
  const api = '/api/product-catalog/' + encodeURIComponent(company);
  const searchText = p => p.name+' '+p.category+(p.part_number?' '+p.part_number:'');
  const listingLabels = {active:'官网在列', obsolete:'官网列为停产', directory:'目录 / 分类页'};
  // Display translation of the vendor's own group / family names; the original name is always shown beside it.
  const zhLabels = {micron:{
    groups:{memory:'内存',storage:'存储','multichip-packages':'多芯片封装',obsolete:'停产型号（只登记）','bare-die':'裸片','nonvolatile-memory-security':'非易失存储安全','product-lifecycle-solutions':'产品生命周期方案','technology-leadership':'技术'},
    families:{'dram-components':'DRAM 颗粒','dram-modules':'DRAM 内存条','lpddr-components':'LPDDR 颗粒','lpddr-modules':'LPDDR 模组',hbm:'高带宽内存 HBM','graphics-memory':'显存 GDDR',ssd:'固态硬盘 SSD','nand-flash':'NAND 闪存','nor-flash':'NOR 闪存','managed-nand':'嵌入式存储','memory-cards':'存储卡','emmc-based-mcp':'e.MMC 多芯片封装','nand-based-mcp':'NAND 多芯片封装','ufs-based-mcp':'UFS 多芯片封装'}}};
  const zh=(kind,id,label)=>{const t=zhLabels[company]?.[kind]?.[id];return t?`${t} · ${label}`:label;};
  const natural=(a,b)=>a.localeCompare(b,'en',{numeric:true});
  function vendorLine(p) {
    if(!vendorPath)return '';
    const path=(p.taxonomy||[]).map(t=>t.name||t.slug).join(' › ');
    return `<p class="muted">官方产品路径：${esc(path||'未提供')}${p.part_number?` · 料号：${esc(p.part_number)}`:''} · 官网状态（原文）：${esc(p.official_status||'未标注')}${p.listing?` · ${esc(listingLabels[p.listing]||p.listing)}`:''}</p>`;
  }
  document.querySelectorAll('#company-switch a').forEach(a=>{if(a.dataset.company===company)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  for(const mode of ['products','map','specs'])$('#export-'+mode).href=api+'?export='+mode;
  if(vendorPath){
    document.title=`${companyLabel} 产品规格库 · inresearch.ai`;
    $('#catalog-title').textContent=`${companyLabel} 产品规格库`;
    $('#batch-link').textContent='Fetchspec 交付';$('#batch-link').href='/supply.html#providers';
    $('#groups').classList.add('vendor');
    $('#query').placeholder='型号、料号或官方分类';
  }
  let catalog = {products:[]}, selected = '', selectedSeries = new URLSearchParams(location.search).get('series') || '', generation = 0, detailGeneration = 0, loadController;
  let byId = new Map();
  const seriesById = new Map();
  // ?group=&family= open a vendor family directly (links from the company page)
  const linkedPath = new URLSearchParams(location.search);
  let group = linkedPath.get('group') || (vendorPath ? '' : 'datacenter'), family = linkedPath.get('family') || '', scope = linkedPath.get('scope') || 'catalog', page = 0;
  $('#kind').value=linkedPath.get('kind')||'';$('#with-specs').checked=linkedPath.get('with_specs')==='1';
  const pageSize = 15;
  const compared = new Set();
  const detailsById = new Map();
  const specificationGaps = {
    official_specification_source_unavailable: {
      label: '官网规格来源不可用',
      detail: '官网型号专属规格页已删除或不可用；产品与来源记录已保留，不以相邻型号或非官方参数补值。'
    },
    vendor_specification_gap: {
      label: '官网零件页未提供规格',
      detail: '已核对的官网零件页没有型号规格组件，也没有可抓取的系列规格资料；产品与来源记录已保留，不以相邻型号补值。'
    },
    part_page_unavailable: {
      label: '官网零件页已下线',
      detail: '官网 sitemap 仍列出该零件，但页面返回 404 / 410；保留身份，不推断停产。'
    },
    not_collected_obsolete: {
      label: '停产型号（只登记）',
      detail: '官网把该零件列在停产目录下：按标准只登记身份，不抓规格。'
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
  const tableCount = p => Number(p?.table_count ?? p?.tables?.length ?? 0);
  function tableHtml(table) {
    const rich=s=>esc(s).replace(/\^\{([^{}]*)\}/g,'<sup>$1</sup>').replace(/_\{([^{}]*)\}/g,'<sub>$1</sub>');
    const refs=table.source_refs||[];
    const evidence=refs.length?`<p class="source">表格来源：${refs.map(r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener">查看原始附件</a> · SHA-256：${esc(r.sha256)}`).join('；')}</p>`:'';
    return `<h3>${rich(table.section || `官方表格 ${table.index}`)}</h3><div class="table-wrap"><table aria-label="${esc(table.section)}"><tbody>${table.rows.map(row=>`<tr>${row.map(c=>{const tag=c.header?'th':'td';return `<${tag} colspan="${Number(c.colspan)||1}" rowspan="${Number(c.rowspan)||1}">${rich(c.text)}</${tag}>`;}).join('')}</tr>`).join('')}</tbody></table></div>${table.notes?`<p class="notes">${rich(table.notes)}</p>`:''}${evidence}`;
  }
  const simpleParameters=p=>{
      const pairs=new Map();
      for(const t of p.tables||[])for(const row of t.rows||[]){
        if(row.length!==2||row.some(c=>Number(c.colspan||1)!==1||Number(c.rowspan||1)!==1)||row[1].header)continue;
        const [key,value]=row.map(c=>c.text?.trim());
        if(!key||!value)continue;
        if(pairs.has(key))pairs.set(key,null);else pairs.set(key,value);
      }
      return pairs;
  };
  function details(p, compact = false) {
    const parameters=[...simpleParameters(p)].filter(([key,value])=>value!=null&&/processor|cpu|gpu|memory|capacity|dimensions|form factor|power|interface|network/i.test(key)).slice(0,6);
    const highlights=!compact&&parameters.length?`<div class="key-parameters"><h3>关键参数 · 官方原文</h3><dl>${parameters.map(([key,value])=>`<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl><p class="basis">仅列明确的单值字段，配置与适用条件请核对完整原表。</p></div>`:'';

    const parent=p.parent_id?catalog.products.find(x=>x.id===p.parent_id):null;
    const resources=p.official_resources||[];
    const compute=p.compute;
    const chipLine=(compute?.chip_links||[]).map(l=>`<p>使用芯片：<a href="/product-catalog.html?${new URLSearchParams({c:company,product_id:l.product_id})}">${esc(catalog.products.find(x=>x.id===l.product_id)?.name||l.product_id)}</a> · 官方对应原文：${esc(l.evidence_quote)} ${(l.source_refs||[]).map(r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener">来源</a>`).join(' ')}</p>`).join('');
    const computeLine=compute?`<p>计算分类：${esc(({cpu:'CPU',gpu:'GPU',accelerator:'其他计算加速器',unknown:'待核验',excluded:'非计算芯片'})[compute.category])} · 形态：${esc(({chip:'芯片',board:'板卡',module:'模组',system:'整机 / 平台',series:'系列 / 目录',ip:'IP',unknown:'待核验'})[compute.form])} · 架构原文：${esc(compute.architecture||'—')}</p>${compute.classification_note?`<p>${esc(compute.classification_note)}</p>`:''}`:'';
    const sm=p.website_sitemap||{};
    const localized=(p.official_pages||[]).filter(x=>x.url!==p.source_url);
    return `<h2>${esc(p.name)}</h2><p>${esc(p.navigation?.family_label)} · ${esc(kinds[p.kind])}${parent?` · 所属平台：${esc(parent.name)}`:''}</p>${vendorLine(p)}${computeLine}${chipLine}${highlights}<details><summary>产品分类与获取记录</summary><p>${esc(p.category)}</p><p class="muted">在售状态：待核对 · 产品地图：${esc(p.map_change_status||'已登记')} · 来源出现在官方语言 sitemap：${sm.matched?'是（'+esc((sm.roles||[]).join('、'))+'）':'否 / 尚未匹配'} · 获取于 ${esc(p.observed_at)}</p></details>${compact?'':`<button id="compare">${compared.has(p.id)?'移出并排核查':'加入并排核查（最多 4 项）'}</button>`}${p.tables.length?p.tables.map(t=>p.tables.length>3?`<details class="raw-specification"><summary>${esc(t.section||'官方表格 '+t.index)}</summary>${tableHtml(t)}</details>`:tableHtml(t)).join(''):`<p class="notice"><strong>${esc(gap(p).label)}</strong><br>${esc(gap(p).detail)}</p>`}<p class="source"><a href="${esc(p.source_url)}" target="_blank" rel="noopener">查看官方来源</a> · 原文快照 SHA-256：${esc(p.source_sha256)}</p>${localized.length?`<details><summary>其他语言官方来源（${localized.length}）</summary><ul>${localized.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">查看官方页面</a> · SHA-256：${esc(s.sha256)}</li>`).join('')}</ul></details>`:''}${resources.length?`<details open><summary>官方规格资料入口（${resources.length}，尚未确认文件可直接下载）</summary><ul>${resources.map(a=>`<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url)}</a> · ${esc(a.access_status||'待核实')}</li>`).join('')}</ul></details>`:''}${p.attachments.length?`<details><summary>关联附件（${p.attachments.length}）</summary><ul>${p.attachments.map(a=>`<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url.split('/').pop())}</a></li>`).join('')}</ul></details>`:''}`;
  }
  async function fetchDetail(id) {
    if(detailsById.has(id))return detailsById.get(id);
    const batch=generation;
    const response=await fetch(api+'?'+new URLSearchParams({product_id:id}),{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw Error('产品规格暂时不可用，请稍后重试。');
    const data=await response.json();
    if(!data.product)throw Error('这项产品已不在当前目录中，请刷新产品清单。');
    if(batch!==generation)throw Error('目录已刷新，请重新选择产品。');
    detailsById.set(id,data.product);
    return data.product;
  }
  let comparisonGeneration=0;
  async function renderComparison() {
    const current=++comparisonGeneration;
    const products=(await Promise.all([...compared].map(async id=>{
      try{return await fetchDetail(id);}catch{return null;}
    }))).filter(Boolean);

    if(current!==comparisonGeneration)return;
    $('#comparison').hidden=!compared.size;
    // Only simple, unambiguous two-cell rows can join the matrix. Complex tables
    // retain configuration columns, merged cells and notes in the original below.
    const maps=products.map(simpleParameters), keys=[...new Set(maps.flatMap(m=>[...m.keys()]))].slice(0,12);
    const failures=[...compared].filter(id=>!products.some(p=>p.id===id));
    $('#comparison-matrix').innerHTML=`<p class="basis">参数名与数值保留官方原文，不合并不同单位、配置或测试条件。复杂合并表在下方原表核查。</p>${failures.length?`<p class="comparison-failure">${failures.map(id=>esc(byId.get(id)?.name||id)).join('、')} 规格读取失败。<button id="retry-comparison">重试对比</button></p>`:''}${products.length?`<div class="table-wrap"><table><thead><tr><th>官方参数</th>${products.map(p=>`<th>${esc(p.name)}</th>`).join('')}</tr></thead><tbody>${keys.map(k=>`<tr><th scope="row">${esc(k)}</th>${maps.map(m=>`<td>${esc(m.get(k)??'— / 查看原表')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:''}${keys.length?'':'<p>当前表格需要按原始配置列核查，未自动合成参数。</p>'}`;
    $('#retry-comparison')?.addEventListener('click',renderComparison);
    $('#comparison-items').innerHTML=products.map(p=>`<article><details><summary>${esc(p.name)} · 官方完整原表与来源</summary>${details(p,true)}</details></article>`).join('');
    document.querySelectorAll('#model-rows input').forEach(el=>{el.checked=compared.has(el.dataset.id);});
  }
  async function select(id) {
    selected=id;
    remember({product_id:id,series:'',group,family});
    const summary=byId.get(id);
    if(!summary)return;
    document.querySelectorAll('.product').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===id||(!!b.dataset.series&&b.dataset.series===summary.parent_id))));
    const current=++detailGeneration;
    $('#detail').innerHTML=`<h2>${esc(summary.name)}</h2><p class="muted">正在读取这项产品的官方规格…</p>`;
    let p;
    try {p=await fetchDetail(id);} catch(e) {
      if(current===detailGeneration)$('#detail').innerHTML=`<h2>${esc(summary.name)}</h2><p class="notice">${esc(e.message)}</p><button id="retry-detail">重试规格</button>`;
      $('#retry-detail')?.addEventListener('click',()=>select(id));
      return;
    }
    if(current!==detailGeneration||selected!==id)return;
    const series=vendorPath&&byId.get(p.parent_id);
    $('#detail').innerHTML=(series&&series.listing==='directory'?`<button id="back-series">← 返回系列：${esc(series.name)}</button>`:'')+details(p);
    if($('#back-series'))$('#back-series').onclick=()=>selectSeries(series.id);
    $('#compare').onclick=()=>{
      if(compared.has(id))compared.delete(id);else if(compared.size<4)compared.add(id);else {$('#status').textContent='最多并排核查 4 项，请先移出一项。';return;}
      renderComparison();
      select(id);
    };
  }
  function navigation() {
    const items=catalog.products.filter(p=>p.navigation.role==='catalog');
    // Vendor taxonomy: largest groups first, groups with no products (pure category pages) left to the
    // directory list, the vendor's obsolete catalogue last. NVIDIA keeps its curated order.
    const size=g=>items.filter(p=>p.navigation.group===g.id).length;
    const groups=vendorPath?catalog.navigation.groups.filter(g=>size(g)>0).sort((a,b)=>(/obsolete/i.test(a.id)-/obsolete/i.test(b.id))||size(b)-size(a)):catalog.navigation.groups;
    if(!groups.some(g=>g.id===group))group=groups[0]?.id||'';
    $('#groups').innerHTML=groups.map(g=>`<button data-group="${esc(g.id)}" aria-pressed="${scope==='catalog'&&group===g.id&&!$('#query').value}"><strong>${esc(zh('groups',g.id,g.label))}</strong><small>${items.filter(p=>p.navigation.group===g.id).length} ${vendorPath?'个目录条目':'个产品 / 系列条目'}</small></button>`).join('');
    $('#auxiliary').textContent=`${vendorPath?'目录与分类页 / 待归类':'辅助资料 / 待归类'}（${catalog.products.length-items.length}）`;
    $('#auxiliary').setAttribute('aria-pressed',String(scope==='auxiliary'));
    $('#groups').querySelectorAll('button').forEach(b=>b.onclick=()=>{group=b.dataset.group;family='';scope='catalog';page=0;$('#query').value='';filter();});
    const families=new Map();
    items.filter(p=>p.navigation.group===group).forEach(p=>families.set(p.navigation.family,p.navigation.family_label));
    const familySize=id=>items.filter(p=>p.navigation.group===group&&p.navigation.family===id).length;
    const choices=[...families].sort((a,b)=>vendorPath?familySize(b[0])-familySize(a[0]):a[1].localeCompare(b[1],'zh-CN'));
    if(!family||!families.has(family))family=choices.some(([id])=>id==='accelerators')?'accelerators':choices[0]?.[0]||'';
    $('#families').innerHTML=choices.map(([id,label])=>`<button data-family="${esc(id)}" aria-pressed="${family===id}">${esc(zh('families',id,label))} <small>${familySize(id)}</small></button>`).join('');
    $('#families').hidden=scope!=='catalog'||!!$('#query').value;
    $('#families').querySelectorAll('button').forEach(b=>b.onclick=()=>{family=b.dataset.family;page=0;filter();});
  }
  // The series path between the family and the series itself, e.g. "Data center SSD".
  const seriesPath=entry=>(entry.taxonomy||[]).slice(2,-1).map(t=>t.name||t.slug).join(' › ');
  function seriesList(parts) {
    const groups=new Map();
    parts.forEach(p=>{const id=byId.has(p.parent_id)?p.parent_id:'';if(!groups.has(id))groups.set(id,[]);groups.get(id).push(p);});
    const orphans=groups.get('')||[];groups.delete('');
    // Series with official specifications first; within that, the vendor sub-path with the most parts
    // (e.g. Data center SSD) first, then series names in natural order.
    const list=[...groups].map(([id,members])=>({entry:byId.get(id),members}));
    const pathSize=new Map();list.forEach(s=>pathSize.set(seriesPath(s.entry),(pathSize.get(seriesPath(s.entry))||0)+s.members.length));
    const empty=s=>Number(!s.members.some(tableCount));
    list.sort((a,b)=>empty(a)-empty(b)||pathSize.get(seriesPath(b.entry))-pathSize.get(seriesPath(a.entry))||natural(seriesPath(a.entry),seriesPath(b.entry))||natural(a.entry.name,b.entry.name));
    page=Math.min(page,Math.max(0,Math.ceil(list.length/pageSize)-1));
    const shown=list.slice(page*pageSize,(page+1)*pageSize);
    const statusText=members=>{const n=members.filter(p=>p.official_status==='Production').length;return n?` · 量产 ${n}`:'';};
    $('#products').innerHTML=shown.map(({entry,members})=>`<button class="product series" data-series="${esc(entry.id)}" aria-pressed="${entry.id===selectedSeries}"><strong>${esc(entry.name)}</strong><small>${seriesPath(entry)?esc(seriesPath(entry))+' · ':''}${members.length} 个料号 · 有规格 ${members.filter(tableCount).length}${statusText(members)}</small></button>`).join('')
      +orphans.map(p=>`<button class="product" data-id="${esc(p.id)}" aria-pressed="${p.id===selected}"><strong>${esc(p.name)}</strong><small>未挂在官方系列页下 · ${tableCount(p)?`${tableCount(p)} 张规格表`:esc(gap(p).label)}</small></button>`).join('')
      ||'<p>没有符合筛选条件的条目。</p>';
    $('#matches').textContent=`${list.length} 个系列 · ${parts.length} 个料号`;
    $('#previous').disabled=page===0;$('#next').disabled=(page+1)*pageSize>=list.length;
    document.querySelectorAll('.product[data-series]').forEach(b=>b.onclick=()=>selectSeries(b.dataset.series));
    document.querySelectorAll('.product[data-id]').forEach(b=>b.onclick=()=>select(b.dataset.id));
    if(shown.length)selectSeries(shown.some(s=>s.entry.id===selectedSeries)?selectedSeries:shown[0].entry.id);
    else if(orphans.length)select(orphans[0].id);
    else $('#detail').textContent='没有符合筛选条件的产品。';
  }
  async function fetchSeries(id) {
    if(seriesById.has(id))return seriesById.get(id);
    const batch=generation;
    const response=await fetch(api+'?'+new URLSearchParams({series_id:id}),{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw Error('系列对比暂时不可用，请稍后重试。');
    const data=await response.json();
    if(!data.series)throw Error('这个系列已不在当前目录中，请刷新产品清单。');
    if(batch!==generation)throw Error('目录已刷新，请重新选择系列。');
    seriesById.set(id,data.series);
    return data.series;
  }
  function seriesHtml(s) {
    const c=s.counts, path=(s.taxonomy||[]).map(t=>t.name||t.slug).join(' › ');
    const statuses=Object.entries(c.by_official_status).map(([k,v])=>`${k==='unspecified'?'官网未标注':k} ${v}`).join(' / ');
    const common=s.common.length?`<h3>本系列共同参数（每个料号相同，${s.common.length} 项）</h3><div class="table-wrap"><table class="series-common"><tbody>${s.common.map(r=>`<tr><th scope="row">${esc(r.label)}</th><td>${esc(r.value)}</td></tr>`).join('')}</tbody></table></div>`:'';
    const decoded=s.columns.some(col=>/decoded from part number/.test(col))?'<p class="notes">“decoded from part number” 列按厂商产品简介给出的料号规则解码（容量、外形），不是零件页原文。</p>':'';
    const compare=s.columns.length?`<h3>料号对比（${c.parts} 个料号 × ${s.columns.length} 项不同参数）</h3><p class="muted">每行一个官方料号，列名是官网零件页的原样参数名；点料号查看单项规格与来源。</p>${decoded}<div class="table-wrap"><table class="series-table"><thead><tr><th scope="col">料号</th><th scope="col">官网状态</th>${s.columns.map(col=>`<th scope="col">${esc(col)}</th>`).join('')}</tr></thead><tbody>${s.parts.map(p=>`<tr><th scope="row"><button class="part-link" data-id="${esc(p.id)}">${esc(p.name)}</button></th><td>${esc(p.official_status||'未标注')}</td>${s.columns.map(col=>`<td>${esc(p.values[col]??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'';
    const shared=s.shared_tables.map(t=>`<h3>系列规格总表</h3><p class="muted">厂商系列资料中的规格表，适用本系列 ${t.part_ids.length} 个料号；不是逐料号测得的数值。</p>${tableHtml(t)}`).join('');
    const listed=!s.columns.length?`<h3>料号（${c.parts}）</h3><ul class="series-parts">${s.parts.map(p=>`<li><button class="part-link" data-id="${esc(p.id)}">${esc(p.name)}</button> · ${esc(p.official_status||'官网未标注状态')}${Object.keys(p.values).length||s.shared_tables.some(t=>t.part_ids.includes(p.id))?'':' · '+esc(gap(p).label)}</li>`).join('')}</ul>`:'';
    return `<h2>${esc(s.name)}</h2><p class="muted">官方产品路径：${esc(path)} · <a href="${esc(s.source_url)}" target="_blank" rel="noopener">官网系列页</a></p><p>${c.parts} 个料号 · 有官方规格 ${c.with_specifications} / ${c.parts} · 官网状态（原文）：${esc(statuses)}</p>${common}${shared}${compare}${listed}<p class="source">系列页原文快照 SHA-256：${esc(s.source_sha256)} · 获取于 ${esc(s.observed_at)}</p>`;
  }
  async function selectSeries(id) {
    selectedSeries=id;selected='';
    remember({series:id,product_id:'',group,family});
    const entry=byId.get(id);
    document.querySelectorAll('.product').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.series===id)));
    const current=++detailGeneration;
    $('#detail').innerHTML=`<h2>${esc(entry?.name||'')}</h2><p class="muted">正在读取这个系列的官方规格…</p>`;
    let s;
    try {s=await fetchSeries(id);} catch(e) {
      if(current===detailGeneration)$('#detail').innerHTML=`<h2>${esc(entry?.name||'')}</h2><p class="notice">${esc(e.message)}</p><button id="retry-series">重试系列</button>`;
      $('#retry-series')?.addEventListener('click',()=>selectSeries(id));
      return;
    }
    if(current!==detailGeneration||selectedSeries!==id)return;
    $('#detail').innerHTML=seriesHtml(s);
    $('#detail').querySelectorAll('.part-link').forEach(b=>b.onclick=()=>select(b.dataset.id));
  }
  function modelRows(products) {
    $('#model-rows').innerHTML=products.slice(page*pageSize,(page+1)*pageSize).map(p=>`<tr><td><input type="checkbox" aria-label="对比 ${esc(p.name)}" data-id="${esc(p.id)}" ${compared.has(p.id)?'checked':''}></td><td><button data-product="${esc(p.id)}">${esc(p.name)}</button><small>${esc(p.kind==='named_product'?'具体型号':'系列 / 目录')}</small></td><td>${esc(p.category||'—')}</td><td>${esc(({chip:'芯片',board:'板卡',module:'模组',system:'整机 / 平台',series:'系列',ip:'IP'})[p.compute?.form]||'未登记')}</td><td>${tableCount(p)?tableCount(p)+' 张官方表':'待补规格'}</td></tr>`).join('')||'<tr><td colspan="5">没有符合筛选条件的产品。</td></tr>';
    $('#model-rows').querySelectorAll('[data-product]').forEach(b=>b.onclick=()=>{select(b.dataset.product);$('#detail').scrollIntoView({behavior:'smooth',block:'start'});});
    $('#model-rows').querySelectorAll('input').forEach(el=>el.onchange=()=>{
      if(el.checked&&compared.size>=4){el.checked=false;$('#status').textContent='最多并排核查 4 项，请先移出一项。';return;}
      if(el.checked)compared.add(el.dataset.id);else compared.delete(el.dataset.id);
      renderComparison();
    });
  }
  $('#clear-comparison').onclick=()=>{compared.clear();renderComparison();};
  function remember(fields) {
    const u=new URL(location.href);
    for(const [k,v] of Object.entries(fields)){if(v)u.searchParams.set(k,v);else u.searchParams.delete(k);}
    history.replaceState(null,'',u);
  }
  function filter() {
    if(!catalog.navigation)return;
    navigation();
    const q=$('#query').value.trim().toLowerCase(), kind=$('#kind').value;
    const activeGroup=q||scope!=='catalog'?'':group, activeFamily=q||scope!=='catalog'?'':family;
    const products=catalog.products.filter(p=>(scope==='catalog'?p.navigation.role==='catalog':p.navigation.role!=='catalog')&&(!activeGroup||p.navigation.group===activeGroup)&&(!activeFamily||p.navigation.family===activeFamily)&&(!kind||p.kind===kind)&&(!$('#with-specs').checked||tableCount(p))&&searchText(p).toLowerCase().includes(q)).sort((a,b)=>Number(b.kind==='named_product')-Number(a.kind==='named_product')||Number(!!tableCount(b))-Number(!!tableCount(a))||a.name.localeCompare(b.name,'en',{numeric:true}));
    const familyLabel=catalog.products.find(p=>p.navigation.group===group&&p.navigation.family===family)?.navigation.family_label||'';
    $('#breadcrumb').textContent=scope!=='catalog'?(vendorPath?'目录与分类页 / 待归类（数量按条目类型计）':'辅助资料 / 待归类（不计作具体产品）'):q?'跨大类搜索结果':`${zh('groups',group,catalog.navigation.groups.find(g=>g.id===group)?.label||'')} › ${zh('families',family,familyLabel)}`;
    for(const mode of ['products','map','specs'])$('#export-'+mode).href=api+'?'+new URLSearchParams({export:mode,q,kind,with_specs:$('#with-specs').checked?'1':'',group:activeGroup,family:activeFamily,scope});
    // Vendor catalogs list part numbers: browse them by series (the official page the parts hang from),
    // except in search, a kind filter, or the vendor's obsolete catalogue (listed parts only).
    modelRows(products);
    remember({q,kind,group:activeGroup,family:activeFamily,scope,with_specs:$('#with-specs').checked?'1':''});
    if(vendorPath&&scope==='catalog'&&!q&&!kind&&group!=='obsolete')return seriesList(products);
    page=Math.min(page,Math.max(0,Math.ceil(products.length/pageSize)-1));
    modelRows(products);
    const shown=products.slice(page*pageSize,(page+1)*pageSize);
    $('#products').innerHTML=shown.map(p=>`<button class="product" data-id="${esc(p.id)}" aria-pressed="${p.id===selected}"><strong>${esc(p.name)}</strong><small>${tableCount(p)?`${tableCount(p)} 张规格表`:gap(p).label} · ${p.kind==='named_product'?'具体型号':p.kind==='software_service'?'软件 / 服务':'系列 / 目录'}${vendorPath&&p.official_status?` · ${esc(p.official_status)}`:''}</small></button>`).join('')||'<p>没有符合筛选条件的条目。</p>';
    $('#matches').textContent=`${products.length} 项 · 当前显示 ${products.length?page*pageSize+1:0}–${Math.min(products.length,(page+1)*pageSize)}`;
    $('#previous').disabled=page===0;$('#next').disabled=(page+1)*pageSize>=products.length;
    document.querySelectorAll('.product').forEach(b=>b.onclick=()=>select(b.dataset.id));
    if(shown.length)select(shown.some(p=>p.id===selected)?selected:shown[0].id);
    if(!products.length)$('#detail').textContent='没有符合筛选条件的产品。';
  }
  async function load() {
    const current=++generation;
    detailGeneration++;comparisonGeneration++;
    if(loadController)loadController.abort();
    loadController=new AbortController();
    const timeout=setTimeout(()=>loadController.abort(),15000);
    $('#status').textContent='正在读取产品清单…';
    try {
      const response=await fetch(api+'?view=index',{cache:'no-store',signal:loadController.signal});
      if(current!==generation)return;
      if(response.status===404){window.dispatchEvent(new CustomEvent('company:catalog-error',{detail:'unregistered'}));$('#detail').textContent='尚未建立产品目录，已登记的公司关系可在下方查看。';throw Error(`尚未为这家公司建立产品目录。`);}
      if(!response.ok)throw Error('产品数据库暂时不可用，请刷新重试。');
      const data=await response.json();if(current!==generation)return;
      companyLabel=data.company?.label||company;
      document.title=`${companyLabel} · 公司与产品 · inresearch.ai`;
      $('#catalog-title').textContent=`${companyLabel} 产品规格库`;
      if(data.registered_companies)$('#company-switch').innerHTML=data.registered_companies.map(c=>`<a href="?c=${encodeURIComponent(c.id)}" data-company="${esc(c.id)}" ${c.id===company?'aria-current="page"':''}>${esc(c.label)}</a>`).join('');
      if(vendorPath)$('#groups-note').textContent='按已交付的官方产品路径浏览；未交付目录与待补规格分别展示。';
      if(vendorPath&&data.products.length&&!data.products.some(p=>p.navigation.role==='catalog'))scope='auxiliary';
      catalog=data;byId=new Map(data.products.map(p=>[p.id,p]));
      window.dispatchEvent(new CustomEvent('company:catalog',{detail:data}));
      const linkedProduct=byId.get(new URLSearchParams(location.search).get('product_id'));
      if(linkedProduct&&!new URLSearchParams(location.search).has('q'))$('#query').value=linkedProduct.name;
      detailsById.clear();seriesById.clear();compared.clear();comparisonGeneration++;$('#comparison').hidden=true;selected=linkedProduct?.id||'';detailGeneration++;
      // ?series=<id> opens that series (links from the company page)
      const linked=byId.get(selectedSeries);
      if(linked){const part=data.products.find(p=>p.parent_id===linked.id&&p.navigation.role==='catalog');if(part){group=part.navigation.group;family=part.navigation.family;}}
      if(!data.available){$('#model-rows').innerHTML='<tr><td colspan="5">等待首次目录交付。</td></tr>';$('#detail').textContent='尚无已交付产品规格。';$('#groups').replaceChildren();$('#families').replaceChildren();$('#status').textContent=vendorPath?`等待 Fetchspec 首次交付 ${companyLabel} 产品清单。`:'等待 M5 首次交付产品清单。';$('#coverage-line').textContent='';return;}
      const c=data.coverage;
      const alignment=data.research_alignment||{target_ids:[],part_ids:[]};
      const pm=c.product_map||{};
      const delta=Object.entries(pm.changes||{}).map(([k,v])=>`${k} ${v}`).join(' / ');
      const sm=c.website_sitemap||{};
      // vendor catalogs list obsolete parts without collecting them: the denominator is the current parts
      const named=data.products.filter(p=>p.kind==='named_product'&&p.listing!=='obsolete');
      const namedWithSpecs=named.filter(p=>tableCount(p));
      const explicitGaps=named.filter(p=>specificationGaps[p.extraction_status]);
      $('#status').textContent=`更新于 ${data.generated_at} · 具体型号规格 ${namedWithSpecs.length} / ${named.length} · 产品地图 ${pm.entries||data.products.length} 项${delta?` · 本次 ${delta}`:''}${vendorPath&&sm.candidate_urls==null?'':` · 官方 sitemap 候选 ${sm.candidate_urls??'尚未同步'}`} · 尚未确认全公司产品总数`;
      const cov=data.summary?.specification_coverage;
      // The standard's first denominator: current named products (obsolete parts are listed, not collected).
      const covNamed=cov?.current_named_products||cov?.named_products;
      $('#coverage-line').textContent=cov?`规格覆盖（两个分母分开）：${cov.current_named_products?'在售':''}具体型号有官方规格表 ${covNamed.with_tables} / ${covNamed.total} · 全部目录实体有规格表 ${cov.all_entities.with_tables} / ${cov.all_entities.total}${(data.summary?.by_extraction_status||{}).family_brief_table_extracted?`（其中 ${data.summary.by_extraction_status.family_brief_table_extracted} 个是系列产品简介的规格总表，非逐型号）`:''}${cov.obsolete_listed?` · 另有停产型号 ${cov.obsolete_listed} 个只登记不抓规格`:''}`:'';
      if(vendorPath)$('#groups-note').innerHTML=`分类沿用 <a href="${esc(data.navigation?.official_source||data.company?.products_url||'')}" target="_blank" rel="noopener">${esc(companyLabel)} 官方目录</a>。系列可展开料号与参数；停产登记不计当前型号覆盖，原文参数保留各自配置与条件。`;

      $('#alignment').innerHTML=`已与新版主线对齐：当前 ${esc(companyLabel)} 资料可服务 <strong>${esc(alignment.target_ids.length)}</strong> 条 Fetchspec 生成目标、<strong>${esc(alignment.part_ids.length)}</strong> 个部件；这里只显示候选规格，不自动写成正式研究事实。 <a href="/node.html?node=root">查看数据中心节点树</a> · <a href="/supply.html#providers">查看 Fetchspec 目标</a>`;
      const sum=data.summary||{};
      const vendorMetrics=[['目录实体',sum.entities],[cov?.current_named_products?'在售型号规格覆盖':'具体型号规格覆盖',cov?`${covNamed.with_tables} / ${covNamed.total}`:'—'],['有规格表的全部条目',cov?`${cov.all_entities.with_tables} / ${cov.all_entities.total}`:'—'],['官网明确规格缺口',explicitGaps.length],...Object.entries(sum.by_listing||{}).map(([k,v])=>[listingLabels[k]||'未标注列出状态',v]),...Object.entries(sum.by_official_status||{}).map(([k,v])=>['官网状态：'+(k==='unspecified'?'未标注':k),v]),['待访问页面',c.pending_pages??'—'],['访问失败（可重试）',c.failed_pages??'—']];
      $('#metrics').innerHTML=vendorPath?vendorMetrics.map(([label,n])=>`<div class="metric"><strong>${esc(n)}</strong>${esc(label)}</div>`).join(''):[['产品目录入口',c.directory_entries],['目录实体',pm.entries||data.products.length],['具体型号规格覆盖',`${namedWithSpecs.length} / ${named.length}`],['官网明确规格缺口',explicitGaps.length],['有规格表的全部条目',c.with_spec_tables],['官方 sitemap 候选 URL',sm.candidate_urls??'—'],['已核对产品 URL',`${sm.product_path_observed??0} / ${sm.product_path_candidates??'—'}`],['产品来源命中 sitemap',sm.matched_catalog_sources??'—'],['待访问页面',c.pending_pages],['访问失败（可重试）',c.failed_pages],['官网已删除旧页',c.unavailable_pages??0],['策略阻止跳转',c.policy_blocked_pages??0]].map(([label,n])=>`<div class="metric"><strong>${esc(n)}</strong>${esc(label)}</div>`).join('');
      $('#limitations').innerHTML=(c.limitations||[]).map(v=>`<li>${esc(v)}</li>`).join('');
      const initialQuery=new URLSearchParams(location.search).get('q');if(initialQuery!==null)$('#query').value=initialQuery;
      filter();
    } catch(e) {if(current===generation&&e.message!=='尚未为这家公司建立产品目录。')window.dispatchEvent(new CustomEvent('company:catalog-error',{detail:'failed'}));if(current===generation)$('#status').textContent=e.name==='AbortError'?'产品清单读取超时，请点击刷新重试。':e.message;}
    finally {clearTimeout(timeout);}
  }
  $('#query').oninput=()=>{page=0;filter();};$('#kind').onchange=()=>{page=0;filter();};$('#with-specs').onchange=()=>{page=0;filter();};$('#retry').onclick=load;
  $('#auxiliary').onclick=()=>{scope=scope==='auxiliary'?'catalog':'auxiliary';page=0;$('#query').value='';filter();};
  $('#previous').onclick=()=>{page--;filter();};$('#next').onclick=()=>{page++;filter();};
  window.addEventListener('pageshow',event=>{
    if(event.persisted&&(!catalog.navigation||$('#status').textContent.includes('正在读取')))load();
  });
  window.addEventListener('popstate',()=>location.reload());
  load();
})();
