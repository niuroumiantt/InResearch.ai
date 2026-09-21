(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  let data, tab = 'providers', selected = 'fetchspec', admin = false, generation = 0, pending, saving = false;
  const kinds = {existing_repo:'已有 repo · 待接入',existing_feed:'已有新闻接口 · 任务未接入',existing_channel:'已有上传渠道 · 待统一接入',proposed:'能力已登记 · repo 待规划'};
  const execution = task => task.execution_mode === 'continuous' ? '持续采集 · AWS' : task.execution_mode === 'assisted' ? '人工辅助 · macmini' : '旧计划 · 尚未指定执行机';
  const providerOptions = () => data.catalog.providers.map(p => `<option value="${escape(p.id)}">${escape(p.name)} · ${escape(p.capability)}</option>`).join('');
  function render() {
    if (!data) return;
    document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tab === tab)));
    $('counts').textContent = `${data.catalog.providers.length} 个供应入口 · ${data.demands.length} 项资料需求 · ${data.tasks.length} 项计划任务 · 交付状态尚未接通`;
    $('create-panel').hidden = !admin || tab !== 'demands';
    if (tab === 'providers') {
      $('list').innerHTML = data.catalog.providers.map(p => `<button type="button" class="record" data-provider="${escape(p.id)}" aria-pressed="${selected===p.id}"><em>${escape(kinds[p.kind])}</em><strong>${escape(p.name)}</strong><small>${escape(p.capability)}</small><small>${data.tasks.filter(t=>t.provider_id===p.id).length} 项计划任务</small></button>`).join('');
      const p = data.catalog.providers.find(x => x.id===selected) || data.catalog.providers[0];
      const tasks = data.tasks.filter(t=>t.provider_id===p.id);
      $('detail').innerHTML = `<h3>${escape(p.name)}</h3><p>${escape(kinds[p.kind])}</p><dl><dt>研究映射</dt><dd>${escape(p.mapping)}</dd><dt>资料验收重点</dt><dd>${escape(p.acceptance)}</dd></dl>${p.repository?`<p><a href="${escape(p.repository)}" target="_blank" rel="noopener">查看 GitHub 仓库</a></p>`:''}<h3>分配给该供应方的任务</h3>${tasks.length?tasks.map(t=>`<div class="task">${escape(data.demands.find(d=>d.id===t.demand_id)?.title || t.demand_id)}<br><small>${escape(execution(t))} · 已计划，等待执行接入</small></div>`).join(''):'<p>尚未分配任务。</p>'}<div class="actions"><button type="button" id="to-demands">查看需求与分配</button></div>`;
      $('to-demands').onclick=()=>{tab='demands';render();};
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
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render();});
  $('refresh').onclick=load;
  $('provider').onchange=()=>{
    if (!$('provider').value) $('execution-mode').value='';
    else if (!$('execution-mode').value) $('execution-mode').value='continuous';
  };
  $('create-form').onsubmit=e=>{e.preventDefault();const mode=$('execution-mode').value;const provider=$('provider').value;save({action:'create',question_id:$('question').value,title:$('title').value,scope:$('scope').value,acceptance:$('acceptance').value,provider_id:provider,execution_mode:mode,execution_host:mode?data.catalog.execution_policy[mode].host:''});};
  load();
})();
