/* Real first-login, owner-grant and scoped approval UI; isolated private runtime. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {mkdtempSync,rmSync,mkdirSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join,resolve} = require('node:path');
const {createInterface} = require('node:readline');
const {chromium} = require('playwright');
const {setAppearance} = require('./ui_helpers.cjs');
const directory = mkdtempSync(join(tmpdir(),'inresearch-project-access-'));
const env = {...process.env,INRESEARCH_RUNTIME_ROOT:join(directory,'runtime'),INRESEARCH_INTAKE_ROOT:join(directory,'intake'),INRESEARCH_MATERIAL_APPROVER:'owner',HUB_AUTH:'on',INRESEARCH_MARKET_ENABLED:'0',PYTHONDONTWRITEBYTECODE:'1'};
const server = spawn(process.env.PYTHON || 'python3',['-u','-c',"import sys,json,secrets;sys.path.insert(0,'src');from inresearch.storage.layout import initialize_runtime;initialize_runtime();from inresearch.interfaces import http,auth;http.AUTH_ON=True;auth.add_user('owner',secrets.token_urlsafe(32),'admin');auth.add_user('isaac','isaac-test-password','intern');s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port,'cookie':auth.make_cookie('owner').split(';')[0]}),flush=True);s.serve_forever()"],{cwd:resolve(__dirname,'..'),env,stdio:['ignore','pipe','inherit']});
const lines = createInterface({input:server.stdout});
const ready = new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',code=>reject(Error('test server exited '+code)));});
(async()=>{
  let browser;
  try {
    const config=await ready,base='http://127.0.0.1:'+config.port;
    browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});
    const owner=await browser.newPage(),errors=[];
    owner.on('pageerror',error=>errors.push(error.message));
    await owner.context().addCookies([{name:'hub_session',value:config.cookie.slice(config.cookie.indexOf('=')+1),url:base}]);
    await owner.goto(base+'/tasks.html#submission-progress');
    await owner.locator('#task-management-tab').waitFor();
    assert.equal(await owner.locator('#submission-progress').isVisible(),true);
    await owner.locator('#task-management-tab').click();
    assert.equal(await owner.locator('#manage-members-link').isVisible(),true);
    assert.equal(await owner.locator('#manage-reviews-link').isVisible(),true);
    assert.equal(await owner.locator('#manage-accounts-link').isVisible(),true);
    for(const width of [1440,320]) {
      await owner.setViewportSize({width,height:900});await owner.evaluate(()=>scrollTo(0,0));
      assert.ok(await owner.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'admin tab has no page overflow');
      if(process.env.UI_QA_DIR) {mkdirSync(process.env.UI_QA_DIR,{recursive:true});await owner.screenshot({path:join(process.env.UI_QA_DIR,`project-management-${width}.png`),fullPage:true});}
    }
    await owner.setViewportSize({width:1440,height:900});
    await owner.locator('#manage-members-link').click();
    await owner.waitForURL(base+'/admin/project-access.html');
    async function create(name,approve) {
      await owner.locator('#project-create [name=username]').fill(name);
      const response=owner.waitForResponse(r=>r.url().endsWith('/api/project-access') && r.request().method()==='POST');
      await owner.locator('#project-create button').click();
      const created=await (await response).json();assert.equal(created.ok,true);
      await owner.waitForFunction(name=>document.querySelector('#project-user')?.value===name,name);
      const form=owner.locator('#project-grant');
      await form.locator('[name=display_name]').fill(name==='alice'?'林同学':'陈审阅');
      await form.locator('[name=enabled]').check();
      await form.locator('[name=frontend]').check();
      await form.locator('[data-submit="dc-census-cn"]').check();
      if(approve) await form.locator('[data-approve="dc-census-cn"]').check();
      await form.locator('[type=submit]').click();
      await owner.waitForFunction(()=>document.querySelector('#project-save-status')?.textContent==='授权已保存。');
      return created.password;
    }
    const initial=await create('alice',false);
    const reviewInitial=await create('reviewer',true);
    async function login(name,password,first=false) {
      const page=await browser.newPage();await page.clock.install();page.on('pageerror',error=>errors.push(error.message));
      await page.goto(base+'/login');
      await page.locator('[name=username]').fill(name);await page.locator('[name=password]').fill(password);
      await page.locator('[data-auth-form] button').click();
      if(first) {
        await page.waitForURL(base+'/account');
        await page.locator('[name=old_password]').fill(password);
        await page.locator('[name=new_password]').fill(name+'-chosen-password');
        await page.locator('[name=confirm_password]').fill(name+'-chosen-password');
        await page.locator('[data-auth-form] button').click();
      }
      await page.waitForURL(base+'/tasks.html');await page.locator('#my-work-tab').waitFor();
      await page.waitForFunction(()=>window.activeResearchTaskView==='my-work');
      return page;
    }
    async function get(page,path) {
      // APIRequestContext does not apply Chromium's Secure-cookie loopback exception.
      const Cookie=(await page.context().cookies()).map(c=>c.name+'='+c.value).join('; ');
      return page.request.get(base+path,{headers:{Cookie}});
    }
    const alice=await login('alice',initial,true),reviewer=await login('reviewer',reviewInitial,true),intern=await login('isaac','isaac-test-password');
    assert.equal(intern.url(),base+'/tasks.html');
    assert.equal(await intern.evaluate(()=>window.activeResearchTaskView),'my-work');
    assert.equal(await intern.locator('#task-management-tab').isHidden(),true);
    assert.equal(await intern.locator('#my-review-link').isHidden(),true);
    assert.equal(await alice.locator('#task-management-tab').isHidden(),true);
    assert.equal(await reviewer.locator('#task-management-tab').innerText(),'作业审批');
    assert.equal(await alice.locator('#my-review-link').isHidden(),true);
    assert.equal(await alice.locator('#my-access-link').isHidden(),true);
    assert.equal(await alice.locator('#my-front-link').isVisible(),true);
    assert.equal(await alice.locator('#my-packages [data-open-package]').count(),1);
    assert.equal(await reviewer.locator('#my-review-link').isVisible(),true);
    await alice.locator('[data-task-view=task-home]').click();
    await alice.locator('#package-dashboard [data-package-dashboard]').nth(5).waitFor();
    assert.equal(await alice.locator('[data-task-view=task-home]').innerText(),'团队进展');
    await alice.locator('[data-task-view=my-work]').click();
    await alice.locator('#my-packages [data-open-package]').click();
    await alice.locator('#task-upload-form').waitFor();
    assert.equal(await alice.locator('#upload-package option:not([value=""])').count(),1);
    assert.equal(await alice.locator('[name=submitter]').inputValue(),'林同学');
    await alice.locator('[name=project_name]').fill('合成测试园区资料');
    await alice.locator('[name=file]').setInputFiles({name:'project-test.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic source for scoped approval UI')});
    let releaseUpload;
    const uploadGate=new Promise(resolve=>{releaseUpload=resolve;});
    await alice.route('**/api/task-uploads',async route=>{
      const response=await route.fetch();
      await uploadGate;
      await route.fulfill({response});
    });
    const uploadResponse=alice.waitForResponse(r=>r.url().endsWith('/api/task-uploads') && r.status()===201);
    await alice.locator('#upload-submit').click();
    await alice.locator('[data-task-view=my-work]').click();
    releaseUpload();
    const uploaded=await (await uploadResponse).json();
    await alice.waitForFunction(()=>!document.querySelector('#upload-submit').disabled);
    assert.equal(await alice.evaluate(()=>window.activeResearchTaskView),'my-work','late upload completion preserves the chosen tab');
    await alice.unroute('**/api/task-uploads');
    await alice.locator('#my-refresh').click();
    await alice.locator('#my-submissions').filter({hasText:'project-test.txt'}).waitFor();
    assert.match(await alice.locator('#my-submissions').innerText(),/等待审批/);
    assert.equal((await get(reviewer,'/api/project-work')).status(),200);
    assert.deepEqual((await (await get(reviewer,'/api/project-work')).json()).items,[]);
    await reviewer.locator('#my-review-link').click();
    await reviewer.locator('[data-id="'+uploaded.item.id+'"]').click();
    await reviewer.locator('[data-action=approve_and_analyze]').click();
    await reviewer.waitForFunction(()=>document.querySelector('#review-detail-content')?.textContent.includes('正在分析'));
    await alice.locator('#my-refresh').click();
    await alice.waitForFunction(()=>document.querySelector('#my-submissions')?.textContent.includes('等待处理'));
    assert.equal(await alice.locator('#my-processing').isVisible(),true);
    assert.match(await alice.locator('#my-processing').innerText(),/处理反馈稍后更新/);
    await alice.locator('[data-task-view=submission-progress]').click();
    await alice.locator('#package-refresh').click();
    await alice.locator('#package-processing').waitFor();
    assert.match(await alice.locator('#package-processing').innerText(),/正在处理，反馈稍后更新/);
    assert.match(await alice.locator('#package-processing').innerText(),/1 份等待处理/);
    if(process.env.UI_QA_DIR) {
      mkdirSync(process.env.UI_QA_DIR,{recursive:true});
      await alice.locator('#package-active-panel').screenshot({path:join(process.env.UI_QA_DIR,'project-processing.png')});
    }
    await alice.locator('[data-task-view=my-work]').click();
    // A current full review stays active even with old feedback; timers refresh the visible view.
    const workFixture=await (await get(alice,'/api/project-work')).json();
    workFixture.items[0].processing_state='running';
    workFixture.items[0].analysis_scope={mode:'full_native_campus',state:'continuing'};
    workFixture.items[0].feedback=[{text:'合成的历史抽样反馈'}];
    await alice.route('**/api/project-work',route=>route.fulfill({json:workFixture}));
    await alice.clock.fastForward(30001);
    await alice.waitForFunction(()=>document.querySelector('#my-submissions')?.textContent.includes('正在审阅'));
    workFixture.items[0].processing_state='blocked';
    await alice.clock.fastForward(30001);
    await alice.waitForFunction(()=>document.querySelector('#my-submissions')?.textContent.includes('处理受阻'));
    assert.equal(await alice.locator('#my-processing').getAttribute('data-state'),'blocked');
    assert.match(await alice.locator('#my-processing').innerText(),/等待管理员处理/);
    assert.equal(await alice.locator('#my-processing').evaluate(node=>getComputedStyle(node).backgroundColor),'rgb(232, 240, 233)');
    await alice.unroute('**/api/project-work');await alice.locator('#my-refresh').click();
    await alice.waitForFunction(()=>document.querySelector('#my-submissions')?.textContent.includes('等待处理'));
    assert.equal((await get(alice,'/task-reviews.html')).status(),403);
    assert.equal((await get(alice,'/api/materials/content/'+uploaded.item.id)).status(),200);
    const front=await get(alice,'/api/industry?overview=1');assert.equal(front.status(),200);
    assert.equal((await get(alice,'/projects.html')).status(),200);
    assert.equal((await get(alice,'/api/status')).status(),403);
    for(const width of [1440,390,320]) {
      await alice.setViewportSize({width,height:900});await owner.setViewportSize({width,height:900});
      for(const mode of ['light','dark']) {
        for(const page of [alice,owner]) {
          await setAppearance(page,mode);
          await page.evaluate(()=>scrollTo(0,0));
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');
          if(process.env.UI_QA_DIR) {mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:join(process.env.UI_QA_DIR,`project-${page===alice?'work':'access'}-${width}-${mode}.png`),fullPage:true});}
        }
      }
    }
    // Saving grants invalidates already-issued cookies immediately, while records remain.
    await owner.locator('#project-user').selectOption('alice');
    await owner.locator('[name=enabled]').uncheck();
    await owner.locator('#project-grant [type=submit]').click();
    await owner.waitForFunction(()=>document.querySelector('#project-save-status')?.textContent==='授权已保存。');
    assert.equal((await get(alice,'/api/project-work')).status(),401);
    const revoked=await login('alice','alice-chosen-password');
    assert.match(await revoked.locator('#my-status').innerText(),/尚未获此项目授权/);
    assert.equal(await revoked.locator('#my-submissions a').count(),0);
    assert.equal((await get(revoked,'/api/materials/content/'+uploaded.item.id)).status(),403);
    assert.deepEqual(errors,[]);
    console.log('PASS individual first login, owner grants, personal/team views, real upload and scoped review, revocation, 320/390/1440 light/dark');
  } finally {if(browser)await browser.close();server.kill();lines.close();rmSync(directory,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
