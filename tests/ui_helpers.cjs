/* Exercise the same theme buttons users operate; no programmatic preference shortcut. */
async function setAppearance(page, mode) {
  const menu = page.locator('.ui-theme-menu');
  await menu.locator(':scope > summary').waitFor();
  if (!await menu.evaluate(node => node.open)) await menu.locator(':scope > summary').click();
  await menu.locator('[data-ui-mode-choice="' + mode + '"]').click();
  await page.waitForFunction(value => document.documentElement.dataset.uiMode === value, mode);
}
// Explicit navigation fixture: shell tests exercise rendering; auth_appearance uses the real API.
function navigationProjection(role, active) {
  const manifest = require('../framework/site_navigation.json');
  const kind = role === 'reader' ? 'anonymous' : role === 'customer' ? 'customer' : 'team';
  const filter = items => items.filter(item => item.roles.includes(role)).map(item => ({...item, children:item.children.filter(child => !child.roles || child.roles.includes(role))}));
  return {ok:true,version:manifest.version,identity:{kind,name:role==='reader'?null:'navigation-'+role,role},
    public_navigation:manifest.public_navigation,navigation:{delivery:filter(manifest.navigation.delivery),backstage:filter(manifest.navigation.backstage)},
    active,footer:kind==='anonymous'?{groups:[],legal:[]}:{...manifest.footer,runtime:null},
    search:{enabled:kind!=='anonymous',scopes:role==='intern'?['backstage']:kind==='customer'?['delivery']:['delivery','backstage','all'],default_scope:role==='intern'?'backstage':'delivery'}};
}
module.exports = {setAppearance,navigationProjection};
