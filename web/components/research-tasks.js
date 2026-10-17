/* Project coordination only. Source registration and publication keep their own authority. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statuses = {unassigned:'待分配',ready:'待开始',in_progress:'进行中',blocked:'受阻',delivered:'已交付'};
  const fields = ['title','region','scope','sources','assignee','machine','model','due','status','delivery_pointer','note'];
  const form = $('package-form');
  const viewForHash = hash => {
    const id = decodeURIComponent(String(hash || '').replace(/^#/,''));
    if (id === 'upload' || id === 'my-submissions' || id === 'submission-progress') return 'submission-progress';
    if (id.startsWith('package-')) return 'submission-progress';
    return 'task-home';
  };
  const showTaskView = view => {
    const allowed = new Set(['my-work','task-home','submission-progress','task-management']);
    if (!allowed.has(view) || (view === 'task-management' && $('task-management-tab').hidden)) view = 'task-home';
    document.querySelectorAll('[data-task-panel]').forEach(panel => {
      panel.hidden = panel.dataset.taskPanel !== view;
    });
    document.querySelectorAll('[data-task-view]').forEach(button => {
      const active = button.dataset.taskView === view;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
    window.activeResearchTaskView = view;
    document.body.dataset.activeTaskView = view;
    window.dispatchEvent(new CustomEvent('research-task-view',{detail:{view}}));
  };
  document.querySelectorAll('[data-task-view]').forEach(button => button.addEventListener('click',()=>showTaskView(button.dataset.taskView)));
  function moveTab(event, buttons) {
    const index = buttons.indexOf(event.target);
    if (index < 0 || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
      (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].click(); buttons[next].focus({preventScroll:true});
  }
  document.querySelector('.mission-nav').addEventListener('keydown', event =>
    moveTab(event, [...document.querySelectorAll('[data-task-view]')].filter(button=>!button.hidden)));
  document.querySelectorAll('[data-task-view-request]').forEach(button => button.addEventListener('click',()=>showTaskView(button.dataset.taskViewRequest)));
  window.addEventListener('research-task-view-requested',event=>showTaskView(event.detail?.view));
  window.addEventListener('hashchange',()=>showTaskView(viewForHash(location.hash)));
  let state = null, pending = null, editing = null, editingRevision = null, selectedPackageId = null;
  let readState = 'loading', readAt = null, loadSequence = 0;
  function setReadState(kind, message = '') {
    readState = kind;
    $('package-active-panel').dataset.readState = kind;
    $('package-current-heading').textContent = kind === 'current' ? '共同现行反馈与下一步' : state ? '上次读取的共同反馈' : '共同反馈与下一步';
    const note = $('package-read-status');
    note.hidden = kind === 'current';
    note.textContent = kind === 'current' ? '' : kind === 'loading' ? state ? '正在刷新；上次数据暂不作执行依据。' : '正在读取最新共同反馈…' : state ? '刷新失败；上次数据未确认有效，请重试后再执行。' : message || '读取失败，请稍后重试。';
  }
  const canEdit = item => state && (item.can_update || state.can_create || (state.role === 'intern' && String(item.assignee || '').split(/[,，、;；\n]+/).map(name => name.trim()).includes(state.actor)));
  const value = name => form.elements.namedItem(name);

  async function load() {
    const sequence = ++loadSequence;
    setReadState('loading');
    if (state) renderPackageWorkspace();
    $('tasks-status').textContent = '正在读取任务台账…';
    try {
      const response = await fetch('/api/research-tasks', {cache:'no-store'});
      if (!response.ok) throw Error(response.status === 401 ? '请登录后查看任务' : '任务台账暂不可用，请刷新重试');
      const latest = await response.json();
      if (sequence !== loadSequence) return;
      state = latest; readAt = Date.now() / 1000; setReadState('current');
      window.researchTasksState = state;
      window.dispatchEvent(new CustomEvent('research-tasks-loaded',{detail:state}));
      $('new-package').hidden = !state.can_create;
      $('task-role-note').textContent = state.can_create ? '内部成员可以新增、分配和更新工作包；多人协作可用逗号分隔成员登录名，各成员可更新自己的状态、交付与备注。' : state.role === 'intern' ? '实习生成员可查看全部分工；只可更新包含自己登录名的工作包状态、交付与备注。范围、参与成员、机器与模型由内部成员维护。' : state.role === 'collaborator' ? '可查看本项目的分工与共同进展；个人提交进度在“我的工作”中更新，任务安排由负责人维护。' : '任务方向、协调状态和公开样例可直接查看；实际参与成员、机器、模型、备注和交付指针登录后可见。';
      render(); renderRegister();
      $('tasks-status').textContent = `服务端台账 · 版本 ${state.revision} · ${state.packages.length} 个工作包。${state.public_view?'公开只读视图；登录后可查看实际分工并协作。':'机器与模型按实际执行填写，未分配不默认运行。'}`;
    } catch (error) {
      if (sequence !== loadSequence) return;
      setReadState('error',error.message);
      if (state) renderPackageWorkspace();
      $('tasks-status').textContent = error.message;
      $('register-stats').textContent = '台账读取失败，请刷新重试。';
      $('mission-progress-value').textContent = '暂不可用';
      $('package-dashboard').textContent = error.message;
    }
  }

  function renderRegister() {
    const c = state.map_register?.counts;
    if (!c) { $('register-stats').textContent = '当前地图台账不可用。'; return; }
    const n = number => new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(number);
    const located = Math.max(0,c.sites - c.unlocated);
    $('register-stats').innerHTML = [[n(c.sites),'条','参与统计项目记录'],[n(located),'条','有地图坐标记录'],[n(c.operating/1000),'GW','投运 IT · 含参考估算'],[n(c.unknown),'条','容量待补']].map(([v,u,label]) => `<div><strong>${esc(v)}<small>${u}</small></strong><span>${esc(label)}</span></div>`).join('');
    $('register-basis').textContent = `投运标量合计含参考估算 ${n((c.estimated?.operating || 0)/1000)} GW；${c.ranged_sites} 条区间容量记录单列、不取中点。记录含跨园区集群，去重尚需逐址补齐，不等于全球唯一物理园区普查；基础登记与研究核验、实际发布分别计量。`;
  }

  function render() {
    const count = s => state.packages.filter(p => p.status === s).length;
    const total = state.packages.length, delivered = count('delivered');
    const published = state.site_progress?.published_sites ?? 0;
    const target = state.site_progress?.target;
    const formatCount = value => new Intl.NumberFormat('zh-CN').format(value);
    $('mission-site-progress').max = Math.max(1,target || 1);
    $('mission-site-progress').value = target ? Math.min(published,target) : 0;
    $('mission-site-progress').hidden = !target;
    $('mission-site-progress').setAttribute('aria-label', target
      ? `模型审阅后已上线 ${published} 个去重园区，暂定目标 ${target} 个`
      : `模型审阅后已上线 ${published} 个去重园区；园区目标待初步研究后设定`);
    $('mission-progress-value').textContent = `${formatCount(published)} 个园区已入库`;
    $('mission-progress-detail').textContent = target ? `暂定目标 ${formatCount(target)} · ${Math.round(published / target * 100)}%` : '目标总量待盘点 · 持续采集与补齐';
    $('mission-progress-basis').textContent = state.site_progress?.basis || '按实际发布回执计数；同园区多字段只计一次。';
    $('mission-work-package-count').textContent = formatCount(total);
    $('mission-reviewed-reports').textContent = formatCount(state.site_progress?.reviewed_reports ?? 0);
    $('mission-published-statements').textContent = formatCount(state.site_progress?.published_statements ?? 0);
    $('mission-site-target').textContent = target ? `${formatCount(target)} 个园区` : '先建 ID／地点底图';
    const basis = state.site_progress?.target_basis;
    const setAt = state.site_progress?.target_set_at;
    const date = setAt ? new Date(setAt).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'}) : '';
    $('mission-target-basis').textContent = target
      ? `园区暂定目标依据：${basis || '未登记'}${date ? ` · ${date} 设定` : ''}。容量和水电按同一园区 ID 分轮补齐。`
      : '当前先固定可回查的物理园区 ID 与地点；园区数量分母由初步盘点后设定。';
    $('mission-package-detail').textContent = `工作包 ${delivered}/${total} 已交付 · ${count('in_progress')} 进行中 · ${count('blocked')} 受阻（仅协作状态）`;
    $('mission-target-form').hidden = state.role !== 'admin';
    if (state.role === 'admin') {
      $('mission-target-form').elements.target_site_count.value = target || '';
      $('mission-target-form').elements.target_site_basis.value = basis || '';
    }
    $('package-counts').innerHTML = [[count('unassigned'),'待分配'],[count('ready')+count('in_progress'),'待开始 / 进行中'],[count('blocked'),'受阻'],[count('delivered'),'已交付']].map(([n,label])=>`<span><strong>${n}</strong>${label}</span>`).join('');
    const filter = $('package-filter').value;
    const items = state.packages.filter(p => !filter || p.status === filter);
    $('package-rows').innerHTML = items.map(p => `<tr data-package="${esc(p.id)}"><td data-label="工作包"><strong class="package-name">${esc(p.title)}</strong><span class="package-region">${esc(p.region)}</span><p class="package-scope">${esc(p.scope)}</p><details><summary>${state.public_view?'来源方向':'来源方向与备注'}</summary><p>${esc(p.sources)}</p>${p.note?`<p>${esc(p.note)}</p>`:''}</details></td><td data-label="参与成员">${esc(state.public_view?'登录后可见':p.assignee || '待分配')}</td><td data-label="机器 / 模型">${state.public_view?'<span class="muted">登录后可见</span>':`${esc(p.machine || '待确认')}<br><span class="muted">${esc(p.model || '模型未登记')}</span>`}</td><td data-label="截止日">${esc(state.public_view?'登录后可见':p.due || '待安排')}</td><td data-label="协调状态"><span class="package-status ${esc(p.status)}">${esc(statuses[p.status] || p.status)}</span></td><td data-label="交付 / 操作">${state.public_view?'<a href="/login">登录协作 →</a>':p.delivery_pointer?`<details><summary>交付指针</summary><p class="delivery-pointer">${esc(p.delivery_pointer)}</p></details>`:'<span class="muted">尚无交付指针</span>'}${canEdit(p)?`<button type="button" data-edit="${esc(p.id)}">${state.can_create?'分配 / 更新':'更新我的进度'}</button>`:''}</td></tr>`).join('') || '<tr><td colspan="6">这个状态下暂无工作包。</td></tr>';
    $('package-rows').querySelectorAll('[data-edit]').forEach(button=>button.addEventListener('click',()=>openPackage(button.dataset.edit)));
    renderDashboard();
    renderPackageWorkspace();
  }

  function renderDashboard() {
    const format = n => new Intl.NumberFormat('zh-CN').format(n);
    $('package-dashboard').innerHTML = state.packages.map(p => {
      const progress = state.package_progress?.[p.id] || {};
      return `<button type="button" class="package-dashboard-card" data-package-dashboard="${esc(p.id)}"><span class="dashboard-package-title">${esc(p.title)}</span><span class="dashboard-package-count"><strong data-package-published-sites>${format(progress.published_sites ?? 0)}</strong> 个园区已入库</span><span class="dashboard-package-meta">${format(progress.reviewed_files ?? 0)} 份已审 · ${format(progress.published_statements ?? 0)} 条来源记录</span><span class="dashboard-package-link">查看提交与进展 →</span></button>`;
    }).join('');
    $('package-dashboard').querySelectorAll('[data-package-dashboard]').forEach(button => button.addEventListener('click', () => {
      selectedPackageId = button.dataset.packageDashboard;
      renderPackageWorkspace();
      showTaskView('submission-progress');
    }));
  }

  const packageTime = value => value ? new Date(value * 1000).toLocaleString('zh-CN',
    {timeZone:'Asia/Shanghai',hour12:false}) + '（北京时间）' : '尚无已完成审阅';
  const packageShortTime = value => value ? new Date(value * 1000).toLocaleString('zh-CN',
    {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '时间未记录';

  function renderPackageWorkspace() {
    const packages = state.packages;
    const fromHash = location.hash.startsWith('#package-') ? location.hash.slice(9) : '';
    let remembered = '';
    try { remembered = localStorage.getItem('inresearch-active-package-v1') || ''; } catch { /* Optional preference. */ }
    if (!packages.some(p=>p.id === selectedPackageId)) {
      selectedPackageId = [fromHash, remembered, 'dc-census-cn', packages[0]?.id]
        .find(id=>packages.some(p=>p.id === id));
    }
    const current = packages.find(p=>p.id === selectedPackageId);
    if (!current) return;
    const tabs = $('package-tabs');
    tabs.innerHTML = packages.map(p=>`<button type="button" role="tab" data-package-tab="${esc(p.id)}" aria-controls="package-active-panel" aria-selected="${p.id === current.id}" tabindex="${p.id === current.id ? 0 : -1}">${esc(p.title)}</button>`).join('');
    tabs.querySelectorAll('[data-package-tab]').forEach(button=>button.addEventListener('click',()=>{
      selectedPackageId = button.dataset.packageTab;
      try { localStorage.setItem('inresearch-active-package-v1',selectedPackageId); } catch { /* Optional preference. */ }
      renderPackageWorkspace();
    }));
    const progress = state.package_progress?.[current.id] || {};
    const task = progress.current_task || {version:1,scope:current.scope,next_action:'按当前工作包范围，先找具名园区及可回查来源。'};
    const currentRead = readState === 'current';
    const processing = progress.processing || {};
    const active = (processing.running || 0) + (processing.waiting || 0);
    const blocked = processing.blocked || 0, sourceErrors = processing.source_error || 0;
    const notice = $('package-processing');
    notice.hidden = !currentRead || !(active || blocked || sourceErrors || current.status === 'in_progress');
    notice.dataset.state = blocked || sourceErrors ? 'blocked' : 'running';
    const heading = blocked ? '部分材料处理受阻，等待负责人处理' : sourceErrors ? '有原件需要修正，请查看处理反馈' : active ? '正在处理，反馈稍后更新' : '工作进行中，资料整理好后可随时提交';
    const details = [[processing.running,'份正在审阅'],[processing.waiting,'份等待处理'],[blocked,'份处理受阻'],[sourceErrors,'份原件需修正']].filter(([n])=>n).map(([n,label])=>`${n} ${label}`).join(' · ');
    notice.innerHTML = `<strong>${esc(heading)}</strong><p>${esc(details || '继续补齐当前工作包的园区与来源。')}${active ? '。已收到的材料无需重复提交；你可以继续整理其他资料。' : ''}</p><small>本页每 30 秒自动刷新 · 最近读取 ${esc(packageTime(readAt))}</small>`;
    $('package-current-meta').textContent = currentRead ? `当前共同任务 v${task.version} · ${task.updated_at ? '更新于 '+packageTime(task.updated_at) : '尚无完成审阅的材料'}` : `上次读取于 ${packageTime(readAt)} · 任务 v${task.version} · 未确认当前有效`;
    $('package-current-title').textContent = current.title;
    $('package-current-scope').textContent = task.scope || current.scope;
    const format = value => new Intl.NumberFormat('zh-CN').format(value ?? 0);
    const publishedSites = progress.published_sites ?? task.completed?.published_sites ?? 0;
    const publishedStatements = task.completed?.published_statements ?? progress.published_statements ?? 0;
    const feedbackRounds = task.completed?.feedback_rounds ?? task.completed?.reviewed_rounds;
    $('package-current-progress-summary').textContent = `${currentRead ? '共同进展' : '上次读取的共同进展'}：${current.title}已成功入库 ${format(publishedSites)} 个去重园区，${format(publishedStatements)} 条来源已上线${feedbackRounds == null ? '' : `，${format(feedbackRounds)} 轮团队反馈已形成`}。`;
    const latestReceived = (progress.events || [])[0];
    $('package-current-received').textContent = latestReceived?.received_at
      ? `最新收到：${latestReceived.submitter}（${latestReceived.submitter_verified ? '账号' : '自填'}）提交的${latestReceived.material} · ${packageTime(latestReceived.received_at)}`
      : '最新收到：尚无负责人确认的材料。';
    $('package-current-feedback').textContent = `${currentRead ? '最新审阅' : '上次读取的审阅'}：${task.feedback_summary || '尚无已完成审阅，按当前工作包范围提交材料。'}`;
    $('package-current-next').hidden = !currentRead;
    $('package-history-guidance').textContent = currentRead ? '历史记录仅供追溯，执行以上方共同现行反馈与下一步为准；原件和完整审核记录保持原权限。' : '历史记录仅供追溯；最新共同反馈尚未确认，请成功刷新后再查看执行要求。';
    $('package-current-next').textContent = `${currentRead ? '下一步' : '上次读取的下一步（未确认当前有效）'}：${task.next_action}`;
    const remaining = Array.isArray(task.remaining) ? task.remaining.filter(row=>typeof row === 'string' && row !== task.next_action) : [];
    $('package-current-remaining').hidden = !currentRead || !remaining.length;
    $('package-current-remaining').innerHTML = remaining.map(row=>`<li>${esc(row)}</li>`).join('');
    $('package-published-sites').textContent = format(publishedSites);
    $('package-progress-note').textContent = `已上线来源 ${format(publishedStatements)} 条 · ${feedbackRounds == null ? `${format(progress.reviewed_files)} 份材料已审阅` : `${format(feedbackRounds)} 轮团队反馈`}`;
    const events = progress.events || [];
    $('package-history-count').textContent = `· ${events.length} 条`;
    $('package-timeline').innerHTML = events.length ? events.map(event=>{
      const historyStatus = event.outcome === 'sampled_incomplete' ? '抽样反馈 · 全表待审' :
        event.outcome === 'reviewed' ? '已出审核反馈' : event.outcome === 'manual_feedback' ? '已出负责人反馈' : event.outcome === 'blocked' ? '分析暂时受阻' :
        event.outcome === 'source_error' ? '原件需修订' : '已确认，待分析';
      const liveStatus = ({running:'正在审阅 · 反馈稍后更新',waiting:'等待处理 · 反馈稍后更新',blocked:'处理受阻',source_error:'原件需修订'})[event.processing_state];
      const status = liveStatus ? liveStatus + (event.reviewed_at || event.feedback_at ? ' · 历史：'+historyStatus : '') : historyStatus;
      const repliedAt = event.reviewed_at || event.feedback_at;
      const reply = repliedAt ? `${event.reviewed_at ? '审阅并回复' : '处理反馈'}：${packageTime(repliedAt)}` : '审阅并回复：尚未完成';
      const packageState = current.status === 'delivered' ? '当前工作包已交付' : '当前工作包未完成，请继续';
      return `<article class="package-timeline-entry"><details class="package-event"><summary><time title="${esc(packageTime(event.received_at))}">${esc(packageShortTime(event.received_at))}</time><strong>${esc(event.submitter)}（${event.submitter_verified ? '账号' : '自填'}） · ${esc(event.material)}</strong><em>${esc(status)}</em></summary><div class="package-event-body"><p>提交：${esc(packageTime(event.received_at))} · ${esc(reply)}</p><p>系统接受并上线：${esc(event.published_statements ?? 0)} 条 · ${esc(packageState)}</p></div></details></article>`;
    }).join('') : `<p class="package-empty">${currentRead ? '这个工作包尚无已确认的团队接力记录。可按上方当前任务提交第一批原件。' : '上次读取时，这个工作包尚无已确认的团队接力记录。'}</p>`;
    window.activeResearchPackageId = current.id;
    window.dispatchEvent(new CustomEvent('research-package-selected',{detail:{packageId:current.id}}));
  }

  $('package-upload-action').addEventListener('click',()=>{
    showTaskView('submission-progress');
    $('upload-package').focus({preventScroll:true});
  });
  $('package-tabs').addEventListener('keydown', event => {
    const before = [...$('package-tabs').querySelectorAll('[data-package-tab]')];
    const index = before.indexOf(event.target);
    if (index < 0 || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? before.length - 1 :
      (index + (event.key === 'ArrowRight' ? 1 : -1) + before.length) % before.length;
    const id = before[next].dataset.packageTab;
    before[next].click();
    [...$('package-tabs').querySelectorAll('[data-package-tab]')].find(button => button.dataset.packageTab === id)?.focus({preventScroll:true});
  });
  $('package-refresh').addEventListener('click',load);
  window.addEventListener('research-package-requested',event=>{
    if (!state?.packages.some(p=>p.id === event.detail?.packageId)) return;
    selectedPackageId = event.detail.packageId;
    renderPackageWorkspace();
  });

  $('mission-target-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (state?.role !== 'admin') return;
    const target = Number(event.currentTarget.elements.target_site_count.value);
    const basis = event.currentTarget.elements.target_site_basis.value.trim();
    if (!Number.isInteger(target) || target < 1 || target > 1000000 || basis.length < 5 || basis.length > 500) return;
    const message = $('mission-target-message'); message.textContent = '正在保存…';
    try {
      const response = await fetch('/api/research-tasks',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'research-tasks'},
        body:JSON.stringify({action:'set_target',expected_revision:state.revision,operation_id:crypto.randomUUID(),target_site_count:target,target_site_basis:basis})});
      const result = await response.json();
      if (!response.ok) throw Error(result.error || '目标保存失败');
      await load(); message.textContent = '目标已保存。';
    } catch (error) { message.textContent = error.message; }
  });

  function openPackage(id = null) {
    if (!state) return;
    editing = id ? state.packages.find(p=>p.id === id) : null;
    if (editing ? !canEdit(editing) : !state.can_create) return;
    editingRevision = state.revision;
    pending = null; form.reset();
    value('package_id').value = id || '';
    fields.forEach(key=> {
      value(key).value = editing?.[key] || (key === 'status' ? 'unassigned' : '');
      value(key).disabled = (state.role === 'intern' && !['status','delivery_pointer','note'].includes(key));
    });
    $('package-dialog-title').textContent = editing ? editing.title : '新建工作包';
    $('package-message').textContent = '';
    $('package-dialog').showModal();
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const payload = {action:editing?'update':'create',expected_revision:editingRevision};
    if (editing) payload.package_id = editing.id;
    fields.forEach(key=> { if (!value(key).disabled) payload[key] = value(key).value.trim(); });
    if (payload.assignee && payload.status === 'unassigned') payload.status = 'ready';
    const fingerprint = JSON.stringify(payload);
    if (!pending || pending.fingerprint !== fingerprint) pending = {fingerprint, operation_id:crypto.randomUUID()};
    payload.operation_id = pending.operation_id;
    $('save-package').disabled = true; $('package-message').textContent = '正在保存到服务端…';
    try {
      const response = await fetch('/api/research-tasks',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'research-tasks'},body:JSON.stringify(payload)});
      const result = await response.json();
      if (!response.ok) {
        if (response.status === 409) {
          $('package-dialog').close(); await load(); pending = null;
          $('tasks-status').textContent = '其他成员已修改台账，当前表单未保存。已显示最新版本，请重新打开工作包核对后编辑。';
          return;
        }
        throw Error(result.error || '保存失败，请重试');
      }
      pending = null; $('package-dialog').close(); await load();
    } catch (error) { $('package-message').textContent = error.message; }
    finally { $('save-package').disabled = false; }
  });

  $('new-package').addEventListener('click',()=>openPackage());
  $('close-package').addEventListener('click',()=>$('package-dialog').close());
  const stageLabels = {complete:'本步已有执行结果',pending:'尚未完成',blocked:'受阻',not_applicable:'本例未执行此项'};
  function artifactRow(artifact) {
    if (!artifact) return '';
    const size = artifact.size < 1024 ? artifact.size+' B' : artifact.size < 1024*1024 ? (artifact.size/1024).toFixed(1)+' KiB' : (artifact.size/1024/1024).toFixed(1)+' MiB';
    return `<li class="example-artifact" data-artifact="${esc(artifact.id)}"><div>${artifact.available?`<a href="${esc(artifact.download_url)}" download>${esc(artifact.filename)} ↓</a>`:`<span>${esc(artifact.filename)} · 产物不可用</span>`}<small>${esc(size)} · ${artifact.access_scope==='public'?'公开样例产物':'登录可见产物'}</small><code>SHA256 ${esc(artifact.sha256)}</code></div></li>`;
  }
  function renderExample(sample, authenticated) {
    const artifacts = Object.fromEntries(sample.artifacts.map(a=>[a.id,a]));
    const used = new Set(sample.stages.flatMap(stage=>stage.artifact_ids));
    const facts = sample.facts.map(f=>`<div><dt>${esc(f.label)}</dt><dd>${esc(f.value===null?'未知':f.value)}${f.unit?` <small>${esc(f.unit)}</small>`:''}<div class="example-fact-sources">${f.source_ids.map(id=>`<a href="#example-${esc(sample.id)}-source-${esc(id)}">来源 ${esc(id)} ↗</a>`).join(' ')}${f.locator?`<span>${esc(f.locator)}</span>`:''}</div></dd></div>`).join('');
    const identityFacts = sample.facts.filter(f=>['address','operator','developer','opening'].includes(f.id));
    const summaryFacts = (identityFacts.length ? identityFacts : sample.facts).slice(0,4).map(f=>`<div><dt>${esc(f.label)}</dt><dd>${esc(f.value===null?'未知':f.value)}${f.unit?` <small>${esc(f.unit)}</small>`:''}</dd></div>`).join('');
    const execution = sample.execution || {};
    const stages = sample.stages.map((stage,index)=>{
      const missing = stage.artifact_ids.some(id=>!artifacts[id]?.available);
      return `<details class="example-stage" data-stage="${esc(stage.id)}" ${index===0?'open':''}><summary><span class="example-stage-number">${String(index+1).padStart(2,'0')}</span><strong>${esc(stage.title)}</strong><span class="example-stage-state ${esc(stage.state)}">${esc(stageLabels[stage.state])}</span></summary><div class="example-stage-body"><p>${esc(stage.result)}</p>${missing?'<p class="example-warning">本步有产物缺失或摘要不符，当前无法复验，请联系负责人恢复原产物。</p>':''}<ul class="example-artifacts">${stage.artifact_ids.map(id=>artifactRow(artifacts[id])).join('')}</ul>${!stage.artifact_ids.length?'<p class="small muted">本步没有可供当前访问者下载的产物；执行状态按实际记录保留。</p>':''}</div></details>`;
    }).join('');
    const extra = sample.artifacts.filter(a=>!used.has(a.id));
    const stageSummary = sample.stages.map(stage=>`<li class="${esc(stage.state)}"><strong>${esc(stage.title)}</strong><span>${esc(stageLabels[stage.state])}</span></li>`).join('');
    return `<article class="worked-example-card" data-example="${esc(sample.id)}"><header class="example-heading"><div><p class="mission-eyebrow">真实园区 · ${esc(sample.id)}</p><h3>${esc(sample.name)}</h3><p>${esc(sample.status)} · 处理记录 ${esc(sample.processed_at || '时间未登记')}</p></div><div class="example-links">${sample.links.project?`<a href="${esc(sample.links.project)}">查看园区档案${authenticated?'':'（登录）'} →</a>`:''}${sample.links.map?`<a href="${esc(sample.links.map)}">在地图定位${authenticated?'':'（登录）'} →</a>`:''}</div></header><div class="example-summary-grid"><div><p class="example-summary-label">这次先固定</p><dl class="example-key-facts">${summaryFacts}</dl></div><aside class="example-template-note"><strong>照着交一包</strong><p>一处物理园区、地点、分期或主体，以及能回到原文的定位。</p><ul><li>原件不改字节</li><li>未知明确留空</li><li>上传后按回执继续补项</li></ul></aside></div><div class="example-stage-summary"><strong>真实进度</strong><ol>${stageSummary}</ol></div><details class="example-full-record"><summary>查看完整真实样例：原件、过程、未知项与来源</summary><div class="example-full-record-body"><dl class="example-facts">${facts}</dl><div class="example-execution"><strong>本次实际执行</strong><span>${authenticated?`机器 ${esc(execution.machine || '未登记')} · 模型 ${esc(execution.model || '未使用或未登记')} · 操作者 ${esc(execution.actor || '未登记')}`:'登录后查看实际机器、模型与操作者。'}</span><span>阅读范围：${esc(execution.reading_scope || '未登记，不据此认定全文阅读')}</span></div><div class="example-stages">${stages}</div>${extra.length?`<details class="example-stage"><summary><strong>其他交付产物</strong></summary><ul class="example-artifacts example-stage-body">${extra.map(artifactRow).join('')}</ul></details>`:''}<div class="example-unknowns"><h4>本例仍然不知道什么</h4>${sample.unknowns.length?sample.unknowns.map(row=>`<article><strong>${esc(row.label)}</strong><p>${esc(row.reason)}</p><small>下一步：${esc(row.next_action)}</small></article>`).join(''):'<p class="small muted">未登记缺项清单，不据此声称信息完整。</p>'}</div><details class="example-source-list"><summary>原文出处与证据定位 · ${sample.sources.length} 项</summary>${sample.sources.map(s=>`<article id="example-${esc(sample.id)}-source-${esc(s.id)}"><strong>${esc(s.id)} · ${esc(s.title)}</strong>${s.url?`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">访问原始出处 ↗</a>`:''}<p>${esc(s.locator || '定位未登记')}</p>${s.artifact_id?`<ul class="example-artifacts">${artifactRow(artifacts[s.artifact_id])}</ul>`:''}</article>`).join('')}</details></div></details></article>`;
  }
  let examplesLoaded = false;
  async function loadExamples(force = false) {
    if (examplesLoaded && !force) return;
    $('examples-status').textContent = '正在读取真实样例…';
    try {
      const response = await fetch('/api/research-task-examples',{cache:'no-store'});
      if (!response.ok) throw Error('样例包暂不可用，请刷新或联系负责人修复。');
      const data = await response.json();
      examplesLoaded = true;
      if (!data.examples.length) {
        $('examples-status').textContent = '真实样例尚未安装。';
        $('example-content').innerHTML = '<div class="example-empty">目前没有可回查的真实样例包。原件、候选和真实回执安装后会逐步显示；这里不会用模板或假数据填成已完成。</div>';
        return;
      }
      $('examples-status').textContent = '状态来自实际样例记录；每个下载文件按登记 SHA 和大小核对，缺失或变化会停止下载。';
      $('example-content').innerHTML = data.examples.map(sample=>renderExample(sample,data.authenticated)).join('');
    } catch (error) {
      $('examples-status').textContent = error.message;
      $('example-content').innerHTML = '<div class="example-empty">无法读取真实样例，请重试。已有样例不因暂时失败被重建或标为完成。</div>';
    }
  }
  $('refresh-examples').addEventListener('click',()=>loadExamples(true));
  $('example-content').addEventListener('click',event=>{
    const link = event.target.closest('a[href^="#example-"]');
    if (!link) return;
    const target = document.getElementById(link.getAttribute('href').slice(1));
    if (!target) return;
    event.preventDefault();
    const drawer = target.closest('details'); if (drawer) drawer.open = true;
    target.scrollIntoView({block:'start'}); target.tabIndex = -1; target.focus({preventScroll:true});
  });
  $('refresh-tasks').addEventListener('click',load);
  $('package-filter').addEventListener('change',()=> {if(state)render();});
  showTaskView(viewForHash(location.hash));
  load();
  loadExamples();
  setInterval(() => {
    if (!document.hidden && readState !== 'loading' && window.activeResearchTaskView === 'submission-progress') load();
  }, 30000);
})();
