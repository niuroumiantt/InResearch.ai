/* Anonymous submission and receipt holder view. Owner decisions live in task-reviews.js. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const key = 'inresearch-task-upload-receipts-v1';
  const labels = {pending_approval:'待负责人确认',queued:'待负责人确认',approved:'已确认，待研究端接收',archived:'研究端已接收',rejected:'已退回'};
  const results = {revision_required:'需要修改',sampled_incomplete:'抽样反馈 · 全表待审',accepted:'本次验收通过',blocked:'暂时受阻',ineligible:'不符合任务范围'};
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) + '（北京时间）' : '时间未记录';
  const receipts = () => { try { const rows = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(rows) ? rows.slice(0,100) : []; } catch { return []; } };
  const save = rows => localStorage.setItem(key, JSON.stringify(rows.slice(0,100)));
  let knownItems = [];
  let selectedPackageId = window.activeResearchPackageId || '';
  window.addEventListener('research-package-selected',event=>{
    selectedPackageId = event.detail?.packageId || '';
    if ([...$('upload-package').options].some(option=>option.value === selectedPackageId))
      $('upload-package').value = selectedPackageId;
  });
  const feedback = item => `<details class="upload-feedback"><summary>分析验收反馈 · ${(item.feedback || []).length} 条</summary>${(item.feedback || []).length ? item.feedback.map(row => `<article><small>${esc(time(row.at))} · ${esc(results[row.result] || row.result)}</small><p>${esc(row.text)}</p></article>`).join('') : '<p>尚未登记分析验收反馈。</p>'}</details>`;
  const progress = item => item.analysis_progress ? `<p class="small">自动分析：${esc(item.analysis_progress.state === 'source_error' ? '原件需修正，请查看反馈并重新提交' : item.analysis_progress.state === 'sampled_incomplete' ? '仅抽样反馈，全表待审' : item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端会重试' : item.analysis_progress.state === 'completed' ? '已完成' : '进行中')} · ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(time(item.analysis_progress.at))}</p>` : '';
  const scope = item => item.analysis_scope?.mode === 'sampled_native_cells' ? `<p class="upload-sampled" role="status">仅 ${esc(item.analysis_scope.excerpted_cells)}/${esc(item.analysis_scope.total_nonblank_cells)} 个非空单元格片段交给模型，${esc(item.analysis_scope.not_fully_seen_cells)} 个未完整审阅；本次 0 条上线不代表全表无合格条目。请展开下方反馈查看下一步。</p>` : '';
  function ownCard(item) {
    const decision = item.decision;
    return `<article class="upload-card"><div class="upload-card-head"><strong>${esc(item.name)}</strong><span class="upload-status">${esc(labels[item.status] || item.status)}</span></div><p class="small muted">上传于 ${esc(time(item.created))}</p>${decision ? `<p class="small">${esc(decision.action === 'reject' ? '退回' : '已确认')}：${esc(time(decision.at))}${decision.note ? ` · ${esc(decision.note)}` : ''}</p>` : ''}${progress(item)}${scope(item)}${feedback(item)}<details class="upload-file-meta"><summary>文件编号与校验信息</summary><p class="small muted">文件编号 ${esc(item.id)}<br>SHA256 ${esc(item.sha256)}</p></details></article>`;
  }
  async function readReceipt(row) {
    const response = await fetch('/api/task-uploads/receipt', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(row),cache:'no-store'});
    if (!response.ok) throw Error('回执无效或状态暂不可用');
    return (await response.json()).item;
  }
  async function refreshOwn() {
    const rows = receipts();
    if (!rows.length) { knownItems = []; $('upload-own-list').innerHTML = '<p class="small muted">当前浏览器还没有提交回执。</p>'; return; }
    const results = await Promise.all(rows.map(row => readReceipt(row).then(item => ({item})).catch(error => ({error}))));
    knownItems = results.map(row => row.item).filter(Boolean);
    const groups = new Map();
    results.forEach(({item,error}, i) => {
      if (!item) { groups.set(`error:${i}`, {name:'无法读取的回执',items:[`<p class="small muted">${esc(rows[i].id)}：${esc(error.message)}</p>`]}); return; }
      const name = item.submitter?.trim() || '旧提交（未留姓名）';
      if (!groups.has(name)) groups.set(name,{name,items:[]});
      groups.get(name).items.push(item);
    });
    $('upload-own-list').innerHTML = [...groups.values()].map(group => {
      const items = group.items.sort((a,b) => (b.created || 0) - (a.created || 0));
      return `<section class="upload-person-group"><h4>${esc(group.name)}</h4>${items.map(item => typeof item === 'string' ? item : `<p class="small muted upload-project-name">${esc(item.project_name || '旧提交 · 未填写项目')}</p>${ownCard(item)}`).join('')}</section>`;
    }).join('');
  }
  async function loadPackages() {
    try {
      const response = await fetch('/api/research-tasks', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      $('upload-package').insertAdjacentHTML('beforeend', data.packages.map(p => `<option value="${esc(p.id)}">${esc(p.title)} · ${esc(p.region)}</option>`).join(''));
      selectedPackageId = window.activeResearchPackageId || selectedPackageId;
      if (data.packages.some(p=>p.id === selectedPackageId)) $('upload-package').value = selectedPackageId;
    } catch { $('upload-message').textContent = '工作包暂不可用，请刷新页面后再提交。'; }
  }
  $('upload-package').addEventListener('change',event=>{
    if (event.target.value) window.dispatchEvent(new CustomEvent('research-package-requested',
      {detail:{packageId:event.target.value}}));
  });
  $('task-upload-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget, files = [...form.elements.file.files];
    if (!files.length) return;
    const submitter = form.elements.submitter.value.trim(), projectName = form.elements.project_name.value.trim();
    if (!submitter || !projectName) { $('upload-message').textContent = '请填写提交人姓名和本次材料主题。'; return; }
    if (!form.elements.package_id.value) { $('upload-message').textContent = '请先选择所属工作包。'; return; }
    if (files.length > 20) { $('upload-message').textContent = '一次最多提交 20 份附件。'; return; }
    if (files.some(file => file.size < 1 || file.size > 64 * 1024 * 1024)) { $('upload-message').textContent = '每份附件须为 1 字节至 64 MiB。'; return; }
    const batchId = crypto.randomUUID(), common = {submitter,project_name:projectName,batch_id:batchId,package_id:form.elements.package_id.value,source:form.elements.source.value.trim(),note:form.elements.upload_note.value.trim()};
    const prior = knownItems.filter(item => item.package_id === common.package_id && item.submitter?.trim() === submitter && item.project_name?.trim() === projectName).sort((a,b)=>(b.created||0)-(a.created||0))[0];
    const continuation = prior ? receipts().find(row => row.id === prior.id) : null;
    $('upload-submit').disabled = true;
    const saved = [], failed = [];
    try {
      for (const [index,file] of files.entries()) {
        $('upload-message').textContent = `正在上传第 ${index+1}/${files.length} 份：${file.name}`;
        try {
          const metadata = {...common,name:file.name,...(continuation ? {continuation_id:continuation.id,continuation_receipt:continuation.receipt} : {})};
          const response = await fetch('/api/task-uploads', {method:'POST',headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify(metadata))},body:file});
          if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(response.status === 403 ? '网站安全防护拦截' : `服务返回 HTTP ${response.status}`);
          const result = await response.json();
          if (!response.ok) throw Error(result.error || `HTTP ${response.status}`);
          const receipt = {id:result.item.id,receipt:result.receipt};
          save([receipt,...receipts().filter(row => row.id !== receipt.id)]);
          saved.push({name:file.name,...receipt});
        } catch (error) { failed.push(`${file.name}：${error.message}`); }
      }
      $('upload-message').innerHTML = `${saved.length} 份附件已收到，等待负责人确认。${saved.map(row => `<br>${esc(row.name)} · 编号 <code>${esc(row.id)}</code> · 回执码 <code class="upload-receipt-code">${esc(row.receipt)}</code>`).join('')}${failed.length ? `<br>${esc(failed.length+' 份未确认收到，请只重选这些文件提交：'+failed.join('；'))}` : ''}`;
      form.elements.file.value = '';
      if (saved.length) $('my-submissions').open = true;
      await refreshOwn(); await refreshOwnerShortcut();
    } catch (error) { $('upload-message').textContent = error.message; }
    finally { $('upload-submit').disabled = false; }
  });
  $('upload-receipt-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget, row = {id:form.elements.id.value.trim(),receipt:form.elements.receipt.value.trim()};
    try {
      await readReceipt(row);
      save([row,...receipts().filter(item => item.id !== row.id)]);
      form.reset(); $('receipt-message').textContent = '回执已加入当前浏览器。'; await refreshOwn();
    } catch (error) { $('receipt-message').textContent = error.message; }
  });
  async function refreshOwnerShortcut() {
    try {
      const response = await fetch('/api/materials', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      if (!data.can_approve) return;
      $('upload-owner-shortcut').hidden = false;
      const pending = data.items.filter(item => ['pending_approval','queued'].includes(item.status) || item.status === 'archived' && /\.(xlsx|txt|md|csv|tsv|json|html?|pdf|docx)$/i.test(item.name) && !item.analysis_requested_at).length;
      $('upload-owner-shortcut-count').textContent = pending ? `${pending} 份文件待确认。审批与上线报告已移到独立工作台。` : '审批与上线报告已移到独立工作台。';
    } catch { /* Anonymous uploading remains usable when the owner inbox is unavailable. */ }
  }
  $('upload-refresh').addEventListener('click',refreshOwn);
  loadPackages(); refreshOwn(); refreshOwnerShortcut();
})();
