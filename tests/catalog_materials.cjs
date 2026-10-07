const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');const {join}=require('node:path');const {createInterface}=require('node:readline');
const {chromium}=require('playwright');
(async()=>{
 const runtime=mkdtempSync(join(tmpdir(),'catalog-materials-'));
 const server=spawn(process.env.PYTHON||'python3',['-u','-c',"import sys,json;sys.path.insert(0,'src');from tests.unit.test_catalog_supplement import historical_fixture;from inresearch.paths import project_root;from inresearch.workflow.product_catalog import receive;from inresearch.interfaces import http;base,data=historical_fixture();receive(project_root(),base,'supermicro');receive(project_root(),data,'supermicro');s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port}),flush=True);s.serve_forever()"],{env:{...process.env,INRESEARCH_RUNTIME_ROOT:runtime,INRESEARCH_MARKET_ENABLED:'0'},stdio:['ignore','pipe','inherit']});
 let browser;
 try{
 const ready=await new Promise((resolve,reject)=>{createInterface({input:server.stdout}).once('line',s=>{try{resolve(JSON.parse(s));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',c=>reject(Error('server exited '+c)));});
 const base='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/product-catalog.html?c=supermicro');await page.locator('#company-materials-link').waitFor();
 assert.match(await page.locator('#company-materials-link').innerText(),/2 份/);
 await page.locator('#company-materials-link').click();await page.waitForFunction(()=>document.querySelector('#material-status')?.textContent.includes('2 份已索引'));
 assert.equal(await page.locator('#material-list li').count(),2);
 assert.match(await page.locator('#material-status').innerText(),/1 份型号待关联/);
 const pdf=page.locator('#material-list strong a').first();assert.match(await pdf.getAttribute('href'),/^https:\/\/www.supermicro.com\//);
 await page.locator('#material-query').fill('unassigned');await page.locator('#material-search button').click();await page.waitForFunction(()=>document.querySelector('#material-status').textContent.includes('当前匹配 1 份'));
 assert.match(await page.locator('#material-list').innerText(),/型号待关联/);
 await page.reload();await page.waitForFunction(()=>document.querySelector('#material-status').textContent.includes('当前匹配 1 份'));
 await page.locator('#material-query').fill('Test Report');await page.locator('#material-search button').click();await page.waitForFunction(()=>document.querySelector('#material-list').textContent.includes('Test Report'));
 await page.locator('#material-list p a').click();await page.waitForFunction(()=>document.querySelector('#detail h2')?.textContent.includes('SYS-6039P-TXRT'));
 await page.goto(base+'/product-catalog.html?c=supermicro&view=materials');await page.waitForFunction(()=>document.querySelector('#material-status').textContent.includes('2 份已索引'));
 for(const width of [1440,390,320])for(const theme of ['light','dark']){await page.setViewportSize({width,height:900});await page.evaluate(t=>{document.documentElement.dataset.uiTheme=t;document.documentElement.dataset.uiMode=t;},theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'material page overflow '+width+' '+theme);}
 assert.deepEqual(errors,[]);console.log('PASS real historical supplement -> preserved models -> homepage document count -> searchable orphan/linked originals -> model -> refresh and responsive materials view');
 }finally{if(browser)await browser.close();server.kill();rmSync(runtime,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
