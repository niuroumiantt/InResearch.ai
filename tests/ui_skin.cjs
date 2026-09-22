/* Browser regression. Start: python3 manage.py serve 8878
 * Run: NODE_PATH=<directory containing playwright> node tests/ui_skin.cjs
 * UI_BASE_URL defaults to local server; screenshots go to UI_QA_DIR if set.
 * Requires a locally installed Chrome and Playwright; no production dependency.
 * 2026-09-22: one shared appearance (line style) with light/dark; the Attio/folk switch is gone.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8878';
const manifest = require('../framework/interface_manifest.json');
const dir = process.env.UI_QA_DIR;
const BG = {light:'rgb(250, 249, 246)', dark:'rgb(27, 28, 25)'};
(async () => {
 const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true, args:['--enable-unsafe-swiftshader']});
 try {
 // CI has software WebGL. Keep CSS dimensions and real scenes, with fewer raster pixels.
 const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark',
   reducedMotion:'reduce',deviceScaleFactor:process.env.CI ? 0.5 : 1});
 const page = await context.newPage(); const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const measure = () => page.evaluate(()=>({theme:document.documentElement.dataset.uiTheme,width:document.documentElement.scrollWidth,viewport:innerWidth,bg:getComputedStyle(document.body).backgroundColor,bar:document.querySelectorAll('#ui-skinbar').length,font:getComputedStyle(document.body).fontFamily}));
 for (const file of manifest.static_pages) {
   const query = file==='research.html'?'?node=part:gpu&view=P&tab=tasks':file==='doc.html'?'?f=framework/05_interface_system.md':'';
   await page.goto(base+'/'+file+query); await page.locator('#ui-skinbar').waitFor();
   await page.locator('.ui-navigation a[aria-current=page]').waitFor();
   assert.equal(await page.locator('.ui-navigation a[aria-current=page]').count(),1,file+' active section');
   assert.equal(await page.locator('[data-ui-choice]').count(),0,file+' has no skin switch');
   if(file==='company.html') await page.locator('.head h1').waitFor();
   if(file==='report.html') {await page.locator('.finding').first().waitFor();assert.equal(await page.locator('.finding').count(),150);}
   if(file==='research.html') await page.locator('.rg-node h2').waitFor();
   if(file==='ops.html'){await page.locator('#modules .mod').first().waitFor();assert.equal(await page.locator('#modules .mod').count(),15);assert.equal(await page.locator('#error').textContent(),'');assert.ok(await page.locator('#projects tr').count()>100);}
   const settledUrl=page.url();
   // Shared fonts: the bundled Inter + Noto Sans SC stack applies to the body of every application page.
   const fonts=await page.evaluate(async()=>{await document.fonts.ready;return [...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)});
   assert.ok(fonts.includes('Inter')&&fonts.includes('Noto Sans SC'),file+' bundled fonts loaded: '+fonts.join(','));
   assert.match((await measure()).font,/^Inter, "Noto Sans SC"/,file+' body font stack');
   for (const mode of ['light','dark']) {
     await page.locator('#ui-appearance').selectOption(mode);
     const state=await measure(); assert.equal(state.theme,mode);assert.equal(state.bar,1);
     const url=page.url();assert.equal(url,settledUrl);
     const radius=await page.evaluate(()=>getComputedStyle(document.querySelector('.board,.rg-node,.hud,.card,.kpi')||document.documentElement).borderRadius);
     if (['index.html','research.html','bom3d.html','rack3d.html'].includes(file)) assert.equal(radius,'0px',file+' panel geometry');
     assert.equal(state.bg,BG[mode]);
     if(dir && ['index.html','research.html','admin/product/index.html','doc.html','bom3d.html','rack3d.html'].includes(file) && mode==='light'){
       await page.waitForTimeout(file.includes('3d')?2200:200);
       await page.screenshot({path:path.join(dir,file.replaceAll('/','-')+'-'+mode+'.png')});
     }
     if(file==='research.html'){
       assert.equal(await page.locator('.rg-detail-tab').first().evaluate(e=>getComputedStyle(e).borderRadius),'0px');
       assert.equal(await page.locator('#researchSearch').evaluate(e=>getComputedStyle(e).borderRadius),'2px');
     }
     // Form controls: native select chrome is replaced everywhere, including the appearance control itself.
     assert.equal(await page.locator('#ui-appearance').evaluate(e=>getComputedStyle(e).appearance),'none',file+' select appearance');
     if(file==='materials.html'){
       const contrast=await page.locator('#submit').evaluate(e=>{
         const css=getComputedStyle(e);
         const luminance=rgb=>rgb.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255)
           .map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
         const a=luminance(css.color),b=luminance(css.backgroundColor);
         return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
       });
       assert.ok(contrast>=4.5,'primary button contrast '+mode+' '+contrast);
     }
     for(const width of [360,1440]){
       await page.setViewportSize({width,height:width===360?800:1000});
       const state=await measure();
       const overflow = state.width>width+1 ? await page.evaluate(()=>Array.from(document.querySelectorAll('body *'))
         .filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>e.tagName+'#'+e.id)) : [];
       assert.ok(state.width<=width+1,`${file} ${mode}: page ${state.width} exceeds ${width}; ${overflow.join(', ')}`);
       if(dir && width===360 && mode==='light') await page.screenshot({path:path.join(dir,file.replaceAll('/','-')+'-mobile.png')});
     }
   }
   // Head bar must remain usable on a phone: brand + appearance on one row, navigation on a second, nothing more.
   await page.setViewportSize({width:360,height:800});
   const box=await page.locator('#ui-skinbar').boundingBox();assert.ok(box.width<=360);
   assert.ok(box.height<=90,file+' phone head bar is two rows, got '+box.height+'px');
   const b=await page.locator('#ui-appearance').boundingBox();assert.ok(b.x>=0 && b.x+b.width<=361,file+' appearance control on screen');
   if(file==='research.html') {assert.ok((await measure()).width<=361);if(dir)await page.screenshot({path:path.join(dir,'research-mobile.png')});}
   await page.setViewportSize({width:1440,height:1000});console.log('PASS',file,'light/dark, fonts, controls + phone head bar');
 }
 await page.goto(base+'/research.html?node=part:gpu&view=P&tab=tasks');
 await page.locator('.rg-node h2').waitFor();
 assert.equal(await page.locator('.rg-case-step').count(),3);
 await page.getByRole('button',{name:'查看陈述与回答',exact:true}).click();
 assert.equal(new URL(page.url()).searchParams.get('node'),'part:gpu');
 assert.equal(new URL(page.url()).searchParams.get('view'),'P');
 assert.equal(new URL(page.url()).searchParams.get('tab'),'statements');
 await page.getByRole('button',{name:'继续处理任务',exact:true}).click();
 assert.equal(new URL(page.url()).searchParams.get('tab'),'tasks');
 const before=await page.locator('.rg-node').textContent();const url=page.url();
 await page.locator('#ui-appearance').selectOption('light');
 assert.equal(await page.locator('.rg-node').textContent(),before);assert.equal(page.url(),url);
 await page.reload();assert.equal((await measure()).theme,'light');
 const second=await context.newPage();await second.goto(base+'/index.html');
 await second.locator('#ui-appearance').selectOption('dark');await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='dark');
 await page.locator('#ui-appearance').selectOption('system');assert.equal((await measure()).theme,'dark');await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='light');
 await page.locator('#ui-appearance').selectOption('light');await page.emulateMedia({colorScheme:'dark'});assert.equal((await measure()).theme,'light');
 await page.emulateMedia({media:'print'});assert.equal(await page.locator('#ui-skinbar').isVisible(),false);
 await page.emulateMedia({media:'screen'});
 // Preferences saved before 2026-09-22 carried a skin field; it is ignored and the mode still applies.
 await page.evaluate(()=>localStorage.setItem('inresearch.ui.v1','{"skin":"attio","mode":"dark"}'));await page.reload();assert.equal((await measure()).theme,'dark');
 await page.evaluate(()=>localStorage.setItem('inresearch.ui.v1','{bad json'));await page.reload();assert.equal((await measure()).theme,'light');
 const blocked=await browser.newContext();await blocked.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw Error('disabled')}}));
 const bp=await blocked.newPage();await bp.goto(base+'/index.html');await bp.locator('#ui-appearance').selectOption('dark');assert.equal(await bp.locator('html').getAttribute('data-ui-theme'),'dark');assert.match(await bp.locator('#ui-save-status').textContent(),/未保存/);await blocked.close();
 assert.deepEqual(errors,[]);console.log('PASS persistence, cross-tab sync, explicit/system mode, print, legacy/corrupt/blocked storage, preserved research state; no page errors');
 await context.close();
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
