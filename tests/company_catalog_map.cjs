/* Real isolated SQLite -> HTTP -> homepage -> business filter -> one specification.
 * Model/path identities are from the delivered batch; cells are TEST_VALUE fixtures.
 */
const assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join}=require('node:path');
const {createInterface}=require('node:readline');
const {chromium}=require('playwright');
(async()=>{
 const runtime=mkdtempSync(join(tmpdir(),'company-catalog-map-'));
 const server=spawn(process.env.PYTHON||'python3',['-u','-c',
  "import sys,json;sys.path.insert(0,'src');from tests.unit.test_company_window import company_catalog_fixture;from inresearch.paths import project_root;from inresearch.workflow import product_catalog;from inresearch.interfaces import http;product_catalog.receive(project_root(),company_catalog_fixture(),company='supermicro');s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port}),flush=True);s.serve_forever()"],
  {env:{...process.env,INRESEARCH_RUNTIME_ROOT:runtime,INRESEARCH_MARKET_ENABLED:'0'},stdio:['ignore','pipe','inherit']});
 let browser;
 try{
  const ready=await new Promise((resolve,reject)=>{createInterface({input:server.stdout}).once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',code=>reject(Error('Fixture server exited '+code)));});
  const base='http://127.0.0.1:'+ready.port;
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(base+'/product-catalog.html?c=supermicro');
  await page.locator('#catalog-summary strong').first().waitFor();
  assert.deepEqual(await page.locator('#catalog-summary strong').allTextContents(),['5','5','5']);
  assert.match(await page.locator('#catalog-categories').innerText(),/5 个条目尚无原厂分类/);
  assert.equal(await page.locator('#product-lines .product-example').count(),4);
  assert.equal(requests.filter(url=>url.includes('/api/product-catalog/')).length,0,'homepage does not fetch specification bodies');
  for(const theme of ['light','dark'])for(const width of [1440,390,320]){
   await page.evaluate(t=>{document.documentElement.dataset.uiTheme=t;document.documentElement.dataset.uiMode=t;},theme);
   await page.setViewportSize({width,height:1100});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),theme+' '+width+' no overflow');
   if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+'/company-catalog-map-'+theme+'-'+width+'.png',fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1100});
  await page.locator('.product-line-entry').filter({hasText:'AI / GPU 服务器'}).click();
  await page.getByRole('heading',{name:'SYS-821GE-TNHR',exact:true}).waitFor();
  assert.equal(await page.locator('#products .product').count(),1);
  for(const width of [390,320]){
   await page.setViewportSize({width,height:1100});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'product filter '+width+' no overflow');
  }
  await page.setViewportSize({width:1440,height:1100});
  assert.match(await page.locator('#detail').innerText(),/TEST_VALUE/);
  assert.match(await page.locator('#detail a').last().getAttribute('href'),/sys-821ge-tnhr/);
  const exportUrl=await page.locator('#export-products').getAttribute('href');
  assert.equal(new URL(exportUrl,base).searchParams.get('line'),'gpu-systems');
  const csv=await (await page.request.get(base+exportUrl)).text();
  assert.ok(csv.includes('SYS-821GE-TNHR'));assert.ok(!csv.includes('SYS-442B-NR'));
  await page.reload();await page.getByRole('heading',{name:'SYS-821GE-TNHR',exact:true}).waitFor();
  await page.locator('#business-lines [data-line=servers]').click();
  await page.waitForFunction(()=>document.querySelectorAll('#products .product').length===3);
  assert.match(await page.locator('#products').innerText(),/SYS-442B-NR/);
  assert.ok(!(await page.locator('#products').innerText()).includes('SYS-821GE-TNHR'));
  await page.reload();
  await page.waitForFunction(()=>document.querySelectorAll('#products .product').length===3);
  assert.equal(new URL(page.url()).searchParams.get('line'),'servers','refresh preserves the entire category');
  await page.locator('#business-lines [data-line=storage]').click();
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('没有符合'));
  assert.equal(await page.locator('#products .product').count(),0,'zero category stays empty');
  await page.locator('#all-catalog').click();
  await page.waitForFunction(()=>document.querySelectorAll('#products .product').length===5);
  // A newer mixed run must not hide the unclassified model behind a catalog-only scope.
  const mixed=spawnSync(process.env.PYTHON||'python3',['-c',
   "import sys;sys.path.insert(0,'src');from tests.unit.test_company_window import company_catalog_fixture;from inresearch.paths import project_root;from inresearch.workflow import product_catalog;d=company_catalog_fixture();d['generated_at']='2026-10-07T00:01:00+00:00';d['products'][0]['taxonomy']=[{'slug':'servers','name':'Servers'}];product_catalog.receive(project_root(),d,company='supermicro')"],
   {env:{...process.env,INRESEARCH_RUNTIME_ROOT:runtime,INRESEARCH_MARKET_ENABLED:'0'},encoding:'utf8'});
  assert.equal(mixed.status,0,mixed.stderr);
  await page.locator('#company-home-link').click();
  await page.locator('#product-lines .product-example').filter({hasText:'SYS-212GB-FNR'}).click();
  await page.getByRole('heading',{name:'SYS-212GB-FNR',exact:true}).waitFor();
  assert.match(await page.locator('#detail').innerText(),/TEST_VALUE/);
  assert.deepEqual(errors,[]);
  console.log('company catalog map: received SQLite, taxonomy-free models, business filters, CSV, exact detail and responsive layouts OK');
 }finally{
  if(browser)await browser.close();
  await new Promise(resolve=>{if(server.exitCode!==null)return resolve();server.once('exit',resolve);server.kill();});
  rmSync(runtime,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
