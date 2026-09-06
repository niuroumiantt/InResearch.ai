/* Browser regression. Start: python3 pipeline/serve.py 8878
 * Run: NODE_PATH=<directory containing playwright> node tests/ui_skin.cjs
 * UI_BASE_URL defaults to local server; screenshots go to UI_QA_DIR if set.
 * Requires a locally installed Chrome and Playwright; no production dependency.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8878';
const manifest = require('../framework/interface_manifest.json');
const dir = process.env.UI_QA_DIR;
(async () => {
 const browser = await chromium.launch({channel:'chrome', headless:true, args:['--enable-unsafe-swiftshader']});
 try {
 const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark'});
 const page = await context.newPage(); const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const measure = () => page.evaluate(()=>({skin:document.documentElement.dataset.uiSkin,theme:document.documentElement.dataset.uiTheme,width:document.documentElement.scrollWidth,viewport:innerWidth,bg:getComputedStyle(document.body).backgroundColor,bar:document.querySelectorAll('#ui-skinbar').length}));
 for (const file of manifest.static_pages) {
   const query = file==='research.html'?'?node=part:gpu&view=P&tab=tasks':file==='doc.html'?'?f=framework/05_interface_system.md':'';
   await page.goto(base+'/'+file+query); await page.locator('#ui-skinbar').waitFor();
   if(file==='research.html') await page.locator('.rg-node h2').waitFor();
   const settledUrl=page.url();
   for (const skin of ['folk','attio']) for (const mode of ['light','dark']) {
     await page.getByRole('button',{name:skin==='folk'?'folk':'Attio',exact:true}).click();
     await page.locator('#ui-appearance').selectOption(mode);
     const state=await measure(); assert.equal(state.skin,skin);assert.equal(state.theme,mode);assert.equal(state.bar,1);
     const url=page.url();assert.equal(url,settledUrl);
     const geometry=await page.evaluate(()=>({radius:getComputedStyle(document.querySelector('.board,.rg-node,.hud,.card,.kpi')||document.documentElement).borderRadius,icon:getComputedStyle(document.querySelector('.ui-icon-'+(document.documentElement.dataset.uiSkin==='folk'?'attio':'folk'))).display}));
     if (['index.html','research.html','bom3d.html','rack3d.html'].includes(file)) assert.equal(geometry.radius,skin==='folk'?'0px':'10px',file+' panel geometry');
     assert.equal(geometry.icon,'none');
     const expected=skin==='folk'?(mode==='light'?'rgb(250, 249, 246)':'rgb(25, 26, 24)'):(mode==='light'?'rgb(246, 247, 250)':'rgb(17, 21, 28)');assert.equal(state.bg,expected);
     if(dir && ['index.html','research.html','admin/product/index.html','doc.html','bom3d.html','rack3d.html'].includes(file) && mode==='light'){
       await page.waitForTimeout(file.includes('3d')?2200:200);
       await page.screenshot({path:path.join(dir,file.replaceAll('/','-')+'-'+skin+'.png')});
     }
   }
   // Head bar must remain usable on a phone; preexisting large data tables may scroll.
   await page.setViewportSize({width:360,height:800});
   const box=await page.locator('#ui-skinbar').boundingBox();assert.ok(box.width<=360);
   for(const sel of ['[data-ui-choice=folk]','[data-ui-choice=attio]','#ui-appearance']){
     const b=await page.locator(sel).boundingBox();assert.ok(b.x>=0 && b.x+b.width<=361,file+' '+sel);
   }
   if(file==='research.html') {assert.ok((await measure()).width<=361);if(dir)await page.screenshot({path:path.join(dir,'research-mobile.png')});}
   await page.setViewportSize({width:1440,height:1000});console.log('PASS',file,'four appearances + phone controls');
 }
 await page.goto(base+'/research.html?node=part:gpu&view=P&tab=tasks');
 await page.locator('.rg-node h2').waitFor();
 const before=await page.locator('.rg-node').textContent();const url=page.url();
 await page.getByRole('button',{name:'folk',exact:true}).click();await page.locator('#ui-appearance').selectOption('light');
 assert.equal(await page.locator('.rg-node').textContent(),before);assert.equal(page.url(),url);
 await page.reload();assert.equal((await measure()).skin,'folk');assert.equal((await measure()).theme,'light');
 const second=await context.newPage();await second.goto(base+'/index.html');
 await second.getByRole('button',{name:'Attio',exact:true}).click();await page.waitForFunction(()=>document.documentElement.dataset.uiSkin==='attio');
 await page.locator('#ui-appearance').selectOption('system');assert.equal((await measure()).theme,'dark');await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='light');
 await page.locator('#ui-appearance').selectOption('light');await page.emulateMedia({colorScheme:'dark'});assert.equal((await measure()).theme,'light');
 await page.emulateMedia({media:'print'});assert.equal(await page.locator('#ui-skinbar').isVisible(),false);
 await page.emulateMedia({media:'screen'});
 await page.evaluate(()=>localStorage.setItem('inresearch.ui.v1','{bad json'));await page.reload();assert.equal((await measure()).skin,'folk');assert.equal((await measure()).theme,'light');
 const blocked=await browser.newContext();await blocked.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw Error('disabled')}}));
 const bp=await blocked.newPage();await bp.goto(base+'/index.html');await bp.getByRole('button',{name:'Attio',exact:true}).click();assert.equal(await bp.locator('html').getAttribute('data-ui-skin'),'attio');assert.match(await bp.locator('#ui-save-status').textContent(),/未保存/);await blocked.close();
 assert.deepEqual(errors,[]);console.log('PASS persistence, cross-tab sync, explicit/system mode, print, corrupt/blocked storage, preserved research state; no page errors');
 await context.close();
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
