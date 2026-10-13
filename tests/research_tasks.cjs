const {setAppearance} = require('./ui_helpers.cjs');
/* Real durable mutations run against an isolated runtime, never the source tree. */
const assert = require('node:assert/strict');
const {spawn,execFileSync} = require('node:child_process');
const {mkdtempSync,rmSync,readFileSync,mkdirSync,writeFileSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join,resolve} = require('node:path');
const {createInterface} = require('node:readline');
const {chromium} = require('playwright');
const {createHash} = require('node:crypto');
const root = resolve(__dirname,'..');
const directory = mkdtempSync(join(tmpdir(),'inresearch-tasks-'));
const environment = {...process.env,INRESEARCH_RUNTIME_ROOT:join(directory,'runtime'),INRESEARCH_INTAKE_ROOT:join(directory,'intake'),HUB_AUTH:'on',INRESEARCH_MARKET_ENABLED:'0',PYTHONDONTWRITEBYTECODE:'1'};
const code = "import sys,json,secrets;sys.path.insert(0,'src');from inresearch.storage.layout import initialize_runtime;initialize_runtime();from inresearch.interfaces import http,auth;http.AUTH_ON=True;[(auth.add_user(name,secrets.token_urlsafe(32),role)) for name,role in [('task-admin','admin'),('task-member','member'),('task-intern','intern')]];cookies={name:auth.make_cookie(name).split(';')[0] for name in ['task-admin','task-member','task-intern']};s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler);print(json.dumps({'port':s.server_port,'cookies':cookies}),flush=True);s.serve_forever()";
const server = spawn(process.env.PYTHON || 'python3',['-u','-c',code],{cwd:root,env:environment,stdio:['ignore','pipe','inherit']});
const lines = createInterface({input:server.stdout});
const ready = new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});server.once('error',reject);server.once('exit',c=>reject(Error('task test server exited '+c)));});

