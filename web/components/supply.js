(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const allowedTabs = new Set(['overview','coverage','resources','providers','demands','deliveries']);
  let data, tab = 'overview', selected = 'fetchspec', admin = false, generation = 0, pending, saving = false;
  const kinds = {existing_repo:'已有 repo · 待接入',existing_feed:'已有新闻接口 · 任务未接入',existing_channel:'已有上传渠道 · 待统一接入',proposed:'能力已登记 · repo 待规划'};
  const execution = task => task.execution_mode === 'continuous' ? '持续采集 · AWS' : task.execution_mode === 'assisted' ? '人工辅助 · macmini' : '旧计划 · 尚未指定执行机';
  const providerOptions = () => data.catalog.providers.map(p => `<option value="${escape(p.id)}">${escape(p.name)} · ${escape(p.capability)}</option>`).join('');
  const setTab = next => { tab = allowedTabs.has(next) ? next : 'overview'; if (location.hash !== '#'+tab) history.replaceState(null,'','#'+tab); render(); };
  const plan = () => data.catalog.operating_plan;
  const taskCounts = () => ({planned:data.tasks.filter(t=>t.status==='planned').length, aws:data.tasks.filter(t=>t.execution_host==='aws').length, macmini:data.tasks.filter(t=>t.execution_host==='macmini').length});
  function render() {
    if (!data) return;
    document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tab === tab)));
    $('counts').textContent = `${data.catalog.providers.length} 个供应入口 · ${data.demands.length} 项资料需求 · ${data.tasks.length} 项计划任务 · 交付状态尚未接通`;
    $('create-panel').hidden = !admin || tab !== 'demands';
    if (tab === 'overview') {
      const p=plan(), c=taskCounts();
      $('list').innerHTML=`<h2>目的与当前进展</h2><p>${escape(p.purpose)}</p><div class="plan-grid"><div class="plan-card"><strong>${p.baseline.planned_product_records} 条</strong><small>当前产品资料待补目录</small></div><div class="plan-card"><strong>${data.catalog.providers.length} 个</strong><small>已登记资料供应入口</small></div><div class="plan-card"><strong>${data.demands.length} 项</strong><small>已登记研究需求</small></div><div class="plan-card"><strong>${c.planned} 项</strong><small>已计划任务；尚未开始采集</small></div></div><p class="muted">${escape(p.baseline.meaning)}</p>`;
      $('detail').innerHTML=`<h2>本页如何使用</h2><ol><li><b>广度与深度</b>：确认先补哪一类产品和何时进入深抓。</li><li><b>资源与执行</b>：确认 AWS、macmini、Spark 的固定职责。</li><li><b>供应方与任务</b>：查看各供应入口承担的计划任务。</li><li><b>研究需求</b>：由研究问题创建可验收的资料任务。</li><li><b>交付与验收</b>：查看原件接收、审核和研究采用状态。</li></ol><p class="status-waiting">交付接口当前未接通，因此不会把历史文件或新闻数量误报为本计划的完成量。</p>`;
    } else if (tab === 'coverage') {
      const p=plan();
      $('list').innerHTML=`<h2>先广后深</h2>${p.phases.map(x=>`<div class="phase"><b>${escape(x.name)}</b><span>${escape(x.purpose)}<br><small>退出条件：${escape(x.exit)}</small></span></div>`).join('')}`;
      $('detail').innerHTML=`<h2>覆盖范围</h2>${p.coverage.map(x=>`<div class="task"><b>${escape(x.name)}</b><br><small>${escape(x.focus)}</small></div>`).join('')}<p class="muted">“产品地图”只确认入口与基本身份；进入深抓后才要求规格、部署与条件证据。</p>`;
    } else if (tab === 'resources') {
      const policy=data.catalog.execution_policy,c=taskCounts();
      $('list').innerHTML=`<h2>资源分工</h2><div class="phase"><b>${escape(policy.continuous.label)}</b><span>${escape(policy.continuous.meaning)}<br><small class="status-planned">${c.aws} 项已计划任务</small></span></div><div class="phase"><b>${escape(policy.assisted.label)}</b><span>${escape(policy.assisted.meaning)}<br><small class="status-planned">${c.macmini} 项已计划任务</small></span></div><div class="phase"><b>Spark</b><span>${escape(policy.storage_and_analysis.meaning)}<br><small>不是采集执行机</small></span></div>`;
      $('detail').innerHTML=`<h2>执行规则</h2><p>一项采集任务只指定一台主执行机。相同来源和时间窗不可在 AWS 与 macmini 同时抓取。</p><p>持续公开源由 AWS 运行；需要浏览器登录、插件或人工识别的来源由 macmini 执行。两者交付的原件均进入 Spark 后再审核、提取和深读。</p>`;
    } else if (tab === 'providers') {
      $('list').innerHTML = data.catalog.providers.map(p => `<button type="button" class="record" data-provider="${escape(p.id)}" aria-pressed="${selected===p.id}"><em>${escape(kinds[p.kind])}</em><strong>${escape(p.name)}</strong><small>${escape(p.capability)}</small><small>${data.tasks.filter(t=>t.provider_id===p.id).length} 项计划任务</small></button>`).join('');
      const p = data.catalog.providers.find(x => x.id===selected) || data.catalog.providers[0];
      const tasks = data.tasks.filter(t=>t.provider_id===p.id);
      $('detail').innerHTML = `<h3>${escape(p.name)}</h3><p>${escape(kinds[p.kind])}</p><dl><dt>研究映射</dt><dd>${escape(p.mapping)}</dd><dt>资料验收重点</dt><dd>${escape(p.acceptance)}</dd></dl>${p.repository?`<p><a href="${escape(p.repository)}" target="_blank" rel="noopener">查看 GitHub 仓库</a></p>`:''}<h3>分配给该供应方的任务</h3>${tasks.length?tasks.map(t=>`<div class="task">${escape(data.demands.find(d=>d.id===t.demand_id)?.title || t.demand_id)}<br><small>${escape(execution(t))} · 已计划，等待执行接入</small></div>`).join(''):'<p>尚未分配任务。</p>'}<div class="actions"><button type="button" id="to-demands">查看需求与分配</button></div>`;
      $('to-demands').onclick=()=>setTab('demands');
      document.querySelectorAll('[data-provider]').forEach(b=>b.onclick=()=>{selected=b.dataset.provider;render();});
    } else if (tab === 'demands') {
      $('list').innerHTML = data.demands.length ? data.demands.map(d=>`<button type="button" class="record" data-demand="${escape(d.id)}" aria-pressed="${selected===d.id}"><strong>${escape(d.title)}</strong><small>${escape(d.question_id)} · ${data.tasks.filter(t=>t.demand_id===d.id).length} 个供应任务</small></button>`).join('') : '<h3>尚无资料需求</h3><p>管理员可在下方创建第一项真实需求。演示数据不会写入这里。</p>';
      const d = data.demands.find(x=>x.id===selected) || data.demands[0];
      $('detail').innerHTML = d ? `<h3>${escape(d.title)}</h3><dl><dt>研究问题</dt><dd>${escape(d.question_id)}</dd><dt>范围</dt><dd>${escape(d.scope)}</dd><dt>验收条件</dt><dd>${escape(d.acceptance)}</dd><dt>已分配</dt><dd>${data.tasks.filter(t=>t.demand_id===d.id).map(t=>`${escape(data.catalog.providers.find(p=>p.id===t.provider_id)?.name)}（${escape(execution(t))}）`).join('<br>') || '待分配'}</dd><dt>登记人 / 时间</dt><dd>${escape(d.created_by)} / ${escape(d.created_at)}</dd></dl>${admin?`<form id="assign-form"><label for="assign-provider">增加供应方任务</label><select id="assign-provider">${providerOptions()}</select><label for="assign-mode">执行方式</label><select id="assign-mode"><option value="continuous">持续采集 · AWS</option><option value="assisted">人工辅助 · macmini</option></select><p class="muted">同一项任务只有一个主执行机；切换要建立新任务，不在两台机器同时采集。</p><button type="submit">保存分配</button></form>`:''}` : '<h3>需求先于采集</h3><p>选择研究问题，定义对象范围和验收条件，再匹配供应方。新需求不会自动关闭研究问题。</p>';
      document.querySelectorAll('[data-demand]').forEach(b=>b.onclick=()=>{selected=b.dataset.demand;render();});
      if ($('assign-form')) $('assign-form').onsubmit=e=>{e.preventDefault();const mode=$('assign-mode').value;save({action:'assign',demand_id:d.id,provider_id:$('assign-provider').value,execution_mode:mode,execution_host:data.catalog.execution_policy[mode].host});};
    } else {
      $('list').innerHTML='<h3>统一交付接口待接通</h3><p>此处没有将旧新闻同步、上传回执或 Spark 阅读数量混计为已验收资料。</p><p>第一批对接 fetchspec 与本地 raw materials，再扩展其他供应方。</p><a href="/supply-demo.html">查看交付验收演示 →</a>';
      $('detail').innerHTML='<h3>后续交付闭环</h3><ol><li>原件、来源和版本登记</li><li>逐项完整性与范围验收</li><li>合格项入库，缺件项补交</li><li>Spark 提取与深读</li><li>候选证据与独立研究采用</li></ol><a href="/materials.html">现有资料上传入口</a>';
    }
  }
  async function load() {
    const seq=++generation;
    try {
      const responses = await Promise.all([fetch('/api/supply'),fetch('/api/whoami')]);
      if (responses.some(r=>!r.ok)) throw Error('无法读取供应台账，请确认登录后重试。');
      const [next,user]=await Promise.all(responses.map(r=>r.json()));
      if(seq!==generation)return;
      data=next;admin=user.role==='admin';
      const question=$('question').value,provider=$('provider').value,mode=$('execution-mode').value;
      $('question').innerHTML='<option value="">请选择研究问题</option>'+data.questions.map(q=>`<option value="${escape(q.id)}">${escape(q.id+' · '+q.text)}</option>`).join('');
      $('question').value=question;
      $('provider').innerHTML='<option value="">暂不分配</option>'+providerOptions();$('provider').value=provider;
      $('execution-mode').value=mode;
      render();$('status').textContent='';
    } catch(error) {if(seq===generation)$('status').textContent=error.message+' 已显示内容可能过期。';}
  }
  async function save(fields) {
    if(saving)return;
    saving=true;
    const key=JSON.stringify(fields);
    if(!pending || pending.key!==key)pending={key,id:crypto.randomUUID()};
    $('status').textContent='正在保存…';
    try {
      const response=await fetch('/api/supply',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'supply-center'},body:JSON.stringify({...fields,operation_id:pending.id,expected_revision:data.revision})});
      const result=await response.json();
      if(!response.ok)throw Error(result.error || '保存失败');
      pending=null;
      if(fields.action==='create')$('create-form').reset();
      await load();$('status').textContent='已保存到服务器。任务处于计划状态，尚未触发爬取。';
    } catch(error) {$('status').textContent=error.message;} finally {saving=false;}
  }
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
  window.addEventListener('hashchange',()=>setTab(location.hash.slice(1)));
  $('refresh').onclick=load;
  $('provider').onchange=()=>{
    if (!$('provider').value) $('execution-mode').value='';
    else if (!$('execution-mode').value) $('execution-mode').value='continuous';
  };
  $('create-form').onsubmit=e=>{e.preventDefault();const mode=$('execution-mode').value;const provider=$('provider').value;save({action:'create',question_id:$('question').value,title:$('title').value,scope:$('scope').value,acceptance:$('acceptance').value,provider_id:provider,execution_mode:mode,execution_host:mode?data.catalog.execution_policy[mode].host:''});};
  tab=allowedTabs.has(location.hash.slice(1))?location.hash.slice(1):'overview';
  if(!location.hash) history.replaceState(null,'','#overview');
  load();
})();
