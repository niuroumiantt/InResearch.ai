/* Reader company context uses public definitions; internal annexes live in /admin/. */
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cid = new URLSearchParams(location.search).get('c') || 'nvidia';
  const roles = {chip:'芯片', 'server-odm':'服务器', storage:'内存与存储', network:'网络', electrical:'电气设备', cooling:'散热', hyperscaler:'云与数据中心', colo:'数据中心运营'};
  const url = value => {try {const u = new URL(/^https?:\/\//i.test(value) ? value : 'https://' + value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';} catch {return '';}};
  const read = async path => {const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();};
  window.addEventListener('company:catalog',e=>{
    const d=e.detail;
    $('#catalog-updated').textContent=d.available&&d.generated_at?'资料更新 '+d.generated_at.slice(0,10):'';
  });
  window.addEventListener('company:catalog-error',()=>{$('#catalog-updated').textContent='';});
  function diagram(c,bom,rights) {
    const parts=(bom.parts||[]).filter(p=>(p.companies||[]).includes(cid));
    const held=(rights.rights||[]).filter(p=>(p.companies||[]).includes(cid));
    const nodes=[...parts.map(p=>({name:p.name,id:'part:'+p.id})),...held.map(p=>({name:p.name,id:'site:'+p.id}))];
    $('#relationship-diagram').innerHTML=`<div class="relationship-map"><div class="actor-box"><span>公司</span><strong>${esc(c.name_cn||c.name)}</strong></div><div class="relationship-arrow" aria-hidden="true">→</div><div class="relationship-nodes">${nodes.length?nodes.map(n=>`<a href="/node.html?${new URLSearchParams({id:n.id,col:'5'})}">${esc(n.name)}</a>`).join(''):'<p>暂无可展示的部件与权利关系。</p>'}</div></div><p class="basis">${parts.length} 个部件 · ${held.length} 条站点权利。展示该公司的产品与业务涉及的部件；具体项目的供货与持有关系需依据项目资料。</p>`;
  }
  async function metadata() {
    try {
      const doc=await read('/data/companies.json'), c=doc.records.find(x=>x.company_id===cid);
      if(!c)throw Error('公司不存在: '+cid);
      $('#actor-switch').innerHTML=doc.records.slice().sort((a,b)=>(a.name_cn||a.name).localeCompare(b.name_cn||b.name,'zh-CN')).map(x=>`<option value="${esc(x.company_id)}" ${x.company_id===cid?'selected':''}>${esc(x.name_cn||x.name)} · ${esc(x.name)}</option>`).join('');
      $('#actor-switch').onchange=e=>{location.href='/product-catalog.html?'+new URLSearchParams({c:e.target.value});};
      const label=c.name_cn?`${c.name_cn} · ${c.name}`:c.name;
      $('#company-profile').textContent='按产品系列查阅官方规格，核对型号、配置与参数，并选择产品进行比较。';
      $('#catalog-title').textContent=label;$('#catalog-title').dataset.companyName=label;
      const homepage=c.website&&url(c.website), parent=doc.records.find(x=>x.company_id===c.parent_company_id);
      const children=doc.records.filter(x=>x.parent_company_id===cid);
      $('#company-meta').innerHTML=`${(c.roles||[]).filter(v=>roles[v]).map(v=>`<span class="chip">${esc(roles[v])}</span>`).join('')}${c.hq_country?`<span class="chip">总部 ${esc(({US:"美国",CN:"中国",TW:"中国台湾",JP:"日本",KR:"韩国"})[c.hq_country]||c.hq_country)}</span>`:''}${homepage?`<a href="${esc(homepage)}" target="_blank" rel="noopener">官网 ↗</a>`:''}${parent?`<a href="?c=${encodeURIComponent(parent.company_id)}">母公司 ${esc(parent.name_cn||parent.name)}</a>`:''}${children.map(x=>`<a href="?c=${encodeURIComponent(x.company_id)}">${esc(x.name)}</a>`).join('')}`;
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
})();
