/* Account-bound uploads reuse the existing receipt-sealed batch workflow. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let key = 'inresearch-task-upload-receipts-v1';
  let pendingBatchKey = 'inresearch-task-upload-pending-batches-v1';
  let identityReady = false;
  window.addEventListener('project-work-loaded',event=>{
    const identity = event.detail;
    identityReady = Boolean(identity.member);
    key = 'inresearch-task-upload-receipts-v2:' + identity.user_id;
    pendingBatchKey = 'inresearch-task-upload-pending-batches-v2:' + identity.user_id;
    if (identityReady && !uploading) finishBatches();
    if (window.researchTasksState) loadPackages(window.researchTasksState);
  });
  const size = value => value >= 1048576 ? `${(value / 1048576).toFixed(1)} MiB` : `${Math.ceil(value / 1024)} KiB`;
  const receipts = () => { try { const rows = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(rows) ? rows.slice(0,100) : []; } catch { return []; } };
  const save = rows => localStorage.setItem(key, JSON.stringify(rows.slice(0,100)));
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
    button.disabled = true; await finishBatches({recoverIncomplete:button.id === 'upload-recover-incomplete'});
  });
  let selectedPackageId = window.activeResearchPackageId || '';
  window.addEventListener('research-package-selected',event=>{
    selectedPackageId = event.detail?.packageId || '';
    if ([...$('upload-package').options].some(option=>option.value === selectedPackageId))
      $('upload-package').value = selectedPackageId;
  });
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
    if (window.projectWorkState) {
      const ids = new Set(window.projectWorkState.packages.filter(p=>p.can_submit).map(p=>p.id));
      data = {...data, packages:data.packages.filter(p=>ids.has(p.id))};
    }
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
    if (!identityReady) { $('upload-message').textContent = '请登录并取得项目提交权限。'; return; }
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
      savePendingBatches([...pendingBatches(),{batch_id:batchId,batch_token:batchToken,items:[],queue_ids:entries.map(row=>row.id),upload_complete:false}]);
      for (const [index,file] of files.entries()) {
        $('upload-message').textContent = `正在上传第 ${index+1}/${files.length} 份：${file.name}`;
        try {
          const metadata = {...common,name:file.name,batch_total:files.length,batch_index:index};
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
      $('upload-message').innerHTML = `<span data-upload-result="${received.length}">${received.length} 份附件已收到${received.length ? batchFinished ? '，等待负责人按批次确认；后续请查看本工作包的共同现行反馈。' : '，批次提交尚未完成，请恢复提交状态。' : '。'}</span>${remaining.length ? `<p>${esc(remaining.length+' 份尚未确认收到，已保留在待提交列表：'+remaining.map(row=>row.text).join('；'))}</p>` : ''}`;
      pendingFiles = pendingFiles.filter(row=>!saved.some(savedRow=>savedRow.queueId === row.id));
      if (saved.length) window.dispatchEvent(new CustomEvent('project-work-refresh'));
      if (saved.length) window.dispatchEvent(new CustomEvent('research-task-view-requested',{detail:{view:'submission-progress'}}));
      await refreshOwnerShortcut();
    } catch (error) { $('upload-message').textContent = error.message; }
    finally { uploading = false; $('upload-submit').disabled = false; form.elements.file.disabled = false; renderPendingFiles(); }
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
    } catch { /* The authorized submission flow remains usable when the review queue is unavailable. */ }
  }
  $('task-upload-form').elements.file.addEventListener('change',event=>{
    addFiles([...event.target.files]);
    event.target.value = '';
  });
  const activateView = view => {
    if (view === 'submission-progress' && identityReady) { refreshOwnerShortcut(); if (!uploading) finishBatches(); }
  };
  window.addEventListener('research-task-view',event=>activateView(event.detail?.view));
  activateView(window.activeResearchTaskView || '');
})();
