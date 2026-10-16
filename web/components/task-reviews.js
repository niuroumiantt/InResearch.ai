/* Owner-only submission queue. Server-side inbox and review endpoints enforce authorization. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const results = {revision_required:'需要修改',sampled_incomplete:'抽样反馈 · 全表待审',accepted:'本次验收通过',blocked:'暂时受阻',ineligible:'不符合任务范围'};
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '时间未记录';
  const isoTime = value => value ? new Date(value).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '时间未记录';
  const formatValue = value => typeof value === 'object' ? JSON.stringify(value) : String(value ?? '未知');
  const size = value => value >= 1048576 ? `${(value / 1048576).toFixed(1)} MiB` : `${Math.ceil((value || 0) / 1024)} KiB`;
  const isReviewable = item => /\.(xlsx|txt|md|csv|tsv|json|html?|pdf|docx)$/i.test(item.name);
  const state = item => {
    if (item.status === 'rejected') return 'rejected';
    if (item.review_batch_recovery) return 'pending';
    if (item.full_analysis) return item.full_analysis.state === 'completed' ? 'done' : 'working';
    if ((item.analysis_reports || []).length) return 'done';
    if (item.analysis_progress?.state === 'source_error') return 'done';
    if (item.analysis_requested_at) return 'working';
    if (['pending_approval','queued'].includes(item.status) || isReviewable(item) && ['approved','archived'].includes(item.status)) return 'pending';
    return 'other';
  };
  const stateText = {pending:'待确认',working:'分析中',done:'已有反馈',rejected:'已退回',other:'已接收'};
  const fullStateLabel = item => item.full_analysis.state === 'completed' ? '全表原生文本已审' : item.full_analysis.state === 'pilot_completed' ? '试点已审 · 待网站核验' : item.analysis_progress?.state === 'blocked' ? '完整审阅受阻' : item.analysis_progress?.state === 'waiting' ? '完整审阅等待中' : '完整审阅中';
  const stateLabel = item => recoveryFor(item) ? '确认未完成' : item.full_analysis ? fullStateLabel(item) : item.analysis_progress?.error_code === 'joint_model_output_invalid_requires_operator' ? '需人工复核' : item.analysis_progress?.state === 'source_error' ? '需修正原件' : item.analysis_scope?.mode === 'sampled_native_cells' ? '抽样反馈 · 全表待审' : stateText[state(item)];
  let items = [], selected = '', filter = 'pending', initialized = false, packageNames = new Map(), packageRows = [];
  const taskGroup = item => {
    if (item.package_id) return {key:`package:${item.package_id}`, title:packageNames.get(item.package_id) || item.package_id, kind:'系统工作包', linked:true};
    const title = item.project_name?.trim();
    if (title) return {key:`project:${title}`, title, kind:'自填项目 · 待绑定工作包', linked:false};
    return {key:'unassigned', title:'未归属任务', kind:'旧提交 · 待确认归属', linked:false};
  };
  const sameTask = (a,b) => taskGroup(a).key === taskGroup(b).key;
  const recoveryFor = item => item.review_batch_recovery || items.find(row => row.review_batch_recovery?.items.some(member => member.id === item.id))?.review_batch_recovery;
  const batchRows = item => recoveryFor(item)
    ? recoveryFor(item).items.map(member => items.find(row => row.id === member.id)).filter(Boolean)
    : Array.isArray(item.upload_batch?.member_ids) && item.upload_batch.sealed
    ? item.upload_batch.member_ids.map(id => items.find(row => row.id === id)).filter(Boolean).sort((a,b) => a.created - b.created)
    : item.batch_id ? items.filter(row => row.batch_id === item.batch_id
    && row.package_id === item.package_id && row.submitter === item.submitter
    && row.project_name === item.project_name).sort((a,b) => a.created - b.created) : [item];
  const analysisRows = item => batchRows(item).filter(row => state(row) !== 'rejected'
    && (item.upload_batch || item.review_batch_id || recoveryFor(item) || state(item) !== 'pending'
      || ['pending_approval','queued'].includes(row.status)));
  const hasBatch = item => Boolean(recoveryFor(item) || item.batch_id
    && (item.upload_batch || item.review_batch_id || ['pending_approval','queued'].includes(item.status)) && (item.upload_batch?.sealed
    ? analysisRows(item).length > 1 : analysisRows(item).length > 1 || item.upload_batch?.expected > 1 || item.batch_total > 1));
  const batchOperations = new Map();

  function batchHtml(item) {
    const rows = batchRows(item);
    if (rows.length < 2 && !hasBatch(item)) return '';
    return `<section class="review-batch"><h3>同批材料 · ${rows.length} 份</h3><p class="review-metadata">一并核对关联、重复与冲突；每份保留原件和独立反馈。</p><ul>${rows.map(row => `<li><button type="button" data-related-id="${esc(row.id)}" title="${esc(row.name)}">${esc(row.name)}</button><span class="review-state review-state-${state(row)}">${stateLabel(row)}</span><a href="/api/materials/content/${esc(row.id)}" download aria-label="下载 ${esc(row.name)}">下载 ↓</a></li>`).join('')}</ul></section>`;
  }

  function jointReportHtml(joint) {
    if (!joint) return '';
    const kinds = {revision:'版本衔接',support:'相互补证',conflict:'存在冲突',duplicate:'重复内容'};
    const label = id => items.find(row => row.id === id)?.name || id.slice(0,8);
    return `<details class="review-joint-report"><summary>本批联合结论 · ${(joint.members || []).length} 份 · ${(joint.relationships || []).length} 项关联</summary><p>${esc(joint.summary)}</p><ol>${(joint.relationships || []).map(row => `<li><strong>${esc(kinds[row.kind] || row.kind)}</strong><span>${esc(label(row.source_id))} · ${esc(row.source_locator)} ↔ ${esc(label(row.target_id))} · ${esc(row.target_locator)}</span><span>${esc(row.description)}</span></li>`).join('')}</ol></details>`;
  }


  function reportHtml(item) {
    const rows = item.analysis_reports || [];
    if (!rows.length) return '';
    return `<section class="review-reports"><h3>自动分析与上线报告</h3>${rows.map(row => {
      const report = row.report || {}, published = report.published || [], held = report.held || [];
      const publication = report.publication || {};
      const scope = report.review_scope;
      const sampled = scope?.mode === 'sampled_native_cells';
      return `<details class="review-report"><summary><span>${esc(time(row.at))}</span><strong>${sampled ? `抽样 ${esc(scope.excerpted_cells)}/${esc(scope.total_nonblank_cells)} 格 · 全表待审` : `已上线 ${published.length} 条 · 待核候选 ${held.length} 条`}</strong></summary><div class="review-report-body">${sampled ? `<p class="review-scope-note">仅 ${esc(scope.excerpted_cells)} 个单元格片段交给模型，其中 ${esc(scope.prefix_only_cells)} 个只见前90字；${esc(scope.not_fully_seen_cells)} 个未完整审阅。0 条上线只表示本次抽样未生成发布候选，不能判定全表没有合格条目。</p>` : ''}<p>${esc(report.summary || '无报告摘要')}</p>${jointReportHtml(report.batch_review)}<p class="review-metadata">发布回执：${esc(publication.state || '未发布')} · 审阅模型：${esc(report.model?.actual || report.model?.requested || '未记录')}${report.model?.backend === 'codex_cli' ? '（CLI 请求身份，服务方实际身份未回传）' : ''}${report.task_provenance ? ` · 系统任务版本 ${esc(report.task_provenance.revision)}${report.task_provenance.previous_submission_id ? ' · 已关联上版回执' : ''}` : ' · 旧报告未记录任务版本'}</p>${published.length ? `<h4>实际上线</h4><ol>${published.map(p => `<li><strong>${esc(p.site_id)} · ${esc(p.field)} · ${p.registration_kind === 'reconfirmation' ? '同值再次核对' : '新登记'}</strong><span>${esc(p.locator)} · 观测编号 ${esc(p.statement_id)}${p.model_checked_at ? ` · 本轮模型核对 ${esc(isoTime(p.model_checked_at))}` : ''}</span>${String(p.url || '').startsWith('/project.html?') ? `<a href="${esc(p.url)}">查看园区 ↗</a>` : ''}</li>`).join('')}</ol>` : ''}${held.length ? `<h4>未上线及原因</h4><ol>${held.map(h => `<li><strong>${h.classification === 'duplicate' ? '无增量重复' : h.classification === 'conflict' ? '数值冲突' : '待补证据'} · ${esc(h.locator || '未定位')}</strong><span>${esc(h.reason || '原因未记录')}</span>${h.existing && h.incoming ? `<span>现有值 ${esc(formatValue(h.existing.value))} · 来源 ${esc(h.existing.source_sha256 || h.existing.observation_id || '旧台账')} · ${esc(h.existing.source_locator || '原定位未记录')}<br>本次值 ${esc(formatValue(h.incoming.value))} · 来源 ${esc(h.incoming.source_sha256)} · ${esc(h.incoming.source_locator)}</span>` : ''}</li>`).join('')}</ol>` : ''}<p class="review-metadata">批准原件 SHA256 ${esc(row.sha256)}</p></div></details>`;
    }).join('')}</section>`;
  }

  function feedbackHtml(item) {
    const rows = item.feedback || [];
    return `<details class="review-feedback"><summary>员工可见的反馈与修改任务书 · ${rows.length} 条</summary>${rows.length ? rows.map(row => `<article><small>${esc(time(row.at))} · ${esc(results[row.result] || row.result)}</small><p>${esc(row.text)}</p></article>`).join('') : '<p>尚无反馈。</p>'}</details>`;
  }

  function fullProgressHtml(item) {
    const attempt = item.full_analysis, progress = item.analysis_progress || {};
    const completed = attempt.completed_package_ids?.length ?? 0, total = attempt.package_ids?.length ?? '?';
    const isComplete = attempt.state === 'completed', isPilot = attempt.state === 'pilot_completed';
    const message = isComplete ? '本轮全部园区及未归属包均已形成完整原生文本审阅回执。来源真假、外链原件、图片与图表仍须独立核验。'
      : isPilot ? '首个园区包已完成审阅；正在核对实际网站回执，余包尚未放行。'
      : progress.state === 'blocked' ? '审阅暂时受阻；已保存的窗口结果保留，等待研究端核对原因。'
      : progress.state === 'waiting' ? '等待研究资源可用，已完成的窗口结果保留。'
      : ['reading','running','continuing'].includes(progress.state || attempt.state) ? '正在逐窗阅读完整原件并综合核对同一园区；只有完整包通过校验后才形成回执。'
      : '当前审阅状态尚未确认，请刷新或由研究端核对。';
    const window = !isComplete && !isPilot && Number.isInteger(progress.window_total)
      ? `<p>当前园区包窗口：${esc(progress.window_completed ?? 0)}/${esc(progress.window_total)}；窗口完成不等于该包已验收。</p>` : '';
    return `<section class="review-progress review-full-progress" role="status"><h3>${esc(fullStateLabel(item))}</h3><p>${esc(message)}</p><p>完整包回执：${esc(completed)}/${esc(total)}（含未归属内容）；已验收原生单元格：${esc(attempt.covered_cells ?? 0)}/${esc(attempt.total_nonblank_cells ?? '?')}。</p>${window}${progress.reason && !isComplete && !isPilot ? `<p class="review-metadata">研究端状态：${esc(progress.reason)}</p>` : ''}<p class="review-metadata">旧抽样报告保留在下方历史中；完整审阅不等于所有条目已上线或达到 C3。</p></section>`;
  }

  function actionsHtml(item) {
    const status = state(item);
    if (recoveryFor(item)) return '<section class="review-decision"><h3>本批确认尚未完成</h3><p>原操作已保存，继续完成同一份清单即可开始联合审阅。</p><button type="button" class="review-primary" data-batch-action="approve_and_analyze">恢复本批确认</button></section>';
    if (item.full_analysis) return fullProgressHtml(item);
    if (item.analysis_progress?.error_code === 'joint_model_output_invalid_requires_operator') return '<section class="review-rejected"><h3>定位校验受阻 · 需人工复核</h3><p>联合结果经一次纠正仍未通过原件定位校验，已保存结果并停止自动模型调用。请核对原件定位，修订材料后重新提交。</p></section>';
    if (status === 'pending' && hasBatch(item)) {
      const rows = analysisRows(item), excluded = batchRows(item).length - rows.length, expected = item.upload_batch?.expected || item.batch_total || rows.length;
      const ready = (!item.upload_batch || item.upload_batch.sealed)
        && rows.length >= 2 && rows.length <= 20 && rows.every(row => state(row) === 'pending' && isReviewable(row));
      const issue = rows.some(row => !isReviewable(row)) ? '本批含暂不支持模型审阅的附件。请先退回对应文件，再联合审阅其余附件。' : `本批已收到 ${batchRows(item).length}/${expected} 份。请在上传页完成这批提交，确认所有成员均可审阅后再整批处理。`;
      return `<section class="review-decision review-batch-decision"><h3>整批确认与联合审阅</h3><p>${ready ? `本批 ${rows.length} 份附件共用当前工作包与最新台账，模型联合核对，逐份返回定位与反馈。` : issue}${excluded ? ` 已退回或此前已处理的 ${excluded} 份不参与本轮分析。` : ''}</p><label>审批备注<input class="decision-note" maxlength="4000" placeholder="可选；退回时请写明原因"></label><div class="review-decision-actions"><button type="button" class="review-primary" data-batch-action="approve_and_analyze"${ready ? '' : ' disabled'}>确认本批 ${rows.length} 份并联合分析</button>${['pending_approval','queued'].includes(item.status) ? '<button type="button" data-action="reject">退回当前文件</button>' : ''}</div></section>`;
    }
    if (status === 'pending') {
      const action = ['pending_approval','queued'].includes(item.status) ? isReviewable(item) ? 'approve_and_analyze' : 'approve' : 'start_analysis';
      const excel = item.name.toLowerCase().endsWith('.xlsx');
      const waiting = action === 'start_analysis' && item.status !== 'archived';
      return `<section class="review-decision"><h3>处理这份文件</h3><p>${isReviewable(item) ? excel ? '确认后开始模型分析。只有经原件与单元格复核合格的普通来源条目才会自动上线；结果和修改任务书随后显示在这里。' : '确认后审阅可提取的文字并生成下一版任务。此类附件暂不自动上线事实。' : '确认后研究端才能接收这份资料；此格式暂无自动审阅。'}</p><label>审批备注或退回原因<input class="decision-note" maxlength="4000" placeholder="可选；退回时请写明原因"></label><div class="review-decision-actions"><button type="button" class="review-primary" data-action="${action}"${waiting ? ' disabled' : ''}>${waiting ? '已确认 · 等待研究端接收' : isReviewable(item) ? excel ? '确认并分析 · 合格条目自动上线' : '确认并分析 · 生成修改任务' : '批准接收'}</button>${['pending_approval','queued'].includes(item.status) ? '<button type="button" data-action="reject">退回文件</button>' : ''}</div></section>`;
    }
    if (status === 'working') return `<section class="review-progress"><h3>正在分析</h3><p>已确认于 ${esc(time(item.analysis_requested_at))}。${item.analysis_progress ? `当前 ${esc(item.analysis_progress.completed ?? 0)}/${esc(item.analysis_progress.total ?? '?')} 批 · ${esc(item.analysis_progress.state === 'blocked' ? '暂时受阻，研究端将重试' : '处理中')}` : '研究端正在接收或准备原件。'}</p><p class="review-metadata">刷新后查看新进度；分析完成后会出现上线报告和员工修改任务书。</p></section>`;
    if (item.analysis_scope?.mode === 'sampled_native_cells') return `<section class="review-sampled" role="status"><h3>抽样反馈已出 · 全表审核未完成</h3><p>原件 ${esc(item.analysis_scope.total_nonblank_cells)} 个非空单元格，模型仅见 ${esc(item.analysis_scope.excerpted_cells)} 个片段；${esc(item.analysis_scope.not_fully_seen_cells)} 个未完整审阅。当前 0 条上线不能视为全表无合格条目。</p><p>下一步：保留原件，按当前工作包和最新台账继续审核未覆盖内容；员工按下方修改任务书提供较小、可定位的证据包。</p></section>`;
    if (item.analysis_progress?.state === 'source_error') return '<section class="review-rejected"><h3>原件无法分析</h3><p>本次未进行模型审阅，也没有条目上线。请查看下方修改任务书，并让员工修正后重新提交。</p></section>';
    if (status === 'rejected') return `<section class="review-rejected"><h3>已退回</h3><p>${esc(item.decision?.note || '未填写退回原因')}</p></section>`;
    return '';
  }

  function packageAssignmentHtml(item) {
    if (item.status === 'rejected' || item.full_analysis || (item.analysis_reports || []).length || item.analysis_progress?.state === 'source_error') return '';
    if (!packageRows.length) return '<section class="review-decision"><h3>系统工作包</h3><p>暂时无法读取当前工作包，请刷新后再绑定。</p></section>';
    const options = packageRows.map(row => `<option value="${esc(row.id)}"${row.id === item.package_id ? ' selected' : ''}>${esc(row.title)} · ${esc(row.region)} · ${esc(row.id)}</option>`).join('');
    const form = `<section class="review-decision"><h3>系统工作包</h3><p>核对原件后指定工作包。${item.analysis_requested_at ? '改绑后须按最新任务与台账重审。' : ''}</p><form class="owner-package"><label>对应工作包<select name="package_id" required><option value=""${packageNames.has(item.package_id) ? '' : ' selected'}>请选择当前系统工作包</option>${options}</select></label><button type="submit">${item.package_id ? '保存工作包绑定' : '绑定工作包'}</button></form></section>`;
    return item.package_id ? `<details class="review-package"><summary>工作包：${esc(packageNames.get(item.package_id) || item.package_id)} · 调整归属</summary>${form}</details>` : form;
  }

  function detailHtml(item) {
    const status = state(item);
    const group = taskGroup(item);
    const taskRows = items.filter(row => row.id !== item.id && sameTask(item,row)).sort((a,b) => b.created - a.created).slice(0,12);
    const nameRows = items.filter(row => row.id !== item.id && row.submitter?.trim() && row.submitter.trim() === item.submitter?.trim() && !sameTask(item,row)).sort((a,b) => b.created - a.created).slice(0,8);
    return `<div class="review-detail-head"><div><p class="review-eyebrow">${esc(group.kind)} / ${esc(group.title)} · 文件 ${esc(item.id.slice(0,8))}</p><h2 id="review-detail-title">${esc(item.name)}</h2><span class="review-state review-state-${status}">${stateLabel(item)}</span></div><a class="review-download" href="/api/materials/content/${esc(item.id)}" download>下载原件核对 ↓</a></div>
      ${batchHtml(item)}${actionsHtml(item)}${packageAssignmentHtml(item)}
      <dl class="review-facts"><div><dt>任务归属</dt><dd>${esc(group.title)}${group.linked ? '' : '（待确认）'}</dd></div><div><dt>提交人</dt><dd>${esc(item.submitter || '未留称呼')}</dd></div><div><dt>员工自填项目名</dt><dd>${esc(item.project_name || '旧提交 · 未填写')}</dd></div><div><dt>上传时间</dt><dd>${esc(time(item.created))}</dd></div><div><dt>对应工作包编号</dt><dd>${esc(item.package_id || '未指定')}</dd></div><div><dt>文件大小</dt><dd>${esc(size(item.size))}</dd></div></dl>
      <details class="review-related"><summary>${group.linked ? '本工作包的其他提交' : '同名自填项目的其他提交'} · ${taskRows.length} 份</summary><p class="review-metadata">${group.linked ? '跨提交人查看同一系统工作包的记录。' : '员工自填项目名仅帮助查找，不能单独证明属于同一系统任务。'}审阅时请核对最新任务与已上线数据。</p>${taskRows.map(row => `<button type="button" data-related-id="${esc(row.id)}"><span>${esc(time(row.created))} · ${esc(row.submitter || '未留称呼')} · ${esc(row.name)}</span><span class="review-state review-state-${state(row)}">${stateLabel(row)}</span></button>`).join('') || '<p>目前没有其他相关提交。</p>'}</details>
      ${nameRows.length ? `<details class="review-name-history"><summary>同名提交人的其他项目 · ${nameRows.length} 份</summary><p class="review-metadata">姓名只作查找线索，不用于确认身份或任务归属。</p>${nameRows.map(row => `<button type="button" data-related-id="${esc(row.id)}">${esc(time(row.created))} · ${esc(taskGroup(row).title)} · ${esc(row.name)}</button>`).join('')}</details>` : ''}
      <div class="review-context"><div><strong>资料来源</strong><p>${esc(item.source || '未填写')}</p></div><div><strong>提交说明</strong><p>${esc(item.note || '未填写')}</p></div></div>
      <details class="review-integrity"><summary>文件编号与 SHA256 校验</summary><p>文件编号 ${esc(item.id)}<br>SHA256 ${esc(item.sha256)}</p></details>
      ${reportHtml(item)}${feedbackHtml(item)}
      ${item.approval ? `<details class="review-manual"><summary>追加人工反馈</summary><form class="owner-feedback"><label>验收结论<select name="result"><option value="revision_required">需要修改</option><option value="accepted">本次验收通过</option><option value="blocked">暂时受阻</option><option value="ineligible">不符合任务范围</option></select></label><label>反馈内容<textarea name="text" rows="5" maxlength="20000" required></textarea></label><button type="submit">登记反馈</button></form></details>` : ''}`;
  }

  function render() {
    const counts = {pending:0,working:0,done:0,rejected:0};
    items.forEach(item => { if (state(item) in counts) counts[state(item)]++; });
    Object.entries(counts).forEach(([name,value]) => { $('review-count-'+name).textContent = value; });
    $('review-filters').querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
    const query = $('review-search').value.trim().toLocaleLowerCase();
    const visible = items.filter(item => (filter === 'all' || state(item) === filter) && (!query || [item.name,item.submitter,item.project_name,item.id,item.package_id,taskGroup(item).title].some(value => String(value || '').toLocaleLowerCase().includes(query))));
    $('review-visible-count').textContent = `${visible.length} 份`;
    if (!visible.some(item => item.id === selected)) selected = visible[0]?.id || '';
    const grouped = new Map();
    visible.forEach(item => { const group = taskGroup(item); if (!grouped.has(group.key)) grouped.set(group.key,{...group,rows:[]}); grouped.get(group.key).rows.push(item); });
    const groups = [...grouped.values()].sort((a,b) => Math.max(...b.rows.map(row => row.created || 0)) - Math.max(...a.rows.map(row => row.created || 0)));
    $('review-queue-list').innerHTML = visible.length ? groups.map(group => {
      const people = new Set(group.rows.map(row => row.submitter?.trim()).filter(Boolean));
      const rows = group.rows.sort((a,b) => b.created - a.created);
      return `<section class="review-task-group"><div class="review-task-group-head"><small>${esc(group.kind)}</small><h3>${esc(group.title)}</h3><span>${rows.length} 份 · ${people.size} 位提交人</span></div>${rows.map(item => `<button type="button" class="review-queue-item ${item.id === selected ? 'is-selected' : ''}" data-id="${esc(item.id)}" aria-current="${item.id === selected ? 'true' : 'false'}"><span class="review-queue-top"><strong>${esc(item.name)}</strong><span class="review-state review-state-${state(item)}">${stateLabel(item)}</span></span><span class="review-queue-meta">${esc(item.submitter || '未留称呼')} · ${esc(time(item.created))}${hasBatch(item) ? ` · 同批 ${batchRows(item).length} 份` : ''}</span></button>`).join('')}</section>`;
    }).join('') : '<p class="review-queue-empty">当前筛选下没有文件。</p>';
    const item = items.find(row => row.id === selected);
    $('review-detail-content').innerHTML = item ? detailHtml(item) : '<div class="review-empty"><h2 id="review-detail-title">选择一份文件</h2><p>从左侧列表查看原件、分析进度和报告。</p></div>';
    const url = new URL(location.href);
    if (item) url.searchParams.set('id',item.id); else url.searchParams.delete('id');
    history.replaceState(null,'',url);
  }

  async function refresh() {
    try {
      const tasks = fetch('/api/research-tasks', {cache:'no-store'}).then(response => response.ok ? response.json() : null).catch(() => null);
      const response = await fetch('/api/materials', {cache:'no-store'});
      if (!response.ok) throw Error(`无法读取审批列表（HTTP ${response.status}）`);
      const data = await response.json();
      if (!data.can_approve) throw Error('当前账号不是指定审批人，无法查看或处理作业。');
      const taskData = await tasks;
      packageRows = Array.isArray(taskData?.packages) ? taskData.packages : [];
      packageNames = new Map(packageRows.map(row => [row.id,row.title]));
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
    $('review-message').textContent = action === 'assign_package' ? '已绑定系统工作包；已启动的分析会按最新任务重新核对。' : action === 'feedback' ? '反馈已登记，员工可通过回执查看。' : action === 'reject' ? '文件已退回。' : ['approve_and_analyze','start_analysis'].includes(action) ? '已确认分析。合格条目上线后将显示报告。' : '已批准接收。';
    filter = 'all'; selected = item.id;
    await refresh();
    const updated = items.find(row => row.id === item.id);
    if (updated && ['pending','working','done'].includes(state(updated))) filter = state(updated);
    $('review-filters').querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
    render();
  }

  async function reviewBatch(item, note) {
    const rows = analysisRows(item);
    const members = rows.map(row => ({id:row.id,sha256:row.sha256,expected_revision:row.revision}));
    const identity = JSON.stringify({items:members,note});
    if (!batchOperations.has(identity)) batchOperations.set(identity,crypto.randomUUID());
    const payload = recoveryFor(item) || {operation_id:batchOperations.get(identity),action:'approve_and_analyze',note,items:members};
    const response = await fetch('/api/materials/review-batch', {method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'material-intake'},body:JSON.stringify(payload)});
    if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw Error(`整批确认未到达应用，请重试（HTTP ${response.status}）`);
    const result = await response.json();
    if (!response.ok) throw Error(result.error || '批次已变化，请刷新核对后重试');
    $('review-message').textContent = `本批 ${rows.length} 份已确认，正在联合分析。`;
    filter = 'all'; selected = item.id;
    await refresh();
    filter = state(items.find(row => row.id === item.id) || item);
    render();
  }

  $('review-queue-list').addEventListener('click', event => { const row = event.target.closest('[data-id]'); if (!row) return; selected = row.dataset.id; render(); if (matchMedia('(max-width: 700px)').matches) $('review-detail-content').scrollIntoView({block:'start'}); });
  $('review-detail-content').addEventListener('click', async event => {
    const related = event.target.closest('[data-related-id]');
    if (related) { selected = related.dataset.relatedId; filter = 'all'; render(); return; }
    const button = event.target.closest('[data-action], [data-batch-action]'); if (!button) return;
    const item = items.find(row => row.id === selected); if (!item) return;
    const note = $('review-detail-content').querySelector('.decision-note')?.value.trim() || '';
    button.disabled = true;
    try {
      if (button.dataset.batchAction) await reviewBatch(item,note);
      else await review(item,button.dataset.action,{note});
    }
    catch (error) { $('review-message').textContent = error.message; button.disabled = false; }
  });
  $('review-detail-content').addEventListener('submit', async event => {
    const form = event.target; if (!form.matches('.owner-feedback, .owner-package')) return;
    event.preventDefault(); const item = items.find(row => row.id === selected); if (!item) return;
    const button = form.querySelector('button'); button.disabled = true;
    try {
      if (form.matches('.owner-package')) await review(item,'assign_package',{package_id:form.elements.package_id.value});
      else await review(item,'feedback',{result:form.elements.result.value,text:form.elements.text.value.trim()});
    }
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
