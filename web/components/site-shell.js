/* Explicit site shell. Page bodies declare section and responsive panels. */
(() => {
  'use strict';
  const root = document.documentElement;
  const {getState, setPreference} = window.InresearchUI;

  // Brand every image shown in the site without altering the source artwork or
  // downloaded originals. The observer also covers atlas images mounted later.
  const WATERMARK_SRC = '/assets/brand/inresearch-ai/wordmark-primary.svg';
  const WATERMARK_EXCLUDE = new Set(['ui-brand-watermark', 'ui-icon', 'favicon']);
  function shouldBrandImage(node) {
    if (!(node instanceof Element) || !['IMG', 'CANVAS'].includes(node.tagName)) return false;
    if (node.dataset.noWatermark === 'true' || node.closest('[data-no-watermark="true"]')) return false;
    if (node.closest('#ui-skinbar, .ui-brand-watermark')) return false;
    return ![...node.classList].some(name => WATERMARK_EXCLUDE.has(name));
  }
  function brandImage(node) {
    if (!shouldBrandImage(node) || node.dataset.brandWatermarked === 'true') return;
    const wrapper = document.createElement('span');
    wrapper.className = 'ui-branded-image';
    wrapper.dataset.brandWatermark = 'true';
    wrapper.setAttribute('data-image-watermark', 'inresearch.ai');
    node.dataset.brandWatermarked = 'true';
    node.parentNode?.insertBefore(wrapper, node);
    wrapper.append(node);
    const mark = document.createElement('img');
    mark.className = 'ui-brand-watermark';
    mark.src = WATERMARK_SRC;
    mark.alt = '';
    mark.setAttribute('aria-hidden', 'true');
    mark.draggable = false;
    wrapper.append(mark);
  }
  function brandImages() {
    document.querySelectorAll('img, canvas').forEach(brandImage);
  }
  function mountImageBranding() {
    brandImages();
    const observer = new MutationObserver(records => {
      records.forEach(record => record.addedNodes.forEach(node => {
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        if (node.matches?.('img, canvas')) brandImage(node);
        node.querySelectorAll?.('img, canvas').forEach(brandImage);
      }));
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
  }
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
  // 一级导航为行业总览与研究目录（05「目录」）：七项按角色出现；页面用 data-section 说自己属于哪一项。
  // 业务导航与右上账号区分别显示；身份确认前只展示公开入口。
  const LINKS = [
    ['industry', '行业总览', '/'], ['tasks', '任务跟踪', '/tasks.html'], ['datacenter', '数据中心研究', '/node.html'], ['ledger', '账本', '/ledger.html'], ['bom', '爆炸图', '/bom.html'],
    ['acquisition', '采集', '/supply.html'], ['results', '成果', '/report.html']
  ];
  const VISIBLE = {
    admin: ['industry', 'tasks', 'datacenter', 'ledger', 'bom', 'acquisition', 'results'],
    member: ['industry', 'tasks', 'datacenter', 'ledger', 'bom', 'acquisition', 'results'],
    intern: ['tasks', 'acquisition'],
    reader: ['industry', 'tasks']
  };
  function navigation(section) {
    const nav = document.createElement('nav');
    nav.className = 'ui-navigation'; nav.setAttribute('aria-label', '全站导航');
    function render(role) {
      nav.replaceChildren();
      document.querySelectorAll('[data-requires-login]').forEach(el => { el.hidden = role === 'reader'; });
      const visible = VISIBLE[role] || VISIBLE.reader;
      for (const [id, label, href] of LINKS) {
        if (!visible.includes(id)) continue;
        const link = document.createElement('a');
        link.href = href; link.textContent = label;
        if (id === section) link.setAttribute('aria-current', 'page');
        nav.append(link);
      }
    }
    render('reader');
    return {element: nav, render};
  }
  function account(audience, section) {
    const area = document.createElement('div'); area.className = 'ui-account';
    function render(user) {
      area.replaceChildren();
      if (!user || !['admin', 'member', 'intern'].includes(user.role)) {
        const login = document.createElement('a'); login.href = '/login'; login.className = 'ui-login'; login.textContent = '登录';
        area.append(login); return;
      }
      const details = document.createElement('details'); details.className = 'ui-account-menu';
      const summary = document.createElement('summary');
      const username = typeof user.user === 'string' && user.user ? user.user : '账号';
      summary.setAttribute('aria-label', `${username} · ${user.role}，账号菜单`);
      summary.title = `${username} · ${user.role}`;
      const name = document.createElement('span'); name.className = 'ui-account-name'; name.textContent = username;
      const role = document.createElement('span'); role.className = 'ui-account-role'; role.textContent = user.role;
      summary.append(name, role);
      const menu = document.createElement('div'); menu.className = 'ui-account-panel';
      const identity = document.createElement('p'); identity.className = 'ui-account-identity';
      const fullName = document.createElement('strong'); fullName.textContent = username;
      const fullRole = document.createElement('span'); fullRole.textContent = user.role;
      identity.append(fullName, fullRole); menu.append(identity);
      const link = (href, text, className) => {
        const el = document.createElement('a'); el.href = href; el.textContent = text;
        if (className) el.className = className;
        menu.append(el); return el;
      };
      link('/account', '个人信息');
      if (user.role === 'admin') {
        const management = link('/ops.html', '管理台', 'ui-management-link');
        if (section === 'admin') management.setAttribute('aria-current', 'page');
        if (audience === 'reader') {
          const current = new URLSearchParams(location.search);
          const query = new URLSearchParams({c: current.get('c') || 'nvidia'});
          if (current.get('product_id')) query.set('product_id', current.get('product_id'));
          if (current.get('series')) query.set('series', current.get('series'));
          link('/admin/company.html?' + query, '本公司后台', 'ui-admin-link');
        }
      }
      link('/logout', '退出登录', 'ui-logout');
      details.append(summary, menu); area.append(details);
    }
    area.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      const details = area.querySelector('details');
      if (details?.open) { details.open = false; details.querySelector('summary').focus(); }
    });
    document.addEventListener('click', event => {
      if (!area.contains(event.target)) {
        const details = area.querySelector('details'); if (details) details.open = false;
      }
    });
    render(null);
    return {element: area, render};
  }
  function mount() {
    const host = document.querySelector('inresearch-shell');
    if (!host || document.getElementById('ui-skinbar')) return;
    const bar = document.createElement('div'); bar.id = 'ui-skinbar'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', '全站外观');
    const brand = document.createElement('a'); brand.href = '/index.html'; brand.className = 'ui-home'; brand.append(icon('home'), document.createTextNode('inresearch.ai'));
    bar.append(brand);
    const section = location.pathname === '/tasks.html' ? 'tasks' : host.dataset.section;
    const nav = host.dataset.section !== 'auth' ? navigation(section) : null;
    if (nav) bar.append(nav.element);
    const controls = document.createElement('div'); controls.className = 'ui-appearance-controls';
    bar.append(controls);
    const label = document.createElement('label'); label.htmlFor = 'ui-appearance';
    const labelText = document.createElement('span'); labelText.className = 'ui-appearance-label'; labelText.textContent = '外观'; label.append(labelText);
    const select = document.createElement('select'); select.id = 'ui-appearance'; select.setAttribute('aria-label', '外观');
    for (const [value, text] of [['light', '浅色'], ['dark', '深色'], ['system', '跟随系统']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option);
    }
    select.addEventListener('change', () => setPreference({mode: select.value})); label.append(select); controls.append(label);
    const identity = account(host.dataset.audience, section); controls.append(identity.element);
    const note = document.createElement('span'); note.id = 'ui-save-status'; note.setAttribute('role', 'status'); controls.append(note);
    host.append(bar);
    fetch('/api/whoami', {cache: 'no-store'}).then(response => response.ok ? response.json() : null)
      .then(user => {
        if (!user?.role) throw Error('identity unavailable');
        nav?.render(user.role); identity.render(user);
        document.querySelectorAll('[data-ui-account-name]').forEach(el => { el.textContent = user.user || '未登录'; });
        document.querySelectorAll('[data-ui-account-role]').forEach(el => { el.textContent = user.role; });
      }).catch(() => {
        document.querySelectorAll('[data-ui-account-name], [data-ui-account-role]').forEach(el => { el.textContent = '暂时无法读取，请刷新'; });
      });
    const measure = () => root.style.setProperty('--ui-bar-height', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    if (window.ResizeObserver) new ResizeObserver(measure).observe(bar);
    measure();
    const phone = matchMedia('(max-width:700px)');
    const compact = () => document.querySelectorAll('[data-responsive-panel]').forEach(panel => { panel.open = !phone.matches; });
    compact(); phone.addEventListener('change', compact);
    apply();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, {once: true});
    document.addEventListener('DOMContentLoaded', mountImageBranding, {once: true});
  } else {
    mount();
    mountImageBranding();
  }
})();
