/* Daily Python job status; the same administrator gate protects its JSON. */
(async function () {
  const box = document.createElement('p');
  box.className = 'repo-note';
  box.setAttribute('role', 'status');
  document.querySelector('.repo-wrap h1').after(box);
  try {
    const response = await fetch('/admin/repo-content/job-status.json', {cache:'no-store'});
    if (!response.ok) throw new Error('unavailable');
    const status = await response.json();
    const time = value => value ? new Date(value).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '未完成';
    const stale = !status.last_success_at || Date.now()-Date.parse(status.last_success_at)>36*3600000;
    box.textContent = '系统定时更新 · 每日北京时间 0:00 · 上次完成：'+time(status.last_success_at);
    if (status.state === 'failed') box.textContent += ' · 最近更新失败，保留上次结果：'+(status.error||'请查看系统日志');
    else if (status.state === 'running') box.textContent += ' · 正在更新（开始：'+time(status.started_at)+'）';
    if (stale) box.textContent += ' · 更新结果已过期或尚未完成';
  } catch (_) {
    box.textContent = '系统每日北京时间 0:00 更新；任务状态暂时未取得，当前页面保留所标日期的结果。';
  }
})();
