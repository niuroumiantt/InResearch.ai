/* 采集页「规格批次」标签：NVIDIA 产品资料验证链路的进度（/api/pilot-progress/nvidia，候选、未采用）。原 nvidia-pilot.html 并入（2026-09-28）。 */
(() => {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let mounted = false, timer = null;
  async function load() {
    const status = document.getElementById('pilot-status'); if (!status) return;
    try {
      const r = await fetch('/api/pilot-progress/nvidia', {cache: 'no-store'});
      if (!r.ok) throw Error(r.status === 403 ? '规格批次进度只对内部成员开放' : '线上状态暂不可读取');
      const d = await r.json();
      if (!d.available) { status.textContent = '等待 M5 首次推送进度。'; return; }
      const c = d.counts || {};
      status.textContent = `最近更新：${d.generated || '未知'} · 接收于 ${d.received_at || '未知'} · 来源：M5 Claude Code CLI · 状态：候选（未采用）`;
      document.getElementById('pilot-metrics').innerHTML = [['本轮阅读总数', d.documents_total ?? '—'], ['完整候选', c.complete ?? 0], ['阻塞', c.blocked ?? 0], ['失败', c.failed ?? 0]]
        .map(([k, v]) => `<div class="plan-card"><strong>${esc(v)}</strong><small>${esc(k)}</small></div>`).join('');
      document.getElementById('pilot-documents').innerHTML = (d.documents || []).map(x => `<article class="task"><strong>${esc(x.title || x.id)}</strong><br><small>阅读覆盖：${esc(x.coverage?.pages_read ?? '?')} / ${esc(x.coverage?.pages_total ?? '?')} 页 · 范围：${x.coverage?.scope === 'pdf_native_text_only' ? '正文阅读 · 图片未读' : (x.coverage?.complete ? '全文处理完成' : '尚未完成')}</small>${x.source_url ? `<br><a href="${esc(x.source_url)}" target="_blank" rel="noopener">官方来源</a>` : ''}</article>`).join('') || '<p class="muted">当前无可展示候选</p>';
    } catch (e) { status.textContent = e.message; }
  }
  window.InresearchPilot = {
    mount() { load(); if (!mounted) { mounted = true; timer = setInterval(() => { if (!document.getElementById('pilot-panel')?.hidden) load(); }, 60000); } },
    reload: load,
  };
})();
