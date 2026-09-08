/* Shared appearance only: never reload data or remount application content. */
(() => {
  'use strict';
  const root = document.documentElement;
  const KEY = 'inresearch.ui.v1';
  const defaults = {skin: 'folk', mode: 'light'};
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = input => ({skin: ['folk', 'attio'].includes(input?.skin) ? input.skin : defaults.skin,
    mode: ['light', 'dark', 'system'].includes(input?.mode) ? input.mode : defaults.mode});
  const read = () => { try { return valid(JSON.parse(localStorage.getItem(KEY))); } catch (_) { return {...defaults}; } };
  let preference = read();
  const resolved = () => preference.mode === 'system' ? (media.matches ? 'dark' : 'light') : preference.mode;
  function apply() {
    root.dataset.uiSkin = preference.skin;
    root.dataset.uiMode = preference.mode;
    root.dataset.uiTheme = resolved();
    document.querySelectorAll('[data-ui-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.uiChoice === preference.skin)));
    const select = document.getElementById('ui-appearance');
    if (select) select.value = preference.mode;
    window.dispatchEvent(new CustomEvent('inresearch:appearance', {detail: {...preference, resolved: resolved()}}));
  }
  function setPreference(update) {
    preference = valid({...preference, ...update});
    try { localStorage.setItem(KEY, JSON.stringify(preference)); const note = document.getElementById('ui-save-status'); if (note) note.textContent = ''; }
    catch (_) { const note = document.getElementById('ui-save-status'); if (note) note.textContent = '本页有效，偏好未保存'; }
    apply();
  }
  const scenePalette = () => {
    const css = getComputedStyle(root);
    return {background: css.getPropertyValue('--ui-scene').trim() || '#f7f6f2'};
  };
  window.InresearchUI = Object.freeze({getState: () => ({...preference, resolved: resolved()}), setPreference, scenePalette});
  // Runs in the head, before the stylesheet/first paint.
  apply();
  if (media.addEventListener) media.addEventListener('change', () => { if (preference.mode === 'system') apply(); });
  else media.addListener(() => { if (preference.mode === 'system') apply(); });
  window.addEventListener('storage', event => { if (event.key === KEY || event.key === null) { preference = read(); apply(); } });

  // Original project icons: two geometries, no remote icon fonts or brand assets.
  const icons = {
    home: ['<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>', '<path d="M3 21V9l9-7 9 7v12H3Z M9 21v-9h6v9"/>'],
    research: ['<path d="M12 5C8 2 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-2-10 1Z M12 5v15"/>', '<path d="M2 21V5h8l3 3h9v13H2Z M5 5V2h8l3 3h4v3 M5 12h14 M5 16h10"/>'],
    product: ['<path d="m12 2 9 5v10l-9 5-9-5V7l9-5Z M3 7l9 5 9-5 M12 12v10"/>', '<rect x="2" y="11" width="9" height="10"/><rect x="13" y="11" width="9" height="10"/><rect x="7" y="1" width="10" height="8"/><path d="M5 14h3 M16 14h3 M10 4h4"/>'],
    three: ['<path d="m12 2 10 6-10 6L2 8l10-6Z M2 12l10 6 10-6 M2 16l10 6 10-6"/>', '<path d="M2 8h13v14H2V8Z M2 8l7-6h13v14l-7 6 M15 8l7-6 M15 15l7-6 M2 15h13"/>'],
    tasks: ['<rect x="2" y="3" width="20" height="18" rx="3"/><path d="M9 3v18 M16 3v18 M5 7h1 M12 7h1 M19 7h1"/>', '<path d="M2 2h20v20H2V2Z M2 7h20 M9 7v15 M16 7v15 M4 10h3v5H4v-5Z M11 10h3v8h-3v-8Z M18 10h2v3h-2v-3Z"/>'],
    document: ['<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z M14 2v6h6 M8 13h8 M8 17h6"/>', '<path d="M3 2h12l6 6v14H3V2Z M15 2v6h6 M6 12h12 M6 15h12 M6 18h8"/>'],
    settings: ['<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v3 M12 20v3 M1 12h3 M20 12h3"/>', '<path d="M2 5h20 M2 12h20 M2 19h20"/><rect x="6" y="2" width="4" height="6"/><rect x="14" y="9" width="4" height="6"/><rect x="7" y="16" width="4" height="6"/>']
  };
  function icon(name) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    el.setAttribute('viewBox', '0 0 24 24'); el.setAttribute('aria-hidden', 'true'); el.setAttribute('class', 'ui-icon');
    el.innerHTML = '<g class="ui-icon-attio">' + icons[name][0] + '</g><g class="ui-icon-folk">' + icons[name][1] + '</g>';
    return el;
  }
  function mount() {
    if (document.getElementById('ui-skinbar')) return;
    const bar = document.createElement('div'); bar.id = 'ui-skinbar'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', '全站外观');
    const brand = document.createElement('a'); brand.href = '/index.html'; brand.className = 'ui-home'; brand.append(icon('home'), document.createTextNode('inresearch.ai'));
    bar.append(brand);
    const inbox = document.createElement('a'); inbox.href = '/materials.html'; inbox.className = 'ui-home'; inbox.textContent = '资料提交'; bar.append(inbox);
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
    const docs = document.createElement('a'); docs.className = 'ui-standard'; docs.href = '/doc.html?f=framework/05_interface_system.md'; docs.textContent = '界面规范'; bar.append(docs);
    document.body.prepend(bar);
    const measure = () => root.style.setProperty('--ui-bar-height', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    if (window.ResizeObserver) new ResizeObserver(measure).observe(bar);
    measure();
    const routeIcon = path => path.includes('research') ? 'research' : path.includes('product') || path.includes('company') ? 'product' : path.includes('3d') || path.includes('bom') ? 'three' : path.includes('team') ? 'tasks' : path.includes('ops') || path.includes('compare') ? 'settings' : path.includes('doc') || path.includes('report') || path.includes('poster') ? 'document' : 'home';
    document.querySelectorAll('.topbar a, .rg-topbar nav a').forEach(link => {
      try { if (!link.querySelector('.ui-icon')) link.prepend(icon(routeIcon(new URL(link.href).pathname))); } catch (_) { /* no link mutation */ }
    });
    const phone = matchMedia('(max-width:700px)');
    const compact = () => document.querySelectorAll('.ui-mobile-overview').forEach(panel => { panel.open = !phone.matches; });
    compact(); phone.addEventListener('change', compact);
    apply();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true}); else mount();
})();
