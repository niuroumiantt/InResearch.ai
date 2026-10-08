/* Management observes published execution snapshots; reading and adoption stay separate. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n = v => typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('zh-CN') : '—';
const when = v => {
  if(!v) return '未记录';
  const d = new Date(typeof v==='number'?v*1000:v);
  return Number.isNaN(+d) ? '时间未知' : d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
};
const duration = s => typeof s !== 'number' ? '—' : s < 60 ? Math.floor(s)+' 秒' : s < 3600 ? Math.floor(s/60)+' 分钟' : s < 86400 ? (s/3600).toFixed(1)+' 小时' : (s/86400).toFixed(1)+' 天';
const labels = {extract:'正文提取',triage:'评分分流',read:'分块精读',synthesize:'综合报告',organize:'资料归档',receipt:'交付回执'};
const states = {pending:'排队',queued:'排队',running:'执行中',blocked:'阻塞',failed:'失败',succeeded:'成功',complete:'完整阅读完成',summarized:'摘要阅读完成',ready:'待采用',timeout:'超时',unknown:'未知',idle:'空闲',degraded:'有异常',not_connected:'未连接'};
const tag = (text, cls='neutral') => `<span class="ops-tag ${cls}">${esc(text)}</span>`;
const empty = text => `<div class="ops-empty">${esc(text)}</div>`;
const tasks = [
 ['news','查询新闻同步','查看 Spark 发布的线索台账，不启动采集。','查看状态'],
 ['reader','查询阅读状态','读取 Spark 快照，不启动或重启阅读。','查看状态'],
 ['verify','生成核验清单','列出过期、争议与待复核记录，生成完整清单。','检查与清单'],
 ['queue','生成旧表精读清单','旧打分表迁移视图；与上方 Spark 实际队列分开。','检查与清单'],
 ['validate','检查登记数据','检查数据格式与口径规则；不代表事实证据校验通过。','检查与清单'],
 ['facts','检查事实证据','检查事实字段、原件哈希与可比性，不改写事实。','检查与清单'],
 ['indicators','回填指标','重新计算并写入已有指标；不采集新数据。','执行操作'],
 ['export','导出成果快照','生成 Markdown 与 JSON；在成果页查看及打印。','执行操作'],
 ['map','生成 Top10 地图','生成 HTML；有浏览器渲染环境才同时生成 PDF。','执行操作'],
 ['intake','检查并分流投递','处理已收到的成员投递，按既有规则分流。','执行操作']
];
let data=null, tab='pending', loading=false, loaded=false;
const busy = new Set();
function kpi(value,label,detail,cls='') { return `<div class="ops-kpi"><div class="label">${esc(label)}</div><div class="value ${cls}">${n(value)}</div><div class="detail">${esc(detail)}</div></div>`; }
function healthRow(title,status,detail,cls) { return `<div class="ops-health-row"><div>${esc(title)}<small>${esc(detail)}</small></div><div class="right">${tag(status,cls)}</div></div>`; }
function latestTask(task) { return data?.tasks?.[task] || {}; }
function render() {
 const r=data.reader || {}, o=r.operations, quality=data.quality, target=data.targets;
 const hasOps=o && o.schema_version===1 && Array.isArray(o.stages) && o.queues;
 const fresh=!r.stale && r.generated_age_seconds!==null && typeof r.generated_age_seconds==='number' && r.generated_age_seconds<=900;
 const counts=o?.current_documents || r.counts;
 const exec=o?.execution_documents;
 const pending=hasOps ? o.queues.pending?.total : undefined;
 const blockers=exec ? (exec.blocked||0)+(exec.failed||0) : counts ? (counts.blocked||0)+(counts.failed||0) : undefined;
 const factsErrors=quality?.facts?.errors;
 const categories=o?.bottleneck_documents;
 const completed=counts ? counts.complete||0 : undefined;
 const important=quality?.verification?.counts?.['1'];
 $('ops-kpis').innerHTML=kpi(completed,'完整阅读完成 · 文档','当前结果；摘要、分块成功与采用不计入')+
   kpi(pending,'当前排队 · 任务',hasOps?'当前执行版本；一份文档可含多个分块任务':'等待 Spark 发布任务明细')+
   kpi(blockers,'执行受阻 · 文档',hasOps?(categories?`执行异常 ${n((categories.execution||0)+(categories.service||0))} · 材料缺口 ${n(categories.material||0)} · 策略暂存 ${n(categories.policy||0)}`:'含待处理与按策略暂存，见下方分类'):'旧快照文档统计；待补原因分布',categories?((categories.execution||0)+(categories.service||0)>0?'bad':''):(blockers?'bad':''))+
   kpi(factsErrors,'事实证据问题 · 项',quality?`${n(quality.facts.records)} 条事实接受检查`:'事实台账尚未读到',factsErrors?'bad':'');
 const issues=[];
 if(!fresh) issues.push({title:'Spark 快照未连接、过期或生成时间未知',cls:'bad',detail:`网站收到：${when(r.received_at)}；Spark 生成：${when(r.generated)}。过期阈值 15 分钟，旧数据不代表现在仍在运行。`,action:'核对 Spark 阅读服务和 inresearch-reader-publish.timer 的发布日志。',href:'#ops-health'});
 if(!hasOps) issues.push({title:'尚未收到队列诊断明细',detail:'旧快照没有排队文件、阻塞分布和近期产出。页面保留已知状态，其余标为未知。',action:'更新 Spark 发布端并等待新快照；无需点击按钮开始阅读。',href:'#ops-stages'});
 if(r.recent_failures?.some(x=>x.error_code==='worker_service_inactive')) issues.push({title:'阅读服务在发布时未运行',cls:'bad',detail:'发布端检测到 inresearch-reader.service 未处于 active。',action:'检查 Spark 阅读服务与最近退出原因。',href:'#ops-health'});
 if(factsErrors) issues.push({title:`${n(factsErrors)} 项事实证据校验未通过`,cls:'bad',detail:'登记数据校验与事实证据校验是两项检查；原件身份等字段缺口在下方逐条列出。',action:'查看事实问题，按记录回原件核对后修订。',href:'#ops-quality'});
 if(important) issues.push({title:`${n(important)} 条优先核验待办`,detail:'发现过期、争议或标记 needs-review 的记录。',action:'打开核验待办，按建议动作查证来源。',href:'#ops-quality'});
 const errors=hasOps && Array.isArray(o.errors) ? [...o.errors].sort((a,b)=>({service:0,execution:1,material:2,policy:3}[a.kind]??4)-({service:0,execution:1,material:2,policy:3}[b.kind]??4)||b.documents-a.documents) : [];
 for(const e of errors.slice(0,5)) issues.push({title:`${e.title} · ${n(e.documents)} 份文档`,cls:e.kind==='execution'||e.kind==='service'?'bad':e.kind==='policy'?'neutral':'',detail:`${labels[e.stage]||e.stage} · ${e.code} · 最早受阻 ${when(e.since)}。${e.kind==='policy'?'这是策略暂存，单独判断是否恢复。':''}`,action:e.action,href:'#ops-queues',code:e.code});
 const stuck=hasOps?(o.queues.running?.items||[]).filter(j=>j.started && Date.parse(o.generated)-Date.parse(j.started)>3600000):[];
 if(fresh && stuck.length) issues.push({title:`${n(stuck.length)} 个执行任务已超过 1 小时`,detail:'长任务需要核对，不自动判定卡死。',action:'检查具体分块、开始时间与模型等待状态。',href:'#ops-queues'});
 if(fresh && hasOps && pending>0 && !(o.windows?.['24h']||[]).some(x=>x.state==='succeeded'&&x.count>0)) issues.push({title:'仍有排队任务，但近 24 小时未记录成功产出',cls:'bad',detail:'请核对点名范围、优先级、模型额度等待和服务日志。',action:'查看阶段与具体队列，确认是否有意暂停。',href:'#ops-stages'});
 const recentFailures=Object.entries(data.tasks||{}).filter(([,v])=>['failed','timeout'].includes(v.outcome));
 for(const [task,t] of recentFailures.slice(0,3)) {
  const runs=(data.history?.items||[]).filter(x=>x.task===task);let consecutive=0;for(const x of runs){if(!['failed','timeout'].includes(x.outcome))break;consecutive++;}
  issues.push({title:`${t.name}：上次${states[t.outcome]}`,cls:'bad',detail:`${when(t.finished)} · 用时 ${duration(t.duration_seconds)}。这是手动任务结果，与常驻服务状态分开。`,action:'查看执行记录和完整日志。',href:'#ops-history'}); if(consecutive>1) issues[issues.length-1].detail+=` 最近留存记录中连续 ${consecutive} 次未通过。`;
 }
 if(data.unavailable?.length) for(const text of data.unavailable) issues.push({title:text,cls:'bad',detail:'该分区无法确认状态，不能解释为零问题。',action:'刷新重试并检查网站服务日志。',href:'#ops-health'});
 const source=r.acquisition?.sources?.inews;
 const news=source?.last_run;
 const newsAge=news?.finished?Math.max(0,(Date.parse(data.generated)-Date.parse(news.finished))/1000):null;
 const newsLate=typeof newsAge==='number'&&newsAge>2700;
 if(newsLate) issues.push({title:'新闻同步超过 45 分钟未更新',cls:'bad',detail:`最近完成 ${when(news.finished)}；每 15 分钟计划同步一次。`,action:'核对 inresearch-news.timer 与最近同步错误。',href:'#ops-health'});
 if(errors.length>5) issues.push({title:`另有 ${errors.length-5} 类阻塞`,detail:'上方优先展示执行异常，再按受影响文档数展示前 5 类；完整错误码可在队列样本和 Spark 台账查看。',action:'查看阻塞任务与错误码。',href:'#ops-queues'});
 if(Array.isArray(r.last_scan?.errors)&&r.last_scan.errors.length) issues.push({title:`资料扫描有 ${r.last_scan.errors.length} 项异常`,cls:'bad',detail:JSON.stringify(r.last_scan.errors.slice(0,3)),action:'核对 Spark 原件扫描路径与服务日志。',href:'#ops-health'});
 const severe=issues.some(i=>i.cls==='bad');
 const banner=$('ops-banner'); banner.className='ops-banner '+(severe?'bad':issues.length?'':'good');
 banner.innerHTML=`<strong>${severe?'有需要处理的问题':issues.length?'有待关注事项':'已连接，当前检查范围内未发现异常'}</strong><p>${fresh?'Spark 快照在 15 分钟有效期内。':'Spark 状态暂不能视为实时。'} ${issues.length?'先看下方“需要你注意”，再查看阶段和具体任务。':'健康状态与任务进展见下方。'} 页面每 30 秒刷新；Spark 通常每 5 分钟发布。</p>`;
 const alertCard=i=>`<article class="ops-alert">${tag(i.cls==='bad'?'需处理':i.cls==='neutral'?'按策略暂存':'待关注',i.cls||'')}<h3>${esc(i.title)}</h3><p>${esc(i.detail)}</p><p>${esc(i.action)}</p><a href="${i.href}"${i.code?` data-error-filter="${esc(i.code)}"`:''}>查看位置 →</a></article>`;
 $('ops-attention').innerHTML=issues.length?issues.slice(0,3).map(alertCard).join('')+(issues.length>3?`<details class="ops-more"><summary>展开另外 ${issues.length-3} 项关注事项</summary>${issues.slice(3).map(alertCard).join('')}</details>`:''):empty('当前检查范围内没有待处理告警。');
 $('ops-health').innerHTML=healthRow('Spark 阅读快照',fresh?'已连接 · '+(states[r.status]||r.status):'未确认 / 已延迟',`生成 ${when(r.generated)} · 收到 ${when(r.received_at)} · 延迟 ${duration(r.snapshot_age_seconds)}`,fresh?(r.status==='degraded'?'':'good'):'bad')+
 healthRow('inews 最近同步',news?(newsLate?'同步延迟':news.status==='success'?'最近一轮成功':news.status):'未收到',news?`${when(news.finished)} · 本轮 ${n(news.count)} 条 · 台账 ${n(source.items)} 条${news.error_code?' · '+news.error_code:''}`:'采集状态与阅读健康分别计量。',news?.status==='success'&&!newsLate?'good':news?'bad':'neutral')+
 healthRow('本机手动数据校验',latestTask('validate').finished?(states[latestTask('validate').outcome]||'未知'):'尚无执行记录',`上次执行 ${when(latestTask('validate').finished)}；不是持续健康探针。`,latestTask('validate').outcome==='succeeded'?'good':'neutral')+
 healthRow('队列调度',r.thermal?.paused_since?'正在降温暂停':r.claim_floor?`优先级 ≥ ${r.claim_floor.min_priority}`:'未收到调度信息',r.claim_floor?`低于下限暂留 ${n(r.claim_floor.held_documents)} 份；温度 ${n(r.thermal?.last_c)} °C`:'调度策略未知，不推定 pending 是代码错误。',r.thermal?.paused_since?'':'neutral')+
 healthRow('Spark 代码版本',r.release?r.release.slice(0,12):'未收到','网站仅展示发布端报告的版本；快照新鲜不证明所有依赖服务健康。','neutral');
 const scope=r.execution_scope;
 $('ops-batch').innerHTML=scope?`<div class="ops-panel"><b>当前点名批次 · ${n(scope.documents)} 份文档</b><div class="ops-batch">${Object.entries(scope.counts||{}).map(([s,c])=>`<span>${esc(states[s]||s)} <b>${n(c)}</b></span>`).join('')}</div><p class="ops-note">已读分块 ${n(scope.chunks_read)} / ${n(scope.chunks_total)}；尚待提取 ${n(scope.awaiting_extraction)} 份。范围外材料仍在总台账中。</p>${scope.model_wait?`<p>模型等待：${esc(scope.model_wait.reason)}；到 ${when(scope.model_wait.until)}</p>`:''}</div>`:'';
 if(hasOps) {
  const rows=Object.keys(labels).map(stage=>{
   const s={}; for(const row of o.stages) if(row.stage===stage) s[row.state]=(s[row.state]||0)+row.count;
   const total=Object.values(s).reduce((a,b)=>a+b,0), done=s.succeeded||0;
   const win=key=>(o.windows?.[key]||[]).filter(x=>x.stage===stage&&x.state==='succeeded').reduce((a,b)=>a+b.count,0);
   return `<tr><td>${labels[stage]}<div class="ops-bar"><span style="width:${total?done/total*100:0}%"></span></div></td><td>${n(done)} / ${n(total)}</td><td><a href="#ops-queues" data-stage="${stage}" data-state="pending">${n(s.pending||0)}</a></td><td><a href="#ops-queues" data-stage="${stage}" data-state="running">${n(s.running||0)}</a></td><td><a href="#ops-queues" data-stage="${stage}" data-state="blocked">${n((s.blocked||0)+(s.failed||0))}</a></td><td>${n(win('1h'))} / ${n(win('24h'))}</td></tr>`;
  });
  $('stage-body').innerHTML=rows.join('');
  const first=o.queues.pending?.items?.[0];
  $('stage-note').textContent=`计量单位：任务 / 分块，采用每份文档当前执行版本；完整阅读文档数见首屏。近 1h / 24h 为时间窗内所有版本的成功任务。最早排队 ${first?when(first.created):'无记录'}。`;
 } else {
  $('stage-body').innerHTML='<tr><td colspan="6">尚未收到当前执行版本的阶段统计。旧快照中的历史任务总数不作为当前进度。</td></tr>';
  $('stage-note').textContent='等待 Spark 发布端补充诊断；不会将历史成功分块当成完整阅读文档。';
 }
 const errorSelect=$('queue-error'), selectedError=errorSelect.value;
 errorSelect.innerHTML='<option value="">全部原因</option>'+errors.map(e=>`<option value="${esc(e.code)}">${esc(e.title)} · ${esc(e.code)} · ${n(e.documents)} 份</option>`).join('');
 errorSelect.value=selectedError;
 $('ops-updated').textContent=`本页检查 ${when(data.generated)} · 北京时间（UTC+8）`;
 renderQueue(); renderQuality(); renderTasks(); renderHistory();
 $('ops-attention').querySelectorAll('[data-error-filter]').forEach(a=>a.onclick=()=>{tab='blocked';$('queue-search').value=a.dataset.errorFilter;$('queue-error').value=a.dataset.errorFilter;renderQueue();});
 $('stage-body').querySelectorAll('[data-stage]').forEach(a=>a.onclick=()=>{tab=a.dataset.state;$('queue-stage').value=a.dataset.stage;$('queue-search').value='';renderQueue();});
}
function renderQueue() {
 const q=data?.reader?.operations?.queues?.[tab];
 const buttons=$('queue-tabs');
 buttons.innerHTML=['pending','running','blocked'].map(s=>`<button role="tab" aria-selected="${s===tab}" data-tab="${s}">${states[s]} ${n(data?.reader?.operations?.queues?.[s]?.total)}</button>`).join('');
 buttons.querySelectorAll('button').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;renderQueue();});
 if(!q || !Array.isArray(q.items)) { $('queue-body').innerHTML='<tr><td colspan="6">未收到文件明细；请等待发布端更新。</td></tr>';$('queue-note').textContent='未知与空队列分开显示。';return; }
 const stage=$('queue-stage').value, query=$('queue-search').value.toLocaleLowerCase();
 const examples=tab==='blocked'&&query?(data?.reader?.operations?.errors||[]).flatMap(e=>e.examples||[]):[];
 const all=[...new Map([...q.items,...examples].map(j=>[j.job_id,j])).values()];
 const rows=all.filter(j=>(!stage||j.stage===stage)&&(!query||[j.original_name,j.doc_id,j.revision_id,j.error_code].some(v=>String(v||'').toLocaleLowerCase().includes(query))));
 $('queue-note').textContent=`总计 ${n(q.total)} 个任务；快照提供最早的 ${n(q.items.length)} 个（上限 ${q.limit}）。筛选结果 ${n(rows.length)} 个${examples.length?'（加入每类错误最多 3 个定位样本）':''}；完整台账位于 Spark catalog/catalog.sqlite。`;
 $('queue-body').innerHTML=rows.length?rows.map(j=>{
  const since=j.state==='running'?j.started:tab==='blocked'?j.finished:j.created;
  const elapsed=since?Math.max(0,(Date.parse(data.reader.operations.generated)-Date.parse(since))/1000):null;
  return `<tr><td class="file"><b>${esc(j.original_name)}</b><details><summary>任务定位与代码位置</summary><dl><dt>文档</dt><dd><code>${esc(j.doc_id)}</code></dd><dt>版本</dt><dd><code>${esc(j.revision_id)}</code></dd><dt>任务</dt><dd><code>${esc(j.job_id)}</code> · chunk ${esc(j.chunk)}</dd><dt>代码入口</dt><dd><code>${esc(j.code_path)}</code>（阶段处理入口，需日志确认具体报错行）</dd><dt>日志</dt><dd><code>journalctl --user -u inresearch-reader.service --since '${esc(since ? since.slice(0,19).replace('T',' ')+' UTC' : 'today')}'</code> · 按上述文档 / revision 检索</dd><dt>创建</dt><dd>${when(j.created)}</dd><dt>可领取</dt><dd>${when(j.available)}</dd><dt>尝试</dt><dd>${n(j.attempts)} 次 · 页数 ${n(j.pages_total)} · 已读块 ${n(j.chunks_read)}/${n(j.chunks_total)}</dd></dl></details></td><td>${esc(labels[j.stage]||j.stage)}</td><td>${tag(states[j.state]||j.state,tab==='blocked'?'bad':'neutral')}<br><code>${esc(j.error_code||'')}</code></td><td>${esc(duration(elapsed))}<br><small>${when(since)}</small></td><td>${n(j.priority)}</td><td>${j.state==='pending'?'等待领取；可领取时间和优先级见定位':j.state==='running'?'正在执行；耗时本身不证明卡死':'按错误分类核对后选择性处理'}</td></tr>`;
 }).join(''):'<tr><td colspan="6">'+(q.total?'当前快照样本中没有匹配项；这不表示全库不存在该任务。':'此队列没有任务。')+'</td></tr>';
}
function renderQuality() {
 const q=data.quality, t=data.targets;
 $('target-progress').innerHTML=t?`<p>目标行 ${n(t.total)} · 已交付 ${n(t.states.delivered||0)} · 有来源 ${n(t.states.sourced||0)} · 假设 ${n(t.states.assumed||0)} · 仍缺 ${n(t.states.needed||0)}</p><p class="ops-note">已交付表示载体收到资料；正式采用与阅读完成分别核验。</p><div class="tablewrap"><table><thead><tr><th>队伍</th><th>已交付</th><th>有来源</th><th>仍缺</th></tr></thead><tbody>${t.teams.map(x=>`<tr><td>${esc(x.team)}</td><td>${n(x.delivered||0)}</td><td>${n(x.sourced||0)}</td><td>${n(x.needed||0)}</td></tr>`).join('')}</tbody></table></div><p class="ops-note"><a href="/supply.html#targets">进入目标表与派工 →</a></p>`:empty('目标行台账不可用。');
 if(!q) { $('quality-detail').innerHTML=empty('事实与核验台账未读到。');return; }
 const facts=q.facts.items||[], verify=q.verification.items||[];
 $('quality-detail').innerHTML=`<details${facts.length?' open':''}><summary>事实证据：${n(q.facts.errors)} 项问题</summary><p class="ops-note">共 ${n(q.facts.records)} 条；以下最多 ${q.facts.limit} 项。代码入口：knowledge/fact_contract.py。</p><div class="tablewrap"><table><thead><tr><th>记录 ID</th><th>具体问题</th></tr></thead><tbody>${facts.map(f=>`<tr><td><code>${esc(f.id)}</code></td><td>${esc(f.reason)}</td></tr>`).join('')||'<tr><td colspan="2">当前事实检查通过。</td></tr>'}</tbody></table></div></details><details style="margin-top:16px"><summary>核验待办：P1 ${n(q.verification.counts['1']||0)} · P2 ${n(q.verification.counts['2']||0)}</summary><div class="tablewrap"><table><thead><tr><th>优先级 / 记录</th><th>原因</th><th>下一步</th></tr></thead><tbody>${verify.map(v=>`<tr><td>P${v.p} · ${esc(v.table)}<br><code>${esc(v.id)}</code></td><td>${esc(v.reason)}</td><td>${esc(v.action)}${(v.urls||[]).filter(u=>/^https?:\/\//i.test(u)).map(u=>`<br><a href="${esc(u)}" target="_blank" rel="noopener">核对来源 ↗</a>`).join('')}</td></tr>`).join('')||'<tr><td colspan="3">没有待核验记录。</td></tr>'}</tbody></table></div></details>`;
}
function renderTasks() {
 $('tasks').innerHTML=['查看状态','检查与清单','执行操作'].map(group=>`<div class="ops-task-group"><h3>${group}</h3><div class="tasks">${tasks.filter(t=>t[3]===group).map(([id,title,desc])=>{
  const s=latestTask(id), running=s.running||busy.has(id);
  return `<button class="task-btn" data-task="${id}"${running?' disabled':''}><b>${esc(title)}</b><span>${esc(desc)}</span><span class="task-state">${running?'执行中…':s.finished?`${esc(states[s.outcome]||'未知')} · ${when(s.finished)}${s.legacy?' · 旧记录未保存结果':''}`:'尚未执行'}</span></button>`;
 }).join('')}</div></div>`).join('');
 $('tasks').querySelectorAll('button').forEach(b=>b.onclick=()=>runTask(b.dataset.task));
}
function renderHistory() {
 const h=data.history;
 $('history-note').textContent=`仅记录管理页手动执行；显示最近 ${h?.items?.length||0} 次（上限 50），共 ${n(h?.total)} 次留存。Spark 持续执行的失败看上方队列；旧日志没有结果元数据，不能推定成功。`;
 $('history-body').innerHTML=h?.items?.length?h.items.map(r=>`<tr><td>${esc(r.name)}</td><td>${tag(states[r.outcome]||r.outcome,r.outcome==='succeeded'?'good':'bad')}</td><td>${when(r.started)}</td><td>${esc(duration(r.duration_seconds))}</td><td>${esc(r.returncode??'—')}</td><td><a href="/api/ops/log?id=${esc(r.id)}">完整日志 ↓</a></td></tr>`).join(''):'<tr><td colspan="6">新版执行历史从首次操作开始留存。</td></tr>';
}
async function refresh() {
 if(loading) return;
 loading=true;$('ops-refresh').disabled=true;
 const controller=new AbortController();
 const timeout=setTimeout(()=>controller.abort(),20000);
 try {
  const response=await fetch('/api/ops',{cache:'no-store',signal:controller.signal,priority:'high'});
  if(!response.ok) throw Error(response.status===403?'运行诊断仅管理员可见':response.status===401?'登录已失效，请重新登录':'HTTP '+response.status);
  data=await response.json();render();loaded=true;
  $('ops-error').textContent='';
 } catch(e) {
  const reason=controller.signal.aborted?'读取超时（20 秒）':e.message;
  $('ops-error').textContent='更新失败：'+reason+'。'+(loaded?'保留上次画面，当前状态未确认。':'尚未读到管理数据。');
  if(!loaded) {
   $('ops-updated').textContent='本页检查 '+when(new Date().toISOString())+' · 北京时间（UTC+8）';
   $('ops-kpis').innerHTML=kpi(null,'完整阅读完成 · 文档','未读到状态')+kpi(null,'当前排队 · 任务','未读到状态')+kpi(null,'执行受阻 · 文档','未读到状态')+kpi(null,'事实证据问题 · 项','未读到状态');
   for(const id of ['ops-attention','ops-health','target-progress','quality-detail']) $(id).innerHTML=empty('暂未读到管理数据。请点击“刷新状态”重试。');
   for(const id of ['stage-body','queue-body','history-body']) $(id).innerHTML='<tr><td colspan="6">状态未知。读取失败，请刷新重试。</td></tr>';
   $('stage-note').textContent='未读到当前阶段统计，不推定任务为零。';
   $('queue-note').textContent='未读到队列明细，不推定没有排队或阻塞任务。';
  }
  $('ops-banner').className='ops-banner bad';$('ops-banner').innerHTML='<strong>当前状态未确认</strong><p>数据请求失败，请重试。保留的旧数字不能证明系统仍然正常。</p>';
 } finally { clearTimeout(timeout);loading=false;$('ops-refresh').disabled=false;
  // A cold font download must not consume the connection before the first status.
  const fonts=$('ops-fonts');if(fonts)fonts.media='all'; }
}
async function runTask(id) {
 if(busy.has(id)) return;
 busy.add(id);renderTasks();
 const div=document.createElement('article');div.className='ops-run';
 const heading=document.createElement('b');heading.textContent=tasks.find(t=>t[0]===id)?.[1]+' · 执行中…';div.append(heading);$('run-results').prepend(div);
 try {
  const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:id})});
  const result=await response.json();heading.textContent=(result.name||tasks.find(t=>t[0]===id)?.[1])+' · '+(result.ok?'执行成功':'需检查');
  const p=document.createElement('p');p.textContent=result.ok?'本次程序执行成功。任务清单里的待办与整体健康仍以上方 dashboard 为准。':'查看错误摘要与完整日志；程序未通过不一定代表常驻服务停止。';div.append(p);
  if(result.log_url) {const a=document.createElement('a');a.href=result.log_url;a.textContent='下载完整日志';div.append(a);}
  const details=document.createElement('details');details.open=!result.ok;const summary=document.createElement('summary');summary.textContent='查看本次输出'+(result.truncated?'（中段折叠）':'');details.append(summary);
  const pre=document.createElement('pre');pre.textContent=result.output||result.error||'无输出';details.append(pre);div.append(details);
 } catch(e) {heading.textContent='请求中断 · '+e.message+'；请核对执行记录，避免重复操作。';}
 finally {busy.delete(id);await refresh();renderTasks();}
}
window.clog = text => {const p=document.createElement('p');p.textContent=text;$('run-results').prepend(p);};
$('ops-refresh').onclick=refresh;
$('queue-stage').onchange=renderQueue;
$('queue-search').oninput=renderQueue;
$('queue-error').onchange=()=>{if($('queue-error').value)tab='blocked';$('queue-search').value=$('queue-error').value;renderQueue();};
renderTasks();
refresh();
setInterval(()=>{if(!document.hidden)refresh();},30000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
