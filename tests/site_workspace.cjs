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
 # A persisted ordinary test observation exercises interval/nested-scope cells
 # through the actual server; this temporary source is never formally adopted.
 from inresearch.paths import project_root
 from inresearch.delivery import source_publication
 from inresearch.knowledge import object_observations
 from datetime import datetime,timezone
 import hashlib
 identity=object_observations.object_record('statistic',{'publisher':'SYNTHETIC UI FIXTURE',
   'series':'SYNTHETIC interval only','geography':'test','definition':'browser rendering only'},'SYNTHETIC interval only')
 stamp=datetime.now(timezone.utc).isoformat()
 marker='SYNTHETIC browser interval fixture; not research evidence'
 row={'id':'synthetic-workspace-interval','object_id':identity['id'],'metric':'range',
   'scope':{'configuration':{'region':'SYNTHETIC UI ONLY','modes':['A','B']},'quantity':0,'live':False},
   'kind':'reported','basis':'SYNTHETIC browser fixture only','unit':'test units','value':{'value_range':[0,1.25]},
   'effective_at':'2026-10-13','recorded_at':stamp,'target_ids':[],
   'registration':{'status':'unverified','at':stamp,'registered_by':'workspace-browser-fixture'},
   'source':{'url':'https://example.invalid/synthetic-workspace-fixture',
     'sha256':hashlib.sha256(marker.encode()).hexdigest(),'locator':'temporary browser fixture',
     'quote':marker,'context_sha256':hashlib.sha256(marker.encode()).hexdigest(),'published_at':'2026-10-13'}}
 object_observations.check({'version':1,'objects':{identity['id']:identity},'records':[row]})
 publication=source_publication.empty();publication['objects'][identity['id']]=identity;publication['records']=[row]
 path=workspace_path(source_publication.PATH,project_root());assert path.is_relative_to(Path(temporary).resolve())
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(publication))
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
  await page.goto(base+'/project.html?site=fi-salo-atnorth-fin05');await page.locator('#detail .campus-dossier').waitFor();assert.equal(await page.locator('#detail a[href^="/supply.html"]').count(),0,'delivered project navigation has no forbidden original-workflow entry');assert.equal(await page.locator('#detail a[href="#site-observation-timeline"]').count(),1);assert.ok(await page.locator('#site-observation-timeline').count()>0);
  await page.goto(base+'/report.html');await page.locator('#q4 h2').waitFor();assert.equal(await page.locator('#docroot section.chapter').count(),4);assert.equal(await page.locator('#q4 h2').innerText(),'四、口径与来源');assert.ok(!/undefined|\bNaN\b|\[object Object\]|阅读队列|审核队列|派工/.test(await page.locator('#docroot').innerText()),'delivered report renders safe API fields without internal workflow or missing-value artifacts');await mobile(page,'delivered report');
  await page.goto(base+'/workspace.html?section=companies&view=companies');await page.locator('#workspace-app[aria-busy=false]').waitFor();const initial=await page.locator('#workspace-content tbody tr').count(),term=await page.locator('#workspace-content tbody tr td').first().innerText();await page.locator('#workspace-query').fill(term);await page.locator('#workspace-filter button').click();await page.waitForURL(url=>url.searchParams.get('q')===term);await page.waitForFunction(value=>!document.getElementById('workspace-app').getAttribute('aria-busy').includes('true')&&document.querySelectorAll('#workspace-content tbody tr').length<value,initial);assert.ok(await page.locator('#workspace-content tbody tr').count()>0);
  await page.locator('#workspace-query').fill('__no-such-workspace-record__');await page.locator('#workspace-filter button').click();await page.locator('.workspace-empty').waitFor();assert.equal(await page.locator('#workspace-content tbody tr').count(),0);
  // Delay genuine responses to keep the replacement request pending after the
  // first browser fetch aborts. No response payload is fabricated or replaced.
  const delayed=new Map(),started=new Map(),signals=new Map();
  for(const key of ['__cancelled_old_workspace__','Microsoft'])signals.set(key,new Promise(resolve=>started.set(key,resolve)));
  const routePattern='**/api/workspace?*';
  const delayWorkspace=async route=>{
   const key=new URL(route.request().url()).searchParams.get('q');
   if(!signals.has(key))return route.continue();
   const response=await route.fetch(),data=await response.json();let release;
   const wait=new Promise(resolve=>{release=resolve;});
   const entry={data,release,done:null};delayed.set(key,entry);started.get(key)();
   entry.done=(async()=>{await wait;try{await route.fulfill({response});}catch(error){if(!route.request().failure())throw error;}})();
   await entry.done;
  };
  await page.route(routePattern,delayWorkspace);
  await page.locator('#workspace-query').fill('__cancelled_old_workspace__');await page.locator('#workspace-filter button').click();await signals.get('__cancelled_old_workspace__');
  const oldAborted=page.waitForEvent('requestfailed',{predicate:r=>new URL(r.url()).pathname==='/api/workspace'&&new URL(r.url()).searchParams.get('q')==='__cancelled_old_workspace__'});
  await page.locator('#workspace-query').fill('Microsoft');await page.locator('#workspace-filter button').click();await Promise.all([oldAborted,signals.get('Microsoft')]);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await page.locator('#workspace-app').getAttribute('aria-busy'),'true','cancelled old request cannot finish the replacement loading state');
  assert.equal(await page.locator('#workspace-error').isVisible(),false);
  delayed.get('__cancelled_old_workspace__').release();await delayed.get('__cancelled_old_workspace__').done;
  assert.equal(await page.locator('#workspace-app').getAttribute('aria-busy'),'true','late cancelled response cannot alter the new busy state');
  delayed.get('Microsoft').release();await delayed.get('Microsoft').done;await page.locator('#workspace-app[aria-busy=false]').waitFor();
  assert.equal(await page.locator('#workspace-content tbody tr').count(),delayed.get('Microsoft').data.blocks.reduce((n,b)=>n+b.rows.length,0));
  assert.equal(await page.locator('#workspace-content tbody tr td').first().innerText(),delayed.get('Microsoft').data.blocks[0].rows[0].name);assert.equal(await page.locator('#workspace-error').isVisible(),false);await page.unroute(routePattern,delayWorkspace);
  await admin.page.goto(base+'/workspace.html?section=content&view=statistics');await admin.page.locator('#workspace-app[aria-busy=false]').waitFor();
  const statistics=admin.page.locator('.workspace-block').filter({has:admin.page.getByRole('heading',{name:'统计与报价观测历史',exact:true})});
  assert.ok(!/\[object Object\]/.test(await statistics.innerText()),'actual stored statistic scopes are readable');
  const native=statistics.locator('tbody tr').filter({hasText:'Texas industrial electricity price'}).first();assert.match(await native.innerText(),/sector：industrial.*coverage：ultimate customers/s);
  const interval=statistics.locator('tbody tr').filter({hasText:'SYNTHETIC interval only'});assert.equal(await interval.count(),1);assert.equal(await interval.locator('td').nth(2).innerText(),'0 至 1.25');
  assert.match(await interval.locator('td').nth(4).innerText(),/configuration：\{region：SYNTHETIC UI ONLY；modes：\[A、B\]\}；quantity：0；live：false/);
  assert.equal(await interval.locator('td').nth(6).innerText(),'unverified');await mobile(admin.page,'statistics objects and intervals');
  console.log('PASS actual statistic scope/nested arrays/zero/false and native interval formatting; cancelled real response cannot clear replacement busy state or overwrite current rows');
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
