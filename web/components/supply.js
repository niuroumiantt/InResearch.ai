(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const allowedTabs = new Set(['targets','matching','tasks','inbox','pilot','overview','coverage','resources','providers','demands','deliveries']);
  const panelTabs = new Set(['targets','tasks','inbox','pilot']);
  const intro=document.querySelector('main > p'), originalIntro=intro.textContent;
  const internTabs = new Set(['targets','tasks']);
  let data, tab = 'targets', selected = 'fetchspec', admin = false, role = 'member', generation = 0, pending, saving = false;
  const kinds = {existing_repo:'已有 repo · 接收已上线',existing_feed:'已有新闻接口 · 任务未接入',existing_channel:'已有上传渠道 · 待统一接入',proposed:'能力已登记 · repo 待规划'};
  const execution = task => task.execution_mode === 'continuous' ? '持续采集 · AWS' : task.execution_mode === 'assisted' ? '人工辅助 · macmini' : '旧计划 · 尚未指定执行机';
  const providerOptions = () => data.catalog.providers.map(p => `<option value="${escape(p.id)}">${escape(p.name)} · ${escape(p.capability)}</option>`).join('');
  const setTab = next => { tab = allowedTabs.has(next) ? next : 'overview'; if (location.hash !== '#'+tab) history.replaceState(null,'','#'+tab); render(); };
  const plan = () => data.catalog.operating_plan;
  const taskCounts = () => ({planned:data.tasks.filter(t=>t.status==='planned').length, aws:data.tasks.filter(t=>t.execution_host==='aws').length, macmini:data.tasks.filter(t=>t.execution_host==='macmini').length});
  function render() {
    document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tab === tab)));
    // 目标表是第一屏，不依赖供应台账；收件箱、规格批次、研究问题任务是并入的三页；实习生只有目标表与任务
    document.querySelectorAll('[data-tab]').forEach(b => { b.hidden = role === 'intern' && !internTabs.has(b.dataset.tab); });
    const panel = panelTabs.has(tab);
    document.querySelector('main > h1').textContent=tab==='matching'?'材料与新闻进展':'采集';
    intro.textContent=tab==='matching'?'查看已交付的结果、正在处理的材料和待解决的问题。':originalIntro;
    document.querySelector('main > .notice').hidden=tab==='matching';
    document.querySelector('.pipeline').hidden=tab==='matching';
    document.querySelector('.layout').classList.toggle('matching-layout',tab==='matching');
    document.querySelectorAll('[data-panel]').forEach(p => { p.hidden = p.dataset.panel !== tab; });
    document.querySelector('.layout').hidden = panel; $('counts').hidden = panel || tab==='matching';
    if (tab === 'targets' && window.InresearchTargets) window.InresearchTargets.mount($('targets-panel'));
    if (tab === 'tasks' && window.InresearchTasks) window.InresearchTasks.mount(role);
    if (tab === 'pilot' && window.InresearchPilot) window.InresearchPilot.mount();
    if (!data) return;
    const receivedItems=data.deliveries.reduce((n,d)=>n+(d.received_items||0),0);
    $('counts').textContent = `${data.catalog.providers.length} 个供应入口 · Fetchspec ${data.generated_targets.total} 个生成目标 · ${data.demands.length} 项人工资料需求 · ${data.tasks.length} 项计划任务 · ${data.deliveries.length} 个交付回执 · ${receivedItems} 件原件已接收`;
    $('create-panel').hidden = !admin || tab !== 'demands';
    if (tab === 'matching') {
      renderMatching();
    } else if (tab === 'overview') {
      const p=plan(), c=taskCounts();
      $('list').innerHTML=`<h2>目的与当前进展</h2><p>${escape(p.purpose)}</p><div class="plan-grid"><div class="plan-card"><strong>${data.generated_targets.total} 条</strong><small>Fetchspec 生成目标</small></div><div class="plan-card"><strong>${data.generated_targets.needed} 条</strong><small>仍缺规格目标</small></div><div class="plan-card"><strong>${data.catalog.providers.length} 个</strong><small>已登记资料供应入口</small></div><div class="plan-card"><strong>${data.demands.length} 项</strong><small>人工补充需求</small></div><div class="plan-card"><strong>${data.deliveries.length} 个</strong><small>真实交付回执</small></div><div class="plan-card"><strong>${receivedItems} 件</strong><small>已校验并接收原件</small></div></div><p class="muted">${escape(p.baseline.meaning)}</p>`;
      $('detail').innerHTML=`<h2>本页如何使用</h2><ol><li><b>广度与深度</b>：确认先补哪一类产品和何时进入深抓。</li><li><b>资源与执行</b>：确认 AWS、macmini、Spark 的固定职责。</li><li><b>供应方与任务</b>：查看各供应入口承担的计划任务。</li><li><b>研究需求</b>：由研究问题创建可验收的资料任务。</li><li><b>交付与验收</b>：查看原件接收、审核和研究采用状态。</li></ol><p class="${data.deliveries.length?'status-ready':'status-waiting'}">${data.deliveries.length?'已接通 Fetchspec 交付回执；阅读、证据审核和研究采用仍分别计量。':'等待第一份 Fetchspec 交付包；不把历史文件或新闻数量计入本流程。'}</p>`;
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
      const tasks = data.tasks.filter(t=>t.provider_id===p.id), generated=p.id==='fetchspec'?data.generated_targets.records:[];
      $('detail').innerHTML = `<h3>${escape(p.name)}</h3><p>${escape(kinds[p.kind])}</p><dl><dt>研究映射</dt><dd>${escape(p.mapping)}</dd><dt>资料验收重点</dt><dd>${escape(p.acceptance)}</dd><dt>机器契约</dt><dd>${escape(p.connection)}</dd></dl>${p.repository?`<p><a href="${escape(p.repository)}" target="_blank" rel="noopener">查看 GitHub 仓库</a></p>`:''}${generated.length?`<h3>主线生成目标</h3><p>${generated.length} 条 · 已有 ${data.generated_targets.sourced} · 仍缺 ${data.generated_targets.needed}。这些目标来自部件树与因子树，不由 Fetchspec 自行扩大。</p><div class="target-list">${generated.slice(0,30).map(t=>`<div class="task"><code>${escape(t.id)}</code><br><small>${escape(t.disclosure_type)} × ${escape(t.publisher_category)} · ${escape(t.host)} · ${escape(t.next_due)} · ${escape(t.status)}</small></div>`).join('')}</div>${generated.length>30?`<p class="muted">当前显示前 30 条；完整 ${generated.length} 条在目标清单。</p>`:''}`:`<h3>人工分配任务</h3>${tasks.length?tasks.map(t=>`<div class="task">${escape(data.demands.find(d=>d.id===t.demand_id)?.title || t.demand_id)}<br><small>${escape(execution(t))} · 已计划</small></div>`).join(''):'<p>尚未分配任务。</p>'}`}<div class="actions"><button type="button" id="to-demands">查看人工需求与分配</button></div>`;
      $('to-demands').onclick=()=>setTab('demands');
      document.querySelectorAll('[data-provider]').forEach(b=>b.onclick=()=>{selected=b.dataset.provider;render();});
    } else if (tab === 'demands') {
      $('list').innerHTML = data.demands.length ? data.demands.map(d=>`<button type="button" class="record" data-demand="${escape(d.id)}" aria-pressed="${selected===d.id}"><strong>${escape(d.title)}</strong><small>${escape(d.question_id)} · ${data.tasks.filter(t=>t.demand_id===d.id).length} 个供应任务</small></button>`).join('') : '<h3>尚无资料需求</h3><p>管理员可在下方创建第一项真实需求。演示数据不会写入这里。</p>';
      const d = data.demands.find(x=>x.id===selected) || data.demands[0];
      $('detail').innerHTML = d ? `<h3>${escape(d.title)}</h3><dl><dt>研究问题</dt><dd>${escape(d.question_id)}</dd><dt>范围</dt><dd>${escape(d.scope)}</dd><dt>验收条件</dt><dd>${escape(d.acceptance)}</dd><dt>已分配</dt><dd>${data.tasks.filter(t=>t.demand_id===d.id).map(t=>`${escape(data.catalog.providers.find(p=>p.id===t.provider_id)?.name)}（${escape(execution(t))}）`).join('<br>') || '待分配'}</dd><dt>登记人 / 时间</dt><dd>${escape(d.created_by)} / ${escape(d.created_at)}</dd></dl>${admin?`<form id="assign-form"><label for="assign-provider">增加供应方任务</label><select id="assign-provider">${providerOptions()}</select><label for="assign-mode">执行方式</label><select id="assign-mode"><option value="continuous">持续采集 · AWS</option><option value="assisted">人工辅助 · macmini</option></select><p class="muted">同一项任务只有一个主执行机；切换要建立新任务，不在两台机器同时采集。</p><button type="submit">保存分配</button></form>`:''}` : '<h3>需求先于采集</h3><p>选择研究问题，定义对象范围和验收条件，再匹配供应方。新需求不会自动关闭研究问题。</p>';
      document.querySelectorAll('[data-demand]').forEach(b=>b.onclick=()=>{selected=b.dataset.demand;render();});
      if ($('assign-form')) $('assign-form').onsubmit=e=>{e.preventDefault();const mode=$('assign-mode').value;save({action:'assign',demand_id:d.id,provider_id:$('assign-provider').value,execution_mode:mode,execution_host:data.catalog.execution_policy[mode].host});};
    } else {
      $('list').innerHTML=(data.deliveries.length?`<h2>已登记交付</h2>${data.deliveries.map(d=>`<button type="button" class="record" data-delivery="${escape(d.delivery_id)}" aria-pressed="false"><strong>${escape(d.delivery_id)}</strong><small>${escape(d.status)} · ${d.received_items||0} 件 · ${escape(d.task_id_or_discovery||'discovery')}</small></button>`).join('')}`:'<h3>等待第一份交付包</h3><p>Fetchspec 在采集机生成包含 manifest、SHA256SUMS 和去重原件的 package；Spark 使用接收命令校验后登记。</p>')+`<h2>跨产品资料检索</h2><form id="product-search" class="product-search"><label>公司 ID<input name="company_id" placeholder="nvidia"></label><label>第一层产品分类<input name="category" placeholder="Networking"></label><label>研究问题 ID<input name="question_id" placeholder="Q-SCOPE-arch-nvidia-gpu"></label><label>格式<input name="format" placeholder="pdf"></label><button type="submit">检索已接收资料</button></form><div id="product-results" role="status">正在读取资料索引…</div>`;
      if ($('product-search')) {
        $('product-search').onsubmit=e=>{e.preventDefault();searchProducts(new FormData(e.currentTarget));};
        searchProducts(new FormData($('product-search')));
      }
      const d=data.deliveries[0];
      $('detail').innerHTML=d?`<h3>${escape(d.delivery_id)}</h3><dl><dt>交付状态</dt><dd>${escape(d.status)}</dd><dt>研究任务关联</dt><dd>${escape(d.task_id_or_discovery||'discovery')} · ${escape((d.research_context?.question_ids||[]).join(', ')||'待分配研究问题')}</dd><dt>原件回执</dt><dd>${d.received_items||0} 件</dd><dt>Reader 候选报告</dt><dd>${d.reading?.candidate_ready||0} 件就绪 · ${d.reading?.blocked||0} 件阻塞 · ${d.reading?.not_registered||0} 件尚未登记</dd><dt>后续动作</dt><dd>${escape(d.next||'查看接收回执')}</dd></dl><div class="task">Reader 报告仍是候选；证据审核和 C3 采用不从“已接收/已阅读”推断。</div>`:'<h3>交付闭环</h3><ol><li>采集包逐文件验 SHA256 与契约</li><li>保留不可变原件、URL、第一层产品分类和版本关系</li><li>合格格式进入 Reader，其他格式明确待补</li><li>抽取/深读结果仍为候选证据</li><li>人工复核并按研究标准单独采用</li></ol><p>接收命令：<code>python3 manage.py fetchspec-receive /path/to/deliveries/&lt;delivery-id&gt;</code></p>';
    }
  }
  async function searchProducts(form) {
    const query=new URLSearchParams();
    for(const [key,value] of form.entries())if(String(value).trim())query.set(key,String(value).trim());
    query.set('limit','50');
    const out=$('product-results');if(!out)return;
    out.textContent='正在检索…';
    try {
      const response=await fetch('/api/product-documents?'+query.toString());
      if(!response.ok)throw Error('资料索引读取失败');
      const result=await response.json();
      if(result.status==='not_initialized'){out.textContent='尚无 Fetchspec 资料索引；收到第一批后即可按公司、一级产品分类和研究问题检索。';return;}
      out.innerHTML=`<p>命中 ${result.total} 件候选资料（当前显示 ${result.records.length} 件）。</p>`+(result.records.length?result.records.map(r=>`<article class="task"><strong>${escape(r.title||r.original_filename||r.sha256.slice(0,16))}</strong><br><small>${escape(r.company_id)} · ${escape(r.first_category)} · ${escape(r.format)} · ${escape(r.language)} · ${escape(r.question_id||'未关联问题')} · ${escape(r.version_relation?.type||'')}</small><br><small>SHA256 ${escape(r.sha256)} · ${escape(r.acceptance)}</small><br><a href="${escape(r.source_url)}" target="_blank" rel="noopener">打开官方来源 ↗</a></article>`).join(''):'<p>没有匹配结果。</p>');
    } catch(error){out.textContent=error.message;}
  }
  async function load() {
    const seq=++generation;
    try {
      const [supplyRes,whoRes] = await Promise.all([fetch('/api/supply'),fetch('/api/whoami')]);
      if (!whoRes.ok) throw Error('无法读取供应台账，请确认登录后重试。');
      const user=await whoRes.json();
      if(seq!==generation)return;
      admin=user.role==='admin';role=user.role||'member';
      if (role==='intern' && !internTabs.has(tab)) tab='targets';
      if (!supplyRes.ok) { data=null; render(); $('status').textContent = supplyRes.status===403 ? '供应台账只对内部成员开放；分配给你的目标行在上方目标表。' : '无法读取供应台账，请确认登录后重试。'; return; }
      const next=await supplyRes.json();
      if(seq!==generation)return;
      data=next;
      const question=$('question').value,provider=$('provider').value,mode=$('execution-mode').value;
      $('question').innerHTML='<option value="">请选择研究问题</option>'+data.questions.map(q=>`<option value="${escape(q.id)}">${escape(q.id+' · '+q.text)}</option>`).join('');
      $('question').value=question;
      $('provider').innerHTML='<option value="">暂不分配</option>'+providerOptions();$('provider').value=provider;
      $('execution-mode').value=mode;
      render();$('status').textContent='';
    } catch(error) {if(seq===generation)$('status').textContent=error.message+' 已显示内容可能过期。';}
  }
  function progressOverview(m,scope) {
    const counts=scope?.counts||{}, delivery=data.daily_delivery, received=data.matching_reader;
    const time=value=>{const d=new Date(value);return value&&!Number.isNaN(d.valueOf())?d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+' 北京时间':'尚未接收';};
    const number=(value,available)=>available?String(value||0):'—';
    const phase={extract:'提取正文 / 核对图片页',triage:'确认材料归属',read:'逐段阅读',synthesize:'汇总阅读结果',organize:'保存结果',receipt:'确认交付'};
    const running=(m.records||[]).filter(d=>d.reading?.state==='running');
    const delivered=(delivery?.records||[]).filter(r=>r.delivery_lane==='news').sort((a,b)=>String(b.last_processed_at||'').localeCompare(String(a.last_processed_at||''))).slice(0,6);
    const eventMap=new Map((data.daily_events?.records||[]).map(e=>[e.id,e]));
    const outputs=data.reading_deliveries||[];
    const cards=[['原件已接收',scope?.registered,!!scope],['阅读结果已交付',counts.complete,!!scope],['来源齐全的事件',delivery?.news_total,!!received?.received_at],['正在处理',counts.running,!!scope],['等待阅读',counts.queued,!!scope],['阅读遇到问题',(counts.failed||0)+(counts.blocked||0),!!scope]];
    return `<section class="progress-overview" aria-label="材料处理进展"><h2>材料处理进展</h2><p>网站更新：${escape(time(received?.received_at))}${received?.stale?' · 更新延迟，以下是上次收到的结果':''}。点击上方「刷新」获取最新结果。</p><div class="progress-cards">${cards.map(([label,value,available])=>`<div><strong>${number(value,available)}</strong><span>${label}</span><small>${label==='来源齐全的事件'?'条事件':'份材料'}</small></div>`).join('')}</div>${scope?.documents?`<p>本批材料阅读完成 ${counts.complete||0} / ${scope.documents} 份</p><progress value="${counts.complete||0}" max="${scope.documents}" aria-label="本批材料阅读完成"></progress>`:'<p>尚未收到本批阅读进度。</p>'}<p>阅读结果与项目动态已交付后，仍需核验才能更新正式项目与 GW。${scope?.unread_gap_pages?`已交付报告中有 ${scope.unread_gap_pages} 页未读清，查看报告时保留这些缺口。`:''}</p></section>
    <div class="progress-columns"><section><h2>已交付什么</h2><h3>正式项目已更新 · ${(data.project_updates||[]).length} 个</h3>${(data.project_updates||[]).map(p=>`<article class="task"><a href="/project.html?site=${encodeURIComponent(p.site_id)}">${escape(p.name)}</a><p>${escape(p.scope)}</p><small>已采用字段：${escape(p.fields.join('、'))} · 核验 ${escape(p.verified_date)}</small></article>`).join('')||'<p>本批尚无正式项目更新。</p>'}<h3>来源齐全的事件 · 最近 6 条</h3><p><a href="/supply.html?delivery=news#matching">查看全部 ${delivery?.news_total||0} 条来源齐全的事件 →</a></p>${delivered.map(r=>`<article class="task"><a href="/supply.html?event=${encodeURIComponent(r.event_id)}#matching">${escape(eventMap.get(r.event_id)?.title||r.title||'查看项目动态')}</a><small>来源已绑定 · ${escape(time(r.last_processed_at))}</small></article>`).join('')||'<p>当前快照暂无已上线的项目动态。</p>'}<h3>已完成的阅读结果</h3><p>展开查看提取结果和原文引句；完整证据保留在 Spark。</p><div class="progress-results">${outputs.map(d=>`<details class="task"><summary>${escape(d.title)}</summary>${d.coverage?.gap_pages?.length?`<p>未读页：${escape(d.coverage.gap_pages.join('、'))}</p>`:''}${(d.claims||[]).map(c=>`<p>${escape(c)}</p>`).join('')||'<p>本次网页快照未包含提取结论。</p>'}${(d.quotes||[]).map(q=>`<blockquote>${escape(q.quote)}<small>原件第 ${Number(q.page_index)+1} 页</small></blockquote>`).join('')}<p>这是阅读候选，尚不代表正式采用。</p></details>`).join('')||(counts.complete?'<p>已完成数量见上方；对应内容尚未随本次快照交付。</p>':'<p>尚无已完成阅读结果。</p>')}</div></section>
    <section><h2>现在处理到哪里</h2>${running.map(d=>`<article class="task"><strong>${escape(d.title)}</strong><p>${escape(phase[d.reading.phase]||'处理材料')}${d.reading.phase==='read'?` · 已读 ${d.reading.chunks_read} / ${d.reading.chunks_total} 段`:''}</p></article>`).join('')||'<p>本次快照没有正在处理的材料明细。</p>'}<p>${scope?.executor?.backend==='codex_cli'?'M5 的 Codex CLI 阅读；Spark 保存原件、队列和结果。':'执行者以当前阅读记录为准。'}</p>${scope?.waiting?'<p>模型调用正在等待恢复；任务和已读内容保留。</p>':''}<p>未完成材料继续排队。整批完成时间尚无可靠估计。</p></section>
    <section><h2>还差什么</h2><article class="task"><strong>${number(delivery?.task_counts?.source,!!received?.received_at)} 条事件待找回来源</strong><p>回查 inews 的原标题、链接和正文台账。补链接与阅读分别推进。</p></article><article class="task"><strong>${number((counts.failed||0)+(counts.blocked||0),!!scope)} 份材料有阅读问题</strong><p>检查调用失败或读不清的图片页；未读清的内容保留缺口。</p></article><article class="task"><strong>正式项目与 GW：逐事件核验</strong><p>确认园区、分期、容量口径和采用依据后更新。</p><a href="/projects.html">查看正式项目数据 →</a></article></section></div>`;
  }
  function dailyEdition() {
    const events=data.daily_events?.records||[];
    const dates=[...new Set(events.flatMap(e=>(e.document_refs||[]).map(r=>r.report_date)).filter(Boolean))].sort().reverse();
    if(!dates.length)return '';
    const requested=new URLSearchParams(location.search).get('day');
    const day=dates.includes(requested)?requested:dates[0];
    const rows=events.filter(e=>(e.document_refs||[]).some(r=>r.report_date===day));
    const ids=new Set(rows.map(e=>e.id)), updates=(data.project_updates||[]).filter(p=>ids.has(p.event_id));
    const ecosystem=(data.ecosystem_updates||[]).filter(p=>ids.has(p.event_id));
    const used=new Set([...updates,...ecosystem].map(p=>p.event_id));
    const delivered=new Set((data.daily_delivery?.records||[]).filter(r=>r.delivery_lane==='news').map(r=>r.event_id));
    const withSources=rows.filter(e=>(e.sources||[]).some(s=>(s.urls||[]).some(u=>/^https?:/.test(u)))).length;
    const verified=rows.filter(e=>e.structured_evidence_status==='quotes_verified').length;
    return `<section class="progress-overview" aria-label="本期日报交付"><h2>${escape(day)} 日报 · 用在哪里</h2><label>日报日期 <select id="daily-edition-date">${dates.map(d=>`<option${d===day?' selected':''}>${escape(d)}</option>`).join('')}</select></label><p>${rows.length} 条事件已登记 · ${withSources} 条有来源链接 · ${verified} 条通过引文与数值检查。机械检查之后仍需研究核验。</p><p><strong>${used.size} 条事件已用于 ${updates.length} 个正式园区记录${ecosystem.length?`、${ecosystem.length} 份主体供电协议`:""}</strong>；其余 ${rows.length-used.size} 条按需求继续研究或补证。项目更新可以只补身份、审批或供电，不一定增加 IT GW。</p>${rows.map(e=>`<article class="task"><strong>${escape(e.title)}</strong><p>${used.has(e.id)?(updates.filter(p=>p.event_id===e.id).map(p=>`<a href="/project.html?site=${encodeURIComponent(p.site_id)}">已用于：${escape(p.name)} →</a>`).join(' · ')+ecosystem.filter(p=>p.event_id===e.id).map(p=>`<a href="/company.html?c=${encodeURIComponent(p.parties[0])}#ecosystem">已用于主体关系：${escape(p.name)} →</a>`).join(' · ')):(delivered.has(e.id)?'项目动态已交付；正式采用待核验':'已登记研究材料；按对应需求继续处理')}</p><p>${escape((e.editorial_event?.gaps||[]).join('；')||'逐项核验来源、身份及口径')} · <a href="/supply.html?day=${encodeURIComponent(day)}&event=${encodeURIComponent(e.id)}#matching">查看原文、来源和需求匹配 →</a></p></article>`).join('')}</section>`;
  }
  function renderMatching() {
    const m=data.research_matching, queue=data.demand_queue||[];
    const scope=data.matching_reader?.execution_scope;
    const readingPanel=scope?`<section class="delivery-board" aria-label="本批全文阅读"><h2>本批全文阅读</h2><div class="delivery-metrics"><div><strong>${scope.documents||0}</strong><span>范围内材料</span></div><div><strong>${scope.counts?.complete||0}</strong><span>全文候选报告完成</span></div><div><strong>${scope.counts?.running||0}</strong><span>正在处理</span></div><div><strong>${(scope.counts?.blocked||0)+(scope.counts?.failed||0)}</strong><span>需要处理的阻塞</span></div></div><p>${scope.types?.['.pdf']||0} 份 PDF · ${scope.types?.['.html']||0} 份 HTML · 已登记 ${scope.registered||0} / ${scope.documents||0}。已读 ${scope.chunks_read||0} / ${scope.chunks_total||0} 个已提取正文块；${scope.awaiting_extraction||0} 份尚待提取，当前块总数不代表整批总量。</p><p>执行者 ${escape(scope.executor?.backend||'未知')} · 请求模型 ${escape(scope.executor?.model||'未知')} · ${escape(scope.executor?.reasoning_effort||'默认')}。Spark 保存原件、队列和候选数据库。${scope.waiting?'暂停等待：'+escape(scope.waiting.reason)+'，下次尝试 '+escape(scope.waiting.until):''}</p><p>其中 ${scope.complete_with_gaps||0} 份候选报告有显式缺页，共 ${scope.unread_gap_pages||0} 页未读；缺页不产主张。逐份状态见下方报告。全文结果仍是候选，正式项目与 GW 另经身份、口径和研究采用核验。时间待实测吞吐量估算。</p></section>`:'';
    $('list').innerHTML=`<h2>需求先于材料</h2><p>从三级账、四问、五类变量生成的现行目标，按六队归属等待材料。候选命中不改变目标状态。</p><p>${m.total||0} 份原件已建检索索引 · ${m.matched_documents||0} 份有目标候选 · ${data.matching_reader?.stale?'快照延迟':'快照时间 '+escape(data.matching_reader?.received_at||'尚未连接')}</p><p><a href="/projects.html?view=pipeline">查看新闻 → 园区、容量与水电审批进展</a></p><label>搜索目标或材料<input id="match-search" type="search" placeholder="GPU、并网、目标 ID 或报告名"></label><div id="match-demands"></div>`;
    $('list').innerHTML=`${dailyEdition()}${progressOverview(m,scope)}<details class="matching-technical" id="matching-demands"><summary>查看研究需求与阅读技术记录</summary>${readingPanel}${$('list').innerHTML}</details>`;
    const edition=$('daily-edition-date');
    if(edition)edition.onchange=()=>{const query=new URLSearchParams(location.search);query.set('day',edition.value);query.delete('event');history.replaceState(null,'','?'+query.toString()+'#matching');renderMatching();};
    const renderQueue=()=>{const q=($('match-search').value||'').toLowerCase();const rows=queue.filter(t=>JSON.stringify(t).toLowerCase().includes(q));$('match-demands').innerHTML=rows.map(t=>`<div class="task"><a href="/supply.html?node=${encodeURIComponent(t.part_id?'part:'+t.part_id:t.site_right_id?'site:'+t.site_right_id:'root')}&col=${t.variable_class}#targets"><code>${escape(t.id)}</code></a><br>${escape(t.disclosure_type)}<br><small>变量类 ${t.variable_class} · ${escape(t.team)} · ${t.candidate_documents} 份候选 · ${escape(t.dispatch_state==='reading_candidate'?'已有材料，待深读核验':t.dispatch_state==='awaiting_team'?'主责队尚未接入':'待材料')} · 模型输入 ${escape((t.model_inputs||[]).join('、')||'无')}</small></div>`).join('')||'<p>当前筛选没有需求。</p>';};
    $('match-search').value=new URLSearchParams(location.search).get('match')||'';$('match-search').oninput=()=>{renderQueue();const q=$('match-search').value.toLowerCase();document.querySelectorAll('[data-matched-report]').forEach((e,i)=>{e.hidden=!JSON.stringify(m.records[i]).toLowerCase().includes(q);});};renderQueue();
    const events=data.daily_events||{records:[],total:0};
    const delivery=data.daily_delivery||{records:[],news_total:0,task_counts:{}};
    const dispatch=new Map((delivery.records||[]).map(r=>[r.event_id,r]));
    const lanes={news:'已交付项目动态',source:'待补来源',source_binding:'待核来源对应',research:'部件与公司研究'};
    const deliveryPanel=`<section class="delivery-board" aria-label="事件分流与交付"><h2>事件分流与交付</h2><p>逐条交付，逐项补证。来源对应齐全的项目动态先进入网站；园区、容量和研究采用继续核验，不等待长篇报告。</p><div class="delivery-metrics"><div><strong>${delivery.news_total||0}</strong><span>日报项目动态已交付</span></div><div><strong>${delivery.task_counts?.source||0}</strong><span>待补来源</span></div><div><strong>${delivery.task_counts?.source_binding||0}</strong><span>待核来源对应</span></div><div><strong>${delivery.task_counts?.identity||0}</strong><span>待确认园区身份</span></div></div><p>一条事件可同时已交付动态、待核园区和容量；各项不相加。${delivery.task_counts?.priority_research_review||0} 条已具备结构化项目与引文机检，可优先研究核验。正式容量更新查项目登记，动态不计入 GW。</p><p><a href="/projects.html?view=pipeline">查看已上线项目动态 →</a> · 最近网站接收 ${escape(data.matching_reader?.received_at||'未同步')}</p><label>交付通道<select id="delivery-lane"><option value="all">全部通道</option>${Object.entries(lanes).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label></section>`;
    const stages={awaiting_source:'待补来源',awaiting_identity:'待确认园区',awaiting_caliber:'待核容量口径',awaiting_research_review:'待研究复核'};
    let shown=20;
    const workflow=Object.entries(events.workflow||{}).map(([k,v])=>escape(stages[k]||k)+' '+v+' 条').join(' · ');
    const daily=`<h2>日报 → 逐事件数据库</h2><p>HTML 与内部来源台账进入 Spark 原件库，正文逐事件登记并匹配当前需求；确认园区、分期和容量口径后进入研究复核，采用后更新正式项目与地图。</p><p>${workflow}</p><p>${events.document_versions||0} 个日报版本 · ${events.total} 个去重事件 · ${events.capacity_observations||0} 个容量观察 · ${events.missing_source_links||0} 个事件待补原始链接。原件与变更版本保留，尚未核验的事件不参加已投运/在建 GW。</p><label>按主体、国家、地点或项目查事件<input type="search" id="daily-search" placeholder="微软、澳大利亚、Huntingwood、项目名"></label><label>处理状态<select id="daily-state"><option value="all">全部状态</option>${Object.entries(stages).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><p id="daily-shown"></p><div id="daily-events"></div><button id="daily-more" type="button">再显示 20 条</button>`;
    $('detail').innerHTML=`<h2>报告匹配与新角度</h2><p>下面是页内主题候选。提取全文不等于逐篇深读，命中不证明引文支持参数，更不等于 C3 采用。骨架建议等待讨论。</p>${m.truncated?'<p>当前显示最近 500 份原件；计数覆盖全部索引。</p>':''}${deliveryPanel}${daily}${(m.records||[]).map(d=>`<details class="task" data-matched-report><summary>${escape(d.title)} · ${d.pages} 页 · ${d.matches_total||d.matches.length} 个目标候选 · Reader ${escape(d.reading?.state||'待登记')}</summary><p><code>${escape(d.sha256)}</code></p>${d.matches.map(x=>`<details><summary>${escape(x.target_id)} · 第 ${x.page} 页 · ${escape(x.team)}</summary><p>${escape(x.quote)}</p><p>${escape(x.next_action)}</p></details>`).join('')}${d.matches_total>d.matches.length?'<p>本快照显示前 32 个匹配；完整记录保留在 Spark。</p>':''}${(d.project_observations||[]).map(x=>`<details><summary>项目 / 水电审批观察 · 第 ${x.page} 页</summary><p>${escape(x.quote)}</p><p>候选园区 ${escape((x.site_candidates||[]).map(c=>c.site_id).join('、')||'待核验')} · 容量 ${(x.capacity_observations||[]).map(c=>escape(c.quoted_value)+' / '+escape(c.basis)).join('、')||'未披露'}</p></details>`).join('')}${d.proposals.map(x=>`<details><summary>待讨论角度 · ${escape(x.id)} · 第 ${x.page} 页</summary><p>现有归属 ${escape(x.node)} · 变量类 ${x.variable_class}</p><p>${escape(x.quote)}</p><p>${escape(x.gap)}</p><p>${escape(x.proposal)}</p></details>`).join('')}</details>`).join('')||'<p>尚未收到匹配索引。可通过收件箱提交原件，批量材料使用 research-match 接收。</p>'}`;
    const renderEvents=()=>{const q=($('daily-search').value||'').toLowerCase();const state=$('daily-state').value;const day=new URLSearchParams(location.search).get('day');const rows=events.records.filter(e=>(!day||(e.document_refs||[]).some(r=>r.report_date===day))&&JSON.stringify(e).toLowerCase().includes(q)&&(state==='all'||e.workflow_stage===state)&&($('delivery-lane').value==='all'||dispatch.get(e.id)?.delivery_lane===$('delivery-lane').value));$('daily-shown').textContent=`显示 ${Math.min(shown,rows.length)} / ${rows.length} 条事件`; $('daily-more').hidden=shown>=rows.length;$('daily-events').innerHTML=rows.sort((a,b)=>(dispatch.get(a.id)?.review_priority??2)-(dispatch.get(b.id)?.review_priority??2)).slice(0,shown).map(e=>`<details class="task"><summary>${escape(e.title)} · ${escape(stages[e.workflow_stage]||'待核验')} · ${escape(e.reported_stage)} · ${escape(e.place_quote)}</summary><p><a href="/supply.html?event=${encodeURIComponent(e.id)}#matching">此事件链接</a>${dispatch.get(e.id)?.delivery_lane==='news'?` · <a href="/projects.html?view=pipeline&lead=${encodeURIComponent('daily-'+e.id)}">已交付的项目动态</a>`:''}</p>${(dispatch.get(e.id)?.tasks||[]).map(t=>`<p class="delivery-task"><strong>${escape(t.owner)}</strong> · ${escape(t.next_action)}</p>`).join('')}<p>最近接收处理 ${escape(dispatch.get(e.id)?.last_processed_at||'尚无对应回执')}</p><p>${escape(e.body)}</p>${(e.adoption_updates||[]).map(p=>`<p>本事件已用于正式园区 <a href="/project.html?site=${encodeURIComponent(p.site_id)}">${escape(p.name)}</a> · ${escape(p.scope)}</p>`).join('')}${(data.ecosystem_updates||[]).filter(p=>p.event_id===e.id).map(p=>`<p>本事件已用于主体供电协议 <a href="/company.html?c=${encodeURIComponent(p.parties[0])}#ecosystem">${escape(p.name)}</a> · ${escape(p.scope)}</p>`).join('')}${e.registered_project?`<p>已登记项目 <a href="/project.html?site=${encodeURIComponent(e.registered_project.site_id)}">${escape(e.registered_project.name)}</a> · 当前阶段 ${escape(e.registered_project.status)} · 核验日期 ${escape(e.registered_project.verified_date)}</p>`:''}<p>需求匹配 ${(e.demand_matches||[]).slice(0,6).map(m=>escape(m.target_id)+' / 变量 '+m.variable_class+' / '+escape(m.team)).join('；')||'待关联现行需求'}</p>${e.editorial_event?`<details><summary>采集方提供的逐事件数据 · ${escape(e.structured_evidence_status)}</summary><p>项目 ${escape(e.editorial_event.project?.name||'未披露')} · 城市 ${escape(e.editorial_event.project?.city||'未披露')} · 分期 ${escape(e.editorial_event.project?.phase||'未披露')}</p><p>事件日期 ${escape(e.editorial_event.event_date||'未披露')} · 报道日期 ${escape(e.editorial_event.reported_date||'未披露')}</p>${(e.editorial_event.capacities||[]).map(c=>`<p>${c.value} ${escape(c.unit)} · ${escape(c.basis)} · ${escape(c.scope)} · ${escape(c.phase)} · ${escape(c.nature)}<br>${escape(c.quote)}</p>`).join('')}<p>待补 ${(e.editorial_event.gaps||[]).map(escape).join('；')||'仍须研究复核'}</p></details>`:''}<p>主体 ${escape(e.actors.map(a=>a.name).join('、')||'待核验')} · 国家 ${escape(e.country_mentions.map(c=>c.code).join('、')||'未披露')}</p><p>园区匹配 ${escape(e.site_candidates.map(c=>c.site_id).join('、')||'待新项目登记/核验')}</p>${e.capacity_observations.map(c=>`<p>${escape(c.quoted_value)} · ${escape(c.basis)} · ${escape(c.quote)}</p>`).join('')}<p>来源 ${e.sources.map(r=>escape(r.label)).join('；')||'待补'}</p>${e.sources.flatMap(r=>r.urls||[]).filter(u=>/^https?:/.test(u)).map(u=>`<p><a href="${escape(u)}" target="_blank" rel="noopener noreferrer">原始来源</a></p>`).join('')}<p>原件版本 ${e.document_refs.map(r=>escape(r.report_date)+' / '+escape(r.filename)+' / 第'+r.section+'节 / '+escape(r.sha256)).join('<br>')}</p><p>身份与容量核验 ${escape(e.identity_review)} / ${escape(e.capacity_review)}；${(e.adoption_updates?.length||(data.ecosystem_updates||[]).some(p=>p.event_id===e.id))?'上述明确范围已正式采用，其余字段继续核验':'未采用'}。</p></details>`).join('')||'<p>当前范围暂无事件。</p>';};
    $('detail').innerHTML=`<details class="matching-technical" id="matching-events"><summary>查看全部事件、来源与研究匹配</summary>${$('detail').innerHTML}</details>`;
    $('daily-search').value=new URLSearchParams(location.search).get('event')||'';
    if(new URLSearchParams(location.search).get('delivery')==='news'){ $('delivery-lane').value='news'; $('matching-events').open=true; }
    if($('daily-search').value)$('matching-events').open=true;
    $('delivery-lane').onchange=()=>{shown=20;renderEvents();};$('daily-search').oninput=()=>{shown=20;renderEvents();};$('daily-state').onchange=()=>{shown=20;renderEvents();};$('daily-more').onclick=()=>{shown+=20;renderEvents();};renderEvents();
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
  tab=allowedTabs.has(location.hash.slice(1))?location.hash.slice(1):'targets';
  if(!location.hash) history.replaceState(null,'','#targets');
  render();
  load();
})();
