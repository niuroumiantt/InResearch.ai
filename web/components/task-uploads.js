/* Public submission receipts and private owner decisions for task materials. */
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
  const ownerReports = item => (item.analysis_reports || []).map(row => {
    const report = row.report || {}, published = report.published || [], held = report.held || [];
    return `<details class="upload-feedback"><summary>自动分析与上线报告 · ${esc(time(row.at))} · 已上线 ${published.length} 条</summary><p>${esc(report.summary || '')}</p><p class="small">发布回执：${esc(report.publication?.state || '未发布')} · 模型：${esc(report.model?.actual || '未记录')} · 原件：${esc(row.sha256)}</p>${published.map(p => `<article><strong>${esc(p.site_id)} · ${esc(p.field)}</strong> · ${esc(p.locator)} · <a href="${esc(p.url)}">查看园区</a><br><small>观测编号 ${esc(p.statement_id)}</small></article>`).join('')}${held.map(h => `<article><strong>未上线 · ${esc(h.locator)}</strong><p>${esc(h.reason)}</p></article>`).join('')}</details>`;
  }).join('');
  const progress = item => item.analysis_progress ? `<p class="small">自动分析：${esc(item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端会重试' : item.analysis_progress.state === 'completed' ? '已完成' : '进行中')} · ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(time(item.analysis_progress.at))}</p>` : '';
  function ownCard(item) {
    const decision = item.decision;
    return `<article class="upload-card"><div class="upload-card-head"><strong>${esc(item.name)}</strong><span>${esc(labels[item.status] || item.status)}</span></div><p class="small muted">文件编号 ${esc(item.id)} · 上传 ${esc(time(item.created))} · SHA256 ${esc(item.sha256)}</p>${decision ? `<p class="small">${esc(decision.action === 'reject' ? '退回' : '批准')}：${esc(time(decision.at))}${decision.note ? ` · ${esc(decision.note)}` : ''}</p>` : ''}${progress(item)}${feedback(item)}</article>`;
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
      form.reset(); await refreshOwn(); await refreshOwner();
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
  const ownerCard = item => `<article class="upload-card" data-id="${esc(item.id)}">
    <div class="upload-card-head"><strong>${esc(item.name)}</strong><span>${esc(labels[item.status] || item.status)}</span></div>
    <p class="small muted">${esc(item.submitter || '未留称呼')} · ${esc(time(item.created))} · ${esc(item.size)} 字节 · 文件编号 ${esc(item.id)}</p>
    <p class="small">工作包 ${esc(item.package_id || '未指定')} · 来源 ${esc(item.source || '未填')} · 说明 ${esc(item.note || '未填')}</p>
    <p class="small muted">SHA256 ${esc(item.sha256)}</p><a href="/api/materials/content/${esc(item.id)}" download>下载原件核对 ↓</a>
    ${item.status === 'pending_approval' || item.status === 'queued' ? `<div class="owner-actions"><label>审批备注 / 退回原因 <input class="decision-note" maxlength="4000"></label>${item.name.toLowerCase().endsWith('.xlsx') ? `<button type="button" data-action="approve_and_analyze">确认并分析（合格条目自动上线）</button>` : `<button type="button" data-action="approve">批准接收</button>`}<button type="button" data-action="reject">退回</button></div>` : ''}
    ${item.status === 'archived' && item.name.toLowerCase().endsWith('.xlsx') && !item.analysis_requested_at ? `<button type="button" data-action="start_analysis">确认并分析（合格条目自动上线）</button>` : ''}
    ${item.analysis_requested_at ? `<p class="small">自动分析已启动：${esc(time(item.analysis_requested_at))}</p>` : ''}${progress(item)}
    ${item.approval ? `<p class="small">批准于 ${esc(time(item.approval.at))}，批准摘要 ${esc(item.approval.sha256)}</p><form class="owner-feedback"><label>分析验收结论 <select name="result"><option value="revision_required">需要修改</option><option value="accepted">本次验收通过</option><option value="blocked">暂时受阻</option><option value="ineligible">不符合任务范围</option></select></label><label>反馈内容 <textarea name="text" rows="4" maxlength="20000" required></textarea></label><button type="submit">登记反馈</button></form>` : ''}
    ${item.decision?.action === 'reject' ? `<p>退回原因：${esc(item.decision.note)}</p>` : ''}
    ${ownerReports(item)}${feedback(item)}</article>`;
  let ownerItems = new Map();
  async function refreshOwner() {
    try {
      const response = await fetch('/api/materials', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      if (!data.can_approve) return;
      $('upload-owner').hidden = false;
      ownerItems = new Map(data.items.map(item => [item.id,item]));
      $('upload-owner-list').innerHTML = data.items.length ? data.items.map(ownerCard).join('') : '<p class="small muted">暂无待处理材料。</p>';
    } catch { $('owner-message').textContent = '审批列表暂不可用，请稍后刷新。'; }
  }
  async function review(item, action, extra) {
    const payload = {id:item.id,sha256:item.sha256,expected_revision:item.revision,operation_id:crypto.randomUUID(),action,...extra};
    const response = await fetch('/api/materials/review', {method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'material-intake'},body:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || '操作失败，请刷新');
    $('owner-message').textContent = action === 'feedback' ? '反馈已登记。' : ['approve_and_analyze','start_analysis'].includes(action) ? '已确认分析；合格条目会自动上线，完成后将显示报告。' : action === 'approve' ? '已批准接收。' : '已退回。';
    await refreshOwner(); await refreshOwn();
  }
  $('upload-owner-list').addEventListener('click', async event => {
    const button = event.target.closest('[data-action]'); if (!button) return;
    const card = button.closest('[data-id]'), item = ownerItems.get(card?.dataset.id);
    if (!item) return;
    button.disabled = true;
    try { await review(item,button.dataset.action,{note:card.querySelector('.decision-note')?.value.trim() || ''}); }
    catch (error) { $('owner-message').textContent = error.message; button.disabled = false; }
  });
  $('upload-owner-list').addEventListener('submit', async event => {
    if (!event.target.matches('.owner-feedback')) return;
    event.preventDefault();
    const form = event.target, item = ownerItems.get(form.closest('[data-id]')?.dataset.id);
    if (!item) return;
    const button = form.querySelector('button'); button.disabled = true;
    try { await review(item,'feedback',{result:form.elements.result.value,text:form.elements.text.value.trim()}); }
    catch (error) { $('owner-message').textContent = error.message; button.disabled = false; }
  });
  $('upload-refresh').addEventListener('click',refreshOwn);
  $('upload-owner-refresh').addEventListener('click',refreshOwner);
  loadPackages(); refreshOwn(); refreshOwner();
})();
