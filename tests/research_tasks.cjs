const {setAppearance} = require('./ui_helpers.cjs');
/* Real durable mutations run against an isolated runtime, never the source tree. */
const assert = require('node:assert/strict');
const {spawn,execFileSync} = require('node:child_process');
const {mkdtempSync,rmSync,readFileSync,mkdirSync,writeFileSync,readdirSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join,resolve} = require('node:path');
const {createInterface} = require('node:readline');
const {chromium} = require('playwright');
const {createHash,randomUUID} = require('node:crypto');
const root = resolve(__dirname,'..');
const directory = mkdtempSync(join(tmpdir(),'inresearch-tasks-'));
const environment = {...process.env,INRESEARCH_RUNTIME_ROOT:join(directory,'runtime'),INRESEARCH_INTAKE_ROOT:join(directory,'intake'),INRESEARCH_MATERIAL_APPROVER:'task-admin',HUB_AUTH:'on',INRESEARCH_MARKET_ENABLED:'0',PYTHONDONTWRITEBYTECODE:'1'};
const code = "import sys,json,secrets;sys.path.insert(0,'src');from inresearch.storage.layout import initialize_runtime;initialize_runtime();from inresearch.interfaces import http,auth;http.AUTH_ON=True;[(auth.add_user(name,secrets.token_urlsafe(32),role)) for name,role in [('task-admin','admin'),('task-member','member'),('task-intern','intern')]];cookies={name:auth.make_cookie(name).split(';')[0] for name in ['task-admin','task-member','task-intern']};s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port,'cookies':cookies}),flush=True);s.serve_forever()";
const server = spawn(process.env.PYTHON || 'python3',['-u','-c',code],{cwd:root,env:environment,stdio:['ignore','pipe','inherit']});
const lines = createInterface({input:server.stdout});
const ready = new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',c=>reject(Error('task test server exited '+c)));});

