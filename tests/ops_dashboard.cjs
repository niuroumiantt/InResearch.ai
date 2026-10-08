/* Dashboard states, queue identity, escaping, recovery and mobile geometry.
 * API fixtures are explicitly synthetic; rendering never triggers work. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
const now=new Date().toISOString(), old=new Date(Date.now()-2*3600000).toISOString();
const fixture={generated:now,reader:{status:'degraded',generated:now,received_at:now,stale:false,snapshot_age_seconds:0,generated_age_seconds:0,release:'test-release',counts:{complete:114,blocked:25},claim_floor:{min_priority:7,held_documents:3},thermal:{last_c:72},acquisition:{sources:{inews:{items:14262,last_run:{count:33,status:'success',finished:now}}}},operations:{schema_version:1,generated:now,current_documents:{complete:114},execution_documents:{blocked:25,queued:110},stages:[{stage:'extract',state:'pending',count:111},{stage:'read',state:'succeeded',count:1469},{stage:'extract',state:'blocked',count:25}],windows:{'1h':[{stage:'read',state:'succeeded',count:2}],'24h':[{stage:'read',state:'succeeded',count:50}]},errors:[{title:'模型输出校验失败',documents:25,stage:'read',kind:'execution',code:'model_output_invalid',since:old,action:'核对模型输出后选择性处理。'}],queues:{pending:{total:111,limit:100,items:[{job_id:'job-1',doc_id:'doc-1',revision_id:'rev-1',original_name:'<img src=x onerror="window.pwned=1">',stage:'extract',state:'pending',created:old,available:now,priority:7,chunks_read:0,chunks_total:0,attempts:0,code_path:'src/inresearch/workflow/reading_stages.py'}]},running:{total:0,limit:100,items:[]},blocked:{total:25,limit:100,items:[{job_id:'job-2',doc_id:'doc-2',revision_id:'rev-2',original_name:'模型测试.pdf',stage:'read',state:'blocked',error_code:'model_output_invalid',finished:old,created:old,priority:9,code_path:'src/inresearch/workflow/reading_stages.py'}]}}}},quality:{facts:{records:7849,errors:1,limit:100,items:[{id:'fact-1',reason:'evidence.sha256 缺失'}]},verification:{counts:{'1':24,'2':27},items:[{p:1,id:'M06-F1',table:'research',reason:'needs-review',action:'核对原件',urls:['javascript:bad()']}]}},targets:{total:351,states:{delivered:39,needed:271,sourced:37,assumed:4},teams:[{team:'fetchspec',delivered:39,needed:40}]},tasks:{},history:{total:0,items:[]},unavailable:[]};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE?{executablePath:process.env.UI_BROWSER_EXECUTABLE}:{}),args:['--enable-unsafe-swiftshader']});
 try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 fixture.reader.operations.errors[0].examples=fixture.reader.operations.queues.blocked.items;fixture.reader.operations.queues.blocked.items=[];
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const auxiliary=[];
 page.on('request',request=>{if(/\/(?:data|framework)\/.*\.json/.test(request.url()))auxiliary.push(request.url());});
 let requests=0,api=fixture,fail=false;
 await page.route('**/api/ops',route=>fail?route.fulfill({status:503,body:'{}'}):route.fulfill({json:api}));
 await page.route('**/api/run',route=>{requests++;return route.fulfill({json:{ok:true,name:'数据校验',output:'校验通过（0 warnings）'}});});
 await page.goto(base+'/ops.html');await page.locator('#ops-kpis .value').first().waitFor();
 assert.equal(requests,0,'loading the dashboard does not trigger work');
 assert.deepEqual(auxiliary,[],'closed drawers do not compete with the status request');
 await page.locator('#freshness-drawer > summary').click();
 await page.locator('#freshness tr').nth(1).waitFor({state:'attached'});
 assert.equal(await page.locator('#error').textContent(),'','freshness remains usable inside a collapsed drawer');
 assert.match(await page.locator('#ops-kpis').textContent(),/114/);
 assert.match(await page.locator('#ops-attention').textContent(),/model_output_invalid/);
 assert.match(await page.locator('#queue-note').textContent(),/111.*1.*100/);
 assert.equal(await page.locator('#queue-body img').count(),0);assert.equal(await page.evaluate(()=>window.pwned),undefined);
 await page.locator('#queue-body summary').click();assert.match(await page.locator('#queue-body').textContent(),/rev-1/);
 await page.locator('#ops-attention [data-error-filter]').click();
 assert.match(await page.locator('#queue-body').textContent(),/模型测试.pdf/);
 assert.equal(await page.locator('#quality-detail a[href^="javascript:"]').count(),0);
 await page.locator('#tasks button[data-task=validate]').click();await page.locator('#run-results').getByText('数据校验 · 执行成功',{exact:true}).waitFor();
 assert.equal(requests,1);
 fail=true;await page.locator('#ops-refresh').click();await page.locator('#ops-error').getByText(/更新失败/).waitFor();
 assert.match(await page.locator('#ops-banner').textContent(),/当前状态未确认/);
 fail=false;api={...fixture,reader:{status:'not_connected',stale:true},quality:undefined};
 await page.locator('#ops-refresh').click();await page.getByText('尚未收到队列诊断明细',{exact:true}).waitFor();
 assert.match(await page.locator('#ops-kpis').textContent(),/—/);assert.match(await page.locator('#queue-body').textContent(),/未收到文件明细/);
 api=fixture;await page.locator('#ops-refresh').click();await page.locator('#ops-kpis .value').first().getByText('114',{exact:true}).waitFor();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  for(const mode of ['light','dark']){
   await page.locator('#ui-appearance').selectOption(mode);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no page overflow '+width+' '+mode);
   if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+'/ops-'+width+'-'+mode+'.png',fullPage:true});
  }
 }
 assert.deepEqual(errors,[]);
 // A stylesheet may stall on a slow connection. It must not hold the parser,
 // navigation or status bootstrap behind an inline script / defer dependency.
 const slowPage=await context.newPage();let releaseStyle;
 const heldStyle=new Promise(resolve=>{releaseStyle=resolve;});
 await slowPage.route('**/assets/fonts/fonts.css',async route=>{await heldStyle;await route.continue();});
 await slowPage.route('**/api/ops',route=>route.fulfill({json:fixture}));
 try {
  await slowPage.goto(base+'/ops.html',{waitUntil:'domcontentloaded',timeout:10000});
  await slowPage.locator('#ops-kpis .value').first().waitFor({state:'attached',timeout:10000});
  assert.match(await slowPage.locator('#ops-kpis').textContent(),/114/);
  assert.equal(await slowPage.locator('#ui-skinbar').count(),1,'navigation mounts while font CSS is delayed');
 } finally {releaseStyle();await slowPage.close();}
 // Exercise an actual aborted fetch, with only the 20-second watchdog accelerated.
 const timeoutPage=await context.newPage();
 await timeoutPage.addInitScript(()=>{
  const schedule=window.setTimeout.bind(window);
  window.setTimeout=(fn,ms,...args)=>schedule(fn,ms===20000?100:ms,...args);
 });
 await timeoutPage.route('**/api/ops',()=>{});
 try {
  await timeoutPage.goto(base+'/ops.html');
  await timeoutPage.locator('#ops-error').getByText(/读取超时（20 秒）/).waitFor();
  assert.equal(await timeoutPage.locator('#ops-refresh').isEnabled(),true,'aborted request releases refresh');
  assert.match(await timeoutPage.locator('#stage-body').textContent(),/状态未知/);
  assert.doesNotMatch(await timeoutPage.locator('#ops-error').textContent(),/user aborted/);
  await timeoutPage.unroute('**/api/ops');
  await timeoutPage.route('**/api/ops',route=>route.fulfill({json:fixture}));
  await timeoutPage.locator('#ops-refresh').click();
  await timeoutPage.locator('#ops-kpis .value').first().getByText('114',{exact:true}).waitFor();
  assert.equal(await timeoutPage.locator('#ops-error').textContent(),'');
 } finally {await timeoutPage.close();}
 console.log('ops dashboard: auto-load, lazy drawers, delayed font CSS, bounded samples, identity, escaping, task results, missing telemetry, refresh recovery and responsive themes passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
