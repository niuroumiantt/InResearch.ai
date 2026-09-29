const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/pilot-progress/nvidia',r=>r.fulfill({json:{available:true,project:'nvidia',source:'m5_claude_cli',acceptance:'candidate_only',generated:'2026-09-27T07:34:17Z',received_at:'2026-09-27T07:35:00Z',documents_total:5,counts:{complete:3,blocked:1,failed:1},documents:[{id:'d1',title:'A100 Data Sheet',coverage:{complete:true,pages_read:4,pages_total:4}},{id:'d2',title:'ConnectX-7',coverage:{complete:true,pages_read:2,pages_total:2}},{id:'d3',title:'Ada Artistry',coverage:{complete:true,pages_read:3,pages_total:3}}]}}));
  // 2026-09-28：NVIDIA 打样进度并入采集页的「规格批次」标签；旧地址 302
  const legacy=await page.request.get(process.env.UI_BASE_URL+'/nvidia-pilot.html',{maxRedirects:0});
  assert.equal(legacy.status(),302);assert.match(legacy.headers()['location'],/supply\.html#pilot$/);
  await page.goto(process.env.UI_BASE_URL+'/supply.html#pilot');
  await page.getByRole('heading',{name:'NVIDIA 产品资料验证'}).waitFor();
  await page.locator('#pilot-metrics .plan-card').first().waitFor();
  assert.match(await page.locator('#pilot-status').innerText(),/M5 Claude Code CLI/);
  assert.match(await page.locator('#pilot-metrics').innerText(),/3/);
  assert.match(await page.locator('#pilot-documents').innerText(),/A100 Data Sheet/);
  assert.match(await page.locator('#pilot-panel').innerText(),/Spark 本轮不参与/);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
