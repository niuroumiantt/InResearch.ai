/* Real authenticated server, shared admin navigation and original embedded diagrams. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {resolve, join} = require('node:path');
const {mkdirSync} = require('node:fs');
const {chromium} = require('playwright');
const root = resolve(__dirname, '..');
const fixture = spawn(process.env.PYTHON || 'python3', ['-u', '-c', `
import sys
sys.path[:0] = ['src', 'tests/unit']
from test_repository_pages import RepositoryPageTests
from test_material_flow import measured_fixture
from inresearch.interfaces import material_flow
from unittest.mock import patch
case = RepositoryPageTests()
try:
    case.setUp()
    case.stack.enter_context(patch.object(material_flow, 'snapshot', return_value=measured_fixture()))
    print(case.server.server_port, flush=True)
    sys.stdin.readline()
finally:
    case.doCleanups()
`], {cwd:root, stdio:['pipe','pipe','inherit']});
const lines = createInterface({input:fixture.stdout});
const ready = new Promise((resolve, reject)=>{
  lines.once('line', value=> /^\d+$/.test(value) ? resolve(value) : reject(Error('Invalid fixture port')));
  fixture.once('error', reject);
  fixture.once('exit', code=>reject(Error('Fixture exited: '+code)));
});
(async()=>{
 let browser;
 try {
  const port=await ready, base='http://127.0.0.1:'+port;
  browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE ? {executablePath:process.env.UI_BROWSER_EXECUTABLE} : {})});
  const context=await browser.newContext(), page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/admin/infrarepo.html');
  assert.equal(new URL(page.url()).pathname,'/login');
  const login=await context.request.post(base+'/api/login', {data:{username:'admin',password:'Only-test-architecture-8391'}});
  assert.equal(login.status(),200);
  for(const name of ['repos','inresearchrepo','inewsrepo','fetchspecrepo','infrarepo']) {
   const response=await page.goto(base+'/admin/'+name+'.html');
   assert.equal(response.status(),200,name);
   await page.locator('#ui-skinbar').waitFor();
   assert.equal(await page.locator('.repo-nav a').count(),5);
   if(name==='inresearchrepo') {
     await page.locator('#material-lineage .value').filter({hasText:'447.65'}).waitFor();
     assert.equal(await page.locator('[data-step]').count(),5);
     for(const [step,text] of [['catalog','12,728'],['reading','17,347'],['review','9,819'],['website','29'],['archive','268.06']]) {
       await page.locator('[data-step="'+step+'"]').click();
       assert.ok((await page.locator('#material-detail').innerText()).includes(text),step);
     }
     assert.ok((await page.locator('#material-stores').innerText()).includes('209.29 MB'));
     assert.ok((await page.locator('#material-web-storage').innerText()).includes('138.28 MB'));
   }
   const backgrounds=new Set();
   for(const width of (name==='inresearchrepo'?[1440,390,320]:[1440,390])) for(const mode of ['light','dark']) {
    await page.setViewportSize({width,height:1000});
    await page.locator('#ui-appearance').selectOption(mode);
    assert.ok(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--ui-font').trim()),'shared theme must be active');
    backgrounds.add(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' '+width);
    if(process.env.REPO_SCREENSHOTS) {
      mkdirSync(process.env.REPO_SCREENSHOTS,{recursive:true});
      await page.screenshot({path:join(process.env.REPO_SCREENSHOTS, name+'-'+width+'-'+mode+'.png'),fullPage:name==='inresearchrepo'});
    }
   }
   assert.equal(backgrounds.size,2,'light and dark modes must change the rendered background');
   if(['infrarepo','fetchspecrepo'].includes(name)) {
     const frame=page.frameLocator('iframe');
     await frame.locator('svg').first().waitFor();
     assert.ok(await frame.locator('svg').count()>0);
     // 内嵌图随内容撑高：只有页面一条滚动条，iframe 里不再出现第二条。
     await page.waitForFunction(()=>{const f=document.querySelector('iframe.repo-frame'), d=f.contentDocument;
       return d && d.readyState==='complete' && d.documentElement.scrollHeight<=f.clientHeight+2;}, null, {timeout:5000});
   }
  }
  await page.goto(base+'/admin/inresearchrepo.html');
  await page.locator('#material-lineage .value').filter({hasText:'447.65'}).waitFor();
  await page.route('**/api/admin/material-flow',r=>r.fulfill({status:503,body:'{}'}));
  await page.locator('#material-refresh').click();
  await page.locator('#material-error').waitFor();
  assert.ok((await page.locator('#material-error').innerText()).includes('保留上次结果与时间'));
  assert.ok((await page.locator('#material-lineage').innerText()).includes('447.65'));
  await page.unroute('**/api/admin/material-flow');
  await page.route('**/api/admin/material-flow',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({schema_version:1,stale:true,measurements:{state:'unavailable'},review:{state:'unavailable',candidates:{}},formal:{statements:0},website:{}})}));
  await page.locator('#material-refresh').click();
  await page.waitForFunction(()=>document.querySelector('#material-lineage').innerText.includes('未测量'));
  assert.equal(await page.locator('[data-step=review]').locator('..').locator('.value').innerText(),'— 条');
  await page.unroute('**/api/admin/material-flow');
  await page.route('**/api/admin/material-flow',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({schema_version:1,measurements:{archive:{state:'observed',allocated_bytes:100,directories:{'raw-materials':20}}},review:{state:'unavailable',candidates:{}},formal:{},website:{}})}));
  await page.locator('#material-refresh').click();
  await page.waitForFunction(()=>document.querySelector('[data-step=archive]').parentNode.innerText.includes('0.00 GB'));
  await page.locator('[data-step=archive]').click();
  assert.equal(await page.locator('#material-detail .material-row').nth(1).locator('.number').innerText(),'—');
  assert.equal(await page.locator('#material-detail .material-row').nth(1).locator('.track span').evaluate(e=>e.style.width),'0%');
  await page.unroute('**/api/admin/material-flow');
  await page.locator('#material-refresh').click();
  await page.locator('#material-lineage .value').filter({hasText:'447.65'}).waitFor();
  await page.goto(base+'/admin/fetchspec/reporg.html');
  assert.equal(new URL(page.url()).pathname,'/admin/fetchspecrepo.html');
  await page.goto(base+'/logout');
  await page.goto(base+'/admin/repo-content/infra.html');
  assert.equal(new URL(page.url()).pathname,'/login');
  assert.deepEqual(errors,[]);
  console.log('PASS repository pages: real login/logout, 5 pages, 22 desktop/mobile theme views; material lineage, bytes/scopes, unknown/failure/retry, embedded SVGs without nested scrolling and old-link redirect');
 } finally {
  if(browser) await browser.close();
  lines.close();fixture.stdin.end();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
