const {setAppearance} = require('./ui_helpers.cjs');
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
 const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true, args:['--enable-unsafe-swiftshader'],
   ...(process.env.UI_BROWSER_EXECUTABLE ? {executablePath:process.env.UI_BROWSER_EXECUTABLE} : {})});
 try {
 // CI has software WebGL. Keep CSS dimensions and real scenes, with fewer raster pixels.
 const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark',
   reducedMotion:'reduce',deviceScaleFactor:process.env.CI ? 0.5 : 1});
 // The shared runner owns a temporary real admin account; protected pages keep their server gate.
 if(process.env.UI_ADMIN_COOKIE) {
   const separator=process.env.UI_ADMIN_COOKIE.indexOf('=');
   await context.addCookies([{name:process.env.UI_ADMIN_COOKIE.slice(0,separator),
     value:process.env.UI_ADMIN_COOKIE.slice(separator+1),url:base,httpOnly:true,sameSite:'Lax'}]);
 }
 const page = await context.newPage(); const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const measure = () => page.evaluate(()=>({theme:document.documentElement.dataset.uiTheme,width:document.documentElement.scrollWidth,viewport:innerWidth,bg:getComputedStyle(document.body).backgroundColor,bar:document.querySelectorAll('#ui-skinbar').length,font:getComputedStyle(document.body).fontFamily}));
 for (const file of manifest.static_pages) {
   const query = file==='doc.html'?'?f=framework/05_interface_system.md':'';
   await page.goto(base+'/'+file+query); await page.locator('#ui-skinbar').waitFor();
   await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
   const navState=await page.evaluate(()=>fetch('/api/navigation?'+new URLSearchParams({page:location.pathname+location.search})).then(response=>response.json()));
   if(navState.navigation[navState.active.area]?.some(item=>item.id===navState.active.section)){const active=page.locator('.ui-navigation-'+navState.active.area+' [data-nav-section="'+navState.active.section+'"]');assert.equal(await active.count(),1,file+' registered primary section');assert.equal(await active.evaluate(node=>node.matches('[aria-current=page]')||!!node.querySelector(':scope > summary[aria-current=page]')),true,file+' active primary navigation');}else if(navState.active.section){assert.deepEqual(navState.active,{area:'public',section:'tasks',view:null},file+' only the public task page sits outside signed-in business navigation');}
   assert.equal(await page.locator('.ui-navigation a[href="/login"], .ui-navigation a[href="/account"], .ui-navigation .ui-admin-link').count(),0,file+' business navigation only');
   if(file==='index.html'){await page.locator('.ui-account-menu > summary').waitFor();assert.equal(await page.locator('.ui-navigation-delivery [data-nav-section]').count(),6);assert.equal(await page.locator('.ui-navigation-backstage [data-nav-section]').count(),6);assert.equal(await page.locator('.ui-account-panel .ui-management-link').count(),0,'account menu contains account actions only');}
   assert.equal(await page.locator('[data-ui-choice]').count(),0,file+' has no skin switch');
   if(file==='company.html') {await page.locator('#catalog-title').waitFor();assert.match(page.url(),/product-catalog.html/);}
   if(file==='report.html') {await page.locator('#cover').waitFor();assert.equal(await page.locator('section.chapter').count(),4);}
   if(file==='ops.html'){await page.locator('#tasks .task-btn').first().waitFor();await page.locator('#freshness-drawer > summary').click();await page.locator('#freshness tr').nth(1).waitFor({state:'attached'});assert.ok(await page.locator('#freshness tr').count()>=6,'generated-artifact freshness table');assert.equal(await page.locator('#error').textContent(),'');assert.ok(await page.locator('#tasks .task-btn').count()>0);assert.equal(await page.locator('#modules, #projects, #funnel, #indicators').count(),0,'funnel, monitoring, modules and project blocks retired');}
   // Ledger boot canonicalizes its view hash after fetching the model.
   if(file==='ledger.html')await page.locator('#model-app:not([aria-busy])').waitFor();
   const settledUrl=page.url();
   // Shared fonts: the bundled Inter + Noto Sans SC stack applies to the body of every application page.
   const cacheFontId=file==='ops.html'?'ops-fonts':['index.html','industry.html','projects.html','project.html','market.html'].includes(file)?'home-fonts':null;
   if(cacheFontId)await page.waitForFunction(id=>['cached','fallback'].includes(document.getElementById(id).dataset.fonts),cacheFontId);
   const fonts=await page.evaluate(async()=>{await document.fonts.ready;return [...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)});
   if(cacheFontId)assert.ok(fonts.every(f=>['Inter','Noto Sans SC'].includes(f)),file+' reuses cached shared fonts or system fallback');
   else assert.ok(fonts.includes('Inter')&&fonts.includes('Noto Sans SC'),file+' bundled fonts loaded: '+fonts.join(','));
   assert.match((await measure()).font,/^Inter, "Noto Sans SC"/,file+' body font stack');
   for (const mode of ['light','dark']) {
     await setAppearance(page, mode);
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
     // The compact theme button retains all three preference modes.
     assert.equal(await page.locator('.ui-theme-panel [data-ui-mode-choice]').count(),3,file+' three theme choices');
     assert.equal(await page.locator('[data-ui-mode-choice="'+mode+'"]').getAttribute('aria-pressed'),'true',file+' selected theme');
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
   assert.ok(box.height<=90,file+' phone head bar is two rows, got '+box.height+'px; '+JSON.stringify(await page.locator('#ui-skinbar :scope > *,#ui-skinbar .ui-toolbar > *,#ui-skinbar .ui-mobile-navigation > *').evaluateAll(nodes=>nodes.map(node=>({class:node.className,height:node.getBoundingClientRect().height,margin:getComputedStyle(node).margin,padding:getComputedStyle(node).padding})))));
   const b=await page.locator('#ui-appearance').boundingBox();assert.ok(b.x>=0 && b.x+b.width<=361,file+' appearance control on screen');
   for(const width of [320,390]){
     await page.setViewportSize({width,height:800});
     const summary=page.locator('.ui-account-menu > summary');await summary.click();
     const menu=await page.locator('.ui-account-panel').boundingBox(),header=await page.locator('#ui-skinbar').boundingBox();
     assert.ok(header.width<=width && header.height<=90,file+' account header fits '+width);
     assert.ok(menu.x>=0 && menu.x+menu.width<=width+1,file+' account menu fits '+width);
     await summary.press('Escape');
   }
   if(file==='research.html') {assert.ok((await measure()).width<=361);if(dir)await page.screenshot({path:path.join(dir,'research-mobile.png')});}
   await page.setViewportSize({width:1440,height:1000});console.log('PASS',file,'light/dark, fonts, controls + phone head bar');
 }
 // 研究页已退役（2026-09-28）：节点页承接；刷新保留外观偏好
 await page.goto(base+'/node.html?id=part:gpu');await page.locator('#five .col').first().waitFor();
 await setAppearance(page, 'light');const url=page.url();
 await page.reload();assert.equal((await measure()).theme,'light');assert.equal(page.url(),url);
 const second=await context.newPage();await second.goto(base+'/index.html');
 await setAppearance(second, 'dark');await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='dark');
 await setAppearance(page, 'system');assert.equal((await measure()).theme,'dark');await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='light');
 await setAppearance(page, 'light');await page.emulateMedia({colorScheme:'dark'});assert.equal((await measure()).theme,'light');
 await page.emulateMedia({media:'print'});assert.equal(await page.locator('#ui-skinbar').isVisible(),false);
 await page.emulateMedia({media:'screen'});
 // Preferences saved before 2026-09-22 carried a skin field; it is ignored and the mode still applies.
 await page.evaluate(()=>localStorage.setItem('inresearch.ui.v1','{"skin":"attio","mode":"dark"}'));await page.reload();assert.equal((await measure()).theme,'dark');
 await page.evaluate(()=>localStorage.setItem('inresearch.ui.v1','{bad json'));await page.reload();assert.equal((await measure()).theme,'light');
 const blocked=await browser.newContext();await blocked.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw Error('disabled')}}));
 const bp=await blocked.newPage();await bp.goto(base+'/index.html');await setAppearance(bp, 'dark');assert.equal(await bp.locator('html').getAttribute('data-ui-theme'),'dark');assert.match(await bp.locator('#ui-save-status').textContent(),/未保存/);await blocked.close();
 assert.deepEqual(errors,[]);console.log('PASS persistence, cross-tab sync, explicit/system mode, print, legacy/corrupt/blocked storage, preserved research state; no page errors');
 await context.close();
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
