/* Explicit site shell. Page bodies declare section and responsive panels. */
(() => {
  'use strict';
  const root = document.documentElement;
  const {getState, setPreference} = window.InresearchUI;
  function apply(state = getState()) {
    document.querySelectorAll('[data-ui-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.uiChoice === state.skin)));
    const select = document.getElementById('ui-appearance');
    if (select) select.value = state.mode;
    const note = document.getElementById('ui-save-status');
    if (note) note.textContent = state.saved === false ? '本页有效，偏好未保存' : '';
  }
  window.addEventListener('inresearch:appearance', event => apply(event.detail));
  // Original project icons: two geometries, no remote icon fonts or brand assets.
  const icons = {
    home: ['<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>', '<path d="M3 21V9l9-7 9 7v12H3Z M9 21v-9h6v9"/>'],

  };
  function icon(name) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    el.setAttribute('viewBox', '0 0 24 24'); el.setAttribute('aria-hidden', 'true'); el.setAttribute('class', 'ui-icon');
    el.innerHTML = '<g class="ui-icon-attio">' + icons[name][0] + '</g><g class="ui-icon-folk">' + icons[name][1] + '</g>';
    return el;
  }
  function navigation(section) {
    const nav = document.createElement('nav');
    nav.className = 'ui-navigation'; nav.setAttribute('aria-label', '全站导航');
    const links = [
      ['overview', '总览', '/index.html'], ['research', '研究', '/research.html'],
      ['materials', '资料', '/materials.html'], ['tasks', '任务', '/team.html'],
      ['reports', '成果', '/report.html'], ['admin', '管理', '/ops.html']
    ];
    function render(role) {
      nav.replaceChildren();
      for (const [id, label, href] of links) {
        if (id === 'admin' && role !== 'admin' || role === 'intern' && id !== 'tasks') continue;
        const link = document.createElement('a');
        link.href = href; link.textContent = label;
        if (id === section) link.setAttribute('aria-current', 'page');
        nav.append(link);
      }
    }
    render('member');
    fetch('/api/whoami').then(response => response.ok ? response.json() : null)
      .then(user => { if (user?.role) render(user.role); }).catch(() => {});
    return nav;
  }
  function mount() {
    const host = document.querySelector('inresearch-shell');
    if (!host || document.getElementById('ui-skinbar')) return;
    const bar = document.createElement('div'); bar.id = 'ui-skinbar'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', '全站外观');
    const brand = document.createElement('a'); brand.href = '/index.html'; brand.className = 'ui-home'; brand.append(icon('home'), document.createTextNode('inresearch.ai'));
    bar.append(brand);
    if (host.dataset.section !== 'auth') bar.append(navigation(host.dataset.section));
    const group = document.createElement('div'); group.className = 'ui-skin-choices'; group.setAttribute('role', 'group'); group.setAttribute('aria-label', '视觉风格');
    for (const [value, label] of [['attio', 'Attio'], ['folk', 'folk']]) {
      const button = document.createElement('button'); button.type = 'button'; button.dataset.uiChoice = value;
      button.textContent = label; button.addEventListener('click', () => setPreference({skin: value})); group.append(button);
    }
    const controls = document.createElement('div'); controls.className = 'ui-appearance-controls';
    controls.append(group); bar.append(controls);
    const label = document.createElement('label'); label.htmlFor = 'ui-appearance'; label.textContent = '外观';
    const select = document.createElement('select'); select.id = 'ui-appearance';
    for (const [value, text] of [['light', '浅色'], ['dark', '深色'], ['system', '跟随系统']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option);
    }
    select.addEventListener('change', () => setPreference({mode: select.value})); label.append(select); controls.append(label);
    const note = document.createElement('span'); note.id = 'ui-save-status'; note.setAttribute('role', 'status'); controls.append(note);
    host.append(bar);
    const measure = () => root.style.setProperty('--ui-bar-height', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    if (window.ResizeObserver) new ResizeObserver(measure).observe(bar);
    measure();
    const phone = matchMedia('(max-width:700px)');
    const compact = () => document.querySelectorAll('[data-responsive-panel]').forEach(panel => { panel.open = !phone.matches; });
    compact(); phone.addEventListener('change', compact);
    apply();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true}); else mount();
})();
