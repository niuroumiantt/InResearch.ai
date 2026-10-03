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
case = RepositoryPageTests()
try:
    case.setUp()
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
   const backgrounds=new Set();
   for(const width of [1440,390]) for(const mode of ['light','dark']) {
    await page.setViewportSize({width,height:1000});
    await page.locator('#ui-appearance').selectOption(mode);
    assert.ok(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--ui-font').trim()),'shared theme must be active');
    backgrounds.add(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' '+width);
    if(process.env.REPO_SCREENSHOTS) {
      mkdirSync(process.env.REPO_SCREENSHOTS,{recursive:true});
      await page.screenshot({path:join(process.env.REPO_SCREENSHOTS, name+'-'+width+'-'+mode+'.png')});
    }
   }
   assert.equal(backgrounds.size,2,'light and dark modes must change the rendered background');
   if(['infrarepo','fetchspecrepo'].includes(name)) {
     const frame=page.frameLocator('iframe');
     await frame.locator('svg').first().waitFor();
     assert.ok(await frame.locator('svg').count()>0);
   }
  }
  await page.goto(base+'/admin/fetchspec/reporg.html');
  assert.equal(new URL(page.url()).pathname,'/admin/fetchspecrepo.html');
  await page.goto(base+'/logout');
  await page.goto(base+'/admin/repo-content/infra.html');
  assert.equal(new URL(page.url()).pathname,'/login');
  assert.deepEqual(errors,[]);
  console.log('PASS repository pages: real login/logout, 5 pages, 20 desktop/mobile theme views, embedded SVGs and old-link redirect');
 } finally {
  if(browser) await browser.close();
  lines.close();fixture.stdin.end();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
