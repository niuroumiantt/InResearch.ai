/* One account, one submission history; shared work-package instructions remain authoritative. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time = value => value ? new Date(value * 1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}) : '—';
  let initial = true, request = 0;
  const phase = item => {
    if (item.status === 'rejected') return '已退回 · 请补充';
    if (item.analysis_progress?.state === 'source_error') return '原件需修正 · 尚未审阅';
    if (item.analysis_scope?.mode === 'sampled_native_cells') return '已有抽样反馈 · 全文待审';
    if (item.analysis_scope?.mode === 'full_native_campus') return item.analysis_scope.state === 'completed' ? '全表原生文本已审阅' : '全表审阅中';
    if (item.analysis_state === 'completed') return '已有处理反馈';
    if (item.analysis_progress?.state === 'blocked') return '处理受阻';
    if (item.analysis_progress) return '分析中';
    return {pending_approval:'等待审批',queued:'等待审批',approved:'已确认 · 等待接收',archived:'已接收 · 等待分析'}[item.status] || '已收到';
  };
  function openPackage(id) {
    window.dispatchEvent(new CustomEvent('research-task-view-requested',{detail:{view:'submission-progress'}}));
    window.dispatchEvent(new CustomEvent('research-package-requested',{detail:{packageId:id}}));
  }
  async function load() {
    const current = ++request;
    try {
      const response = await fetch('/api/project-work',{cache:'no-store'});
      if (!response.ok) throw Error(response.status === 401 ? '请先登录，再提交和查看自己的工作。' : '项目权限暂时无法确认，请重新登录或刷新。');
      const data = await response.json();
      if (current !== request) return;
      window.projectWorkState = data;
      $('my-work-tab').hidden = false;
      $('task-home-tab').textContent = '团队进展';
      $('my-identity').textContent = `${data.display_name} · ${data.project.title}`;
      $('my-status').textContent = data.member ? `权限${data.expires_at ? '有效至 '+new Date(data.expires_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间）' : '已开通'} · 本页更新于 ${time(Date.now()/1000)}（北京时间）` : '你尚未获此项目授权，或授权已到期。请联系项目负责人。';
      $('my-review-link').hidden = !data.can_approve;
      $('my-access-link').hidden = !data.can_manage;
      $('my-front-link').hidden = !data.frontend;
      const packages = data.packages.filter(p=>p.can_submit);
      $('my-packages').innerHTML = packages.length ? packages.map(p=>`<div class="project-work-row"><strong>${esc(p.title)}</strong><button type="button" data-open-package="${esc(p.id)}">查看共同进展与提交 →</button></div>`).join('') : '<p>暂无分配给你的提交工作包。</p>';
      const labels = Object.fromEntries(data.packages.map(p=>[p.id,p.title]));
      $('my-submissions').innerHTML = data.items.length ? data.items.map(item=>`<article class="project-work-row"><div><strong>${esc(item.name)}</strong><p>${esc(labels[item.package_id] || '工作包')} · ${esc(phase(item))} · 已返回上线回执 ${item.published_sources || 0} 条</p><small>提交于 ${esc(time(item.created))}（北京时间）</small>${item.decision?.action === 'reject' ? `<p>${esc(item.decision.note)}</p>` : ''}${item.feedback?.length ? `<details><summary>本次提交的处理反馈（历史记录）</summary><p class="project-feedback">${esc(item.feedback[0].text)}</p></details>` : ''}</div><div class="project-row-actions"><a href="/api/materials/content/${encodeURIComponent(item.id)}">下载原件</a><button type="button" data-open-package="${esc(item.package_id)}">查看现行下一步 →</button></div></article>`).join('') : '<p>尚无绑定此账号的提交。旧匿名材料不会按同名自动归入。</p>';
      const form = $('task-upload-form');
      form.hidden = !packages.length;
      form.elements.submitter.value = data.display_name;
      $('project-login-note').textContent = packages.length ? `以 ${data.display_name} 的账号提交，姓名自动记录。` : '当前没有可提交的工作包，请联系负责人授权。';
      window.dispatchEvent(new CustomEvent('project-work-loaded',{detail:data}));
      if (initial && !location.hash) window.dispatchEvent(new CustomEvent('research-task-view-requested',{detail:{view:'my-work'}}));
      initial = false;
    } catch (error) {
      if (current !== request) return;
      $('task-upload-form').hidden = true;
      $('my-submissions').textContent = '';
      $('my-packages').textContent = '';
      $('my-status').textContent = error.message;
      $('project-login-note').innerHTML = `${esc(error.message)} <a href="/login">登录 →</a>`;
    }
  }
  $('my-work').addEventListener('click',event=>{
    const button = event.target.closest('[data-open-package]');
    if (button) openPackage(button.dataset.openPackage);
  });
  $('my-refresh').addEventListener('click',load);
  window.addEventListener('project-work-refresh',load);
  load();
})();
