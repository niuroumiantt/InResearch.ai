/* Public company overview uses the existing catalog projection and public definitions.
   Research annexes are loaded by company-context only after authenticated expansion. */
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cid = new URLSearchParams(location.search).get('c') || 'nvidia';
  const roles = {chip:'芯片', 'server-odm':'服务器', storage:'内存与存储', network:'网络', electrical:'电气设备', cooling:'散热', hyperscaler:'云与数据中心', colo:'数据中心运营'};
  const url = value => {try {const u = new URL(/^https?:\/\//i.test(value) ? value : 'https://' + value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';} catch {return '';}};
  const read = async path => {const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();};
  let catalog, actor;
  function renderCatalog(data) {
    catalog=data;
    if(actor)$('#catalog-title').textContent=actor.name_cn?`${actor.name_cn} · ${actor.name}`:actor.name;
    const all=data.products||[], named=all.filter(p=>p.kind==='named_product'&&p.listing!=='obsolete');
    const has=p=>Number(p.table_count??p.tables?.length??0)>0;
    const covered=named.filter(has).length;
    $('#coverage-figure').innerHTML=data.available?`${covered}<span> / ${named.length}</span>`:'—';
    const ratio=named.length?covered/named.length:0;
    $('#coverage-bar').innerHTML=`<span style="width:${ratio*100}%"></span>`;
    $('#coverage-bar').setAttribute('aria-label',data.available?`${named.length} 个非停产登记的具体型号，${covered} 个有官方规格表`:'尚未交付');
    $('#coverage-caption').textContent=data.available?(named.length?`${covered} 个型号有原表 · ${named.length-covered} 个待补规格`:'本目录暂无具体型号；系列不计入型号分母'):'等待首次目录交付，覆盖率尚不可计算';
    const counts=new Map();all.forEach(p=>{const id=p.navigation?.group||'';const label=data.navigation?.groups?.find(g=>g.id===id)?.label||'待归类';counts.set(label,(counts.get(label)||0)+1);});
    const groups=[...counts].sort((a,b)=>b[1]-a[1]);
    const max=Math.max(1,...groups.map(x=>x[1]));
    const top=groups.slice(0,6);if(groups.length>6)top.push(['其余分类',groups.slice(6).reduce((a,x)=>a+x[1],0)]);
    $('#distribution-chart').innerHTML=data.available?top.map(([label,n])=>`<div class="chart-row"><span>${esc(label)}</span><div class="chart-track"><i style="width:${n/Math.max(max,n)*100}%"></i></div><b>${n}</b></div>`).join('')||'<p>本次交付目录为空。</p>':'<p class="muted">尚无已交付目录，不能绘制产品分布。</p>';
    $('#coverage-caption').append(document.createTextNode(data.generated_at?' · 更新 '+data.generated_at.slice(0,10):''));
  }
  window.addEventListener('company:catalog',e=>renderCatalog(e.detail));
  window.addEventListener('company:catalog-error',e=>{
    $('#coverage-caption').textContent=e.detail==='unregistered'?'尚未建立产品目录，已有公司关系见下方。':'目录读取失败，可在产品区刷新重试。';
    $('#coverage-figure').textContent='—';$('#coverage-bar').replaceChildren();$('#coverage-bar').setAttribute('aria-label','目录未读取');
    $('#distribution-chart').textContent=e.detail==='unregistered'?'尚无目录数据。':'产品分布暂不可用。';
  });
  function diagram(c,bom,rights) {
    const parts=(bom.parts||[]).filter(p=>(p.companies||[]).includes(cid));
    const held=(rights.rights||[]).filter(p=>(p.companies||[]).includes(cid));
    const nodes=[...parts.map(p=>({name:p.name,id:'part:'+p.id})),...held.map(p=>({name:p.name,id:'site:'+p.id}))];
    $('#relationship-diagram').innerHTML=`<div class="relationship-map"><div class="actor-box"><span>主体</span><strong>${esc(c.name_cn||c.name)}</strong></div><div class="relationship-arrow" aria-hidden="true">→</div><div class="relationship-nodes">${nodes.length?nodes.map(n=>`<a href="/node.html?${new URLSearchParams({id:n.id,col:'5'})}">${esc(n.name)}</a>`).join(''):'<p>骨架中尚未登记供应部件或持有权利。</p>'}</div></div><p class="basis">${parts.length} 个部件 · ${held.length} 条站点权利。类别关联不代表已确认的现场供货或项目持有关系。</p>`;
  }
  async function metadata() {
    try {
      const doc=await read('/data/companies.json'), c=doc.records.find(x=>x.company_id===cid);
      if(!c)throw Error('公司不存在: '+cid);
      actor=c;
      $('#actor-switch').innerHTML=doc.records.slice().sort((a,b)=>(a.name_cn||a.name).localeCompare(b.name_cn||b.name,'zh-CN')).map(x=>`<option value="${esc(x.company_id)}" ${x.company_id===cid?'selected':''}>${esc(x.name_cn||x.name)} · ${esc(x.name)}</option>`).join('');
      $('#actor-switch').onchange=e=>{location.href='/product-catalog.html?'+new URLSearchParams({c:e.target.value});};
      const label=c.name_cn?`${c.name_cn} · ${c.name}`:c.name;
      $('#company-profile').textContent=c.profile||((c.roles||[]).map(v=>roles[v]||v).join(' / ')+' · 产品与官方技术资料');
      $('#catalog-title').textContent=label;
      const homepage=c.website&&url(c.website), parent=doc.records.find(x=>x.company_id===c.parent_company_id);
      const children=doc.records.filter(x=>x.parent_company_id===cid);
      $('#company-meta').innerHTML=`${(c.roles||[]).map(v=>`<span class="chip">${esc(roles[v]||v)}</span>`).join('')}${c.hq_country?`<span class="chip">总部 ${esc(c.hq_country)}</span>`:''}${homepage?`<a href="${esc(homepage)}" target="_blank" rel="noopener">官网 ↗</a>`:''}${parent?`<a href="?c=${encodeURIComponent(parent.company_id)}">母公司 ${esc(parent.name_cn||parent.name)}</a>`:''}${children.map(x=>`<a href="?c=${encodeURIComponent(x.company_id)}">${esc(x.name)}</a>`).join('')}`;
      // Diagrammatic illustration conveys the page's technical subject, never a product photograph.
      $('#company-mark').innerHTML=`<svg viewBox="0 0 200 130"><g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="35" y="12" width="130" height="104"/>${[0,1,2,3].map(i=>`<rect x="44" y="${22+i*22}" width="112" height="16"/><circle cx="${136}" cy="${30+i*22}" r="3"/><path d="M52 ${30+i*22}h62"/>`).join('')}<path d="M27 120h146"/></g></svg><span>技术资料 · 示意图</span>`;
      const results=await Promise.allSettled([read('/framework/bom.json'),read('/framework/site_rights.json')]);
      if(results.every(x=>x.status==='fulfilled'))diagram(c,results[0].value,results[1].value);
      else $('#relationship-diagram').innerHTML='<p>部件关系读取失败。</p><button id="retry-company">重试公司档案</button>';
      $('#retry-company')?.addEventListener('click',metadata);
    }catch(e){
      $('#company-profile').textContent='公司档案读取失败：'+e.message;
      $('#relationship-diagram').textContent='档案未读取，不能判断部件关系。';
    }
  }
  metadata();
  read('/api/whoami').then(u=>{const d=$('#research-details');d.hidden=!['admin','member'].includes(u?.role);if(!d.hidden&&['#ecosystem','#registered','#demand','#root','#research-details'].includes(location.hash))d.open=true;}).catch(()=>{});
})();
