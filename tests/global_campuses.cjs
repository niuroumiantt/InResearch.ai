/* Real signed roles and actual HTTP projections; no production writes. */
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const {chromium}=require('playwright');
const {mkdirSync}=require('node:fs');
const server=spawn(process.env.PYTHON||'python3',['-u','-c',String.raw`
import sys,json,tempfile,secrets
from pathlib import Path
sys.path.insert(0,'src')
from inresearch.interfaces import http,auth
with tempfile.TemporaryDirectory(prefix='campus-browser-') as folder:
 auth.USERS_FILE=Path(folder)/'users.json';auth.SECRET_FILE=Path(folder)/'.secret'
 for name,role in [('campus-admin','admin'),('campus-customer','customer')]:auth.add_user(name,secrets.token_urlsafe(32),role)
 http.AUTH_ON=True;http.Handler.log_message=lambda *args:None;http.log_run=lambda *args:None
 server=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler)
 print(json.dumps({'port':server.server_port,'admin':auth.make_cookie('campus-admin').split(';')[0],'customer':auth.make_cookie('campus-customer').split(';')[0]}),flush=True)
 server.serve_forever()
`],{cwd:require('node:path').resolve(__dirname,'..'),env:process.env,stdio:['ignore','pipe','inherit']});
const lines=createInterface({input:server.stdout});
const ready=new Promise((resolve,reject)=>{lines.once('line',s=>{try{resolve(JSON.parse(s));}catch{reject(Error('readiness invalid'));}});server.once('error',reject);server.once('exit',()=>reject(Error('server stopped')));});
(async()=>{
 let browser;
 try{
  const credentials=await ready,base='http://127.0.0.1:'+credentials.port;
  browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE?{executablePath:process.env.UI_BROWSER_EXECUTABLE}:{})});
  const anonymous=await browser.newContext();
  for(const route of ['/regions.html','/projects.html','/project.html?site=us-tx-abilene']){
   const response=await anonymous.request.get(base+route,{maxRedirects:0});assert.equal(response.status(),302);assert.equal(response.headers().location,'/login');
  }
  await anonymous.close();
  for(const role of ['customer','admin']){
   const context=await browser.newContext({viewport:{width:1440,height:1000}});
   const cookie=credentials[role].split('=');await context.addCookies([{name:cookie.shift(),value:cookie.join('='),url:base}]);
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   const go=async route=>{await page.goto(base+route);await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();await page.waitForFunction(()=>document.getElementById('load-status')?.textContent==='');};
   const json=async route=>{const r=await context.request.get(base+route);assert.equal(r.status(),200);return r.json();};
   const source=await json('/api/industry');assert.ok(source.rows.length>0);
   const named=source.rows.find(r=>!r.portfolio&&r.geography?.identity_scope!=='cluster'&&r.country);
   assert.ok(named);const id=named.site_id;
   const nav=await json('/api/navigation?page=%2Fregions.html');
   assert.equal(nav.navigation.delivery.length,7);assert.equal(nav.navigation.delivery.flatMap(x=>x.children).length,15);
   assert.deepEqual(nav.active,{area:'delivery',section:'campuses',view:'regions'});
   assert.deepEqual(nav.navigation.delivery.find(x=>x.id==='campuses').children.map(x=>x.label),['园区名录','地区分析']);
   if(role==='customer')assert.deepEqual(nav.navigation.backstage,[]);
   await go('/projects.html');await page.locator('#project-rows tbody tr').first().waitFor();
   assert.equal(await page.locator('#geographic-filters').count(),1);
   await page.locator('#campus-search input').fill(id);await page.locator('#campus-search button').click();
   await page.waitForFunction(id=>document.querySelector('#project-rows tbody a')?.href.includes('site='+encodeURIComponent(id))&&!document.querySelector('#load-status').textContent,id);
   assert.equal(await page.locator('#project-rows tbody tr').count(),1);assert.equal(await page.locator('#geographic-filters').count(),1);
   await go('/projects.html?view=map');await page.locator('#world-map .site-point').first().waitFor();assert.equal(await page.locator('#project-list').isHidden(),true);
   await go('/regions.html');await page.locator('#region-comparison tbody tr[data-region]').first().waitFor();
   const groups=source.geographic_analysis.groups.filter(g=>g.level==='country');assert.equal(await page.locator('#region-comparison tbody tr[data-region]').count(),groups.length);
   const country=groups.find(g=>g.filters.country===named.country),row=page.locator('#region-comparison tbody tr').filter({has:page.locator('a[href*="country='+named.country+'"]')});
   assert.equal(await row.locator('td').first().innerText(),String(country.totals.sites));
   if(country.known_records)assert.equal(await row.locator('td').nth(1).innerText(),Number(country.totals.operating).toLocaleString('en-US',{maximumFractionDigits:2})+' MW');
   await page.locator('#region-level').selectOption('city');await page.waitForURL('**level=city');
   await page.waitForFunction(()=>!document.querySelector('#load-status').textContent);
   assert.equal(await page.locator('#region-comparison tbody tr[data-region]').count(),source.geographic_analysis.groups.filter(g=>g.level==='city').length);
   for(const width of [320,390,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'region no page overflow '+width);}
   assert.equal(await page.locator('#ui-skinbar').count(),1);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:process.env.UI_QA_DIR+'/regions-'+role+'.png'});}
   await go('/project.html?site='+encodeURIComponent(id)+'#site-observation-timeline');await page.locator('#site-observation-timeline').waitFor();
   assert.equal(await page.locator('[data-campus-module]').count(),7);assert.ok((await page.locator('#campus-overview').innerText()).includes(id));
   assert.match(await page.locator('#campus-equipment').innerText(),/不.*现场安装/);
   assert.match(await page.locator('#campus-economics').innerText(),/不自动填入园区参数/);
   const after=await json('/api/industry?site='+encodeURIComponent(id));assert.deepEqual(after.detail,source.rows.find(r=>r.site_id===id));
   await go('/industry.html');assert.equal(await page.locator('#industry-entry').isVisible(),true);assert.equal(await page.locator('#atlas-tools').isHidden(),true);
   await go('/industry.html?c=meta');await page.locator('#world-map .site-point').first().waitFor();
   if(role==='admin'){
    const content=await json('/api/workspace?section=content&view=projects');assert.ok(content.blocks[0].columns.some(c=>c.key==='site_id'));
    const quality=await json('/api/workspace?section=content&view=quality');assert.equal(quality.blocks[0].title,'园区身份与数据缺口');
   }else assert.equal((await context.request.get(base+'/api/workspace?section=content&view=projects')).status(),403);
   assert.deepEqual(errors,[]);await context.close();
  }
  console.log('PASS global campuses: real roles, legacy IDs/links, geography, native totals, seven detail modules, mobile and backstage');
 }finally{await browser?.close();server.kill();lines.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
