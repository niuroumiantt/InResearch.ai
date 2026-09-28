/* Explicit site shell. Page bodies declare section and responsive panels. */
(() => {
  'use strict';
  const root = document.documentElement;
  const {getState, setPreference} = window.InresearchUI;
  function apply(state = getState()) {
    const select = document.getElementById('ui-appearance');
    if (select) select.value = state.mode;
    const note = document.getElementById('ui-save-status');
    if (note) note.textContent = state.saved === false ? '本页有效，偏好未保存' : '';
  }
  window.addEventListener('inresearch:appearance', event => apply(event.detail));
  // Original project icons: one line geometry, no remote icon fonts or brand assets.
  const icons = {home: '<path d="M3 21V9l9-7 9 7v12H3Z M9 21v-9h6v9"/>'};
  function icon(name) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    el.setAttribute('viewBox', '0 0 24 24'); el.setAttribute('aria-hidden', 'true'); el.setAttribute('class', 'ui-icon');
    el.innerHTML = icons[name];
    return el;
  }
  // 一级导航是四问的全局视图（05「目录」）：六项按角色出现；页面用 data-section 说自己属于哪一项。
  // reader 是公开只读，不登录即是；实习生只见采集入口（目标表与研究问题任务）。
  const LINKS = [
    ['datacenter', '数据中心', '/'], ['ledger', '账本', '/ledger.html'], ['bom', '爆炸图', '/bom.html'],
    ['acquisition', '采集', '/supply.html'], ['results', '成果', '/report.html'], ['admin', '管理', '/ops.html']
  ];
  const VISIBLE = {
    admin: ['datacenter', 'ledger', 'bom', 'acquisition', 'results', 'admin'],
    member: ['datacenter', 'ledger', 'bom', 'acquisition', 'results'],
    intern: ['acquisition'],
    reader: ['datacenter', 'ledger', 'bom', 'results']
  };
  function navigation(section) {
    const nav = document.createElement('nav');
    nav.className = 'ui-navigation'; nav.setAttribute('aria-label', '全站导航');
    function render(role) {
      nav.replaceChildren();
      const visible = VISIBLE[role] || VISIBLE.member;
      for (const [id, label, href] of LINKS) {
        if (!visible.includes(id)) continue;
        const link = document.createElement('a');
        link.href = href; link.textContent = label;
        if (id === section) link.setAttribute('aria-current', 'page');
        nav.append(link);
      }
      if (role === 'reader') {
        const login = document.createElement('a'); login.href = '/login'; login.className = 'ui-login'; login.textContent = '登录';
        nav.append(login);
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
    const controls = document.createElement('div'); controls.className = 'ui-appearance-controls';
    bar.append(controls);
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
