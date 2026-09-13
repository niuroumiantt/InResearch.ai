/* Theme preference owns appearance only; page structure belongs to the shell. */
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
  let saved = true;
  const resolved = () => preference.mode === 'system' ? (media.matches ? 'dark' : 'light') : preference.mode;
  function apply() {
    root.dataset.uiSkin = preference.skin;
    root.dataset.uiMode = preference.mode;
    root.dataset.uiTheme = resolved();
    window.dispatchEvent(new CustomEvent('inresearch:appearance', {detail: {...preference, resolved: resolved(), saved}}));
  }
  function setPreference(update) {
    preference = valid({...preference, ...update});
    try { localStorage.setItem(KEY, JSON.stringify(preference)); saved = true; }
    catch (_) { saved = false; }
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

})();
