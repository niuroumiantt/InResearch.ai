/* Startup definitions recover without constructing a second scene or changing data. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
 const browser = await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
 try {
  const page = await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:.5,reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let failure=true, malformed=false;
  await page.route('**/framework/bom.json*',route=>failure
   ? route.fulfill({status:malformed?200:503,contentType:'application/json',body:malformed?'{"parts":[null]}':'{"error":"injected failure"}'})
   : route.continue());
  for(const path of ['/bom3d.html?p=server','/rack3d.html?node=part:gpu']) {
   failure=true;malformed=path.includes('rack');
   await page.goto(process.env.UI_BASE_URL+path,{waitUntil:'domcontentloaded'});
   const status=page.locator('.rg-scene-startup[data-state=error]');await status.waitFor();
   assert.equal(await page.locator('.hud').evaluate(el=>el.inert),true);
   assert.equal(await page.locator('.rg-3d-panel').count(),0);
   for(const width of [1280,360]) {
    await page.setViewportSize({width,height:900});
    for(const skin of ['Attio','folk']) for(const mode of ['light','dark']) {
     await page.getByRole('button',{name:skin,exact:true}).click();
     await page.locator('#ui-appearance').selectOption(mode);
     assert.ok(await status.getByRole('button',{name:'重试',exact:true}).isVisible());
     const box=await status.boundingBox();assert.ok(box.x>=0 && box.x+box.width<=width);
     assert.equal(await status.getAttribute('aria-busy'),'false');
     assert.equal(await page.getByRole('link',{name:'研究',exact:true}).first().isVisible(),true);
    }
   }
   await page.setViewportSize({width:1280,height:900});
   failure=false;await status.getByRole('button',{name:'重试',exact:true}).click();
   await page.locator('#dossier .rg-3d-panel[data-state=ready]').waitFor();
   assert.equal(await page.locator('.rg-scene-startup').count(),0);
   assert.equal(await page.locator('.hud').evaluate(el=>el.inert),false);
   assert.equal(await page.locator('#dossier canvas').count(),1);
   await page.locator('#dossier').getByRole('button',{name:'关闭部件档案'}).click();
   await page.locator('#play').click();assert.equal(await page.locator('#explode').inputValue(),'100');
  }
  await page.goto(process.env.UI_BASE_URL+'/login');
  await page.evaluate(async()=>{
   const {loadSceneData}=await import('/assets/scene-data.js');
   const check=(value,message)=>{if(!value)throw Error(message);};
   const settle=async()=>{for(let i=0;i<14;i++)await Promise.resolve();};
   const originalFetch=globalThis.fetch, requests=[];
   globalThis.fetch=(url,options)=>new Promise(resolve=>requests.push({url,signal:options.signal,resolve}));
   const control=document.createElement('button');document.body.append(control);
   const sources=[{url:'/a',collection:'records'},{url:'/b',collection:'records'}];
   const ok=value=>({ok:true,json:async()=>({records:[{id:value}]})});
   try {
    const result=loadSceneData(sources,{controls:[control]});
    check(control.inert,'controls were usable during loading');
    requests[0].resolve({ok:false,status:503});await settle();
    check(requests.slice(0,2).every(r=>r.signal.aborted),'failed batch left sibling request active');
    check(document.querySelector('.rg-scene-startup').dataset.state==='error','failure hidden');
    const retry=document.querySelector('.rg-scene-startup button');retry.click();retry.click();await settle();
    check(requests.length===4,'double retry created more than one new batch');
    requests[2].resolve(ok('new-a'));requests[3].resolve(ok('new-b'));
    const data=await result;requests[1].resolve(ok('old-b'));await settle();
    check(data[0].records[0].id==='new-a' && data[1].records[0].id==='new-b','old batch won');
    check(!control.inert && !document.querySelector('.rg-scene-startup'),'success did not release UI');
    // A non-cooperative request can finish after timeout; it still cannot publish.
    control.inert=true;
    const timeout=loadSceneData([sources[0]],{controls:[control],timeoutMs:30});
    await new Promise(resolve=>setTimeout(resolve,60));
    check(requests[4].signal.aborted,'deadline did not cancel fetch');
    check(document.querySelector('.rg-scene-startup').dataset.state==='error','timeout not visible');
    document.querySelector('.rg-scene-startup button').click();await settle();
    requests[5].resolve(ok('retry'));const recovered=await timeout;
    requests[4].resolve(ok('late'));await settle();
    check(recovered[0].records[0].id==='retry' && control.inert,'retry changed prior control state');
   } finally {globalThis.fetch=originalFetch;control.remove();}
  });
  assert.deepEqual(errors,[]);
  console.log('PASS both scene startup HTTP/shape failures → retry → real research/renderer ready; controls/navigation, 8 appearance/width combinations, timeout, sibling cancellation, double retry, stale batch and prior inert state');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
