const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const {readFileSync}=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const fixture=spawn(process.env.PYTHON||'python3',['-u','-c',`
import os,sys,tempfile,threading,json
from pathlib import Path
sys.path.insert(0,'src')
with tempfile.TemporaryDirectory(prefix='inresearch-workspace-browser-') as temporary:
 os.environ['INRESEARCH_RUNTIME_ROOT']=temporary
 from inresearch.storage.layout import initialize_runtime,workspace_path
 initialize_runtime()
 assert workspace_path('data/raw/site-feedback/requests.jsonl').is_relative_to(Path(temporary).resolve())
 from inresearch.interfaces import http as serve,auth
 for username,role in [('workspace-admin','admin'),('workspace-customer','customer')]: auth.add_user(username,'Only-test-workspace-729461',role)
 serve.AUTH_ON=True
 serve.Handler.log_message=lambda *args:None
 serve.log_run=lambda *args:None
 server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 try:
  print(json.dumps({'port':server.server_port,'runtime':temporary}),flush=True)
  sys.stdin.readline()
 finally:
  server.shutdown();server.server_close();worker.join(timeout=2)
`],{stdio:['pipe','pipe','inherit']});
 const lines=createInterface({input:fixture.stdout});let browser;
 try{
  const info=await new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});fixture.once('error',reject);fixture.once('exit',code=>reject(Error('Fixture exited '+code)));});
  const base='http://127.0.0.1:'+info.port;
  browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});
  const errors=[];
  async function mobile(page,label){for(const width of [320,390,1366]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),label+' no overflow '+width);}}
  async function logged(role){const context=await browser.newContext({viewport:{width:1366,height:768}}),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/login');await page.locator('input[name=username]').fill('workspace-'+role);await page.locator('input[name=password]').fill('Only-test-workspace-729461');await Promise.all([page.waitForURL(base+'/'),page.locator('form button').click()]);await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();assert.equal(await page.locator('#ui-skinbar').getAttribute('data-role'),role,'real fixture identity');return {context,page};}
  const customer=await logged('customer'),admin=await logged('admin');
  if(process.env.UI_INDUSTRY_METRICS==='1') for(const role of ['anonymous','customer','admin']){
   const context=await browser.newContext({viewport:{width:1366,height:768}});
   if(role!=='anonymous')await context.addCookies(await (role==='customer'?customer:admin).context.cookies());
   const page=await context.newPage();
   for(const fonts of ['cold','cached-inter']){
    if(fonts==='cached-inter')await page.evaluate(async()=>{const r=await fetch('/assets/fonts/inter-variable.woff2',{cache:'force-cache'});if(!r.ok)throw Error('Font unavailable');await r.arrayBuffer();});
    await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();await page.waitForFunction(()=>['cached','fallback'].includes(document.getElementById('home-fonts').dataset.fonts));await page.evaluate(()=>document.fonts.ready);
    const metrics=await page.evaluate(()=>{const rect=selector=>{const n=document.querySelector(selector);if(!n)return null;const r=n.getBoundingClientRect();return {y:r.y,height:r.height,width:r.width,display:getComputedStyle(n).display,padding:getComputedStyle(n).padding};};return {identity:document.getElementById('ui-skinbar').dataset.identity,role:document.getElementById('ui-skinbar').dataset.role,fontState:document.getElementById('home-fonts').dataset.fonts,loadedFonts:[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family),viewport:{width:innerWidth,height:innerHeight},header:rect('#ui-skinbar'),body:rect('body'),hero:rect('.hero'),localnav:rect('.local-nav'),market:rect('#market-band'),updates:rect('#home-updates'),panelHeading:rect('.atlas-panel>.panel-heading'),map:rect('#world-map')};});
    console.log('INDUSTRY_METRICS '+role+' '+fonts+' '+JSON.stringify(metrics));
   }await context.close();
  }
  const {context,page}=customer;
  assert.equal(await page.locator('.ui-search-scope-fixed').innerText(),'交付内容');assert.equal(await page.locator('.ui-search-scope option[value=all]').count(),0);
  const headers={Cookie:(await context.cookies()).map(cookie=>cookie.name+'='+cookie.value).join('; ')};
  const request={get:url=>context.request.get(url,{headers}),head:url=>context.request.head(url,{headers})};
  for(const path of ['/assets/workspace.js','/assets/site-search.js','/assets/site-guide.js','/assets/workspace.css'])assert.equal((await request.get(base+path)).status(),200,'customer asset '+path);
  for(const [section,view] of [['companies','companies'],['companies','products'],['atlas','systems'],['atlas','equipment'],['reports',''],['industry','updates']]){
   const params=new URLSearchParams({section});if(view)params.set('view',view);
   const response=await page.goto(base+'/workspace.html?'+params);assert.equal(response.status(),200,'customer workspace '+section+'/'+view);
   await page.locator('#workspace-app[aria-busy=false]').waitFor();assert.equal(await page.locator('#workspace-error').isVisible(),false);
   const data=await (await request.get(base+'/api/workspace?'+params)).json();assert.equal(data.ok,true);assert.ok(data.blocks.length>0);assert.ok(data.blocks.some(b=>b.rows.length>0),'actual rows '+section+'/'+view);
   assert.equal(await page.locator('#workspace-content tbody tr').count(),data.blocks.reduce((count,b)=>count+b.rows.length,0));
   for(const row of data.blocks.flatMap(b=>b.rows).filter(row=>row.href)){
    const destination=new URL(row.href,base);
    assert.ok(['http:','https:'].includes(destination.protocol)&&!destination.username&&!destination.password,'safe list destination '+row.href);
    if(destination.origin===base)assert.equal((await request.head(destination.href)).status(),200,'customer list destination '+row.href);
    else assert.ok(row.name||row.title,'external source has a readable name');
   }
   await mobile(page,'workspace '+section+'/'+view);
   console.log('PASS real customer workspace '+section+'/'+view+' rows, assets and authorized destinations');
  }
  await page.goto(base+'/product-catalog.html?c=supermicro&view=categories');await page.locator('.browser-tools').waitFor();assert.equal(await page.locator('.browser-tools a[href*="view=research"]').count(),0,'delivered product navigation has no forbidden research-workflow entry');
  await page.goto(base+'/project.html?site=fi-salo-atnorth-fin05');await page.locator('#detail .detail-grid').waitFor();assert.equal(await page.locator('#detail a[href^="/supply.html"]').count(),0,'delivered project navigation has no forbidden original-workflow entry');assert.equal(await page.locator('#detail a[href="#site-observation-timeline"]').count(),1);assert.ok(await page.locator('#site-observation-timeline').count()>0);
  await page.goto(base+'/report.html');await page.locator('#q4 h2').waitFor();assert.equal(await page.locator('#docroot section.chapter').count(),4);assert.equal(await page.locator('#q4 h2').innerText(),'四、口径与来源');assert.ok(!/undefined|\bNaN\b|\[object Object\]|阅读队列|审核队列|派工/.test(await page.locator('#docroot').innerText()),'delivered report renders safe API fields without internal workflow or missing-value artifacts');await mobile(page,'delivered report');
  await page.goto(base+'/workspace.html?section=companies&view=companies');await page.locator('#workspace-app[aria-busy=false]').waitFor();const initial=await page.locator('#workspace-content tbody tr').count(),term=await page.locator('#workspace-content tbody tr td').first().innerText();await page.locator('#workspace-query').fill(term);await page.locator('#workspace-filter button').click();await page.waitForURL(url=>url.searchParams.get('q')===term);await page.waitForFunction(value=>!document.getElementById('workspace-app').getAttribute('aria-busy').includes('true')&&document.querySelectorAll('#workspace-content tbody tr').length<value,initial);assert.ok(await page.locator('#workspace-content tbody tr').count()>0);
  await page.locator('#workspace-query').fill('__no-such-workspace-record__');await page.locator('#workspace-filter button').click();await page.locator('.workspace-empty').waitFor();assert.equal(await page.locator('#workspace-content tbody tr').count(),0);
  await page.goto(base+'/search.html?q=Microsoft&scope=delivery');await page.locator('.search-item').first().waitFor();assert.deepEqual(await page.locator('#search-scope option').evaluateAll(nodes=>nodes.map(n=>n.value)),['delivery']);const result=await (await request.get(base+'/api/site-search?q=Microsoft&scope=delivery')).json();assert.ok(result.total>0);assert.equal(await page.locator('.search-item').count(),result.rows.length);assert.ok(result.rows.every(row=>row.area==='delivery'));assert.equal((await request.get(base+'/api/site-search?q=tasks&scope=all')).status(),403);await mobile(page,'actual search results');
  await page.locator('#search-query').fill('__no-such-search-record__');await page.locator('#site-search button').click();await page.waitForFunction(()=>document.getElementById('search-status').textContent==='0 条结果');assert.equal(await page.locator('.search-item').count(),0);
  for(const view of ['method','sources','help','about','updates','privacy','terms']){assert.equal((await page.goto(base+'/guide.html?view='+view)).status(),200);await page.locator('[data-guide="'+view+'"].is-current h1').waitFor();assert.equal(await page.locator('[data-guide].is-current').count(),1);}
  await page.goto(base+'/guide.html?view=feedback&from='+encodeURIComponent('/workspace.html?section=companies&view=products'));assert.equal(await page.locator('#feedback-form [name=context]').inputValue(),'/workspace.html?section=companies&view=products');const title='SYNTHETIC temporary browser feedback';await page.locator('#feedback-form [name=title]').fill(title);await page.locator('#feedback-form [name=description]').fill('Temporary test only; never a research adoption or production report.');await page.locator('#feedback-form button').click();await page.waitForFunction(()=>document.getElementById('feedback-status').textContent.includes('记录号：'));const rows=readFileSync(info.runtime+'/data/raw/site-feedback/requests.jsonl','utf8').trim().split('\n').map(JSON.parse);assert.equal(rows.length,1);assert.equal(rows[0].title,title);assert.equal(rows[0].actor,'workspace-customer');assert.equal(rows[0].status,'received');assert.equal(await page.locator('#feedback-form [name=title]').inputValue(),'');
  await admin.page.goto(base+'/workspace.html?section=content&view=quality');await admin.page.locator('#workspace-app[aria-busy=false]').waitFor();assert.match(await admin.page.locator('#workspace-content').innerText(),/SYNTHETIC temporary browser feedback/);
  await admin.page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
  await admin.page.locator('.ui-search-scope').selectOption('all');await admin.page.locator('.ui-search-form [name=q]').fill('Microsoft');
  await Promise.all([admin.page.waitForURL(url=>url.pathname==='/search.html'&&url.searchParams.get('scope')==='all'&&url.searchParams.get('q')==='Microsoft'),admin.page.locator('.ui-search-form button').click()]);
  await admin.page.locator('.search-item').first().waitFor();await admin.page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();assert.equal(await admin.page.locator('.ui-search-scope').inputValue(),'all');assert.equal(await admin.page.locator('#search-scope').inputValue(),'all');
  await admin.page.locator('#search-query').fill('任务');await admin.page.locator('#search-scope').selectOption('backstage');await admin.page.locator('#site-search button').click();await admin.page.waitForURL(url=>url.searchParams.get('scope')==='backstage'&&url.searchParams.get('q')==='任务');await admin.page.waitForFunction(()=>document.querySelector('.ui-search-scope')?.value==='backstage');await admin.page.locator('.search-item').first().waitFor();assert.deepEqual(await admin.page.locator('#search-scope option').evaluateAll(nodes=>nodes.map(n=>n.value)),['delivery','backstage','all']);assert.ok((await admin.page.locator('.search-kind').allInnerTexts()).every(text=>text.startsWith('后台工作')));
  for(const width of [320,390,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'guide width '+width);}
  const anonymous=await browser.newContext();for(const path of ['/workspace.html?section=reports','/search.html','/guide.html?view=help'])assert.equal((await anonymous.request.get(base+path,{maxRedirects:0})).status(),302);await anonymous.close();
  assert.deepEqual(errors,[]);await context.close();await admin.context.close();console.log('PASS real customer workspace rows/filter/destinations, authorized search, guide assets, isolated persisted feedback and IT review; no production or checkout writes');
 }finally{if(browser)await browser.close();fixture.stdin.end('\n');lines.close();if(fixture.exitCode===null)await new Promise(resolve=>fixture.once('exit',resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