(async()=>{
  let browser;
  try {
    const config = await ready, base = 'http://127.0.0.1:'+config.port;
    browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});
    const anonymousContext = await browser.newContext();
    const anonymous = await anonymousContext.newPage();
    const publicPageRequests=[], anonymousErrors=[];
    anonymous.on('request',request=>publicPageRequests.push(new URL(request.url()).pathname));
    anonymous.on('pageerror',error=>anonymousErrors.push(error.message));
    assert.equal((await anonymous.request.get(base+'/api/research-tasks')).status(),200);
    assert.equal((await anonymous.request.post(base+'/api/research-tasks',{data:{}})).status(),401);
    await anonymous.goto(base+'/tasks.html');
    await anonymous.locator('#package-dashboard [data-package-dashboard]').nth(5).waitFor();
    const initialApiLoads = await anonymous.evaluate(()=>performance.getEntriesByType('resource').map(entry=>new URL(entry.name).pathname));
    assert.equal(initialApiLoads.filter(path=>path==='/api/research-tasks').length,1,'initial page shares one task request');
    assert.equal(initialApiLoads.filter(path=>path==='/api/research-task-examples').length,1,'fixed real example loads with the project overview');
    assert.equal(await anonymous.locator('#mission-title').innerText(),'完成全球园区信息的爬取');
    const taskUrl=anonymous.url();
    assert.deepEqual(await anonymous.locator('.mission-nav [data-task-view]').allTextContents(),['任务首页','提交与进展']);
    assert.equal(await anonymous.locator('[data-task-view="task-guide"]').count(),0,'there is no separate guide tab');
    assert.equal(await anonymous.locator('#task-home').isVisible(),true);
    assert.equal(await anonymous.locator('#mission-dashboard').isVisible(),true);
    assert.equal(await anonymous.locator('#worked-example').isVisible(),true);
    assert.equal(await anonymous.locator('#data-angles').isVisible(),true,'the relationship diagram is shown directly on the homepage');
    assert.equal(await anonymous.evaluate(()=>Boolean(document.querySelector('#mission-dashboard').compareDocumentPosition(document.querySelector('#worked-example')) & Node.DOCUMENT_POSITION_FOLLOWING)),true,'dashboard is followed by the fixed real example');
    assert.equal(await anonymous.evaluate(()=>Boolean(document.querySelector('#worked-example').compareDocumentPosition(document.querySelector('#data-angles')) & Node.DOCUMENT_POSITION_FOLLOWING)),true,'the relationship diagram follows the real example');
    const initialTasks=await (await anonymous.request.get(base+'/api/research-tasks')).json();
    assert.equal(await anonymous.locator('#package-dashboard [data-package-dashboard]').count(),initialTasks.packages.length);
    for(const p of initialTasks.packages){
      const card=anonymous.locator('[data-package-dashboard="'+p.id+'"]');
      assert.ok((await card.innerText()).includes(p.title));
      assert.equal(await card.locator('[data-package-published-sites]').innerText(),String(initialTasks.package_progress[p.id].published_sites));
    }
    await anonymous.locator('[data-task-view="task-home"]').focus();
    for(const [key,view] of [['ArrowRight','submission-progress'],['ArrowLeft','task-home'],['End','submission-progress'],['Home','task-home'],['ArrowLeft','submission-progress'],['ArrowRight','task-home']]){
      await anonymous.keyboard.press(key);
      assert.equal(await anonymous.locator('[data-task-view="'+view+'"]').getAttribute('aria-selected'),'true','main tab keyboard activation: '+key);
      assert.equal(await anonymous.evaluate(()=>document.activeElement?.dataset.taskView),view,'main tab keyboard focus: '+key);
      assert.equal(await anonymous.locator('#'+view).isVisible(),true);
      assert.equal(anonymous.url(),taskUrl,'main tab keyboard navigation preserves URL: '+key);
    }
    // Browser-only synthetic counts prove the dashboard renders supplied totals
    // independently; no fixture is written to the ledger or production data.
    const dashboardFixture=structuredClone(initialTasks);
    dashboardFixture.site_progress.published_sites=8123;
    const fixturePackage=dashboardFixture.packages[0];
    dashboardFixture.package_progress[fixturePackage.id].published_sites=456;
    dashboardFixture.package_progress[dashboardFixture.packages[1].id].published_sites=456;
    await anonymous.route('**/api/research-tasks',route=>route.fulfill({json:dashboardFixture}));
    await anonymous.locator('#work-packages > summary').click();
    await anonymous.locator('#refresh-tasks').click();
    await anonymous.waitForFunction(()=>document.querySelector('#mission-progress-value')?.textContent==='8,123 个园区已入库');
    assert.equal(await anonymous.locator('#mission-progress-value').innerText(),'8,123 个园区已入库');
    assert.equal(await anonymous.locator('[data-package-dashboard="'+fixturePackage.id+'"] [data-package-published-sites]').innerText(),'456');
    assert.equal(await anonymous.locator('#mission-site-progress').isHidden(),true,'unknown target has no invented completion percentage');
    await anonymous.unroute('**/api/research-tasks');
    await anonymous.locator('#refresh-tasks').click();
    await anonymous.waitForFunction(published=>document.querySelector('#mission-progress-value')?.textContent===`${new Intl.NumberFormat('zh-CN').format(published)} 个园区已入库`,initialTasks.site_progress.published_sites);
    assert.equal(await anonymous.locator('[data-package-dashboard="'+fixturePackage.id+'"] [data-package-published-sites]').innerText(),String(initialTasks.package_progress[fixturePackage.id].published_sites));
    await anonymous.locator('#work-packages > summary').click();
    assert.equal(await anonymous.locator('#download-template-home, #download-brief, #download-template, #download-package-plan, [data-download-event-plan]').count(),0,'retired task/template/plan downloads are absent');
    assert.equal(await anonymous.locator('#submission-progress #task-upload-form').count(),1,'submission remains beside the shared current work package');
    assert.equal(await anonymous.locator('#upload-own-list, #upload-receipt-form, #my-submissions-title').count(),0,'personal feedback and receipt recovery UI are removed');
    assert.equal(await anonymous.locator('#package-workspace').isHidden(),true);
    await anonymous.locator('[data-task-view="submission-progress"]').click();
    assert.equal(anonymous.url(),taskUrl,'switching the main task tab preserves the URL and hash');
    assert.equal(await anonymous.locator('#task-home').isHidden(),true);
    assert.equal(await anonymous.locator('#submission-progress').isVisible(),true);
    assert.equal(await anonymous.locator('#package-workspace').isVisible(),true);
    assert.equal(await anonymous.evaluate(()=>Boolean(document.querySelector('#task-upload-form').compareDocumentPosition(document.querySelector('#package-workspace')) & Node.DOCUMENT_POSITION_FOLLOWING)),true,'team progress appears below the submission form');
    assert.equal(await anonymous.locator('#upload-package').inputValue(),'dc-census-cn');
    const packageIds=initialTasks.packages.map(p=>p.id), cnIndex=packageIds.indexOf('dc-census-cn');
    await anonymous.locator('#package-tabs [data-package-tab="dc-census-cn"]').focus();
    for(const [key,index] of [['ArrowRight',(cnIndex+1)%packageIds.length],['ArrowLeft',cnIndex],['End',packageIds.length-1],['Home',0],['ArrowLeft',packageIds.length-1],['ArrowRight',0]]){
      await anonymous.keyboard.press(key);
      const packageId=packageIds[index];
      assert.equal(await anonymous.locator('#package-tabs [data-package-tab="'+packageId+'"]').getAttribute('aria-selected'),'true','region tab keyboard activation: '+key);
      assert.equal(await anonymous.evaluate(()=>document.activeElement?.dataset.packageTab),packageId,'region tab keyboard focus: '+key);
      assert.equal(await anonymous.locator('#upload-package').inputValue(),packageId,'region keyboard selection updates submission package');
      assert.equal(anonymous.url(),taskUrl,'region tab keyboard navigation preserves URL: '+key);
    }
    await anonymous.locator('#package-tabs [data-package-tab="dc-census-na"]').click();
    assert.equal(anonymous.url(),taskUrl,'changing the active region preserves the URL and hash');
    assert.equal(await anonymous.locator('#upload-package').inputValue(),'dc-census-na');
    await anonymous.locator('#package-tabs [data-package-tab="dc-census-cn"]').click();
    await anonymous.locator('#upload-package').selectOption('dc-census-na');
    assert.equal(await anonymous.locator('#package-tabs [data-package-tab="dc-census-na"]').getAttribute('aria-selected'),'true','the submission selector keeps the team timeline on the selected work package');
    assert.equal(anonymous.url(),taskUrl);
    await anonymous.locator('#upload-package').selectOption('dc-census-cn');
    await anonymous.locator('[data-task-view="task-home"]').click();
    assert.equal(anonymous.url(),taskUrl);
    if(process.env.UI_TASKS_SCREENSHOT_PREFIX){
      await anonymous.evaluate(()=>scrollTo(0,0));
      await anonymous.setViewportSize({width:1440,height:1000});
      await anonymous.screenshot({path:process.env.UI_TASKS_SCREENSHOT_PREFIX+'-initial-1440.png',fullPage:true});
      await anonymous.setViewportSize({width:390,height:844});
      await anonymous.screenshot({path:process.env.UI_TASKS_SCREENSHOT_PREFIX+'-initial-390.png',fullPage:true});
      await anonymous.setViewportSize({width:1440,height:1000});
    }
    assert.equal(await anonymous.locator('#submission-progress').isHidden(),true);
    await anonymous.locator('[data-task-view="submission-progress"]').click();
    assert.equal(anonymous.url(),taskUrl);
    assert.equal(await anonymous.locator('#submission-progress').isVisible(),true);
    assert.equal(await anonymous.locator('[data-task-view="submission-progress"]').getAttribute('aria-selected'),'true');
    if(process.env.UI_QA_DIR){
      mkdirSync(process.env.UI_QA_DIR,{recursive:true});
      await anonymous.setViewportSize({width:1440,height:900});
      await anonymous.screenshot({path:join(process.env.UI_QA_DIR,'task-upload-desktop.png'),fullPage:true});
      await anonymous.setViewportSize({width:390,height:844});
      await anonymous.screenshot({path:join(process.env.UI_QA_DIR,'task-upload-mobile.png'),fullPage:true});
      await anonymous.setViewportSize({width:1440,height:1000});
    }
    assert.equal(await anonymous.locator('#upload-submit').isVisible(),true);
    const picker = anonymous.locator('#task-upload-form [name="file"]');
    await picker.setInputFiles({name:'first-directory.txt',mimeType:'text/plain',buffer:Buffer.from('first selection')});
    await picker.setInputFiles({name:'second-directory.txt',mimeType:'text/plain',buffer:Buffer.from('second selection')});
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),2,'separate picker selections accumulate');
    const dropped = await anonymous.evaluateHandle(()=>{const data=new DataTransfer();data.items.add(new File(['dropped evidence'],'dropped.txt',{type:'text/plain'}));return data;});
    await anonymous.locator('#upload-drop-zone').dispatchEvent('drop',{dataTransfer:dropped});
    await dropped.dispose();
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),3,'dragged files append to picker selections');
    if(process.env.UI_QA_DIR) {
      for(const width of [1440,390]) {await anonymous.setViewportSize({width,height:1000});await anonymous.locator('#task-upload-form').screenshot({path:join(process.env.UI_QA_DIR,'task-pending-queue-'+width+'.png')});}
      await anonymous.setViewportSize({width:1440,height:1000});
    }
    await anonymous.locator('#upload-pending-files li').filter({hasText:'second-directory.txt'}).locator('button').click();
    assert.deepEqual(await anonymous.locator('#upload-pending-files li>span').allTextContents(),['first-directory.txt','dropped.txt']);
    await anonymous.locator('#upload-clear-files').click();
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),0);
    await picker.setInputFiles(Array.from({length:20},(_,i)=>({name:`limit-${i}.txt`,mimeType:'text/plain',buffer:Buffer.from('bounded fixture')})));
    await picker.setInputFiles({name:'over-limit.txt',mimeType:'text/plain',buffer:Buffer.from('too many')});
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),20,'overflow selection preserves the existing queue');
    assert.match(await anonymous.locator('#upload-message').innerText(),/最多提交 20/);
    await anonymous.locator('#upload-clear-files').click();
    await anonymous.locator('#task-upload-form [name="file"]').setInputFiles({name:'synthetic-submission.bin',mimeType:'application/octet-stream',buffer:Buffer.from('UNTRUSTED SYNTHETIC SUBMISSION')});
    await anonymous.locator('#task-upload-form [name="submitter"]').fill('访客员工');
    await anonymous.locator('#task-upload-form [name="project_name"]').fill('合成测试项目');
    await anonymous.route('**/api/task-uploads', route => route.fulfill({status:403,contentType:'text/html',body:'<!DOCTYPE html><p>Blocked by CDN</p>'}));
    await anonymous.locator('#upload-submit').click();
    await anonymous.waitForFunction(()=>/网站安全防护拦截/.test(document.querySelector('#upload-message')?.textContent || ''));
    assert.match(await anonymous.locator('#upload-message').innerText(),/网站安全防护拦截/);
    assert.equal(await anonymous.locator('#task-upload-form [name="file"]').evaluate(input => input.files.length),0);
    assert.equal(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-receipts-v1')),null);
    await anonymous.unroute('**/api/task-uploads');
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),1,'failed files stay queued without selecting them again');
    await anonymous.locator('#upload-submit').click();
    await anonymous.waitForFunction(()=>/1 份附件已收到/.test(document.querySelector('#upload-message')?.textContent || ''));
    assert.match(await anonymous.locator('#upload-message').innerText(),/1 份附件已收到/);
    await anonymous.waitForFunction(()=>!document.querySelector('#upload-submit').disabled);
    assert.ok(!(await anonymous.locator('#upload-message').innerText()).includes('回执码'));
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),0,'successful files leave the pending queue');
    const publicRecord = JSON.parse(readFileSync(join(directory,'intake',readdirSync(join(directory,'intake')).find(id=>/^[a-f0-9]{32}$/.test(id)),'record.json'),'utf8'));
    assert.equal(publicRecord.status,'pending_approval');
    assert.equal(publicRecord.user,'anonymous');
    assert.equal((await anonymous.request.get(base+'/api/intake-worker/content/'+publicRecord.id)).status(),401);
    assert.equal((await anonymous.request.get(base+'/api/materials/content/'+publicRecord.id)).status(),401);
    assert.equal((await anonymous.request.post(base+'/api/task-uploads/receipt',{data:{id:publicRecord.id,receipt:'wrong'}})).status(),404);
    const workerToken='isolated-worker-token-'+createHash('sha256').update(directory).digest('hex');
    writeFileSync(join(directory,'runtime/data/.reader_sync_token'),workerToken);
    const workerHeaders={Authorization:'Bearer '+workerToken};
    assert.deepEqual((await (await anonymous.request.get(base+'/api/intake-worker/pending',{headers:workerHeaders})).json()).items,[]);
    assert.equal((await anonymous.request.get(base+'/api/intake-worker/content/'+publicRecord.id,{headers:workerHeaders})).status(),403);
    const receiptRow=JSON.parse(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-receipts-v1')))[0];
    assert.equal((await anonymous.request.post(base+'/api/task-uploads/receipt',{data:receiptRow})).status(),200);
    assert.equal((await anonymous.request.get(base+'/task-reviews.html',{maxRedirects:0})).status(),302);
    const admin=await browser.newPage();
    await admin.context().addCookies([{name:'hub_session',value:config.cookies['task-admin'].slice(config.cookies['task-admin'].indexOf('=')+1),url:base}]);
    await admin.goto(base+'/tasks.html');
    await admin.locator('[data-task-view="submission-progress"]').click();
    await admin.locator('#upload-owner-shortcut').waitFor({state:'visible'});
    assert.equal(await admin.locator('#upload-owner-list').count(),0);
    await admin.locator('#upload-owner-shortcut a').click();
    await admin.waitForURL(base+'/task-reviews.html');
    await admin.locator('.review-queue-item[data-id="'+publicRecord.id+'"]').waitFor();
    assert.match(await admin.locator('#review-detail-content').innerText(),/下载原件核对/);
    if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await admin.setViewportSize({width:1440,height:1000});await admin.screenshot({path:join(process.env.UI_QA_DIR,'task-reviews-desktop.png')});}
    await admin.setViewportSize({width:390,height:844});
    assert.equal(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'owner workbench fits mobile width');
    assert.equal(await admin.locator('#review-detail-content [data-action="approve"]').isVisible(),true);
    if(process.env.UI_QA_DIR) await admin.screenshot({path:join(process.env.UI_QA_DIR,'task-reviews-mobile.png')});
    await admin.setViewportSize({width:1440,height:1000});
    await admin.locator('#review-detail-content [data-action="approve"]').click();
    await admin.waitForFunction(id=>document.querySelector('#review-detail-content')?.textContent.includes(id.slice(0,8)) && document.querySelector('#review-message')?.textContent.includes('已批准接收'),publicRecord.id);
    const readyItems=(await (await anonymous.request.get(base+'/api/intake-worker/pending',{headers:workerHeaders})).json()).items;
    assert.equal(readyItems.length,1);
    assert.equal(readyItems[0].id,publicRecord.id);
    assert.ok(!('receipt_hash' in readyItems[0]));
    assert.equal((await anonymous.request.get(base+'/api/intake-worker/content/'+publicRecord.id,{headers:workerHeaders})).status(),200);
    await admin.locator('.review-filters [data-filter="all"]').click();
    await admin.locator('.review-queue-item[data-id="'+publicRecord.id+'"]').click();
    await admin.locator('.review-manual summary').click();
    await admin.locator('.owner-feedback textarea').fill('补齐来源与工作表定位');
    await admin.locator('.owner-feedback button').click();
    await admin.waitForFunction(()=>document.querySelector('.review-feedback summary')?.textContent.includes('1 条'));
    const missingPackage=await anonymous.request.post(base+'/api/task-uploads',{data:Buffer.from('SYNTHETIC XLSX UI FIXTURE'),headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify({name:'synthetic-workbook.xlsx',submitter:'另一位访客',project_name:'合成园区项目'}))}});
    assert.equal(missingPackage.status(),400);
    const xlsxResponse=await anonymous.request.post(base+'/api/task-uploads',{data:Buffer.from('SYNTHETIC XLSX UI FIXTURE'),headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify({name:'synthetic-workbook.xlsx',submitter:'另一位访客',project_name:'合成园区项目',package_id:'dc-census-cn'}))}});
    assert.equal(xlsxResponse.status(),201);
    const xlsx=(await xlsxResponse.json()).item;
    await admin.locator('#review-refresh').click();
    await admin.locator('.review-filters [data-filter="pending"]').click();
    await admin.locator('.review-queue-item[data-id="'+xlsx.id+'"]').click();
    assert.match(await admin.locator('#review-detail-content').innerText(),/确认并分析 · 合格条目自动上线/);
    await admin.locator('#review-detail-content [data-action="approve_and_analyze"]').click();
    await admin.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('正在分析'));
    assert.match(await admin.locator('#review-count-working').innerText(),/1/);
    const activeBefore=JSON.parse(readFileSync(join(directory,'intake',xlsx.id,'record.json'),'utf8'));
    const invalidPackage=await admin.request.post(base+'/api/materials/review',{headers:{'X-Requested-With':'material-intake'},data:{id:xlsx.id,sha256:xlsx.sha256,expected_revision:activeBefore.revision,operation_id:randomUUID(),action:'assign_package',package_id:'employee-made-up'}});
    assert.equal(invalidPackage.status(),400,'only a current server work package can be assigned');
    await admin.locator('#review-detail-content .review-package>summary').click();
    await admin.locator('#review-detail-content .owner-package select').selectOption('dc-census-cn');
    await admin.locator('#review-detail-content .owner-package button').click();
    await admin.waitForFunction(()=>document.querySelector('#review-message')?.textContent.includes('已绑定系统工作包'));
    const activeAfter=JSON.parse(readFileSync(join(directory,'intake',xlsx.id,'record.json'),'utf8'));
    assert.equal(activeAfter.package_id,'dc-census-cn');
    assert.deepEqual(activeAfter.approval,activeBefore.approval);
    assert.equal(activeAfter.analysis_requested_at,activeBefore.analysis_requested_at);
    assert.equal(activeAfter.sha256,activeBefore.sha256);
    assert.match(await admin.locator('#review-detail-content').innerText(),/中国存量园区/);
    const retainedFeedback=(await (await anonymous.request.post(base+'/api/task-uploads/receipt',{data:receiptRow})).json()).item.feedback;
    assert.ok(retainedFeedback.some(row=>row.text==='补齐来源与工作表定位'),'historical private feedback remains available under its original receipt boundary');
    assert.equal(await anonymous.locator('[data-download-feedback]').count(),0);
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-timeline')?.textContent.includes('已出负责人反馈'));
    assert.match(await anonymous.locator('.package-event').filter({hasText:'访客员工'}).textContent(),/已出负责人反馈/);
    const sampleScope={mode:'sampled_native_cells',total_sheets:1,total_nonblank_rows:41,total_nonblank_cells:328,
      excerpted_rows:4,excerpted_cells:32,prefix_only_cells:1,not_excerpted_cells:296,
      not_fully_seen_cells:297,excerpt_character_limit:90};
    const xlsxPath=join(directory,'intake',xlsx.id,'record.json');
    const sampledRecord=JSON.parse(readFileSync(xlsxPath,'utf8'));
    const sampledAt=Date.now()/1000;
    sampledRecord.analysis_reports=[{id:randomUUID(),at:sampledAt,sha256:xlsx.sha256,
      employee_task:'抽样反馈；研究端继续审核未覆盖单元格。',
      report:{summary:'仅抽样评价',published:[],held:[],findings:[],publication:{state:'nothing_eligible'},
        review_scope:{...sampleScope,reviewed_locators:[['Forecast 2025e','A1']]}}}];
    sampledRecord.feedback=[{id:randomUUID(),by:'analysis-worker',at:sampledAt,sha256:xlsx.sha256,
      result:'sampled_incomplete',text:'抽样反馈；研究端继续审核未覆盖单元格。'}];
    sampledRecord.analysis_scope=sampleScope;
    sampledRecord.analysis_state='sampled_incomplete';
    sampledRecord.analysis_progress={state:'sampled_incomplete',completed:1,total:1,at:sampledAt};
    sampledRecord.revision++;
    writeFileSync(xlsxPath,JSON.stringify(sampledRecord));
    await admin.locator('#review-refresh').click();
    await admin.locator('.review-filters [data-filter="done"]').click();
    await admin.locator('.review-queue-item[data-id="'+xlsx.id+'"]').click();
    await admin.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('抽样反馈已出 · 全表审核未完成'));
    assert.match(await admin.locator('#review-detail-content').innerText(),/328.*32.*297.*0 条上线/s);
    assert.equal(await admin.locator('#review-detail-content .review-report').getAttribute('open'),null);
    await anonymous.locator('[data-task-view="submission-progress"]').click();
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-timeline')?.textContent.includes('抽样反馈 · 全表待审'));
    assert.equal(await anonymous.locator('#package-history').evaluate(el=>el.open),false,'historical feedback is folded away from the current execution anchor');
    assert.match(await anonymous.locator('#package-timeline').textContent(),/另一位访客.*Excel 表格.*抽样反馈/s);
    assert.ok(!(await anonymous.locator('#package-active-panel').textContent()).includes('抽样反馈；研究端继续审核未覆盖单元格。'));
    assert.ok(!(await anonymous.locator('#package-active-panel').textContent()).includes(xlsx.sha256));
    const currentTasks=await (await anonymous.request.get(base+'/api/research-tasks')).json();
    const currentPackage=currentTasks.packages.find(p=>p.id==='dc-census-cn');
    const currentProgress=currentTasks.package_progress[currentPackage.id];
    assert.equal(await anonymous.locator('#package-current-next').innerText(),'下一步：'+currentProgress.current_task.next_action);
    assert.ok((await anonymous.locator('#package-progress-note').innerText()).includes(`${currentProgress.current_task.completed.feedback_rounds} 轮团队反馈`));
    assert.match(await anonymous.locator('#package-current-progress-summary').innerText(),/共同进展：.*已成功入库.*个去重园区.*条来源已上线/);
    assert.match(await anonymous.locator('#package-current-received').innerText(),/最新收到：.*Excel 表格/);
    assert.ok((await anonymous.locator('#package-current-feedback').innerText()).includes(currentProgress.current_task.feedback_summary));
    assert.ok(!(await anonymous.locator('#package-current-feedback').innerText()).includes(sampledRecord.feedback[0].text),'the shared feedback never exposes private worker text');
    await anonymous.locator('#package-history>summary').click();
    const sampledEvent=anonymous.locator('#package-timeline .package-event').filter({hasText:'另一位访客'});
    assert.equal(await sampledEvent.evaluate(el=>el.open),false);
    await sampledEvent.locator('summary').click();
    assert.match(await sampledEvent.innerText(),/提交：.*审阅并回复：/s);
    assert.match(await sampledEvent.innerText(),/系统接受并上线：0 条.*当前工作包未完成，请继续/s);
    assert.ok(!(await sampledEvent.innerText()).includes('仅抽样评价'),'the historical row does not repeat superseded review prose');
    assert.equal(await sampledEvent.locator('button,a[download]').count(),0,'historical advice has no execution or download action');
    assert.equal(await anonymous.locator('#package-current-next').innerText(),'下一步：'+currentProgress.current_task.next_action);
    await anonymous.locator('#package-history>summary').click();
    const sharedFixture=structuredClone(currentTasks), sharedProgress=sharedFixture.package_progress[currentPackage.id];
    sharedProgress.published_sites=7;
    sharedProgress.current_task={...sharedProgress.current_task,completed:{...sharedProgress.current_task.completed,published_sites:7,published_statements:9},version:99,feedback_summary:'现行共同反馈：已完成身份核对，下一轮只补新增地点证据。',next_action:'只执行本工作包最新的地点补证要求。',remaining:['仍缺可回查地点来源。']};
    sharedProgress.events.push({received_at:1,reviewed_at:2,submitter:'旧反馈测试',material:'文本资料',outcome:'reviewed',published_statements:0,feedback:'旧共同反馈已被后续版本替代。',next_action:'OLD-NEXT-ACTION-DO-NOT-EXECUTE',feedback_state:'superseded',is_current_feedback:false});
    await anonymous.route('**/api/research-tasks',route=>route.fulfill({json:sharedFixture}));
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-current-next')?.textContent.includes('只执行本工作包最新'));
    assert.equal(await anonymous.locator('#package-current-next').innerText(),'下一步：'+sharedProgress.current_task.next_action);
    assert.ok((await anonymous.locator('#package-current-feedback').innerText()).includes(sharedProgress.current_task.feedback_summary));
    assert.equal(await anonymous.locator('#package-history').evaluate(el=>el.open),false);
    assert.ok(!(await anonymous.locator('#package-active-panel').innerText()).includes('OLD-NEXT-ACTION-DO-NOT-EXECUTE'),'superseded advice is not presented as a current action');
    await anonymous.locator('#package-history>summary').click();
    const retiredEvent=anonymous.locator('.package-event').filter({hasText:'旧反馈测试'});
    await retiredEvent.locator('summary').click();
    assert.ok(!(await retiredEvent.innerText()).includes('OLD-NEXT-ACTION-DO-NOT-EXECUTE'),'old next actions are never rendered, even inside history');
    assert.ok(!(await retiredEvent.innerText()).includes('旧共同反馈已被后续版本替代。'),'historical rows retain only timestamps, accepted results, and task state');
    assert.equal(await retiredEvent.locator('button,a[download]').count(),0);
    assert.equal(await anonymous.locator('#package-current-next').innerText(),'下一步：'+sharedProgress.current_task.next_action);
    await anonymous.locator('#package-history>summary').click();
    // Read freshness is shared by every work package, including failed and racing refreshes.
    const oldHistoryCount=await anonymous.locator('#package-history-count').innerText();
    let releaseFailedRefresh, failedRefreshSeen;
    const failedRefreshHold=new Promise(resolve=>{releaseFailedRefresh=resolve;});
    const failedRefreshStarted=new Promise(resolve=>{failedRefreshSeen=resolve;});
    const failingRefresh=async route=>{failedRefreshSeen();await failedRefreshHold;await route.fulfill({status:503,json:{error:'synthetic refresh outage'}});};
    await anonymous.route('**/api/research-tasks',failingRefresh);
    await anonymous.locator('#package-refresh').click(); await failedRefreshStarted;
    assert.equal(await anonymous.locator('#package-active-panel').getAttribute('data-read-state'),'loading');
    assert.equal(await anonymous.locator('#package-read-status').isVisible(),true);
    assert.equal(await anonymous.locator('#package-current-next').isHidden(),true);
    assert.equal(await anonymous.locator('#package-current-remaining').isHidden(),true);
    assert.match(await anonymous.locator('#package-current-feedback').innerText(),/^上次读取的审阅：/);
    releaseFailedRefresh();
    await anonymous.waitForFunction(()=>document.querySelector('#package-active-panel').dataset.readState==='error');
    assert.match(await anonymous.locator('#package-read-status').innerText(),/刷新失败.*未确认有效/);
    assert.equal(await anonymous.locator('#package-published-sites').innerText(),'7','failed refresh preserves the last read nonzero total');
    assert.equal(await anonymous.locator('#package-history-count').innerText(),oldHistoryCount);
    await anonymous.locator('#package-tabs [data-package-tab="dc-census-na"]').click();
    assert.equal(await anonymous.locator('#package-current-next').isHidden(),true,'switching work packages cannot clear stale-read status');
    assert.match(await anonymous.locator('#package-read-status').innerText(),/刷新失败/);
    assert.ok(!(await anonymous.locator('#package-timeline').textContent()).includes('可按上方当前任务'),'an empty historical package does not point to unconfirmed execution requirements');
    await anonymous.locator('#package-tabs [data-package-tab="dc-census-cn"]').click();
    assert.equal(await anonymous.locator('#package-published-sites').innerText(),'7');
    assert.ok(!(await anonymous.locator('#package-history-guidance').innerText()).includes('上方共同现行'));
    if(process.env.UI_QA_DIR) {
      for(const width of [1440,390]) {await anonymous.setViewportSize({width,height:1000});await anonymous.locator('#package-active-panel').screenshot({path:join(process.env.UI_QA_DIR,'task-refresh-failure-'+width+'.png')});}
      await anonymous.setViewportSize({width:1440,height:1000});
    }
    await anonymous.unroute('**/api/research-tasks',failingRefresh);
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-active-panel').dataset.readState==='current');
    assert.equal(await anonymous.locator('#package-read-status').isHidden(),true);
    assert.equal(await anonymous.locator('#package-current-next').isVisible(),true);
    assert.equal(await anonymous.locator('#package-current-next').innerText(),'下一步：'+sharedProgress.current_task.next_action);
    if(process.env.UI_QA_DIR) await anonymous.locator('#package-active-panel').screenshot({path:join(process.env.UI_QA_DIR,'task-refresh-recovered-1440.png')});

    let releaseLateFailure, lateFailureSeen, lateFailureCalls=0;
    const lateFailureHold=new Promise(resolve=>{releaseLateFailure=resolve;});
    const lateFailureStarted=new Promise(resolve=>{lateFailureSeen=resolve;});
    const lateFailureRoute=async route=>{if(++lateFailureCalls===1){lateFailureSeen();await lateFailureHold;await route.fulfill({status:503,json:{error:'late old failure'}});}else await route.fulfill({json:sharedFixture});};
    await anonymous.route('**/api/research-tasks',lateFailureRoute);
    await anonymous.locator('#package-refresh').click(); await lateFailureStarted;
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-active-panel').dataset.readState==='current');
    const lateFailureResponse=anonymous.waitForResponse(response=>new URL(response.url()).pathname==='/api/research-tasks' && response.status()===503);
    releaseLateFailure(); await lateFailureResponse;
    await anonymous.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await anonymous.locator('#package-active-panel').getAttribute('data-read-state'),'current','an old delayed failure cannot overwrite a later successful read');
    await anonymous.unroute('**/api/research-tasks',lateFailureRoute);

    let releaseLateSuccess, lateSuccessSeen, lateSuccessCalls=0;
    const lateSuccessHold=new Promise(resolve=>{releaseLateSuccess=resolve;});
    const lateSuccessStarted=new Promise(resolve=>{lateSuccessSeen=resolve;});
    const lateFixture=structuredClone(sharedFixture);lateFixture.package_progress[currentPackage.id].current_task.next_action='LATE-OLD-SUCCESS';
    const lateSuccessRoute=async route=>{if(++lateSuccessCalls===1){lateSuccessSeen();await lateSuccessHold;await route.fulfill({json:lateFixture});}else await route.fulfill({status:503,json:{error:'newer failure'}});};
    await anonymous.route('**/api/research-tasks',lateSuccessRoute);
    await anonymous.locator('#package-refresh').click(); await lateSuccessStarted;
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-active-panel').dataset.readState==='error');
    const lateSuccessResponse=anonymous.waitForResponse(response=>new URL(response.url()).pathname==='/api/research-tasks' && response.status()===200);
    releaseLateSuccess(); await lateSuccessResponse;
    await anonymous.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await anonymous.locator('#package-active-panel').getAttribute('data-read-state'),'error','an old delayed success cannot clear a later failed read');
    assert.equal(await anonymous.locator('#package-current-next').isHidden(),true);
    assert.ok(!(await anonymous.locator('#package-current-next').textContent()).includes('LATE-OLD-SUCCESS'));
    await anonymous.unroute('**/api/research-tasks',lateSuccessRoute);
    await anonymous.unroute('**/api/research-tasks');
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-active-panel').dataset.readState==='current');
    await anonymous.waitForFunction(expected=>document.querySelector('#package-current-next')?.textContent==='下一步：'+expected,currentProgress.current_task.next_action);

    await anonymous.locator('[data-task-view="task-home"]').click();
    assert.equal(await anonymous.locator('[data-package-dashboard="dc-census-cn"] [data-package-published-sites]').innerText(),String(currentProgress.published_sites));
    const sourceErrorResponse=await anonymous.request.post(base+'/api/task-uploads',{data:Buffer.from('Synthetic unreadable source'),headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify({name:'synthetic-source-error.txt',submitter:'解析失败测试',project_name:'原件处理失败',package_id:'dc-census-cn'}))}});
    assert.equal(sourceErrorResponse.status(),201);
    const sourceErrorItem=(await sourceErrorResponse.json()).item;
    assert.equal((await admin.request.post(base+'/api/materials/review',{headers:{'X-Requested-With':'material-intake'},data:{id:sourceErrorItem.id,sha256:sourceErrorItem.sha256,expected_revision:sourceErrorItem.revision,operation_id:randomUUID(),action:'approve_and_analyze',note:''}})).status(),200);
    assert.equal((await anonymous.request.post(base+'/api/intake-worker/ack',{headers:workerHeaders,data:{id:sourceErrorItem.id,sha256:sourceErrorItem.sha256}})).status(),200);
    const sourceErrorPath=join(directory,'intake',sourceErrorItem.id,'record.json'), sourceErrorRecord=JSON.parse(readFileSync(sourceErrorPath,'utf8'));
    const sourceErrorAt=Date.now()/1000, sourceErrorAnalysisId=randomUUID();
    sourceErrorRecord.analysis_reports=[{id:sourceErrorAnalysisId,at:sourceErrorAt,sha256:sourceErrorItem.sha256,employee_task:'Synthetic original could not be parsed.',report:{summary:'Synthetic source failure',published:[],held:[],findings:[],publication:{state:'source_error'}}}];
    sourceErrorRecord.feedback=[{id:sourceErrorAnalysisId,by:'analysis-worker',at:sourceErrorAt,sha256:sourceErrorItem.sha256,result:'revision_required',text:'Synthetic original could not be parsed.'}];
    sourceErrorRecord.analysis_progress={state:'source_error',completed:0,total:0,at:sourceErrorAt};sourceErrorRecord.revision++;
    writeFileSync(sourceErrorPath,JSON.stringify(sourceErrorRecord));
    const sourceErrorTaskState=await (await anonymous.request.get(base+'/api/research-tasks')).json();
    const sourceErrorEvent=sourceErrorTaskState.package_progress['dc-census-cn'].events.find(event=>event.submitter==='解析失败测试');
    assert.equal(sourceErrorEvent.reviewed_at,null,'unreadable originals do not receive a completed-reading time');
    assert.equal(sourceErrorEvent.feedback_at,sourceErrorAt);
    await anonymous.locator('[data-task-view="submission-progress"]').click();
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelector('#package-timeline')?.textContent.includes('解析失败测试'));
    await anonymous.locator('#package-history>summary').click();
    const sourceErrorHistory=anonymous.locator('.package-event').filter({hasText:'解析失败测试'});
    await sourceErrorHistory.locator('summary').click();
    assert.match(await sourceErrorHistory.innerText(),/处理反馈：/);
    assert.ok(!(await sourceErrorHistory.innerText()).includes('审阅完成：'),'processing failure feedback is never labeled completed reading');
    if(process.env.UI_QA_DIR) await sourceErrorHistory.screenshot({path:join(process.env.UI_QA_DIR,'task-source-error-feedback-time.png')});
    await anonymous.locator('#package-history>summary').click();
    await admin.close();
    await anonymous.locator('[data-task-view="submission-progress"]').click();
    await anonymous.locator('#task-upload-form [name="submitter"]').fill('访客员工');
    await anonymous.locator('#task-upload-form [name="project_name"]').fill('合成测试项目');
    await anonymous.locator('#task-upload-form [name="file"]').setInputFiles([
      {name:'source.txt',mimeType:'text/plain',buffer:Buffer.from('source evidence')},
      {name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('source notes')}]);
    let lostUploadResponse=false, releaseSecondUpload, secondUploadWaiting;
    const secondUploadSeen=new Promise(resolve=>{secondUploadWaiting=resolve;});
    const secondUploadHold=new Promise(resolve=>{releaseSecondUpload=resolve;});
    await anonymous.route('**/api/task-uploads',async route=>{
      const metadata=JSON.parse(decodeURIComponent(route.request().headers()['x-material-metadata']));
      assert.ok(!('continuation_id' in metadata) && !('continuation_receipt' in metadata),'new uploads use the current shared task without selecting personal prior feedback');
      if(metadata.batch_index===0 && !lostUploadResponse){
        lostUploadResponse=true;
        const response=await route.fetch(); assert.equal(response.status(),201);
        await route.abort('failed');
      } else if(metadata.batch_index===1) { secondUploadWaiting(); await secondUploadHold; await route.continue(); }
      else await route.continue();
    });
    await anonymous.locator('#task-upload-form').evaluate(form=>{form.requestSubmit();form.requestSubmit();});
    await secondUploadSeen;
    const peer=await anonymous.context().newPage();
    await peer.goto(base+'/tasks.html');
    await peer.locator('[data-task-view="submission-progress"]').click();
    await peer.locator('#upload-recover-incomplete').waitFor();
    const activePending=JSON.parse(await peer.evaluate(()=>localStorage.getItem('inresearch-task-upload-pending-batches-v1')))[0];
    assert.equal(activePending.upload_complete,false);
    assert.ok(activePending.batch_token,'another tab preserves the recovery secret during an active upload');
    const activeStatus=await (await peer.request.post(base+'/api/task-uploads/batch-status',{data:{batch_id:activePending.batch_id,batch_token:activePending.batch_token}})).json();
    assert.equal(activeStatus.batch.sealed,false,'refreshing another tab never seals an active partial upload');
    assert.equal(activeStatus.items.length,1);
    releaseSecondUpload(); await peer.close();
    await anonymous.waitForFunction(()=>/2 份附件已收到/.test(document.querySelector('#upload-message')?.textContent || ''));
    await anonymous.waitForFunction(()=>!document.querySelector('#upload-submit').disabled);
    await anonymous.unroute('**/api/task-uploads');
    assert.equal(lostUploadResponse,true);
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),0,'status recovery removes a received attachment after its upload response was lost');
    assert.equal(await anonymous.locator('#upload-own-list, [data-download-feedback], .upload-receipt-code').count(),0);
    assert.equal(JSON.parse(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-receipts-v1'))).length,3,'receipts remain stored privately without being displayed');
    const batchRecords=readdirSync(join(directory,'intake')).filter(id=>/^[a-f0-9]{32}$/.test(id)).map(id=>JSON.parse(readFileSync(join(directory,'intake',id,'record.json'),'utf8'))).filter(r=>['source.txt','notes.txt'].includes(r.name));
    assert.equal(batchRecords.length,2);
    assert.equal(new Set(batchRecords.map(row=>row.batch_id)).size,1,'rapid duplicate submit events create only one upload batch');
    assert.equal(batchRecords[0].batch_id,batchRecords[1].batch_id);
    assert.equal(batchRecords[0].project_name,'合成测试项目');
    const batchReceipts=JSON.parse(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-receipts-v1'))).filter(row=>batchRecords.some(item=>item.id===row.id));
    const sealedReceipt=await (await anonymous.request.post(base+'/api/task-uploads/receipt',{data:batchReceipts[0]})).json();
    assert.equal(sealedReceipt.item.upload_batch.sealed,true,'successful uploads finish their exact receipt batch');
    assert.equal(sealedReceipt.item.upload_batch.received,2);
    assert.equal(sealedReceipt.item.upload_batch.expected,2);
    const batchAdmin=await browser.newPage({viewport:{width:1440,height:1000}});
    await batchAdmin.context().addCookies([{name:'hub_session',value:config.cookies['task-admin'].slice(config.cookies['task-admin'].indexOf('=')+1),url:base}]);
    await batchAdmin.goto(base+'/task-reviews.html?id='+batchRecords[0].id);
    const batchApprove=batchAdmin.locator('[data-batch-action="approve_and_analyze"]');
    await batchApprove.waitFor();
    assert.match(await batchApprove.innerText(),/确认本批 2 份并联合分析/);
    if(process.env.UI_QA_DIR) {await batchAdmin.evaluate(()=>scrollTo(0,0));await batchAdmin.screenshot({path:join(process.env.UI_QA_DIR,'task-batch-approval-1440.png'),fullPage:true});}
    await batchApprove.click();
    await batchAdmin.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('正在分析'));
    const batchPending=(await (await anonymous.request.get(base+'/api/intake-worker/pending',{headers:workerHeaders})).json()).items.filter(row=>batchRecords.some(item=>item.id===row.id));
    assert.equal(batchPending.length,2);
    assert.ok(batchPending[0].review_batch_id);
    assert.equal(batchPending[0].review_batch_id,batchPending[1].review_batch_id,'one approval releases one exact review batch');
    for(const item of batchPending) assert.equal((await anonymous.request.post(base+'/api/intake-worker/ack',{headers:workerHeaders,data:{id:item.id,sha256:item.sha256}})).status(),200);
    const analysisMembers=(await (await anonymous.request.get(base+'/api/intake-worker/analysis-pending',{headers:workerHeaders})).json()).items.filter(row=>row.review_batch_id===batchPending[0].review_batch_id);
    assert.equal(analysisMembers.length,2);
    assert.deepEqual(new Set(analysisMembers[0].review_batch_members.map(row=>row.id)),new Set(batchRecords.map(row=>row.id)));
    await batchAdmin.locator('.review-related>summary').click();
    await batchAdmin.locator('[data-related-id="'+publicRecord.id+'"]').click();
    assert.equal(await batchAdmin.locator('[data-filter="all"]').getAttribute('aria-pressed'),'true','related-file navigation synchronizes the all filter');

    // Ten real uploads exercise compact timelines and persistent seal recovery.
    await anonymous.locator('#task-upload-form [name="file"]').setInputFiles(Array.from({length:10},(_,i)=>({name:`dense-${i}-园区原始来源与地点证据.txt`,mimeType:'text/plain',buffer:Buffer.from(`Synthetic evidence ${i}`)})));
    await anonymous.route('**/api/task-uploads/batch',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'synthetic seal outage'})}));
    await anonymous.locator('#upload-submit').click();
    await anonymous.waitForFunction(()=>document.querySelector('#upload-message')?.textContent.includes('10 份附件已收到'));
    await anonymous.waitForFunction(()=>!document.querySelector('#upload-submit').disabled);
    await anonymous.locator('#upload-retry-batches').waitFor();
    assert.match(await anonymous.locator('#upload-message').innerText(),/批次提交尚未完成/);
    assert.equal(await anonymous.locator('#upload-pending-files li').count(),0,'received files are retained by receipt and never re-uploaded for seal retry');
    const pendingSeals=JSON.parse(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-pending-batches-v1')));
    assert.equal(pendingSeals.length,1);
    assert.equal(pendingSeals[0].items.length,10);
    const denseIds=pendingSeals[0].items.map(row=>row.id);
    await batchAdmin.goto(base+'/task-reviews.html?id='+denseIds[0]);
    await batchAdmin.locator('[data-batch-action="approve_and_analyze"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-batch-action="approve_and_analyze"]').isDisabled(),true,'unsealed uploads cannot be jointly approved');
    await anonymous.unroute('**/api/task-uploads/batch');
    await anonymous.locator('#upload-retry-batches').click();
    await anonymous.waitForFunction(()=>JSON.parse(localStorage.getItem('inresearch-task-upload-pending-batches-v1')||'[]').length===0);
    assert.ok(!(await anonymous.locator('#upload-message').innerText()).includes('批次提交尚未完成'),'successful seal recovery clears the stale incomplete message');
    await batchAdmin.locator('#review-refresh').click();
    await batchAdmin.waitForFunction(()=>!document.querySelector('[data-batch-action="approve_and_analyze"]')?.disabled);
    const denseOwner=(await (await batchAdmin.request.get(base+'/api/materials')).json()).items.filter(item=>denseIds.includes(item.id));
    const recoveryPayload={operation_id:randomUUID(),action:'approve_and_analyze',note:'synthetic interrupted approval',items:denseOwner.map(item=>({id:item.id,sha256:item.sha256,expected_revision:item.revision}))};
    // Interrupt a real isolated approval after its first durable member write.
    execFileSync(process.env.PYTHON || 'python3',['-c',`import sys,json
sys.path.insert(0,'src')
from pathlib import Path
from inresearch.materials import inbox,batch_review
original=inbox.atomic
count=0
def interrupted(path,state):
 global count
 if Path(path).name=='record.json':
  count+=1
  if count==2: raise OSError('synthetic approval interruption')
 return original(path,state)
inbox.atomic=interrupted
try: batch_review.approve(json.loads(sys.argv[1]),'task-admin','admin')
except OSError: pass
else: raise AssertionError('approval was not interrupted')
`,JSON.stringify(recoveryPayload)],{cwd:root,env:environment});
    const preparedMembers=(await (await batchAdmin.request.get(base+'/api/materials')).json()).items.filter(item=>denseIds.includes(item.id));
    const preparedMember=preparedMembers.find(item=>item.review_batch_recovery);
    assert.ok(preparedMember);
    assert.equal((await (await anonymous.request.get(base+'/api/intake-worker/pending',{headers:workerHeaders})).json()).items.some(item=>denseIds.includes(item.id)),false,'partial approval releases no batch member');
    await batchAdmin.goto(base+'/task-reviews.html?id='+preparedMember.id);
    await batchAdmin.locator('[data-batch-action="approve_and_analyze"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-batch-action="approve_and_analyze"]').innerText(),'恢复本批确认');
    if(process.env.UI_QA_DIR) await batchAdmin.locator('.review-detail').screenshot({path:join(process.env.UI_QA_DIR,'task-batch-approval-recovery.png')});
    const recoveryRequest=batchAdmin.waitForRequest(request=>new URL(request.url()).pathname==='/api/materials/review-batch');
    await batchAdmin.locator('[data-batch-action="approve_and_analyze"]').click();
    assert.deepEqual((await recoveryRequest).postDataJSON(),recoveryPayload,'the recovery button replays the original exact operation and members');
    await batchAdmin.waitForFunction(()=>document.querySelector('#review-message')?.textContent.includes('本批 10 份已确认'));
    await anonymous.locator('#package-refresh').click();
    await anonymous.waitForFunction(()=>document.querySelectorAll('#package-timeline .package-event').length>=10);
    await anonymous.locator('#package-history>summary').click();
    for(const width of [1440,390,320]) {
      await anonymous.setViewportSize({width,height:1000});
      const density=await anonymous.evaluate(()=>{
        const team=[...document.querySelectorAll('#package-timeline .package-event')].slice(0,10);
        return {overflow:document.documentElement.scrollWidth>innerWidth+1,
          team:team.map(el=>({open:el.open,height:el.getBoundingClientRect().height})),
          ranges:[6,10].map(count=>team[count-1].getBoundingClientRect().bottom-team[0].getBoundingClientRect().top)};
      });
      assert.equal(density.overflow,false,'compact timelines fit '+width);
      assert.ok(density.team.every(row=>!row.open && row.height<=44),'public records stay one-line rows at '+width);
      assert.ok(density.ranges[0]<=6*44 && density.ranges[1]<=10*44,'six and ten public records remain compact at '+width);
      if(process.env.UI_QA_DIR) {await anonymous.evaluate(()=>scrollTo(0,0));await anonymous.screenshot({path:join(process.env.UI_QA_DIR,'task-timeline-density-'+width+'.png'),fullPage:true});}
    }
    await anonymous.locator('#package-history>summary').click();
    if(process.env.UI_QA_DIR) {
      for(const width of [1440,390]) {await anonymous.setViewportSize({width,height:1000});await anonymous.evaluate(()=>scrollTo(0,0));await anonymous.screenshot({path:join(process.env.UI_QA_DIR,'task-current-feedback-'+width+'.png'),fullPage:true});}
    }
    await anonymous.setViewportSize({width:1440,height:1000});
    await batchAdmin.locator('[data-filter="all"]').click();
    await batchAdmin.locator('.review-queue').scrollIntoViewIfNeeded();
    const filterY=(await batchAdmin.locator('#review-filters').boundingBox()).y;
    await batchAdmin.locator('#review-queue-list').evaluate(el=>{el.scrollTop=el.scrollHeight;});
    assert.ok(Math.abs((await batchAdmin.locator('#review-filters').boundingBox()).y-filterY)<1,'list scrolling keeps search and filters stationary');
    assert.equal(await batchAdmin.locator('#review-search').isVisible(),true);
    // Old upload batches have no batch_total/seal; prior approvals remain independent.
    const legacyBatchId=randomUUID(), legacy=[];
    for(const name of ['legacy-approved.txt','legacy-pending.txt']) {
      const response=await anonymous.request.post(base+'/api/task-uploads',{data:Buffer.from('Synthetic legacy source '+name),headers:{'Content-Type':'application/octet-stream','X-Requested-With':'task-upload','X-Material-Metadata':encodeURIComponent(JSON.stringify({name,submitter:'旧批测试',project_name:'旧版部分批准',package_id:'dc-census-cn',batch_id:legacyBatchId}))}});
      assert.equal(response.status(),201); legacy.push((await response.json()).item);
    }
    assert.equal((await batchAdmin.request.post(base+'/api/materials/review',{headers:{'X-Requested-With':'material-intake'},data:{id:legacy[0].id,sha256:legacy[0].sha256,expected_revision:legacy[0].revision,operation_id:randomUUID(),action:'approve',note:'legacy reception without analysis'}})).status(),200);
    const legacyApproved=JSON.parse(readFileSync(join(directory,'intake',legacy[0].id,'record.json'),'utf8'));
    assert.equal(legacyApproved.status,'approved'); assert.ok(!legacyApproved.analysis_requested_at);
    await batchAdmin.goto(base+'/task-reviews.html?id='+legacy[0].id);
    await batchAdmin.locator('[data-action="start_analysis"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-batch-action]').count(),0,'an already approved legacy member retains its single-source analysis action');
    assert.equal(await batchAdmin.locator('[data-action="start_analysis"]').isDisabled(),true,'approved legacy originals wait for the research receipt before analysis');
    assert.equal((await anonymous.request.post(base+'/api/materials/review',{headers:{'X-Requested-With':'material-intake'},data:{id:legacy[0].id,sha256:legacy[0].sha256,expected_revision:legacyApproved.revision,operation_id:randomUUID(),action:'start_analysis',note:''}})).status(),401,'legacy analysis still requires the designated owner');
    await batchAdmin.goto(base+'/task-reviews.html?id='+legacy[1].id);
    await batchAdmin.locator('[data-action="approve_and_analyze"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-batch-action]').count(),0,'an approved but not analyzed sibling cannot trap the remaining legacy submission in joint approval');
    assert.equal(await batchAdmin.locator('[data-action="approve_and_analyze"]').isDisabled(),false);
    assert.equal((await anonymous.request.post(base+'/api/intake-worker/ack',{headers:workerHeaders,data:{id:legacy[0].id,sha256:legacy[0].sha256}})).status(),200,'single legacy analysis keeps the original research-receipt prerequisite');
    await batchAdmin.goto(base+'/task-reviews.html?id='+legacy[0].id);
    await batchAdmin.locator('[data-action="start_analysis"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-action="start_analysis"]').isDisabled(),false,'archived legacy originals can start their own analysis');
    const legacyStartResponse=batchAdmin.waitForResponse(response=>new URL(response.url()).pathname==='/api/materials/review');
    await batchAdmin.locator('[data-action="start_analysis"]').click();
    assert.equal((await legacyStartResponse).status(),200);
    await batchAdmin.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('正在分析'));
    await batchAdmin.goto(base+'/task-reviews.html?id='+legacy[1].id);
    await batchAdmin.locator('[data-action="approve_and_analyze"]').waitFor();
    assert.equal(await batchAdmin.locator('[data-batch-action]').count(),0,'the remaining pending legacy member is not trapped by its previously approved sibling');
    const legacyApproveResponse=batchAdmin.waitForResponse(response=>new URL(response.url()).pathname==='/api/materials/review');
    await batchAdmin.locator('[data-action="approve_and_analyze"]').click();
    assert.equal((await legacyApproveResponse).status(),200);
    await batchAdmin.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('正在分析'));
    for(const item of legacy) {
      const record=JSON.parse(readFileSync(join(directory,'intake',item.id,'record.json'),'utf8'));
      assert.equal(record.sha256,item.sha256); assert.ok(record.analysis_requested_at); assert.ok(!record.review_batch_id);
    }
    await batchAdmin.close();
    assert.equal(await anonymous.locator('#new-package').isVisible(),false);
    assert.match(await anonymous.locator('#task-role-note').textContent(),/登录后可见/);
    // Synthetic test bytes are private runtime fixtures, separate from the real
    // worked example installed by an operator. They never enter source data.
    const sampleId='equinix-sg3-20261012', sampleDirectory=join(directory,'runtime/data/raw/research-task-examples',sampleId);
    mkdirSync(sampleDirectory,{recursive:true});
    const sampleArtifacts=[['original','SYNTHETIC PUBLIC ORIGINAL\n','public'],['validation','{"offline_valid":true,"synthetic":true}\n','public'],['internal','SYNTHETIC PRIVATE OPERATOR NOTE\n','private']].map(([id,content,access_scope])=>{const bytes=Buffer.from(content);writeFileSync(join(sampleDirectory,id+'.txt'),bytes);return{id,path:id+'.txt',filename:id+'.txt',sha256:createHash('sha256').update(bytes).digest('hex'),size:bytes.length,access_scope};});
    const sample={version:1,id:sampleId,name:'合成浏览器样例 · 不是真实研究数据',site_id:'synthetic-example',status:'测试字节，不可用于研究采用',processed_at:'2026-10-12T12:00:00+08:00',execution:{machine:'private-sample-host',model:'private-sample-model',actor:'private-sample-operator',reading_scope:'仅相关段落，未全文阅读'},sources:[{id:'source-1',title:'合成原件',url:'https://example.invalid/source',artifact_id:'original',locator:'第1节 · 原文定位'}],facts:[{id:'name',label:'园区原名',value:'合成站点',unit:null,source_ids:['source-1'],locator:'第1节'}],unknowns:[{id:'electricity',label:'年度电耗',reason:'原件未披露，保持未知',next_action:'寻找运行年度报告，不填0'}],stages:[{id:'originals',title:'原件取得',state:'complete',result:'已保存合成测试字节',artifact_ids:['original']},{id:'validate',title:'离线验包',state:'complete',result:'合成测试报告',artifact_ids:['validation']},{id:'receive',title:'实际接收',state:'pending',result:'未执行，不可计为已接收',artifact_ids:['internal']},{id:'map',title:'网站与地图回执',state:'pending',result:'未执行，不可计为已点亮',artifact_ids:[]}],artifacts:sampleArtifacts,links:{project:'/project.html?site=synthetic-example',map:'/industry.html?site=synthetic-example'}};
    writeFileSync(join(sampleDirectory,'example.json'),JSON.stringify(sample));
    await anonymous.locator('[data-task-view="task-home"]').click();
    await anonymous.locator('#refresh-examples').click();
    await anonymous.locator('[data-example="'+sampleId+'"]').waitFor();
    assert.ok(!(await anonymous.locator('#example-content').innerText()).includes('private-sample-'));
    assert.equal(await anonymous.locator('[data-example="'+sampleId+'"] .example-key-facts').count(),1);
    assert.equal(await anonymous.locator('[data-example="'+sampleId+'"] .example-full-record').evaluate(el=>el.open),false);
    await anonymous.locator('[data-example="'+sampleId+'"] .example-full-record > summary').click();
    assert.equal(await anonymous.locator('[data-stage="receive"] [data-artifact="internal"]').count(),0);
    assert.match(await anonymous.locator('[data-stage="map"] summary').innerText(),/尚未完成/);
    assert.equal((await anonymous.request.get(base+'/api/research-task-examples/'+sampleId+'/files/internal')).status(),401);
    const [sourceDownload]=await Promise.all([anonymous.waitForEvent('download'),anonymous.locator('[data-stage="originals"] a[download]').click()]);
    assert.equal(createHash('sha256').update(readFileSync(await sourceDownload.path())).digest('hex'),sampleArtifacts[0].sha256);
    await anonymous.locator('.example-fact-sources a').first().click();
    assert.equal(await anonymous.locator('.example-source-list').evaluate(e=>e.open),true);
    assert.match(await anonymous.locator('.example-source-list').innerText(),/第1节 · 原文定位/);
    assert.match(await anonymous.locator('.example-unknowns').innerText(),/年度电耗.*未披露/s);
    const page = await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
    await page.context().addCookies([{name:'hub_session',value:config.cookies['task-member'].split('=')[1],url:base}]);
    assert.equal((await page.request.get(base+'/task-reviews.html')).status(),403);
    const errors = [];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/tasks.html');
    assert.equal((await page.request.get(base+'/api/materials/content/'+publicRecord.id)).status(),404);
    await page.locator('[data-task-view="task-home"]').click();
    await page.locator('#work-packages > summary').click();
    await page.locator('#package-rows tr').nth(5).waitFor();
    await page.locator('[data-example="'+sampleId+'"]').waitFor();
    await page.locator('[data-example="'+sampleId+'"] .example-full-record > summary').click();
    assert.match(await page.locator('.example-execution').innerText(),/private-sample-host/);
    assert.equal(await page.locator('.angle-grid article').count(),12);
    assert.equal(await page.locator('[data-check-id]').count(),58);
    assert.equal(await page.locator('.arch-question').count(),4);
    assert.equal(await page.locator('[data-provider]').count(),6);
    await page.locator('[data-task-view="task-home"]').click();
    assert.equal(await page.locator('#research-context').evaluate(el => el.open),false);
    await page.locator('#research-context > summary').click();
    assert.match(await page.locator('#research-lines').innerText(),/通用数据中心研究/);
    assert.match(await page.locator('#mission-progress-value').innerText(),/0 个园区已入库/);
    assert.match(await page.locator('#mission-progress-detail').innerText(),/目标总量待盘点.*持续采集与补齐/);
    assert.equal(await page.locator('#mission-target-form').isVisible(),false);
    await page.locator('.dashboard-details > summary').click();
    assert.match(await page.locator('#mission-target-basis').innerText(),/园区数量分母由初步盘点后设定/);
    assert.equal(await page.locator('#mission-existing-register').evaluate(el => el.open),false);
    await page.locator('#mission-existing-register > summary').click();
    assert.match(await page.locator('#register-stats').innerText(),/参与统计项目记录/);
    assert.match(await page.locator('#register-basis').innerText(),/参考估算.*区间/);
    assert.equal(await page.locator('#package-rows .package-status.delivered').count(),0);

    await page.locator('[data-edit="dc-census-na"]').click();
    await page.locator('[name="assignee"]').fill('task-intern');
    await page.locator('[name="machine"]').fill('m4');
    await page.locator('[name="model"]').fill('实际模型版本');
    await page.locator('[name="status"]').selectOption('in_progress');
    await page.locator('#save-package').click();
    await page.locator('#package-dialog').waitFor({state:'hidden'});
    await page.reload();
    await page.locator('[data-task-view="task-home"]').click();
    await page.locator('#work-packages > summary').click();
    await page.locator('#package-rows tr').nth(5).waitFor();
    assert.match(await page.locator('[data-package="dc-census-na"]').innerText(),/task-intern.*m4/s);
    const ledger = JSON.parse(readFileSync(join(directory,'runtime/data/raw/research-tasks/ledger.json'),'utf8'));
    assert.equal(ledger.packages[0].assignee,'task-intern');
    assert.equal(ledger.operations.length,1);
    const anonymousTasks=await (await anonymous.request.get(base+'/api/research-tasks')).json();
    assert.equal(anonymousTasks.packages[0].status,'in_progress');
    for(const field of ['assignee','machine','model','note','delivery_pointer','created_by','updated_by','due'])assert.ok(!(field in anonymousTasks.packages[0]),'anonymous field '+field);

    // An editor's old complete form must never pair with a newly loaded revision.
    await page.locator('[data-edit="dc-census-na"]').click();
    await page.locator('[name="note"]').fill('尚未保存的旧表单备注');
    const concurrent = await page.request.post(base+'/api/research-tasks',{headers:{'X-Requested-With':'research-tasks'},data:{action:'update',operation_id:require('node:crypto').randomUUID(),expected_revision:1,package_id:'dc-census-na',machine:'macmini'}});
    assert.equal(concurrent.status(),200);
    await page.locator('#save-package').click();
    await page.locator('#package-dialog').waitFor({state:'hidden'});
    await page.waitForFunction(()=>document.querySelector('#tasks-status').textContent.includes('当前表单未保存'));
    assert.match(await page.locator('[data-package="dc-census-na"]').innerText(),/macmini/);
    await page.locator('[data-edit="dc-census-na"]').click();
    assert.equal(await page.locator('[name="machine"]').inputValue(),'macmini');
    assert.notEqual(await page.locator('[name="note"]').inputValue(),'尚未保存的旧表单备注');
    await page.locator('#close-package').click();

    assert.equal(await page.locator('#download-brief, #download-template-home, #download-template').count(),0,'internal readers cannot restore retired task downloads');
    await page.locator('#new-package').click();
    for(const [name,value] of Object.entries({title:'测试城市定位补充',region:'欧洲',scope:'测试工作包范围',sources:'运营商地点目录'}))await page.locator('#package-dialog [name="'+name+'"]').fill(value);
    await page.locator('#save-package').click();
    await page.locator('#package-dialog').waitFor({state:'hidden'});
    await page.locator('#package-rows tr').nth(6).waitFor();
    await page.locator('#package-filter').selectOption('unassigned');
    assert.equal(await page.locator('#package-rows tr').count(),6);
    await page.locator('#package-filter').selectOption('');
    for(const width of [1440,760,390,320]){
      await page.setViewportSize({width,height:1000});
      await page.locator('[data-task-view="task-home"]').click();
      const responsiveUrl=page.url();
      assert.ok(await page.locator('#mission-dashboard').isVisible(),'homepage dashboard at width '+width);
      assert.ok(await page.locator('#data-angles').isVisible(),'homepage relationship diagram at width '+width);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'homepage responsive width '+width);
      assert.equal(await page.locator('#download-template').count(),0);
      await page.locator('[data-task-view="submission-progress"]').click();
      assert.equal(page.url(),responsiveUrl);
      assert.ok(await page.locator('#task-upload-form').isVisible(),'submission form at width '+width);
      assert.ok(await page.locator('#package-workspace').isVisible(),'team timeline at width '+width);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'submission responsive width '+width);
      await page.locator('[data-task-view="task-home"]').click();
      assert.equal(page.url(),responsiveUrl);
    }
    await page.setViewportSize({width:1440,height:1000});
    if(process.env.UI_TASKS_SCREENSHOT_PREFIX){
      for(const mode of ['light','dark'])for(const width of [1440,390,320]){
        await page.setViewportSize({width,height:1000});
        await setAppearance(page, mode);
        await page.evaluate(()=>scrollTo(0,0));
        await page.screenshot({path:process.env.UI_TASKS_SCREENSHOT_PREFIX+'-'+mode+'-'+width+'.png',fullPage:true});
      }
    }

    const intern = await browser.newPage();
    await intern.context().addCookies([{name:'hub_session',value:config.cookies['task-intern'].split('=')[1],url:base}]);
    await intern.goto(base+'/tasks.html');
    await intern.locator('[data-task-view="task-home"]').click();
    await intern.locator('#work-packages > summary').click();
    await intern.locator('[data-edit="dc-census-na"]').waitFor();
    assert.equal(await intern.locator('#new-package').isVisible(),false);
    assert.equal(await intern.locator('#package-rows [data-edit]').count(),1);
    await intern.locator('[data-edit="dc-census-na"]').click();
    assert.equal(await intern.locator('[name="assignee"]').isDisabled(),true);
    await intern.locator('[name="status"]').selectOption('delivered');
    await intern.locator('[name="delivery_pointer"]').fill('private/delivery-actual/receipt.json');
    await intern.locator('#save-package').click();
    await intern.locator('#package-dialog').waitFor({state:'hidden'});
    await intern.locator('[data-package="dc-census-na"] .package-status.delivered').waitFor();
    assert.match(await intern.locator('[data-package="dc-census-na"]').innerText(),/已交付/);
    assert.equal((await intern.request.get(base+'/api/research-task-examples/'+sampleId+'/files/internal')).status(),200);
    writeFileSync(join(sampleDirectory,'original.txt'),'CHANGED SYNTHETIC ORIGINAL');
    await anonymous.locator('#refresh-examples').click();
    await anonymous.locator('[data-example="'+sampleId+'"] .example-full-record > summary').click();
    await anonymous.locator('[data-stage="originals"] .example-warning').waitFor();
    assert.equal((await anonymous.request.get(base+'/api/research-task-examples/'+sampleId+'/files/original')).status(),409);
    assert.equal(await anonymous.locator('[data-stage="originals"] a[download]').count(),0);

    const owner = await browser.newPage();
    await owner.context().addCookies([{name:'hub_session',value:config.cookies['task-admin'].slice(config.cookies['task-admin'].indexOf('=')+1),url:base}]);
    await owner.goto(base+'/tasks.html');
    await owner.locator('[data-task-view="task-home"]').click();
    await owner.locator('#work-packages > summary').click();
    await owner.locator('#package-rows tr').nth(5).waitFor();
    await owner.locator('.dashboard-details > summary').click();
    assert.equal(await owner.locator('#mission-target-form').isVisible(),true);
    await owner.locator('#mission-target-form [name="target_site_count"]').fill('250');
    await owner.locator('#mission-target-form [name="target_site_basis"]').fill('初步盘点去重的运营商园区清单');
    await owner.locator('#mission-target-form button').click();
    await owner.waitForFunction(()=>document.querySelector('#mission-target-message')?.textContent.includes('目标已保存'));
    assert.match(await owner.locator('#mission-progress-detail').innerText(),/暂定目标 250 · 0%/);
    assert.match(await owner.locator('#mission-target-basis').innerText(),/初步盘点去重的运营商园区清单/);
    const targetLedger=JSON.parse(readFileSync(join(directory,'runtime/data/raw/research-tasks/ledger.json'),'utf8'));
    assert.equal(targetLedger.target_site_count,250);
    assert.equal(targetLedger.target_site_basis,'初步盘点去重的运营商园区清单');
    await anonymous.reload();
    await anonymous.waitForFunction(()=>document.querySelector('#mission-progress-detail')?.textContent.includes('暂定目标 250'));
    assert.match(await anonymous.locator('#mission-progress-detail').innerText(),/暂定目标 250 · 0%/);

    assert.deepEqual(errors,[]);
    assert.deepEqual(anonymousErrors,[]);
    assert.ok(!publicPageRequests.includes('/api/task-uploads/receipt'),'the public page never fetches individual historical receipt feedback');
    const secrets=JSON.parse(await anonymous.evaluate(()=>localStorage.getItem('inresearch-task-upload-receipts-v1')||'[]'));
    const publicText=await anonymous.locator('body').innerText();
    assert.ok(secrets.every(row=>!publicText.includes(row.receipt)),'stored recovery credentials are never displayed');
    console.log('PASS task dashboard, accumulated picker/drop queue and 20-file bound, lost-response receipt recovery, cross-tab active-upload protection, duplicate-submit guard, seal failure recovery, exact joint approval/prepared replay, shared current feedback with 503/recovery and delayed-response ordering, source-error processing time, history-only compact 6/10-row records at 1440/390/320, retired downloads/personal UI absent, sticky filters, task privacy, real-byte examples, concurrent assignments and 4 responsive widths');
  } finally {if(browser)await browser.close();server.kill();lines.close();rmSync(directory,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