(async()=>{
  let browser;
  try {
    const config = await ready, base = 'http://127.0.0.1:'+config.port;
    browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});
    const anonymous = await browser.newPage();
    assert.equal((await anonymous.request.get(base+'/api/research-tasks')).status(),200);
    assert.equal((await anonymous.request.post(base+'/api/research-tasks',{data:{}})).status(),401);
    await anonymous.goto(base+'/tasks.html');
    await anonymous.locator('#package-rows tr').nth(5).waitFor();
    await anonymous.waitForFunction(()=>document.querySelector('#examples-status').textContent.includes('尚未安装'));
    assert.equal(await anonymous.locator('#new-package').isVisible(),false);
    assert.match(await anonymous.locator('#task-role-note').innerText(),/登录后可见/);
    // Synthetic test bytes are private runtime fixtures, separate from the real
    // worked example installed by an operator. They never enter source data.
    const sampleId='equinix-sg3-20261012', sampleDirectory=join(directory,'runtime/data/raw/research-task-examples',sampleId);
    mkdirSync(sampleDirectory,{recursive:true});
    const sampleArtifacts=[['original','SYNTHETIC PUBLIC ORIGINAL\n','public'],['validation','{"offline_valid":true,"synthetic":true}\n','public'],['internal','SYNTHETIC PRIVATE OPERATOR NOTE\n','private']].map(([id,content,access_scope])=>{const bytes=Buffer.from(content);writeFileSync(join(sampleDirectory,id+'.txt'),bytes);return{id,path:id+'.txt',filename:id+'.txt',sha256:createHash('sha256').update(bytes).digest('hex'),size:bytes.length,access_scope};});
    const sample={version:1,id:sampleId,name:'合成浏览器样例 · 不是真实研究数据',site_id:'synthetic-example',status:'测试字节，不可用于研究采用',processed_at:'2026-10-12T12:00:00+08:00',execution:{machine:'private-sample-host',model:'private-sample-model',actor:'private-sample-operator',reading_scope:'仅相关段落，未全文阅读'},sources:[{id:'source-1',title:'合成原件',url:'https://example.invalid/source',artifact_id:'original',locator:'第1节 · 原文定位'}],facts:[{id:'name',label:'园区原名',value:'合成站点',unit:null,source_ids:['source-1'],locator:'第1节'}],unknowns:[{id:'electricity',label:'年度电耗',reason:'原件未披露，保持未知',next_action:'寻找运行年度报告，不填0'}],stages:[{id:'originals',title:'原件取得',state:'complete',result:'已保存合成测试字节',artifact_ids:['original']},{id:'validate',title:'离线验包',state:'complete',result:'合成测试报告',artifact_ids:['validation']},{id:'receive',title:'实际接收',state:'pending',result:'未执行，不可计为已接收',artifact_ids:['internal']},{id:'map',title:'网站与地图回执',state:'pending',result:'未执行，不可计为已点亮',artifact_ids:[]}],artifacts:sampleArtifacts,links:{project:'/project.html?site=synthetic-example',map:'/industry.html?site=synthetic-example'}};
    writeFileSync(join(sampleDirectory,'example.json'),JSON.stringify(sample));
    await anonymous.locator('#refresh-examples').click();
    await anonymous.locator('[data-example="'+sampleId+'"]').waitFor();
    assert.ok(!(await anonymous.locator('#example-content').innerText()).includes('private-sample-'));
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
    const errors = [];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/tasks.html');
    await page.locator('#package-rows tr').nth(5).waitFor();
    await page.locator('[data-example="'+sampleId+'"]').waitFor();
    assert.match(await page.locator('.example-execution').innerText(),/private-sample-host/);
    assert.equal(await page.locator('.angle-grid article').count(),12);
    assert.match(await page.locator('.mission-scale').innerText(),/待校准/);
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

    const [briefDownload] = await Promise.all([page.waitForEvent('download'),page.locator('#download-brief').click()]);
    const brief = readFileSync(await briefDownload.path(),'utf8');
    assert.ok(brief.includes('\n\n## 工作包'), 'task brief uses real newlines');
    assert.ok(!brief.includes('\\n'), 'task brief has no escaped newline sequences');
    assert.match(brief,/task-intern/);
    const [templateDownload] = await Promise.all([page.waitForEvent('download'),page.locator('#download-template').click()]);
    const template = JSON.parse(readFileSync(await templateDownload.path(),'utf8'));
    assert.equal(template.contract,'fetchdata-handoff/1');
    assert.ok(template.files['observations.jsonl']);
    assert.ok('run_id' in template.files['run-report.json']);
    assert.ok('attempted_sources' in template.files['run-report.json'].counts);
    assert.equal(typeof template.files['observations.jsonl'][0].scope,'string');
    // Fill the downloaded schema with synthetic bytes and run the existing
    // offline validator; template nulls never masquerade as a real delivery.
    const bundle = join(directory,'synthetic-download-check'), now = new Date().toISOString();
    const bytes = Buffer.from('{"synthetic":true,"it_mw":60}\n');
    const sha = require('node:crypto').createHash('sha256').update(bytes).digest('hex');
    mkdirSync(join(bundle,'originals'),{recursive:true});writeFileSync(join(bundle,'originals',sha+'.json'),bytes);
    const manifest = template.files['manifest.json'];Object.assign(manifest,{provider_id:'fetchreports',delivery_id:'synthetic-task-template',collector_revision:'0'.repeat(40),generated_at:now,synthetic:true});
    Object.assign(manifest.items[0],{source_id:'synthetic',source_item_id:'synthetic-v1',title:'SYNTHETIC never adopt',publisher:'Synthetic',url:'https://example.invalid/synthetic.json',retrieved_at:now,sha256:sha,path:'originals/'+sha+'.json',content_type:'application/json',access_scope:'public',completeness:'complete'});
    const observation = template.files['observations.jsonl'][0];Object.assign(observation,{observation_id:'synthetic-task-mw',metric:'site.it_mw',value:{type:'number',number:60,raw:'60 MW'},unit:'MW',scope:'Synthetic site whole-site IT capacity; not real data',evidence:{locator:'/it_mw',quote:'"it_mw":60',context:'Synthetic fixture, never research evidence'}});observation.object.name='Synthetic site';
    const report = template.files['run-report.json'];Object.assign(report,{run_id:manifest.delivery_id,team:manifest.provider_id,collector_revision:manifest.collector_revision,started_at:now,finished_at:now,duration_seconds:0,bytes_downloaded:bytes.length});for(const key of Object.keys(report.counts))report.counts[key]=0;Object.assign(report.counts,{scheduled_sources:1,attempted_sources:1,successful_sources:1,new_originals:1,candidates:1,unresolved_candidates:1});
    for(const [name,data] of [['manifest.json',JSON.stringify(manifest)],['SHA256SUMS',sha+'  originals/'+sha+'.json\n'],['observations.jsonl',JSON.stringify(observation)+'\n'],['errors.jsonl',''],['run-report.json',JSON.stringify(report)]])writeFileSync(join(bundle,name),data);
    const validation = JSON.parse(execFileSync(process.env.PYTHON || 'python3',['scripts/validate_collector_handoff.py',bundle],{cwd:root,encoding:'utf8',env:environment}));
    assert.equal(validation.offline_valid,true);

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
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'responsive width '+width);
      assert.ok(await page.locator('#download-template').isVisible());
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
    await anonymous.locator('[data-stage="originals"] .example-warning').waitFor();
    assert.equal((await anonymous.request.get(base+'/api/research-task-examples/'+sampleId+'/files/original')).status(),409);
    assert.equal(await anonymous.locator('[data-stage="originals"] a[download]').count(),0);

    assert.deepEqual(errors,[]);
    console.log('PASS public task privacy, real-byte example downloads, unknowns/evidence/pending states, changed-file rejection, persisted assignment, concurrent-edit protection, own intern delivery and 4 responsive widths');
  } finally {if(browser)await browser.close();server.kill();lines.close();rmSync(directory,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
