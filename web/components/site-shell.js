/* Explicit site shell. Page bodies declare section and responsive panels. */
(() => {
  'use strict';
  const root = document.documentElement;
  const {getState, setPreference} = window.InresearchUI;

  // Brand every image shown in the site without altering the source artwork or
  // downloaded originals. The observer also covers atlas images mounted later.
  const LOGO_LIGHT_SRC = '/assets/brand/inresearch-ai/wordmark-primary.svg';
  const LOGO_DARK_SRC = '/assets/brand/inresearch-ai/wordmark-reverse.svg';
  // Images use the standalone signature icon as a quiet provenance mark. The
  // full wordmark remains reserved for the site header and formal materials.
  const WATERMARK_SRC = '/assets/brand/inresearch-ai/icon-orange.svg';
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
  const MODES = {light: '浅色', dark: '深色', system: '跟随系统'};
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function link(item, className) {
    const node = el('a', className, item.label); node.href = item.href; return node;
  }
  function closeMenus(except = null) {
    document.querySelectorAll('#ui-skinbar details[open]').forEach(menu => {
      if (menu !== except && !menu.contains(except)) menu.open = false;
    });
  }
  function appearance() {
    const menu = el('details', 'ui-theme-menu'), summary = el('summary', '', '◐');
    summary.id = 'ui-appearance'; summary.setAttribute('aria-label', '外观');
    const panel = el('div', 'ui-theme-panel');
    for (const [mode, label] of Object.entries(MODES)) {
      const button = el('button', '', label); button.type = 'button'; button.dataset.uiModeChoice = mode;
      button.addEventListener('click', () => { setPreference({mode}); menu.open = false; summary.focus(); });
      panel.append(button);
    }
    menu.append(summary, panel); return menu;
  }
  function apply(state = getState()) {
    const logo = document.querySelector('.ui-brand-logo');
    if (logo) logo.src = state.resolved === 'dark' ? LOGO_DARK_SRC : LOGO_LIGHT_SRC;
    const summary = document.getElementById('ui-appearance');
    if (summary) { summary.title = '外观：' + MODES[state.mode]; summary.setAttribute('aria-label', summary.title); summary.dataset.uiMode = state.mode; }
    document.querySelectorAll('[data-ui-mode-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.uiModeChoice === state.mode)));
    const note = document.getElementById('ui-save-status');
    if (note) note.textContent = state.saved === false ? '偏好未保存' : '';
  }
  window.addEventListener('inresearch:appearance', event => apply(event.detail));
  function account(identity) {
    const area = el('div', 'ui-account');
    if (identity.kind === 'anonymous') { area.append(link({href: '/login', label: '登录'}, 'ui-login')); return area; }
    const menu = el('details', 'ui-account-menu'), summary = el('summary'), panel = el('div', 'ui-account-panel');
    const name = identity.name || '账号'; summary.setAttribute('aria-label', name + '，账号菜单');
    summary.append(el('span', 'ui-account-name', name), el('span', 'ui-account-role', identity.role));
    const info = el('p', 'ui-account-identity'); info.append(el('strong', '', name), el('span', '', identity.role));
    panel.append(info, link({href: '/account', label: '个人信息'}), link({href: '/account#password', label: '修改密码'}), link({href: '/logout', label: '退出登录'}, 'ui-logout'));
    menu.append(summary, panel); area.append(menu); return area;
  }
  function search(config, active) {
    const area = el('div', 'ui-search'); if (!config?.enabled) return area;
    const scopes = config.scopes || [], labels = {delivery:'交付内容',backstage:'后台工作',all:'全部授权内容'};
    const requested = location.pathname === '/search.html' ? new URLSearchParams(location.search).get('scope') : null;
    const preferred = scopes.includes(requested) ? requested : active.area === 'backstage' ? 'backstage' : config.default_scope;
    const scope = scopes.includes(preferred) ? preferred : scopes[0]; if (!scope) return area;
    const form = el('form', 'ui-search-form'); form.action = '/search.html'; form.method = 'get'; form.setAttribute('role', 'search');
    const query = el('input'); query.name = 'q'; query.type = 'search';
    const compact = link({href: '/search.html?scope=' + scope, label: '搜索'}, 'ui-search-compact');
    const describe = value => { const label = '搜索' + labels[value]; query.placeholder = label; query.setAttribute('aria-label', label); compact.setAttribute('aria-label', label); compact.href = '/search.html?scope=' + value; };
    if (scopes.length > 1) {
      const select = el('select', 'ui-search-scope'); select.name = 'scope'; select.setAttribute('aria-label', '搜索范围');
      scopes.forEach(value => { const option = el('option', '', labels[value]); option.value = value; select.append(option); });
      select.value = scope; select.addEventListener('change', () => describe(select.value)); form.append(select);
    } else {
      const label = el('span', 'ui-search-scope-fixed', labels[scope]); label.setAttribute('aria-label', '搜索范围：' + labels[scope]);
      const hidden = el('input'); hidden.type = 'hidden'; hidden.name = 'scope'; hidden.value = scope; form.append(label, hidden);
    }
    const submit = el('button', '', '搜索'); submit.type = 'submit'; describe(scope); form.append(query, submit);
    area.append(form, compact); return area;
  }
  function itemMenu(item, area, active) {
    const current = active.area === area && active.section === item.id;
    if (!item.children?.length) {
      const anchor = link(item, 'ui-primary-link'); anchor.dataset.navSection = item.id;
      if (current) anchor.setAttribute('aria-current', 'page'); return anchor;
    }
    const menu = el('details', 'ui-section-menu'); menu.dataset.navSection = item.id;
    if (current) menu.dataset.current = 'true';
    const summary = el('summary', '', item.label); summary.setAttribute('aria-label', item.label + '目录');
    if (current) summary.setAttribute('aria-current', 'page');
    const panel = el('div', 'ui-section-panel');
    for (const child of item.children) {
      const anchor = link(child); if (current && active.view === child.id) anchor.setAttribute('aria-current', 'page');
      anchor.addEventListener('click', () => closeMenus()); panel.append(anchor);
    }
    menu.append(summary, panel); return menu;
  }
  function navigation(area, items, active) {
    const nav = el('nav', 'ui-navigation ui-navigation-' + area); nav.dataset.navArea = area;
    nav.setAttribute('aria-label', area === 'delivery' ? '交付目录' : area === 'backstage' ? '后台目录' : '公开导航');
    if (area !== 'public') nav.append(el('span', 'ui-navigation-label', area === 'delivery' ? '交付' : '后台'));
    items.forEach(item => nav.append(itemMenu(item, area, active))); return nav;
  }
  function mobileNavigation(groups, active) {
    const row = el('div', 'ui-mobile-navigation'), tabs = el('div', 'ui-mobile-areas');
    const menu = el('details', 'ui-mobile-menu'), summary = el('summary'), panel = el('div', 'ui-mobile-panel');
    function select(group) {
      tabs.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.area === group.id)));
      const current = group.items.find(item => item.id === active.section && group.id === active.area);
      summary.textContent = current ? current.label : '浏览目录'; summary.setAttribute('aria-label', group.label + '目录'); panel.replaceChildren();
      for (const item of group.items) {
        const on = active.area === group.id && active.section === item.id;
        if (!item.children?.length) {
          const anchor = link(item, 'ui-mobile-direct'); if (on) anchor.setAttribute('aria-current', 'page'); panel.append(anchor);
        } else {
          const section = el('details', 'ui-mobile-section'), title = el('summary', '', item.label), children = el('div', 'ui-mobile-children');
          if (on) { title.setAttribute('aria-current', 'page'); section.open = true; }
          for (const child of item.children) { const anchor = link(child); if (on && active.view === child.id) anchor.setAttribute('aria-current', 'page'); children.append(anchor); }
          section.append(title, children); panel.append(section);
        }
      }
    }
    for (const group of groups) { const button = el('button', '', group.label); button.type = 'button'; button.dataset.area = group.id; button.addEventListener('click', () => { select(group); menu.open = true; }); tabs.append(button); }
    menu.append(summary, panel); row.append(tabs, menu); select(groups.find(group => group.id === active.area) || groups[0]);
    panel.addEventListener('click', event => { if (event.target.closest('a')) menu.open = false; }); return row;
  }
  function footer(data) {
    document.getElementById('ui-site-footer')?.remove();
    const footer = el('footer', 'ui-site-footer'); footer.id = 'ui-site-footer'; footer.dataset.audience = data.identity.kind;
    const scene = !!document.querySelector('canvas#c'); if (scene) footer.classList.add('ui-scene-footer');
    const frame = scene ? el('details', 'ui-footer-disclosure') : el('div'); if (scene) frame.append(el('summary', '', '网站信息'));
    const content = el('div', 'ui-footer-content'), intro = el('div', 'ui-footer-brand'); intro.append(el('strong', '', 'inresearch.ai'));
    if (data.identity.kind !== 'anonymous') intro.append(el('p', '', '数据中心研究、企业与产品、技术图册。')); content.append(intro);
    const footerData = data.identity.kind === 'anonymous' ? {groups:[{label:'',links:[...(data.public_navigation || [{label:'首页',href:'/'},{label:'任务',href:'/tasks.html'}]),{label:'登录',href:'/login'}]}],legal:[]} : (data.footer || {});
    const groups = el('div', 'ui-footer-groups');
    for (const group of footerData.groups || []) { const section = el('section'), links = el('div'); if (group.label) section.append(el('h2', '', group.label)); (group.links || []).forEach(item => links.append(link(item))); section.append(links); groups.append(section); }
    content.append(groups); const legal = el('div', 'ui-footer-legal'); (footerData.legal || []).forEach(item => legal.append(link(item)));
    const top = el('button', 'ui-back-top', '返回顶部'); top.type = 'button'; top.addEventListener('click', () => { window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'}); document.querySelector('.ui-home')?.focus({preventScroll:true}); }); legal.append(top); content.append(legal);
    if (data.identity.kind === 'team') {
      const runtime = el('details', 'ui-footer-runtime'); runtime.append(el('summary', '', '运行信息'));
      for (const [key,label] of [['version','运行版本'],['environment','运行环境'],['deployed_at','部署时间'],['observed_at','状态时间'],['status','运行状态']]) runtime.append(el('p', '', label + '：' + (!data.footer?.runtime?.[key] || data.footer.runtime[key] === 'unknown' ? '未取得' : data.footer.runtime[key])));
      const operations = data.navigation?.backstage?.find(item => item.id === 'operations');
      const links = el('div', 'ui-runtime-links');
      for (const id of ['deployment','health']) { const item = operations?.children?.find(child => child.id === id); if (item) links.append(link(item)); }
      if (links.childNodes.length) runtime.append(links); content.append(runtime);
    }
    frame.append(content); footer.append(frame); document.body.append(footer);
  }
  function mount() {
    const host = document.querySelector('inresearch-shell'); if (!host || document.getElementById('ui-skinbar')) return;
    const bar = el('header'); bar.id = 'ui-skinbar'; bar.dataset.identity = 'anonymous'; bar.setAttribute('aria-label', '全站页眉');
    const toolbar = el('div', 'ui-toolbar'), brand = el('a', 'ui-home'); brand.href = '/index.html'; brand.setAttribute('aria-label', 'inresearch.ai 首页');
    const logo = el('img', 'ui-brand-logo'); logo.src = WATERMARK_SRC; logo.alt = 'inresearch.ai'; logo.width = 150; logo.height = 29; logo.dataset.noWatermark = 'true'; brand.append(logo); toolbar.append(brand);
    const tools = el('div', 'ui-appearance-controls'), identityHost = el('div', 'ui-account-host'); identityHost.append(account({kind:'anonymous'}));
    const note = el('span'); note.id = 'ui-save-status'; note.setAttribute('role', 'status'); tools.append(appearance(), identityHost, note); toolbar.append(tools); bar.append(toolbar); host.append(bar);
    const publicItems = [{id:'home',label:'地图首页',href:'/'},{id:'tasks',label:'任务',href:'/tasks.html'}], initialActive = {area:'public',section:location.pathname === '/tasks.html' ? 'tasks' : 'home'};
    if (host.dataset.section !== 'auth') bar.append(navigation('public', publicItems, initialActive));
    footer({identity:{kind:'anonymous'},footer:{groups:[{label:'',links:[...publicItems,{label:'登录',href:'/login'}]}],legal:[]}});
    const measure = () => root.style.setProperty('--ui-bar-height', Math.ceil(bar.getBoundingClientRect().height) + 'px'); if (window.ResizeObserver) new ResizeObserver(measure).observe(bar);
    function render(data) {
      const identity = data.identity, active = identity.kind === 'anonymous' ? {area:'public',section:location.pathname === '/tasks.html' ? 'tasks' : 'home'} : (data.active || {}); bar.dataset.identity = identity.kind; bar.dataset.role = identity.role || 'reader';
      bar.querySelectorAll(':scope > nav, :scope > .ui-mobile-navigation').forEach(node => node.remove()); tools.querySelector('.ui-search')?.remove(); if (host.dataset.section !== 'auth') tools.prepend(search(data.search, active)); identityHost.replaceChildren(account(identity));
      const groups = ['delivery','backstage'].filter(area => data.navigation?.[area]?.length).map(id => ({id,label:id==='delivery'?'交付':'后台',items:data.navigation[id]}));
      if (host.dataset.section !== 'auth') { if (identity.kind === 'anonymous') bar.append(navigation('public', data.public_navigation || publicItems, active)); else { groups.forEach(group => bar.append(navigation(group.id, group.items, active))); if (groups.length) bar.append(mobileNavigation(groups, active)); } }
      document.querySelectorAll('[data-requires-login]').forEach(node => { node.hidden = identity.kind === 'anonymous'; });
      document.querySelectorAll('[data-ui-account-name]').forEach(node => { node.textContent = identity.name || '未登录'; }); document.querySelectorAll('[data-ui-account-role]').forEach(node => { node.textContent = identity.role || 'reader'; });
      footer(data); apply(); measure(); bar.dataset.navigationReady = 'true'; window.dispatchEvent(new CustomEvent('inresearch:navigation', {detail:data}));
    }
    let loading = false, reloadPending = false;
    async function load() {
      if (loading) { reloadPending = true; return; } loading = true; document.getElementById('ui-navigation-error')?.remove();
      try { const response = await fetch('/api/navigation?' + new URLSearchParams({page:location.pathname + location.search + location.hash}), {cache:'no-store'}); if (!response.ok) throw Error('navigation unavailable'); const data = await response.json(); if (!data.ok || !data.identity?.kind) throw Error('invalid navigation'); render(data); }
      catch (_) { const error = el('button', '', '目录暂不可用，重试'); error.id = 'ui-navigation-error'; error.type = 'button'; error.addEventListener('click', load); tools.append(error); }
      finally { loading = false; measure(); if (reloadPending) { reloadPending = false; load(); } }
    }
    bar.addEventListener('toggle', event => { const menu = event.target; if (menu instanceof HTMLDetailsElement && menu.open && !menu.closest('.ui-mobile-panel')) closeMenus(menu); }, true);
    bar.addEventListener('keydown', event => { if (event.key !== 'Escape') return; const menu = event.target.closest('details[open]') || bar.querySelector('details[open]'); if (menu) { menu.open = false; menu.querySelector('summary')?.focus(); event.stopPropagation(); } });
    document.addEventListener('click', event => { if (!bar.contains(event.target)) closeMenus(); }); window.addEventListener('hashchange', () => { closeMenus(); load(); });
    window.addEventListener('popstate', load);
    window.addEventListener('inresearch:page-navigation', load);
    const phone = matchMedia('(max-width:700px)'), compact = () => { document.querySelectorAll('[data-responsive-panel]').forEach(panel => { panel.open = !phone.matches; }); closeMenus(); measure(); };
    compact(); phone.addEventListener('change', compact); apply(); measure(); load();
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', mount, {once:true}); document.addEventListener('DOMContentLoaded', mountImageBranding, {once:true}); }
  else { mount(); mountImageBranding(); }
})();
