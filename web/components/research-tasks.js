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
    const allowed = new Set(['task-home','submission-progress']);
    if (!allowed.has(view)) view = 'task-home';
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
    moveTab(event, [...document.querySelectorAll('[data-task-view]')]));
  document.querySelectorAll('[data-task-view-request]').forEach(button => button.addEventListener('click',()=>showTaskView(button.dataset.taskViewRequest)));
  window.addEventListener('research-task-view-requested',event=>showTaskView(event.detail?.view));
  window.addEventListener('hashchange',()=>showTaskView(viewForHash(location.hash)));
  let state = null, pending = null, editing = null, editingRevision = null, selectedPackageId = null;
  const canEdit = item => state && (state.can_create || (state.role === 'intern' && String(item.assignee || '').split(/[,，、;；\n]+/).map(name => name.trim()).includes(state.actor)));
  const value = name => form.elements.namedItem(name);

  async function load() {
    $('tasks-status').textContent = '正在读取任务台账…';
    try {
      const response = await fetch('/api/research-tasks', {cache:'no-store'});
      if (!response.ok) throw Error(response.status === 401 ? '请登录后查看任务' : '任务台账暂不可用，请刷新重试');
      state = await response.json();
      window.researchTasksState = state;
      window.dispatchEvent(new CustomEvent('research-tasks-loaded',{detail:state}));
      $('new-package').hidden = !state.can_create;
      $('task-role-note').textContent = state.can_create ? '内部成员可以新增、分配和更新工作包；多人协作可用逗号分隔成员登录名，各成员可更新自己的状态、交付与备注。' : state.role === 'intern' ? '实习生成员可查看全部分工；只可更新包含自己登录名的工作包状态、交付与备注。范围、参与成员、机器与模型由内部成员维护。' : '任务方向、协调状态和公开样例可直接查看；实际参与成员、机器、模型、备注和交付指针登录后可见。';
      render(); renderRegister();
      $('tasks-status').textContent = `服务端台账 · 版本 ${state.revision} · ${state.packages.length} 个工作包。${state.public_view?'公开只读视图；登录后可查看实际分工并协作。':'机器与模型按实际执行填写，未分配不默认运行。'}`;
    } catch (error) {
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
    $('package-current-meta').textContent = `当前共同任务 v${task.version} · ${task.updated_at ? '更新于 '+packageTime(task.updated_at) : '尚无完成审阅的材料'}`;
    $('package-current-title').textContent = current.title;
    $('package-current-scope').textContent = task.scope || current.scope;
    $('package-current-next').textContent = `下一步：${task.next_action}`;
    $('package-published-sites').textContent = new Intl.NumberFormat('zh-CN').format(progress.published_sites ?? 0);
    $('package-progress-note').textContent = `暂定目标待初步盘点 · ${progress.published_statements ?? 0} 条来源陈述已上线 · ${progress.reviewed_files ?? 0} 份材料已审阅`;
    const events = progress.events || [];
    $('package-timeline').innerHTML = events.length ? events.map((event,index)=>{
      const status = event.outcome === 'sampled_incomplete' ? '抽样反馈 · 全表待审' :
        event.outcome === 'reviewed' ? '已出审核反馈' : event.outcome === 'blocked' ? '分析暂时受阻' :
        event.outcome === 'source_error' ? '原件需修订' : '已确认，待分析';
      return `<article class="package-timeline-entry"><details class="package-event"><summary><time title="${esc(packageTime(event.received_at))}">${esc(packageShortTime(event.received_at))}</time><strong>${esc(event.submitter)}（自填） · ${esc(event.material)}</strong><em>${esc(status)}</em></summary><div class="package-event-body"><p>${esc(event.submitter)}（自填） · 提交 ${esc(event.material)} · 入库来源 ${esc(event.published_statements ?? 0)} 条</p><p>收到：${esc(packageTime(event.received_at))}${event.reviewed_at ? ` · 审阅完成：${esc(packageTime(event.reviewed_at))}` : ''}</p><p class="package-event-feedback">团队反馈：${esc(event.feedback)}</p>${event.next_action ? `<p>下一步：${esc(event.next_action)}</p><button type="button" data-download-event-plan="${index}">下载这轮计划 .md ↓</button>` : '<p>负责人确认后形成反馈与下一步计划。</p>'}</div></details></article>`;
    }).join('') : '<p class="package-empty">这个工作包尚无已确认的团队接力记录。可按上方当前任务提交第一批原件。</p>';
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
      value(key).disabled = state.role === 'intern' && !['status','delivery_pointer','note'].includes(key);
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

  function download(name, data, type) {
    const url = URL.createObjectURL(new Blob([data],{type}));
    const link = document.createElement('a'); link.href = url; link.download = name;
    document.body.append(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  const activePackage = () => state?.packages.find(p => p.id === selectedPackageId);
  $('download-package-plan').addEventListener('click', () => {
    const p = activePackage(), progress = state?.package_progress?.[selectedPackageId];
    if (!p || !progress?.current_task) return;
    const task = progress.current_task;
    const text = [`# ${p.title} · 当前计划`, '', `任务版本：v${task.version}`, `更新时间：${packageTime(task.updated_at)}`, '', '## 工作范围', '', task.scope, '', '## 当前成果', '', `已入库 ${progress.published_sites} 个去重园区，${progress.published_statements} 条来源记录；${progress.reviewed_files} 份材料已审阅。`, '', '## 下一步', '', task.next_action, '', '## 交付', '', '按当前范围补齐园区、字段原值与单位、时点和可回查来源；未知留空，保留原件。', '', '提交与进展：https://inresearch.ai/tasks.html', ''].join('\n');
    download(`${p.id}-当前计划-v${task.version}.md`,text,'text/markdown;charset=utf-8');
  });
  $('package-timeline').addEventListener('click', event => {
    const button = event.target.closest('[data-download-event-plan]');
    if (!button) return;
    const p = activePackage(), row = state?.package_progress?.[selectedPackageId]?.events?.[Number(button.dataset.downloadEventPlan)];
    if (!p || !row?.next_action) return;
    const text = [`# ${p.title} · 本轮反馈与下一步`, '', `提交时间：${packageTime(row.received_at)}`, `审阅时间：${packageTime(row.reviewed_at)}`, `提交人：${row.submitter}（自填）`, `材料类型：${row.material}`, '', '## 本轮交付', '', `入库来源记录：${row.published_statements ?? 0} 条`, row.feedback, '', '## 下一步计划', '', row.next_action, '', '本文件是本轮团队公开摘要；执行前请查看该工作包的最新计划，逐项修改要求凭本人回执下载。', ''].join('\n');
    download(`${p.id}-本轮计划-${row.received_at || '未记录'}.md`,text,'text/markdown;charset=utf-8');
  });

  $('download-brief').addEventListener('click',()=> {
    if (!state) { $('tasks-status').textContent = '请先刷新并成功读取服务端任务台账，再下载任务书。'; return; }
    const brief = `# ${state.mission.title}\n\n研究方向：两条研究线，共用证据，按用途连接。通用模型变量绑定既有目标行；园区普查允许先发现登记，按用途建立证据映射。\n优先级：P1\n任务建立：2026-10-12\n\n${state.mission.goal}\n\n${state.mission.scale_note}\n\n## 工作包（服务端台账版本 ${state.revision}）\n\n` + state.packages.map(p=>`### ${p.title}\n\n- ID：${p.id}\n- 范围：${p.region}；${p.scope}\n- 来源：${p.sources}\n- 参与成员：${state.public_view ? '登录后可见' : p.assignee || '待分配'}\n- 机器 / 模型：${state.public_view ? '登录后可见' : p.machine || '待确认'} / ${state.public_view ? '登录后可见' : p.model || '未登记'}\n- 截止日：${state.public_view ? '登录后可见' : p.due || '待安排'}\n- 状态：${statuses[p.status]}\n- 交付指针：${state.public_view ? '登录后可见' : p.delivery_pointer || '尚无'}\n- 备注：${state.public_view ? '登录后可见' : p.note || '无'}\n`).join('\n') + `\n## 每条资料怎么交\n\n保留原生 PDF/HTML/Office/CSV/API 原响应，不改字节。交 manifest.json、SHA256SUMS、originals/、observations.jsonl、errors.jsonl、run-report.json。OCR/文本/JSON 作为 derived/ 增补，带 derived_from_sha256、页码、实际工具与版本、漏页及未读图片。\n\n共用检查清单（版本 ${$('observation-coverage').dataset.version}）：${Array.from(document.querySelectorAll('[data-angle]')).map(el=>el.dataset.angle+'：'+el.textContent.trim()).join('；')}。视图允许交叉扩展，当前数量不表示永久穷尽；未检查、不适用及已查未取得分别说明。\n\n每条候选一个对象、指标和证据范围，保留原值/单位、口径、有效与披露时间、原文引句、页/表/行列和上下文。IT、设施、接电、发电、合同 MW 分开；年度电耗 MWh 另记。缺项保持 null，已知一条即可交，不把全园区与分期重复相加。\n\n候选交换契约：fetchdata-handoff/1。一般信息 target_ids 可为空；研究端映射后按唯一身份和原件追加来源登记，标记基础登记待查。正式结论/答案/模型输入按 C3。采集、原件接收、阅读、登记及实际上线分别留回执；工作包已交付不表示已采用。\n\n完整字段与离线验包：https://inresearch.ai/doc.html?f=docs/guides/fetchdata/delivery-contract.md\n`;
    download('全球数据中心普查-任务书.md',brief,'text/markdown;charset=utf-8');
  });

  const downloadTemplate = () => {
    const unknownTime = {value:null,precision:'unknown',basis:null};
    const template = {
      template_only:true, contract:'fetchdata-handoff/1',
      instructions:['这是待填模板，不是有效交付包。按 files 键名拆成文件，填入真实值后离线验包。','原件另存 originals/<真实SHA256>.<ext>；SHA256SUMS 每行 SHA256 + 两个空格 + 相对路径。','observations.jsonl 每行一个 JSON；下列示意中的 null 与待填项需按真实原文填写。','使用实际队伍 provider_id，不得冒充 fetchspec；现有接收 API 不直接兼容本交换包。','未知时间不造日期；restricted 原文、私有路径、凭据不可公开；模型输出不可冒充原文。'],
      files:{
        'manifest.json':{contract:'fetchdata-handoff/1',provider_id:'待填实际队伍',delivery_id:'待填唯一批号',collector_revision:'待填实际40位Git提交',generated_at:null,items:[{item_id:'source-1',source_id:'待填来源机构/系列',source_item_id:'待填来源原生身份',url:null,title:'待填原文标题',publisher:null,retrieved_at:null,sha256:'待填原件SHA256',path:'originals/<sha256>.<ext>',content_type:null,access_scope:'unknown',completeness:'unknown',version_of:null}]},
        'SHA256SUMS':'<真实SHA256>  originals/<真实SHA256>.<ext>\n',
        'observations.jsonl':[{observation_id:'待填本队唯一ID',source_item_id:'source-1',object:{type:'site',match_status:'unresolved',canonical_id:null,name:'待填原文园区名',identifiers:{country:null,province:null,city:null,address:null,coordinates:null}},metric:'待填稳定指标名',value:{type:'number',number:null,raw:'待填原文值'},unit:null,scope:'待填园区/分期/楼栋边界；容量口径IT/设施/接电/发电/合同；统计期间与条件',kind:'reported',effective_time:unknownTime,published_time:{...unknownTime},evidence:{locator:'待填物理页/表/行列/JSON Pointer',quote:'待填逐字原文',context:'待填表头/脚注/限定条件'},target_ids:[],revision_of:null,conflicts_with:[]}],
        'errors.jsonl':[],
        'run-report.json':{template_only:true,run_id:'待填唯一批号',team:'待填实际队伍',started_at:null,finished_at:null,host:null,collector_revision:'待填实际40位Git提交',model:null,duration_seconds:null,bytes_downloaded:null,counts:{scheduled_sources:null,attempted_sources:null,successful_sources:null,unchanged_sources:null,failed_sources:null,blocked_sources:null,unattempted_sources:null,new_originals:null,duplicate_originals:null,candidates:null,matched_candidates:null,unresolved_candidates:null,conflicts:null,received:null,reviewed:null,adopted:null,published:null},note:'未知计数不能填伪造的0；只填写本次实际执行计数，尚未接通的接收/采用不要报告成功'},
        'derived/README.txt':'可选派生文本/OCR/JSON；逐件记录 derived_from_sha256、页号、工具/模型及版本、未读范围、漏页和人工校对情况。原件不改字节。\n'
      },
      contract_url:'https://inresearch.ai/doc.html?f=docs/guides/fetchdata/delivery-contract.md'
    };
    download('数据中心资料交付-待填模板.json',JSON.stringify(template,null,2)+'\n','application/json;charset=utf-8');
  };
  $('download-template').addEventListener('click',downloadTemplate);
  $('download-template-home').addEventListener('click',downloadTemplate);

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
})();
