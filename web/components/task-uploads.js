/* Anonymous submission and receipt holder view. Owner decisions live in task-reviews.js. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const key = 'inresearch-task-upload-receipts-v1';
  const labels = {pending_approval:'待负责人确认',queued:'待负责人确认',approved:'已确认，待研究端接收',archived:'研究端已接收',rejected:'已退回'};
  const results = {revision_required:'需要修改',accepted:'本次验收通过',blocked:'暂时受阻',ineligible:'不符合任务范围'};
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) + '（北京时间）' : '时间未记录';
  const receipts = () => { try { const rows = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(rows) ? rows.slice(0,100) : []; } catch { return []; } };
  const save = rows => localStorage.setItem(key, JSON.stringify(rows.slice(0,100)));
  const feedback = item => `<details class="upload-feedback"><summary>分析验收反馈 · ${(item.feedback || []).length} 条</summary>${(item.feedback || []).length ? item.feedback.map(row => `<article><small>${esc(time(row.at))} · ${esc(results[row.result] || row.result)}</small><p>${esc(row.text)}</p></article>`).join('') : '<p>尚未登记分析验收反馈。</p>'}</details>`;
  const progress = item => item.analysis_progress ? `<p class="small">自动分析：${esc(item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端会重试' : item.analysis_progress.state === 'completed' ? '已完成' : '进行中')} · ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(time(item.analysis_progress.at))}</p>` : '';
  function ownCard(item) {
    const decision = item.decision;
    return `<article class="upload-card"><div class="upload-card-head"><strong>${esc(item.name)}</strong><span class="upload-status">${esc(labels[item.status] || item.status)}</span></div><p class="small muted">上传于 ${esc(time(item.created))}</p>${decision ? `<p class="small">${esc(decision.action === 'reject' ? '退回' : '已确认')}：${esc(time(decision.at))}${decision.note ? ` · ${esc(decision.note)}` : ''}</p>` : ''}${progress(item)}${feedback(item)}<details class="upload-file-meta"><summary>文件编号与校验信息</summary><p class="small muted">文件编号 ${esc(item.id)}<br>SHA256 ${esc(item.sha256)}</p></details></article>`;
  }
  async function readReceipt(row) {
    const response = await fetch('/api/task-uploads/receipt', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(row),cache:'no-store'});
    if (!response.ok) throw Error('回执无效或状态暂不可用');
    return (await response.json()).item;
  }
  async function refreshOwn() {
    const rows = receipts();
    if (!rows.length) { $('upload-own-list').innerHTML = '<p class="small muted">当前浏览器还没有提交回执。</p>'; return; }
    const results = await Promise.all(rows.map(row => readReceipt(row).then(item => ({item})).catch(error => ({error}))));
    $('upload-own-list').innerHTML = results.map(({item,error}, i) => item ? ownCard(item) : `<p class="small muted">${esc(rows[i].id)}：${esc(error.message)}</p>`).join('');
  }
  async function loadPackages() {
    try {
      const response = await fetch('/api/research-tasks', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      $('upload-package').insertAdjacentHTML('beforeend', data.packages.map(p => `<option value="${esc(p.id)}">${esc(p.title)} · ${esc(p.region)}</option>`).join(''));
    } catch { /* The upload still works without a package selection. */ }
  }
  $('task-upload-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget, file = form.elements.file.files[0];
    if (!file) return;
    if (file.size < 1 || file.size > 64 * 1024 * 1024) { $('upload-message').textContent = '文件须为 1 字节至 64 MiB。'; return; }
    const metadata = {name:file.name,submitter:form.elements.submitter.value.trim(),package_id:form.elements.package_id.value,source:form.elements.source.value.trim(),note:form.elements.upload_note.value.trim()};
    $('upload-submit').disabled = true; $('upload-message').textContent = '正在上传原件…';
    try {
      const response = await fetch('/api/task-uploads', {method:'POST',headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify(metadata))},body:file});
      const type = response.headers.get('Content-Type') || '';
      if (!type.includes('application/json')) {
        const detail = response.status === 403 ? '上传被网站安全防护拦截，文件未进入审批。请联系负责人。' : '上传服务暂不可用，请稍后重试。';
        throw Error(`${detail}（HTTP ${response.status}）`);
      }
      let result;
      try { result = await response.json(); }
      catch { throw Error('上传响应异常，请先向负责人核对是否已收到文件，避免重复提交。'); }
      if (!response.ok) throw Error(result.error || '上传失败');
      save([{id:result.item.id,receipt:result.receipt},...receipts().filter(row => row.id !== result.item.id)]);
      $('upload-message').innerHTML = `已收到文件，等待负责人审批。文件编号 <code>${esc(result.item.id)}</code>；回执码 <code class="upload-receipt-code">${esc(result.receipt)}</code>。请保存回执码，换设备查看反馈时需要它。`;
      form.reset(); await refreshOwn(); await refreshOwnerShortcut();
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
      const pending = data.items.filter(item => ['pending_approval','queued'].includes(item.status) || item.status === 'archived' && item.name.toLowerCase().endsWith('.xlsx') && !item.analysis_requested_at).length;
      $('upload-owner-shortcut-count').textContent = pending ? `${pending} 份文件待确认。审批与上线报告已移到独立工作台。` : '审批与上线报告已移到独立工作台。';
    } catch { /* Anonymous uploading remains usable when the owner inbox is unavailable. */ }
  }
  $('upload-refresh').addEventListener('click',refreshOwn);
  loadPackages(); refreshOwn(); refreshOwnerShortcut();
})();
