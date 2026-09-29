/* 采集页「研究问题任务」标签：/api/tasks 的任务（开放的研究问题 + 兼容工单）与派工（/api/assign，按 workorder_id 兼容）。
   原 team.html 并入（2026-09-28）：任务按骨架节点分组，不再按兼容模块；模块盲区统计退役。 */
(() => {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const $ = id => document.getElementById(id);
  let ORDERS = [], ASSIGN = {}, nodeFilter = '', canWrite = true, loaded = false, curWid = null;
  const rank = {P1: 0, P2: 1, P3: 2};

  async function load() {
    const sub = $('tk-sub'); if (!sub) return;
    try {
      const r = await fetch('/api/tasks', {cache: 'no-store'});
      if (!r.ok) throw Error(r.status === 401 ? '任务登录后可见' : '任务暂不可用');
      const wo = await r.json();
      ORDERS = wo.orders || [];
      ASSIGN = Object.fromEntries(ORDERS.filter(o => o.assignment).map(o => [o.wid, o.assignment]));
      sub.textContent = `任务 ${ORDERS.length} 项 ｜ 队列生成于 ${wo.generated} ｜ 开放的研究问题按骨架节点分组；兼容工单只作兼容任务，不决定新问题是否可派`;
      const whos = [...new Set(Object.values(ASSIGN).map(a => a.assignee).filter(Boolean))].sort();
      $('tk-fwho').innerHTML = '<option value="">全部负责人</option>' + whos.map(w => `<option>${esc(w)}</option>`).join('');
      const sts = [...new Set(Object.values(ASSIGN).map(a => a.status).filter(Boolean))].sort();
      $('tk-fst').innerHTML = '<option value="">全部状态</option><option value="未派">未派</option>' + sts.map(s => `<option>${esc(s)}</option>`).join('');
      loaded = true; draw();
    } catch (e) { sub.textContent = e.message; }
  }
  function nodeOf(o) { return o.node || (o.object_ids && o.object_ids[0]) || 'root'; }
  function drawTotals() {
    const assigned = ORDERS.filter(o => ASSIGN[o.wid]).length;
    const done = ORDERS.filter(o => ['已交付', '已合并'].includes(ASSIGN[o.wid]?.status)).length;
    const questions = ORDERS.filter(o => o.kind === '研究问题开放').length;
    $('tk-tot').innerHTML = [['任务总数', ORDERS.length], ['开放研究问题', questions], ['兼容工单', ORDERS.length - questions], ['已派', assigned], ['未派', ORDERS.length - assigned], ['已交付/合并', done]]
      .map(([k, v]) => `<div class="plan-card"><strong>${v}</strong><small>${k}</small></div>`).join('');
    const groups = {};
    for (const o of ORDERS) { const n = nodeOf(o); groups[n] = (groups[n] || 0) + 1; }
    const top = Object.entries(groups).sort((a, b) => b[1] - a[1]).slice(0, 24);
    $('tk-nodes').innerHTML = top.map(([n, c]) => `<button type="button" class="team-card" data-node="${esc(n)}" aria-pressed="${nodeFilter === n}"><strong>${esc(n === 'root' ? '根（未挂具体节点）' : n)}</strong><small>${c} 项</small></button>`).join('');
    $('tk-nodes').querySelectorAll('[data-node]').forEach(b => b.onclick = () => { nodeFilter = nodeFilter === b.dataset.node ? '' : b.dataset.node; draw(); });
  }
  function draw() {
    if (!loaded) return;
    drawTotals();
    const q = $('tk-q').value.trim().toLowerCase(), fp = $('tk-fpri').value, fs = $('tk-fst').value, fw = $('tk-fwho').value, scope = $('tk-fscope').value;
    const view = ORDERS.filter(o => {
      const a = ASSIGN[o.wid];
      if (scope === 'assignable' && (o.brief || '').startsWith('【这条不派给实习生】')) return false;
      if (nodeFilter && nodeOf(o) !== nodeFilter) return false;
      if (fp && o.pri !== fp) return false;
      if (fs === '未派' ? a : fs && a?.status !== fs) return false;
      if (fw && a?.assignee !== fw) return false;
      if (q && !(o.wid + ' ' + o.gap + ' ' + o.kind + ' ' + nodeOf(o) + ' ' + (a?.assignee || '')).toLowerCase().includes(q)) return false;
      return true;
    }).sort((a, b) => (rank[a.pri] ?? 9) - (rank[b.pri] ?? 9) || nodeOf(a).localeCompare(nodeOf(b)));
    $('tk-cnt').textContent = `${view.length} / ${ORDERS.length} 项`;
    $('tk-table').innerHTML = `<tr><th style="width:110px">任务号</th><th style="width:38px">级</th><th style="width:120px">类型</th><th style="width:150px">节点 · 类</th><th>任务说明</th><th style="width:96px">负责人</th><th style="width:74px">状态</th>${canWrite ? '<th style="width:60px"></th>' : ''}</tr>` +
      view.slice(0, 400).map(o => {
        const a = ASSIGN[o.wid] || {}, internal = (o.brief || '').startsWith('【这条不派给实习生】'), n = nodeOf(o);
        return `<tr class="${internal ? 'internal' : ''}"><td class="wid">${esc(o.wid)}${internal ? '<div class="badge-int">内部</div>' : ''}</td><td><span class="pri ${esc(o.pri)}">${esc(o.pri)}</span></td><td>${esc(o.kind)}</td><td><a href="node.html?${new URLSearchParams(n === 'root' ? {} : {id: n})}">${esc(n)}</a>${o.variable_class ? ` · ${o.variable_class}` : ''}</td><td>${o.brief ? `<div class="brief">${esc(o.brief).replace(/【(.+?)】/g, '<b>【$1】</b>')}</div>` : `<div class="gap">${esc(o.gap)}</div>`}</td><td>${esc(a.assignee || '')}</td><td>${a.status ? `<span class="st st-${esc(a.status)}">${esc(a.status)}</span>` : ''}</td>${canWrite ? `<td><button type="button" data-w="${esc(o.wid)}">派工</button></td>` : ''}</tr>`;
      }).join('');
    $('tk-table').querySelectorAll('button[data-w]').forEach(b => b.onclick = () => openDlg(b.dataset.w));
  }
  function openDlg(wid) {
    curWid = wid;
    const o = ORDERS.find(x => x.wid === wid) || {}, a = ASSIGN[wid] || {};
    $('tk-d-wid').textContent = `${wid}　${nodeOf(o)}`;
    $('tk-d-gap').innerHTML = o.brief ? `<div class="brief">${esc(o.brief).replace(/【(.+?)】/g, '<b>【$1】</b>')}</div>` : esc(o.gap || '');
    $('tk-d-who').value = a.assignee || ''; $('tk-d-st').value = a.status || '已派'; $('tk-d-due').value = a.due || ''; $('tk-d-note').value = a.note || '';
    $('tk-d-msg').className = 'msg'; $('tk-d-msg').textContent = '';
    $('tk-dlg').showModal();
  }
  function bind() {
    $('tk-d-cancel').onclick = () => $('tk-dlg').close();
    $('tk-d-ok').onclick = async () => {
      const msg = $('tk-d-msg');
      const body = {workorder_id: curWid, assignee: $('tk-d-who').value.trim(), status: $('tk-d-st').value, due: $('tk-d-due').value.trim(), note: $('tk-d-note').value.trim()};
      try {
        const r = await fetch('/api/assign', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then(r => r.json());
        msg.className = 'msg ' + (r.ok ? 'ok' : 'no'); msg.textContent = r.ok ? r.msg : r.error;
        if (r.ok) { ASSIGN[curWid] = {...(ASSIGN[curWid] || {}), ...body}; draw(); setTimeout(() => $('tk-dlg').close(), 700); }
      } catch (e) { msg.className = 'msg no'; msg.textContent = '写入失败：' + e.message; }
    };
    ['tk-q', 'tk-fpri', 'tk-fst', 'tk-fwho', 'tk-fscope'].forEach(id => $(id).addEventListener(id === 'tk-q' ? 'input' : 'change', draw));
  }
  let bound = false;
  window.InresearchTasks = {mount(role) { canWrite = role !== 'reader'; if (!bound) { bind(); bound = true; } load(); }, reload: load};
})();
