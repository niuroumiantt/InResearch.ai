/* Owner-only submission queue. Server-side inbox and review endpoints enforce authorization. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const results = {revision_required:'需要修改',accepted:'本次验收通过',blocked:'暂时受阻',ineligible:'不符合任务范围'};
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '时间未记录';
  const size = value => value >= 1048576 ? `${(value / 1048576).toFixed(1)} MiB` : `${Math.ceil((value || 0) / 1024)} KiB`;
  const isExcel = item => item.name.toLowerCase().endsWith('.xlsx');
  const state = item => {
    if (item.status === 'rejected') return 'rejected';
    if ((item.analysis_reports || []).length) return 'done';
    if (item.analysis_requested_at) return 'working';
    if (['pending_approval','queued'].includes(item.status) || isExcel(item) && ['approved','archived'].includes(item.status)) return 'pending';
    return 'other';
  };
  const stateText = {pending:'待确认',working:'分析中',done:'已有报告',rejected:'已退回',other:'已接收'};
  let items = [], selected = '', filter = 'pending', initialized = false;

  function reportHtml(item) {
    const rows = item.analysis_reports || [];
    if (!rows.length) return '';
    return `<section class="review-reports"><h3>自动分析与上线报告</h3>${rows.map(row => {
      const report = row.report || {}, published = report.published || [], held = report.held || [];
      const publication = report.publication || {};
      return `<details class="review-report"><summary><span>${esc(time(row.at))}</span><strong>已上线 ${published.length} 条 · 未上线 ${held.length} 条</strong></summary><div class="review-report-body"><p>${esc(report.summary || '无报告摘要')}</p><p class="review-metadata">发布回执：${esc(publication.state || '未发布')} · 模型：${esc(report.model?.actual || '未记录')}</p>${published.length ? `<h4>实际上线</h4><ol>${published.map(p => `<li><strong>${esc(p.site_id)} · ${esc(p.field)}</strong><span>${esc(p.locator)} · 观测编号 ${esc(p.statement_id)}</span>${String(p.url || '').startsWith('/project.html?') ? `<a href="${esc(p.url)}">查看园区 ↗</a>` : ''}</li>`).join('')}</ol>` : ''}${held.length ? `<h4>未上线及原因</h4><ol>${held.map(h => `<li><strong>${esc(h.locator || '未定位')}</strong><span>${esc(h.reason || '原因未记录')}</span></li>`).join('')}</ol>` : ''}<p class="review-metadata">批准原件 SHA256 ${esc(row.sha256)}</p></div></details>`;
    }).join('')}</section>`;
  }

  function feedbackHtml(item) {
    const rows = item.feedback || [];
    return `<details class="review-feedback"><summary>员工可见的反馈与修改任务书 · ${rows.length} 条</summary>${rows.length ? rows.map(row => `<article><small>${esc(time(row.at))} · ${esc(results[row.result] || row.result)}</small><p>${esc(row.text)}</p></article>`).join('') : '<p>尚无反馈。</p>'}</details>`;
  }

  function actionsHtml(item) {
    const status = state(item);
    if (status === 'pending') {
      const action = ['pending_approval','queued'].includes(item.status) ? isExcel(item) ? 'approve_and_analyze' : 'approve' : 'start_analysis';
      return `<section class="review-decision"><h3>处理这份文件</h3><p>${isExcel(item) ? '确认后开始模型分析。只有经原件与单元格复核合格的普通来源条目才会自动上线；结果和修改任务书随后显示在这里。' : '确认后研究端才能接收这份资料。'}</p><label>审批备注或退回原因<input class="decision-note" maxlength="4000" placeholder="可选；退回时请写明原因"></label><div class="review-decision-actions"><button type="button" class="review-primary" data-action="${action}">${isExcel(item) ? '确认并分析 · 合格条目自动上线' : '批准接收'}</button>${['pending_approval','queued'].includes(item.status) ? '<button type="button" data-action="reject">退回文件</button>' : ''}</div></section>`;
    }
    if (status === 'working') return `<section class="review-progress"><h3>正在分析</h3><p>已确认于 ${esc(time(item.analysis_requested_at))}。${item.analysis_progress ? `当前 ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端将重试' : '处理中')}` : '研究端正在接收或准备原件。'}</p><p class="review-metadata">刷新后查看新进度；分析完成后会出现上线报告和员工修改任务书。</p></section>`;
    if (status === 'rejected') return `<section class="review-rejected"><h3>已退回</h3><p>${esc(item.decision?.note || '未填写退回原因')}</p></section>`;
    return '';
  }

  function detailHtml(item) {
    const status = state(item);
    return `<div class="review-detail-head"><div><p class="review-eyebrow">文件详情 / ${esc(item.id.slice(0,8))}</p><h2 id="review-detail-title">${esc(item.name)}</h2><span class="review-state review-state-${status}">${stateText[status]}</span></div><a class="review-download" href="/api/materials/content/${esc(item.id)}" download>下载原件核对 ↓</a></div>
      ${actionsHtml(item)}
      <dl class="review-facts"><div><dt>提交人</dt><dd>${esc(item.submitter || '未留称呼')}</dd></div><div><dt>上传时间</dt><dd>${esc(time(item.created))}</dd></div><div><dt>文件大小</dt><dd>${esc(size(item.size))}</dd></div><div><dt>对应工作包</dt><dd>${esc(item.package_id || '未指定')}</dd></div></dl>
      <div class="review-context"><div><strong>资料来源</strong><p>${esc(item.source || '未填写')}</p></div><div><strong>提交说明</strong><p>${esc(item.note || '未填写')}</p></div></div>
      <details class="review-integrity"><summary>文件编号与 SHA256 校验</summary><p>文件编号 ${esc(item.id)}<br>SHA256 ${esc(item.sha256)}</p></details>
      ${reportHtml(item)}${feedbackHtml(item)}
      ${item.approval ? `<details class="review-manual"><summary>追加人工反馈</summary><form class="owner-feedback"><label>验收结论<select name="result"><option value="revision_required">需要修改</option><option value="accepted">本次验收通过</option><option value="blocked">暂时受阻</option><option value="ineligible">不符合任务范围</option></select></label><label>反馈内容<textarea name="text" rows="5" maxlength="20000" required></textarea></label><button type="submit">登记反馈</button></form></details>` : ''}`;
  }

  function render() {
    const counts = {pending:0,working:0,done:0,rejected:0};
    items.forEach(item => { if (state(item) in counts) counts[state(item)]++; });
    Object.entries(counts).forEach(([name,value]) => { $('review-count-'+name).textContent = value; });
    const query = $('review-search').value.trim().toLocaleLowerCase();
    const visible = items.filter(item => (filter === 'all' || state(item) === filter) && (!query || [item.name,item.submitter,item.id,item.package_id].some(value => String(value || '').toLocaleLowerCase().includes(query))));
    $('review-visible-count').textContent = `${visible.length} 份`;
    if (!visible.some(item => item.id === selected)) selected = visible[0]?.id || '';
    $('review-queue-list').innerHTML = visible.length ? visible.map(item => `<button type="button" class="review-queue-item ${item.id === selected ? 'is-selected' : ''}" data-id="${esc(item.id)}" aria-current="${item.id === selected ? 'true' : 'false'}"><span class="review-queue-top"><strong>${esc(item.name)}</strong><span class="review-state review-state-${state(item)}">${stateText[state(item)]}</span></span><span class="review-queue-meta">${esc(item.submitter || '未留称呼')} · ${esc(time(item.created))}</span></button>`).join('') : '<p class="review-queue-empty">当前筛选下没有文件。</p>';
    const item = items.find(row => row.id === selected);
    $('review-detail-content').innerHTML = item ? detailHtml(item) : '<div class="review-empty"><h2 id="review-detail-title">选择一份文件</h2><p>从左侧列表查看原件、分析进度和报告。</p></div>';
    const url = new URL(location.href);
    if (item) url.searchParams.set('id',item.id); else url.searchParams.delete('id');
    history.replaceState(null,'',url);
  }

  async function refresh() {
    try {
      const response = await fetch('/api/materials', {cache:'no-store'});
      if (!response.ok) throw Error(`无法读取审批列表（HTTP ${response.status}）`);
      const data = await response.json();
      if (!data.can_approve) throw Error('当前账号不是指定审批人，无法查看或处理作业。');
      items = data.items || [];
      if (!initialized) {
        const requested = items.find(item => item.id === selected);
        if (requested) filter = state(requested) === 'rejected' || state(requested) === 'other' ? 'all' : state(requested);
        else if (!items.some(item => state(item) === 'pending')) filter = items.some(item => state(item) === 'working') ? 'working' : items.some(item => state(item) === 'done') ? 'done' : 'all';
        $('review-filters').querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
        initialized = true;
      }
      render();
    } catch (error) { $('review-message').textContent = error.message; }
  }

  async function review(item, action, extra = {}) {
    const payload = {id:item.id,sha256:item.sha256,expected_revision:item.revision,operation_id:crypto.randomUUID(),action,...extra};
    const response = await fetch('/api/materials/review', {method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'material-intake'},body:JSON.stringify(payload)});
    if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(`审批请求未到达应用，请刷新重试或联系管理员（HTTP ${response.status}）`);
    const result = await response.json();
    if (!response.ok) throw Error(result.error || '操作失败，请刷新列表');
    $('review-message').textContent = action === 'feedback' ? '反馈已登记，员工可通过回执查看。' : action === 'reject' ? '文件已退回。' : ['approve_and_analyze','start_analysis'].includes(action) ? '已确认分析。合格条目上线后将显示报告。' : '已批准接收。';
    filter = 'all'; selected = item.id;
    await refresh();
    const updated = items.find(row => row.id === item.id);
    if (updated && ['pending','working','done'].includes(state(updated))) filter = state(updated);
    $('review-filters').querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
    render();
  }

  $('review-queue-list').addEventListener('click', event => { const row = event.target.closest('[data-id]'); if (!row) return; selected = row.dataset.id; render(); if (matchMedia('(max-width: 700px)').matches) $('review-detail-content').scrollIntoView({block:'start'}); });
  $('review-detail-content').addEventListener('click', async event => {
    const button = event.target.closest('[data-action]'); if (!button) return;
    const item = items.find(row => row.id === selected); if (!item) return;
    const note = $('review-detail-content').querySelector('.decision-note')?.value.trim() || '';
    button.disabled = true;
    try { await review(item,button.dataset.action,{note}); }
    catch (error) { $('review-message').textContent = error.message; button.disabled = false; }
  });
  $('review-detail-content').addEventListener('submit', async event => {
    const form = event.target; if (!form.matches('.owner-feedback')) return;
    event.preventDefault(); const item = items.find(row => row.id === selected); if (!item) return;
    const button = form.querySelector('button'); button.disabled = true;
    try { await review(item,'feedback',{result:form.elements.result.value,text:form.elements.text.value.trim()}); }
    catch (error) { $('review-message').textContent = error.message; button.disabled = false; }
  });
  $('review-filters').addEventListener('click', event => {
    const button = event.target.closest('[data-filter]'); if (!button) return;
    filter = button.dataset.filter;
    $('review-filters').querySelectorAll('[data-filter]').forEach(row => row.setAttribute('aria-pressed', String(row === button)));
    selected = ''; render();
  });
  $('review-search').addEventListener('input', () => { selected = ''; render(); });
  $('review-refresh').addEventListener('click', refresh);
  selected = new URLSearchParams(location.search).get('id') || '';
  refresh();
})();
