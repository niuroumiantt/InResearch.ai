/* Anonymous submission and receipt holder view. Owner decisions live in task-reviews.js. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const key = 'inresearch-task-upload-receipts-v1';
  const pendingBatchKey = 'inresearch-task-upload-pending-batches-v1';
  const labels = {pending_approval:'待负责人确认',queued:'待负责人确认',approved:'已确认，待研究端接收',archived:'研究端已接收',rejected:'已退回'};
  const results = {revision_required:'需要修改',sampled_incomplete:'抽样反馈 · 全表待审',accepted:'本次验收通过',blocked:'暂时受阻',ineligible:'不符合任务范围'};
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) + '（北京时间）' : '时间未记录';
  const shortTime = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '时间未记录';
  const size = value => value >= 1048576 ? `${(value / 1048576).toFixed(1)} MiB` : `${Math.ceil(value / 1024)} KiB`;
  const receipts = () => { try { const rows = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(rows) ? rows.slice(0,100) : []; } catch { return []; } };
  const save = rows => localStorage.setItem(key, JSON.stringify(rows.slice(0,100)));
  let knownItems = [];
  let pendingFiles = [], uploading = false, sealing = null, batchResults = new Map();
  const pendingBatches = () => { try { const rows = JSON.parse(localStorage.getItem(pendingBatchKey) || '[]'); return Array.isArray(rows) ? rows : []; } catch { return []; } };
  const savePendingBatches = rows => localStorage.setItem(pendingBatchKey, JSON.stringify(rows));
  function rememberBatch(batchId, rows) {
    const existing = pendingBatches().find(row=>row.batch_id === batchId) || {};
    savePendingBatches([...pendingBatches().filter(row=>row.batch_id !== batchId),{...existing,batch_id:batchId,items:rows.map(row=>({id:row.id,receipt:row.receipt,name:row.name,batch_index:row.batch_index}))}]);
  }
  async function finishBatches({recoverIncomplete = false} = {}) {
    if (sealing) return sealing;
    sealing = (async()=>{
      const failures = []; let unfinished = 0;
      for (const row of pendingBatches()) {
        if (row.upload_complete === false && !recoverIncomplete) { unfinished++; continue; }
        try {
          let members = row.items;
          if (row.batch_token) {
            const response = await fetch('/api/task-uploads/batch-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch_id:row.batch_id,batch_token:row.batch_token})});
            if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(`批次状态服务返回 HTTP ${response.status}`);
            const result = await response.json();
            if (!response.ok || !Array.isArray(result.items)) throw Error(result.error || '批次状态未确认');
            members = result.items;
            rememberBatch(row.batch_id,members);
            batchResults.set(row.batch_id,members);
            members.forEach(item=>save([{id:item.id,receipt:item.receipt},...receipts().filter(saved=>saved.id !== item.id)]));
            const receivedIds = new Set(members.map(item=>row.queue_ids?.[item.batch_index]).filter(Boolean));
            pendingFiles = pendingFiles.filter(item=>!receivedIds.has(item.id)); renderPendingFiles();
            if (!members.length) { savePendingBatches(pendingBatches().filter(saved=>saved.batch_id !== row.batch_id)); continue; }
          }
          const payload = {batch_id:row.batch_id,items:members.map(item=>({id:item.id,receipt:item.receipt}))};
          const response = await fetch('/api/task-uploads/batch',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'task-upload'},body:JSON.stringify(payload)});
          if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(`服务返回 HTTP ${response.status}`);
          const result = await response.json();
          if (!response.ok || !result.batch?.sealed) throw Error(result.error || '批次提交未完成');
          savePendingBatches(pendingBatches().filter(saved=>saved.batch_id !== row.batch_id));
        } catch (error) { failures.push(error.message); }
      }
      $('upload-batch-status').innerHTML = `${failures.length ? `${failures.length} 批提交状态待恢复：${esc(failures.join('；'))}。<button type="button" id="upload-retry-batches">恢复并完成批次提交</button>` : ''}${unfinished ? `${unfinished} 批仍在上传或曾被中断，请等待上传结束；如已中断，可恢复已收到的附件。<button type="button" id="upload-recover-incomplete">恢复已收附件并完成批次</button>` : ''}`;
      const summary = $('upload-message').querySelector('[data-upload-result]');
      if (!failures.length && !unfinished && summary && Number(summary.dataset.uploadResult)>0) summary.textContent = `${summary.dataset.uploadResult} 份附件已收到，等待负责人按批次确认。`;
      return !failures.length && !unfinished;
    })();
    try { return await sealing; } finally { sealing = null; }
  }
  $('upload-batch-status').addEventListener('click',async event=>{
    const button = event.target.closest('#upload-retry-batches, #upload-recover-incomplete'); if (!button) return;
    if (uploading) return;
    button.disabled = true; await finishBatches({recoverIncomplete:button.id === 'upload-recover-incomplete'}); await refreshOwn();
  });
  let selectedPackageId = window.activeResearchPackageId || '';
  window.addEventListener('research-package-selected',event=>{
    selectedPackageId = event.detail?.packageId || '';
    if ([...$('upload-package').options].some(option=>option.value === selectedPackageId))
      $('upload-package').value = selectedPackageId;
  });
  const feedback = item => `<details class="upload-feedback"><summary>分析验收反馈 · ${(item.feedback || []).length} 条</summary>${(item.feedback || []).length ? item.feedback.map(row => `<article><small>${esc(time(row.at))} · ${esc(results[row.result] || row.result)}</small><p>${esc(row.text)}</p></article>`).join('') : '<p>尚未登记分析验收反馈。</p>'}</details>`;
  const requiresOperator = item => item.analysis_progress?.error_code === 'joint_model_output_invalid_requires_operator';
  const progress = item => item.analysis_progress ? `<p class="small">自动分析：${esc(requiresOperator(item) ? '定位校验受阻，需人工复核' : item.analysis_progress.state === 'source_error' ? '原件需修正，请查看反馈并重新提交' : item.analysis_progress.state === 'sampled_incomplete' ? '仅抽样反馈，全表待审' : item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端会重试' : item.analysis_progress.state === 'completed' ? '已完成' : '进行中')} · ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(time(item.analysis_progress.at))}</p>` : '';
  const scope = item => item.analysis_scope?.mode === 'sampled_native_cells' ? `<p class="upload-sampled" role="status">仅 ${esc(item.analysis_scope.excerpted_cells)}/${esc(item.analysis_scope.total_nonblank_cells)} 个非空单元格片段交给模型，${esc(item.analysis_scope.not_fully_seen_cells)} 个未完整审阅；本次 0 条上线不代表全表无合格条目。请展开下方反馈查看下一步。</p>` : '';
  const status = item => item.status === 'rejected' ? '已退回' : requiresOperator(item) ? '定位校验受阻，需人工复核' : item.analysis_scope?.mode === 'sampled_native_cells' ? '抽样反馈 · 全表待审' : item.analysis_progress?.state === 'source_error' ? '原件需修正' : item.analysis_progress?.state === 'blocked' ? '分析暂时受阻' : item.feedback?.length ? '已有反馈' : item.analysis_requested_at ? '分析中' : item.upload_batch && !item.upload_batch.sealed ? '待完成批次提交' : labels[item.status] || item.status;
  function ownCard(item) {
    const decision = item.decision;
    return `<details class="upload-card" data-submission-id="${esc(item.id)}"><summary><time title="${esc(time(item.created))}">${esc(shortTime(item.created))}</time><strong>${esc(item.name)}</strong><span class="upload-status">${esc(status(item))}</span></summary><div class="upload-card-body"><p><strong>${esc(item.name)}</strong></p><p class="small muted">材料主题：${esc(item.project_name || '旧提交 · 未填写项目')} · 上传于 ${esc(time(item.created))}</p>${item.upload_batch ? `<p class="small muted">同次提交：收到 ${esc(item.upload_batch.received)}/${esc(item.upload_batch.expected)} 份 · ${item.upload_batch.sealed ? '批次提交已完成' : '待完成批次提交'}</p>` : ''}${decision ? `<p class="small">${esc(decision.action === 'reject' ? '退回' : '已确认')}：${esc(time(decision.at))}${decision.note ? ` · ${esc(decision.note)}` : ''}</p>` : ''}${progress(item)}${scope(item)}${feedback(item)}${item.feedback?.length ? `<button type="button" class="feedback-download" data-download-feedback="${esc(item.id)}">下载反馈与下一步 .md ↓</button>` : ''}<details class="upload-file-meta"><summary>文件编号与校验信息</summary><p class="small muted">文件编号 ${esc(item.id)}<br>SHA256 ${esc(item.sha256)}</p></details></div></details>`;
  }
  async function readReceipt(row) {
    const response = await fetch('/api/task-uploads/receipt', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(row),cache:'no-store'});
    if (!response.ok) throw Error('回执无效或状态暂不可用');
    return (await response.json()).item;
  }
  $('upload-own-list').addEventListener('click', event => {
    const button = event.target.closest('[data-download-feedback]');
    const item = button && knownItems.find(row => row.id === button.dataset.downloadFeedback);
    if (!item?.feedback?.length) return;
    const text = [`# ${item.project_name || '材料'} · 反馈与下一步`, '', `原件：${item.name}`, `提交人：${item.submitter || '未留姓名'}（自填）`, `提交时间：${time(item.created)}`, '', ...item.feedback.map(row => [`## ${time(row.at)} · ${results[row.result] || row.result}`, '', row.text, ''].join('\n')), '本文件保留回执中的原反馈。继续提交前，请对照该工作包的最新共同计划。', ''].join('\n');
    const url = URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url; link.download = `${item.id}-反馈与下一步.md`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
  });
  async function refreshOwn() {
    if (!uploading) await finishBatches();
    const expanded = new Set([...$('upload-own-list').querySelectorAll('.upload-card[open]')].map(row=>row.dataset.submissionId));
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
      return `<section class="upload-person-group"><h4>${esc(group.name)}</h4>${items.map(item => typeof item === 'string' ? item : ownCard(item)).join('')}</section>`;
    }).join('');
    $('upload-own-list').querySelectorAll('.upload-card').forEach(row=>{ row.open = expanded.has(row.dataset.submissionId); });
  }
  function renderPendingFiles() {
    $('upload-pending-count').textContent = pendingFiles.length ? `待提交 ${pendingFiles.length}/20 份附件` : '尚未添加附件';
    $('upload-clear-files').hidden = !pendingFiles.length;
    $('upload-clear-files').disabled = uploading;
    $('upload-pending-files').innerHTML = pendingFiles.map(row=>`<li><span>${esc(row.file.name)}</span><small>${esc(size(row.file.size))}</small><button type="button" data-remove-file="${esc(row.id)}" aria-label="移除 ${esc(row.file.name)}"${uploading ? ' disabled' : ''}>移除</button></li>`).join('');
  }
  function addFiles(files) {
    if (uploading || !files.length) return;
    if (pendingFiles.length + files.length > 20) { $('upload-message').textContent = `一次最多提交 20 份附件；已保留当前 ${pendingFiles.length} 份，请减少本次新增文件。`; return; }
    if (files.some(file=>file.size < 1 || file.size > 64 * 1024 * 1024)) { $('upload-message').textContent = '每份附件须为 1 字节至 64 MiB；本次选择未添加，请移除空文件或超限文件后重选。'; return; }
    pendingFiles.push(...files.map(file=>({id:crypto.randomUUID(),file})));
    $('upload-message').textContent = '';
    renderPendingFiles();
  }
  $('upload-pending-files').addEventListener('click',event=>{
    const button = event.target.closest('[data-remove-file]');
    if (!button || uploading) return;
    pendingFiles = pendingFiles.filter(row=>row.id !== button.dataset.removeFile); renderPendingFiles();
  });
  $('upload-clear-files').addEventListener('click',()=>{ if (!uploading) { pendingFiles = []; renderPendingFiles(); } });
  const dropZone = $('upload-drop-zone');
  ['dragenter','dragover'].forEach(name=>dropZone.addEventListener(name,event=>{event.preventDefault(); if (!uploading) {dropZone.classList.add('is-dragging'); event.dataTransfer.dropEffect = 'copy';}}));
  ['dragleave','drop'].forEach(name=>dropZone.addEventListener(name,event=>{event.preventDefault();dropZone.classList.remove('is-dragging');}));
  dropZone.addEventListener('drop',event=>addFiles([...event.dataTransfer.files]));
  function loadPackages(data) {
    if (!Array.isArray(data?.packages)) return;
    const select = $('upload-package'), before = select.value;
    select.innerHTML = '<option value="">选择工作包</option>' + data.packages.map(p => `<option value="${esc(p.id)}">${esc(p.title)} · ${esc(p.region)}</option>`).join('');
    selectedPackageId = window.activeResearchPackageId || selectedPackageId || before;
    if (data.packages.some(p=>p.id === selectedPackageId)) select.value = selectedPackageId;
  }
  window.addEventListener('research-tasks-loaded',event=>loadPackages(event.detail));
  if (window.researchTasksState) loadPackages(window.researchTasksState);
  $('upload-package').addEventListener('change',event=>{
    if (event.target.value) window.dispatchEvent(new CustomEvent('research-package-requested',
      {detail:{packageId:event.target.value}}));
  });
  $('task-upload-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (uploading) return;
    uploading = true; $('upload-submit').disabled = true; form.elements.file.disabled = true; renderPendingFiles();
    const saved = [], failed = [];
    try {
    if (!await finishBatches()) { $('upload-message').textContent = '请先恢复上一批提交状态；已收到的附件会找回回执，无需重复上传。'; return; }
    const entries = [...pendingFiles], files = entries.map(row=>row.file);
    if (!files.length) { $('upload-message').textContent = '请先添加至少一份附件。'; return; }
    const submitter = form.elements.submitter.value.trim(), projectName = form.elements.project_name.value.trim();
    if (!submitter || !projectName) { $('upload-message').textContent = '请填写提交人姓名和本次材料主题。'; return; }
    if (!form.elements.package_id.value) { $('upload-message').textContent = '请先选择所属工作包。'; return; }
    if (files.length > 20) { $('upload-message').textContent = '一次最多提交 20 份附件。'; return; }
    if (files.some(file => file.size < 1 || file.size > 64 * 1024 * 1024)) { $('upload-message').textContent = '每份附件须为 1 字节至 64 MiB。'; return; }
    const batchId = crypto.randomUUID(), batchToken = crypto.randomUUID(), common = {submitter,project_name:projectName,batch_id:batchId,batch_token:batchToken,package_id:form.elements.package_id.value};
    const prior = knownItems.filter(item => item.package_id === common.package_id && item.submitter?.trim() === submitter && item.project_name?.trim() === projectName).sort((a,b)=>(b.created||0)-(a.created||0))[0];
    const continuation = prior ? receipts().find(row => row.id === prior.id) : null;
      savePendingBatches([...pendingBatches(),{batch_id:batchId,batch_token:batchToken,items:[],queue_ids:entries.map(row=>row.id),upload_complete:false}]);
      for (const [index,file] of files.entries()) {
        $('upload-message').textContent = `正在上传第 ${index+1}/${files.length} 份：${file.name}`;
        try {
          const metadata = {...common,name:file.name,batch_total:files.length,batch_index:index,...(continuation ? {continuation_id:continuation.id,continuation_receipt:continuation.receipt} : {})};
          const response = await fetch('/api/task-uploads', {method:'POST',headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify(metadata))},body:file});
          if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(response.status === 403 ? '网站安全防护拦截' : `服务返回 HTTP ${response.status}`);
          const result = await response.json();
          if (!response.ok) throw Error(result.error || `HTTP ${response.status}`);
          const receipt = {id:result.item.id,receipt:result.receipt};
          save([receipt,...receipts().filter(row => row.id !== receipt.id)]);
          saved.push({name:file.name,queueId:entries[index].id,batch_index:index,...receipt});
          rememberBatch(batchId,saved);
        } catch (error) { failed.push({index,text:`${file.name}：${error.message}`}); }
      }
      savePendingBatches(pendingBatches().map(row=>row.batch_id === batchId ? {...row,upload_complete:true} : row));
      const batchFinished = await finishBatches(), received = batchResults.get(batchId) || saved;
      const remaining = failed.filter(row=>!received.some(item=>item.batch_index === row.index));
      $('upload-message').innerHTML = `<span data-upload-result="${received.length}">${received.length} 份附件已收到${received.length ? batchFinished ? '，等待负责人按批次确认。' : '，批次提交尚未完成，请恢复提交状态。' : '。'}</span>${received.length ? `<details class="upload-saved-receipts"><summary>查看并保存 ${received.length} 份回执码</summary>${received.map(row => `<p>${esc(row.name)} · 编号 <code>${esc(row.id)}</code> · 回执码 <code class="upload-receipt-code">${esc(row.receipt)}</code></p>`).join('')}</details>` : ''}${remaining.length ? `<p>${esc(remaining.length+' 份尚未确认收到，已保留在待提交列表：'+remaining.map(row=>row.text).join('；'))}</p>` : ''}`;
      pendingFiles = pendingFiles.filter(row=>!saved.some(savedRow=>savedRow.queueId === row.id));
      if (saved.length) window.dispatchEvent(new CustomEvent('research-task-view-requested',{detail:{view:'submission-progress'}}));
      await refreshOwn(); await refreshOwnerShortcut();
    } catch (error) { $('upload-message').textContent = error.message; }
    finally { uploading = false; $('upload-submit').disabled = false; form.elements.file.disabled = false; renderPendingFiles(); }
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
  $('task-upload-form').elements.file.addEventListener('change',event=>{
    addFiles([...event.target.files]);
    event.target.value = '';
  });
  const activateView = view => {
    if (view === 'submission-progress') { refreshOwnerShortcut(); refreshOwn(); }
  };
  window.addEventListener('research-task-view',event=>activateView(event.detail?.view));
  $('upload-refresh').addEventListener('click',refreshOwn);
  activateView(window.activeResearchTaskView || '');
})();
