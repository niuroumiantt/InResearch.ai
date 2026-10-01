/* 采集页的目标表：六队卡、五系统 × 五类热图、目标行表与派工（读 /api/targets，服务端已按角色过滤）。
   目标表是唯一任务书；行 ID 与节点页双向链接（点行回节点页停在该列）。 */
(() => {
  'use strict';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const STATUS = {sourced: '已有', assumed: '假设', delivered: '已交付', needed: '缺'};
  const CLASSES = {1: '构成', 2: '运行', 3: '价格', 4: '时间', 5: '主体'};
  const TOP = [['facility', '设施'], ['power', '电力'], ['thermal', '冷却'], ['it', 'IT'], ['control', '控制与软件'], ['site', '站点权利'], ['root', '因子（根）']];
  const state = {filters: {team: '', col: '', status: '', system: '', q: '', mine: ''}, data: null, bom: null, host: null, dialog: null};
  const params = new URLSearchParams(location.search);
  for (const k of ['team', 'col', 'status', 'mine', 'node', 'q']) if (params.get(k)) state.filters[k] = params.get(k);

  function topSystem(row) {
    if (row.site_right_id) return 'site';
    if (!row.part_id) return 'root';
    const part = state.bom?.parts?.find(p => p.id === row.part_id);
    if (!part) return 'root';
    const sys = state.bom.systems[part.system] || {};
    return sys.parent || part.system;
  }
  function nodeHref(row) { return 'node.html?' + new URLSearchParams(row.node === 'root' ? {col: row.variable_class} : {id: row.node, col: row.variable_class}); }
  function due(row) { return row.team_state === 'not_connected' ? '<span class="muted">待建队</span>' : esc(row.next_due || ''); }

  function teamCards(rows) {
    const teams = state.data.teams || {};
    return Object.keys(teams).sort().map(id => {
      const mine = rows.filter(r => r.team === id);
      const needed = mine.filter(r => r.status === 'needed').length, delivered = mine.filter(r => r.status === 'delivered').length;
      const connected = mine.some(r => r.team_state === 'connected');
      const next = mine.filter(r => r.next_due && r.status !== 'sourced').map(r => r.next_due).sort()[0];
      const last = mine.map(r => r.assignment?.delivery?.at).filter(Boolean).sort().pop();
      return `<button type="button" class="team-card" data-team="${esc(id)}" aria-pressed="${state.filters.team === id}"><strong>${esc(teams[id].name || id)}</strong><small>${connected ? '已接入' : '待建队'} · ${mine.length} 行 · 缺 ${needed}${delivered ? ' · 已交付 ' + delivered : ''}</small><small>最近交付 ${esc(last || '—')} · 下一到期 ${esc(next || (connected ? '—' : '待建队'))}</small></button>`;
    }).join('');
  }
  function heatmap(rows) {
    const cell = (sys, col) => {
      const hit = rows.filter(r => topSystem(r) === sys && String(r.variable_class) === col);
      const needed = hit.filter(r => r.status === 'needed').length;
      return `<td class="heat ${needed ? 'needed' : hit.length ? 'covered' : ''}" data-system="${sys}" data-col="${col}" title="${hit.length} 行，缺 ${needed}">${hit.length ? `${needed}<small>/${hit.length}</small>` : '·'}</td>`;
    };
    return `<table class="heat"><thead><tr><th>缺 / 行</th>${Object.entries(CLASSES).map(([n, name]) => `<th>${n} ${name}</th>`).join('')}</tr></thead><tbody>${TOP.map(([id, name]) => `<tr><th>${name}</th>${Object.keys(CLASSES).map(col => cell(id, col)).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function cardsCell(cards) {
    // Git 内事件卡：原件指针 + 随交付带来的已审阅参数（厂商原文，不换算；单位与条件照映射记录）
    return cards.map(c => {
      const host = (() => { try { return new URL(c.origin_pointer).hostname.replace(/^www\./, ''); } catch (e) { return c.origin_pointer; } })();
      const link = c.pointer_kind === 'url' ? `<a href="${esc(c.origin_pointer)}" rel="noopener" target="_blank">${esc(host)}</a>` : `<code>${esc(c.origin_pointer)}</code>`;
      const params = c.parameters || [];
      const list = params.length ? `<details><summary>${params.length} 个参数</summary><ul class="params">${params.map(p =>
        `<li title="${esc(p.condition || '')}"><code>${esc(p.parameter_name)}</code> ${esc(p.value)}${p.unit ? ` <small>[${esc(p.unit)}]</small>` : ''}${p.condition ? `<small>${esc(p.condition)}</small>` : ''}</li>`).join('')}</ul></details>` : '';
      return `${link}<small>${esc(c.delivered_at || '')} · 事件卡</small>${list}`;
    }).join('');
  }
  function table(rows) {
    const canWrite = state.data.role !== 'reader';
    return `<div class="tscroll"><table class="targets"><thead><tr><th>目标行</th><th>节点 · 列</th><th>队 / 主机</th><th>状态</th><th>到期</th><th>负责人 / 派工</th><th>交付</th>${canWrite ? '<th></th>' : ''}</tr></thead><tbody>${rows.map(r => {
      const a = r.assignment || {};
      return `<tr data-id="${esc(r.id)}"><td><code>${esc(r.id)}</code><small>${esc(r.disclosure_type)} × ${esc(r.publisher_category)}</small></td><td><a href="${nodeHref(r)}">${esc(r.node === 'root' ? '根' : r.node)}</a> · ${r.variable_class} ${CLASSES[r.variable_class]}</td><td>${esc(r.team)} / ${esc(r.host)}${r.team_state === 'not_connected' ? '<small>待建队</small>' : ''}</td><td><span class="st st-${esc(r.status)}">${STATUS[r.status] || esc(r.status)}</span>${r.sourced_by ? `<small>${r.sourced_by === 'registry' ? '人工登记' : '队交付'}</small>` : ''}</td><td>${due(r)}</td><td>${a.assignee ? `${esc(a.assignee)}<small>${esc(a.status || '')}${a.due ? ' · ' + esc(a.due) : ''}</small>` : '<span class="muted">未派</span>'}</td><td>${(r.cards || []).length ? cardsCell(r.cards) : a.delivery ? `<a href="${esc(a.delivery.evidence_path)}">${esc(a.delivery.evidence_path)}</a><small>${esc(a.delivery.at)} · 运行库有${r.status === 'delivered' ? '' : ' / Git 无'}</small>` : '<span class="muted">—</span>'}</td>${canWrite ? `<td><button type="button" data-assign="${esc(r.id)}">派工</button> <button type="button" data-deliver="${esc(r.id)}">登记交付</button></td>` : ''}</tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function filtered() {
    const f = state.filters, q = f.q.trim().toLowerCase();
    return state.data.targets.filter(r => (!f.team || r.team === f.team) && (!f.col || String(r.variable_class) === f.col) && (!f.status || r.status === f.status)
      && (!f.system || topSystem(r) === f.system) && (!q || (r.id + ' ' + r.disclosure_type + ' ' + r.publisher_category + ' ' + (r.assignment?.assignee || '')).toLowerCase().includes(q)));
  }
  function draw() {
    const host = state.host; if (!host || !state.data) return;
    const rows = filtered(), all = state.data.targets;
    const c = state.data.counts?.by_status || {};
    host.innerHTML = `<div class="targets-head"><h2>目标表 · 唯一任务书 <small class="muted">${state.data.version} · ${esc(state.data.updated)}</small></h2>
      <p class="muted">${state.data.mine ? `只显示分配给 ${esc(state.data.user || '你')} 的行（服务端过滤）。` : `全部 ${state.data.total} 行：已有 ${c.sourced || 0} · 假设 ${c.assumed || 0} · 已交付 ${c.delivered || 0} · 缺 ${c.needed || 0}。`}采集需求只来自这张表，各队不自定抓什么；点行进入节点页停在该列。</p></div>
      <div class="team-cards" id="team-cards">${teamCards(all)}</div>
      <div class="heat-wrap"><h3>缺 / 行 · 五系统 × 五类</h3>${heatmap(all)}</div>
      <form class="filters" id="target-filters" onsubmit="return false"><label>队<select name="team"><option value="">全部</option>${Object.keys(state.data.teams || {}).sort().map(t => `<option ${state.filters.team === t ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label>
        <label>类<select name="col"><option value="">全部</option>${Object.entries(CLASSES).map(([n, name]) => `<option value="${n}" ${state.filters.col === n ? 'selected' : ''}>${n} ${name}</option>`).join('')}</select></label>
        <label>系统<select name="system"><option value="">全部</option>${TOP.map(([id, name]) => `<option value="${id}" ${state.filters.system === id ? 'selected' : ''}>${name}</option>`).join('')}</select></label>
        <label>状态<select name="status"><option value="">全部</option>${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${state.filters.status === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
        <label>搜索<input name="q" value="${esc(state.filters.q)}" placeholder="行 ID、出版方、负责人"></label>
        ${state.data.role === 'intern' ? '' : `<label><input type="checkbox" name="mine" ${state.filters.mine === '1' ? 'checked' : ''}> 只看我的</label>`}
        <span class="muted" id="target-count">${rows.length} / ${all.length} 行</span></form>
      ${table(rows.slice(0, 400))}${rows.length > 400 ? `<p class="muted">只显示前 400 行，请收窄筛选。</p>` : ''}`;
    host.querySelectorAll('[data-team]').forEach(b => b.onclick = () => { state.filters.team = state.filters.team === b.dataset.team ? '' : b.dataset.team; draw(); });
    host.querySelectorAll('td.heat').forEach(td => td.onclick = () => { state.filters.system = td.dataset.system; state.filters.col = td.dataset.col; draw(); });
    const form = host.querySelector('#target-filters');
    form.addEventListener('input', () => {
      for (const k of ['team', 'col', 'system', 'status', 'q']) state.filters[k] = form.elements[k].value;
      const mine = form.elements.mine;
      if (mine && (mine.checked ? '1' : '') !== state.filters.mine) { state.filters.mine = mine.checked ? '1' : ''; load(); return; }
      draw();
    });
    host.querySelectorAll('[data-assign]').forEach(b => b.onclick = () => openDialog('assign', b.dataset.assign));
    host.querySelectorAll('[data-deliver]').forEach(b => b.onclick = () => openDialog('deliver', b.dataset.deliver));
  }
  function ensureDialog() {
    if (state.dialog) return state.dialog;
    const d = document.createElement('dialog'); d.id = 'target-dialog';
    d.innerHTML = `<form method="dialog" id="target-form"><h3 id="td-title"></h3><p class="muted" id="td-row"></p>
      <div id="td-assign"><label>负责人<input name="assignee" maxlength="60"></label><label>状态<select name="status"><option>已派</option><option>进行中</option><option>已交付</option><option>已合并</option><option>已放弃</option></select></label><label>到期<input name="due" placeholder="YYYY-MM-DD"></label></div>
      <div id="td-deliver" hidden><label>证据路径或 URL<input name="evidence_path" placeholder="docs/... 或 https://..." maxlength="500"></label><p class="muted">这是运行库的指针；进入 delivered 要有 Git 内载体（资料计划、事件卡或带 target_id 的价格记录）。</p></div>
      <label>备注<input name="note" maxlength="500"></label><p class="msg" id="td-msg" role="status"></p>
      <div class="row"><button type="button" id="td-cancel">取消</button><button type="submit" id="td-ok">保存</button></div></form>`;
    document.body.append(d); state.dialog = d;
    d.querySelector('#td-cancel').onclick = () => d.close();
    return d;
  }
  function openDialog(kind, id) {
    const d = ensureDialog(), row = state.data.targets.find(r => r.id === id) || {}, a = row.assignment || {}, form = d.querySelector('#target-form');
    d.querySelector('#td-title').textContent = kind === 'assign' ? '派工 · 按目标行' : '登记交付 · 按目标行';
    d.querySelector('#td-row').textContent = `${id} · ${row.disclosure_type || ''} · ${row.team || ''}`;
    d.querySelector('#td-assign').hidden = kind !== 'assign'; d.querySelector('#td-deliver').hidden = kind !== 'deliver';
    form.elements.assignee.value = a.assignee || (state.data.role === 'intern' ? state.data.user || '' : '');
    form.elements.assignee.readOnly = state.data.role === 'intern';
    form.elements.status.value = a.status || '已派'; form.elements.due.value = a.due || ''; form.elements.note.value = ''; form.elements.evidence_path.value = a.delivery?.evidence_path || '';
    d.querySelector('#td-msg').textContent = '';
    form.onsubmit = async e => {
      e.preventDefault();
      const body = kind === 'assign'
        ? {target_id: id, assignee: form.elements.assignee.value.trim(), status: form.elements.status.value, due: form.elements.due.value.trim(), note: form.elements.note.value.trim()}
        : {target_id: id, evidence_path: form.elements.evidence_path.value.trim(), note: form.elements.note.value.trim()};
      const msg = d.querySelector('#td-msg');
      try {
        const r = await fetch(kind === 'assign' ? '/api/assign' : '/api/deliver', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        const out = await r.json();
        msg.textContent = out.ok ? out.msg : out.error;
        if (out.ok) { await load(); setTimeout(() => d.close(), 600); }
      } catch (err) { msg.textContent = '写入失败：' + err.message; }
    };
    d.showModal();
  }
  async function load() {
    const host = state.host; if (!host) return;
    const q = new URLSearchParams();
    if (state.filters.mine === '1') q.set('mine', '1');
    if (state.filters.node) q.set('node', state.filters.node);
    try {
      const [t, bom] = await Promise.all([fetch('/api/targets?' + q, {cache: 'no-store'}), state.bom ? null : fetch('/framework/bom.json', {cache: 'no-store'})]);
      if (!t.ok) throw Error(t.status === 401 ? '目标表与派工登录后可见。' : '目标表暂不可读取');
      state.data = await t.json();
      if (bom && bom.ok) state.bom = await bom.json();
      draw();
    } catch (err) { host.innerHTML = `<p class="muted">${esc(err.message)}</p>`; }
  }
  window.InresearchTargets = {mount(host) { state.host = host; if (!state.data) load(); else draw(); }, reload: load, state};
})();
