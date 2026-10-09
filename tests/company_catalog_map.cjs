/* Real SQLite -> company -> hierarchical category -> selected model.
 * Production URL/model shapes, explicit TEST_VALUE cells; no private corpus claims. */
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {mkdtempSync,rmSync,mkdirSync}=require('node:fs');
const {tmpdir}=require('node:os');const {join}=require('node:path');
const {createInterface}=require('node:readline');const {chromium}=require('playwright');
(async()=>{
 const runtime=mkdtempSync(join(tmpdir(),'company-category-map-'));
 const server=spawn(process.env.PYTHON||'python3',['-u','-c',
  "import sys,json;sys.path.insert(0,'src');from tests.unit.test_catalog_browse import browse_fixture;from inresearch.paths import project_root;from inresearch.workflow import product_catalog;from inresearch.interfaces import http;product_catalog.receive(project_root(),browse_fixture(),'supermicro');s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port}),flush=True);s.serve_forever()"],
  {env:{...process.env,INRESEARCH_RUNTIME_ROOT:runtime,INRESEARCH_MARKET_ENABLED:'0'},stdio:['ignore','pipe','inherit']});
 let browser;
 try{
  const ready=await new Promise((resolve,reject)=>{createInterface({input:server.stdout}).once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',code=>reject(Error('Fixture server exited '+code)));});
  const base='http://127.0.0.1:'+ready.port;
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(base+'/product-catalog.html?c=supermicro');await page.locator('#catalog-summary strong').first().waitFor();
  assert.deepEqual(await page.locator('#catalog-summary strong').allTextContents(),['14','14','20']);
  assert.equal(requests.filter(url=>url.includes('/api/product-catalog/')).length,0,'homepage does not fetch specifications');
  assert.equal(await page.locator('.product-line-entry').filter({hasText:'主板'}).count(),1);
  assert.equal(await page.locator('.product-line-entry').filter({hasText:'扩展卡与附件'}).count(),1);
  await page.locator('.product-line-entry').filter({hasText:'服务器与整柜'}).click();
  await page.locator('#category-children .category-card').first().waitFor();
  assert.match(await page.locator('#category-children').innerText(),/机架式服务器/);
  assert.match(await page.locator('#category-children').innerText(),/机箱/);
  assert.match(await page.locator('#category-children').innerText(),/整柜/);
  assert.equal(await page.locator('#detail').isVisible(),false);
  assert.equal(new URL(page.url()).searchParams.has('product_id'),false,'category never selects a first model');
  assert.equal(requests.filter(url=>new URL(url).searchParams.has('product_id')&&url.includes('/api/')).length,0,'category reads paginated projection only');
  await page.locator('#category-children a').filter({hasText:'机架式服务器'}).click();
  await page.waitForFunction(()=>document.querySelector('#category-children')?.textContent.includes('1U 形态'));
  assert.match(await page.locator('#category-children').innerText(),/1U 形态.*2U 形态.*3U 形态/s);
  await page.locator('#category-children a').filter({hasText:'1U 形态'}).click();
  await page.locator('#browse-rows .model-link').first().waitFor();
  assert.equal(await page.locator('#browse-rows .model-link').count(),1);
  assert.match(await page.locator('#browse-rows').innerText(),/SYS-1028U-TNR4T/);
  const csv=await (await page.request.get(base+await page.locator('#export-products').getAttribute('href'))).text();
  assert.match(csv,/SYS-1028U-TNR4T/);assert.ok(!csv.includes('SYS-6029UZ'));
  await page.reload();await page.locator('#browse-rows .model-link').first().waitFor();
  assert.equal(new URL(page.url()).searchParams.get('category'),'servers/rack-systems/1u');
  await page.locator('#browse-rows .model-link').click();await page.locator('#detail h2').waitFor();
  assert.match(await page.locator('#detail').innerText(),/TEST_VALUE/);
  assert.equal(await page.locator('#browse-body').isVisible(),false,'model page has no duplicate catalog or overview');
  await page.goBack();await page.locator('#browse-rows .model-link').first().waitFor();
  await page.goto(base+'/product-catalog.html?c=supermicro&view=categories');await page.locator('#browse-rows .model-link').first().waitFor();
  await page.locator('#query').fill('B200');
  await page.waitForFunction(()=>document.querySelectorAll('#browse-rows .model-link').length===1);
  assert.match(await page.locator('#browse-rows').innerText(),/SRS-GB200-NVL72.*72 NVIDIA B200.*36 NVIDIA Grace/s);
  assert.equal(await page.locator('#detail').isVisible(),false,'search is a result list');
  if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:process.env.UI_QA_DIR+'/category-search-desktop.png',fullPage:true});}
  await page.locator('#browse-rows .model-link').click();await page.locator('#detail h2').waitFor();
  assert.equal(await page.locator('#detail h2').innerText(),'SRS-GB200-NVL72');
  assert.equal(await page.locator('#browser-breadcrumbs a').first().getAttribute('href'),'/product-catalog.html?c=supermicro','home breadcrumb returns the company window');
  assert.equal(await page.locator('#detail .spec-card').count(),6);
  assert.equal(await page.locator('#detail details.raw-specification').count(),0,'raw tables are expanded');
  assert.match(await page.locator('.detail-highlights').innerText(),/72 NVIDIA B200.*36 NVIDIA Grace.*13.4 TB/s);
  assert.ok(await page.locator('.detail-highlights').evaluate(el=>el.getBoundingClientRect().bottom<innerHeight),'key specification fits first viewport');
  assert.equal(await page.locator('.spec-grid').first().evaluate(el=>getComputedStyle(el).columnCount),'2');
  assert.ok(Number(await page.locator('.spec-card td').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize)))>=15,'normal spec font size');
  for(const theme of ['light','dark'])for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1000});await page.evaluate(t=>{document.documentElement.dataset.uiTheme=t;document.documentElement.dataset.uiMode=t;},theme);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),theme+' '+width+' no page overflow');
   if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+'/model-compact-'+theme+'-'+width+'.png',fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.reload();await page.locator('#detail h2').waitFor();
  assert.equal(new URL(page.url()).searchParams.get('q'),'B200','selected model keeps result context');
  await page.goto(base+'/product-catalog.html?c=supermicro&view=categories');await page.locator('#browse-rows .model-link').first().waitFor();
  await page.locator('[data-compare]').nth(0).check();await page.locator('[data-compare]').nth(1).check();
  await page.locator('#open-comparison').click();await page.locator('#browser-comparison h2').waitFor();
  for(let i=2;i<4;i++)await page.locator('[data-compare]').nth(i).check();
  await page.locator('[data-compare]').nth(4).click();assert.equal(await page.locator('[data-compare]:checked').count(),4);
  assert.match(await page.locator('#status').innerText(),/最多/);
  await page.locator('#clear-comparison').click();assert.equal(await page.locator('[data-compare]:checked').count(),0);
  await page.locator('#category-tree a').filter({hasText:'其他目录路径'}).click();await page.locator('#browse-rows .model-link').waitFor();
  assert.match(await page.locator('#category-children').innerText(),/unexplained/);
  assert.match(await page.locator('#browse-rows').innerText(),/DIRECTORY_TEST/,'unexplained entries remain reachable');
  await page.goto(base+'/product-catalog.html?c=supermicro&view=categories&line=storage');await page.waitForFunction(()=>document.querySelector('#matches').textContent==='0 个匹配条目');
  assert.equal(await page.locator('#browse-rows .model-link').count(),0,'empty business category does not jump to another model');
  let failBrowse=true;
  await page.route('**/api/product-catalog/supermicro?view=browse*',route=>{if(failBrowse){failBrowse=false;return route.fulfill({status:503,body:'{}',contentType:'application/json'});}return route.continue();});
  await page.reload();await page.locator('#retry-browse').waitFor();
  await page.locator('#retry-browse').click();
  await page.waitForFunction(()=>document.querySelector('#matches').textContent==='0 个匹配条目'&&!document.querySelector('#retry-browse'));
  assert.deepEqual(errors,[]);
  assert.equal(requests.filter(u=>/\/data\/(projects|contracts|event_cards|facts)\.json/.test(u)).length,0,'public browsing does not fetch private research annexes');
  console.log('PASS company -> subcategories -> 1U models -> detail; spec search; shared CSV; refresh/back; readable two-column raw tables; 4-model selection; reachable unexplained paths and empty categories');
 }finally{if(browser)await browser.close();server.kill();rmSync(runtime,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
