/* Project coordination only. Source registration and publication keep their own authority. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statuses = {unassigned:'待分配',ready:'待开始',in_progress:'进行中',blocked:'受阻',delivered:'已交付'};
  const fields = ['title','region','scope','sources','assignee','machine','model','due','status','delivery_pointer','note'];
  const form = $('package-form');
  let state = null, pending = null, editing = null, editingRevision = null;
  const canEdit = item => state && (state.can_create || (state.role === 'intern' && item.assignee === state.actor));
  const value = name => form.elements.namedItem(name);

  async function load() {
    $('tasks-status').textContent = '正在读取任务台账…';
    try {
      const response = await fetch('/api/research-tasks', {cache:'no-store'});
      if (!response.ok) throw Error(response.status === 401 ? '请登录后查看任务' : '任务台账暂不可用，请刷新重试');
      state = await response.json();
      $('new-package').hidden = !state.can_create;
      $('task-role-note').textContent = state.can_create ? '内部成员可以新增、分配和更新工作包；负责人使用成员登录名，实习生成员可更新自己的状态、交付与备注。' : state.role === 'intern' ? '实习生成员可查看全部分工；只可更新分配给自己登录名的工作包状态、交付与备注。范围、负责人、机器与模型由内部成员维护。' : '当前角色可以查看任务与下载模板，工作包由内部成员维护。';
      render(); renderRegister();
      $('tasks-status').textContent = `服务端台账 · 版本 ${state.revision} · ${state.packages.length} 个工作包。机器与模型按实际执行填写，未分配不默认运行。`;
    } catch (error) {
      $('tasks-status').textContent = error.message;
      $('register-stats').textContent = '台账读取失败，请刷新重试。';
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
    $('package-counts').innerHTML = [[count('unassigned'),'待分配'],[count('ready')+count('in_progress'),'待开始 / 进行中'],[count('blocked'),'受阻'],[count('delivered'),'已交付']].map(([n,label])=>`<span><strong>${n}</strong>${label}</span>`).join('');
    const filter = $('package-filter').value;
    const items = state.packages.filter(p => !filter || p.status === filter);
    $('package-rows').innerHTML = items.map(p => `<tr data-package="${esc(p.id)}"><td data-label="工作包"><strong class="package-name">${esc(p.title)}</strong><span class="package-region">${esc(p.region)}</span><p class="package-scope">${esc(p.scope)}</p><details><summary>来源方向与备注</summary><p>${esc(p.sources)}</p>${p.note?`<p>${esc(p.note)}</p>`:''}</details></td><td data-label="负责人">${esc(p.assignee || '待分配')}</td><td data-label="机器 / 模型">${esc(p.machine || '待确认')}<br><span class="muted">${esc(p.model || '模型未登记')}</span></td><td data-label="截止日">${esc(p.due || '待安排')}</td><td data-label="协调状态"><span class="package-status ${esc(p.status)}">${esc(statuses[p.status] || p.status)}</span></td><td data-label="交付 / 操作">${p.delivery_pointer?`<details><summary>交付指针</summary><p class="delivery-pointer">${esc(p.delivery_pointer)}</p></details>`:'<span class="muted">尚无交付指针</span>'}${canEdit(p)?`<button type="button" data-edit="${esc(p.id)}">${state.can_create?'分配 / 更新':'更新我的进度'}</button>`:''}</td></tr>`).join('') || '<tr><td colspan="6">这个状态下暂无工作包。</td></tr>';
    $('package-rows').querySelectorAll('[data-edit]').forEach(button=>button.addEventListener('click',()=>openPackage(button.dataset.edit)));
  }

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

  $('download-brief').addEventListener('click',()=> {
    if (!state) { $('tasks-status').textContent = '请先刷新并成功读取服务端任务台账，再下载任务书。'; return; }
    const brief = `# ${state.mission.title}\n\n优先级：P1\n任务建立：2026-10-12\n\n${state.mission.goal}\n\n${state.mission.scale_note}\n\n## 工作包（服务端台账版本 ${state.revision}）\n\n` + state.packages.map(p=>`### ${p.title}\n\n- ID：${p.id}\n- 范围：${p.region}；${p.scope}\n- 来源：${p.sources}\n- 负责人：${p.assignee || '待分配'}\n- 机器 / 模型：${p.machine || '待确认'} / ${p.model || '未登记'}\n- 截止日：${p.due || '待安排'}\n- 状态：${statuses[p.status]}\n- 交付指针：${p.delivery_pointer || '尚无'}\n- 备注：${p.note || '无'}\n`).join('\n') + `\n## 每条资料怎么交\n\n保留原生 PDF/HTML/Office/CSV/API 原响应，不改字节。交 manifest.json、SHA256SUMS、originals/、observations.jsonl、errors.jsonl、run-report.json。OCR/文本/JSON 作为 derived/ 增补，带 derived_from_sha256、页码、实际工具与版本、漏页及未读图片。\n\n十二个检查角度：物理地点与边界；土地与产权；开发/设计/承建/运营；使用方与租赁；电源/输配电/接入；水源/供水/冷却；网络；审批与约束；容量与分期；设备与系统；投资/融资/合同；时间/运行/证据。\n\n每条候选一个对象、指标和证据范围，保留原值/单位、口径、有效与披露时间、原文引句、页/表/行列和上下文。IT、设施、接电、发电、合同 MW 分开；年度电耗 MWh 另记。缺项保持 null，已知一条即可交，不把全园区与分期重复相加。\n\n候选交换契约：fetchdata-handoff/1。一般信息 target_ids 可为空；研究端映射后按唯一身份和原件追加来源登记，标记基础登记待查。正式结论/答案/模型输入按 C3。采集、原件接收、阅读、登记及实际上线分别留回执；工作包已交付不表示已采用。\n\n完整字段与离线验包：https://inresearch.ai/doc.html?f=docs/guides/fetchdata/delivery-contract.md\n`;
    download('全球数据中心普查-任务书.md',brief,'text/markdown;charset=utf-8');
  });

  $('download-template').addEventListener('click',()=> {
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
  });

  $('new-package').addEventListener('click',()=>openPackage());
  $('close-package').addEventListener('click',()=>$('package-dialog').close());
  $('refresh-tasks').addEventListener('click',load);
  $('package-filter').addEventListener('change',()=> {if(state)render();});
  load();
})();
