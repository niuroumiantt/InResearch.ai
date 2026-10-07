const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL;
(async()=>{
 const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack);});
  await page.goto(base+'/supply.html');
  await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  assert.match(page.url(),/#targets$/,'the target table is the first screen');
  assert.equal(await page.locator('#team-cards .team-card').count(),6,'six teams');
  assert.equal(await page.locator('table.heat tbody tr').count(),7,'five systems, site rights and the root by five classes');
  await page.goto(base+'/supply.html?node=part:transformer&col=4#targets');
  await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  assert.equal(await page.locator('table.targets tbody tr').count(),1,'node + column prefilter from the node page');
  assert.match(await page.locator('table.targets tbody').innerText(),/P\.transformer\.lead_time/);
  await page.getByRole('button',{name:'派工',exact:true}).first().click();await page.locator('#target-dialog[open]').waitFor();
  await page.locator('#td-cancel').click();
  await page.goto(base+'/supply.html');await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  await page.getByRole('button',{name:'研究问题任务',exact:true}).click();await page.locator('#tk-table tr').nth(1).waitFor();
  assert.match(page.url(),/#tasks$/);assert.ok((await page.locator('#tk-nodes .team-card').count())>0,'tasks grouped by skeleton node');
  await page.getByRole('button',{name:'收件箱',exact:true}).click();await page.locator('#mi-form').waitFor();assert.match(page.url(),/#inbox$/);
  await page.getByRole('button',{name:'规格批次',exact:true}).click();await page.locator('#pilot-status').waitFor();assert.match(page.url(),/#pilot$/);
  for(const [legacy,hash] of [['/team.html','#tasks'],['/materials.html','#inbox']]){const r=await page.request.get(base+legacy,{maxRedirects:0});assert.equal(r.status(),302,legacy);assert.ok(r.headers()['location'].endsWith('supply.html'+hash),legacy);}
  await page.getByRole('button',{name:'新闻与报告匹配',exact:true}).click();
  await page.getByRole('heading',{name:'材料处理进展',exact:true}).waitFor();
  assert.equal(await page.locator('#matching-demands').evaluate(e=>e.open),false);
  assert.equal(await page.locator('.pipeline').isVisible(),false);
  await page.locator('#matching-demands > summary').click();
  await page.locator('#matching-events > summary').click();
  await page.getByRole('heading',{name:'需求先于材料',exact:true}).waitFor();
  await page.getByRole('heading',{name:'日报 → 逐事件数据库',exact:true}).waitFor();
  await page.locator('#daily-state').selectOption('awaiting_identity');
  assert.match(await page.locator('#daily-shown').innerText(),/显示/);
  await page.locator('#daily-state').selectOption('all');
  await page.getByRole('heading',{name:'事件分流与交付',exact:true}).waitFor();
  const original=await (await page.request.get(base+'/api/supply')).json();
  const ready='daily-event-fixture-ready',missing='daily-event-fixture-missing';
  const event=(id,title)=>({id,title,body:'日报正文只在登录匹配页显示',reported_stage:'unknown',place_quote:'芬兰',actors:[],country_mentions:[],site_candidates:[],capacity_observations:[],sources:[],document_refs:[],identity_review:'pending',capacity_review:'pending',workflow_stage:'awaiting_identity'});
  await page.route('**/api/supply',route=>route.fulfill({json:{...original,
   matching_reader:{received_at:'2026-10-06T08:00:00Z',execution_scope:{documents:133,registered:131,counts:{complete:2,running:2,queued:127,blocked:2},types:{'.pdf':69,'.html':62},chunks_read:18,chunks_total:156,awaiting_extraction:126,native_text_only_complete:1,skipped_image_pages:3,text_layer_empty_pages:1,executor:{pdf_mode:'native_text_only',backend:'codex_cli',model:'gpt-6.1-sol <img src=x>',reasoning_effort:'medium'}}},
   project_updates:[{site_id:'fi-reviewed',name:'正式采用园区',verified_date:'2026-10-06',fields:['规划IT容量'],scope:'一期包含在园区总量内，供电不计入IT'}],
   reading_deliveries:[{title:'已完成日报 <img src=x>',claims:['已提取的合同信息'],quotes:[{quote:'Original source text',page_index:16}],coverage:{gap_pages:[2]}},
    {title:'正文候选报告',claims:['75MW power 与 60MW IT 分开记录'],quotes:[{quote:'60MW IT; 75MW power',page_index:0}],coverage:{scope:'pdf_native_text_only',visual_review_performed:false,text_layer_empty_pages:[3],skipped_image_pages:[1,3]}}],
   daily_events:{records:[event(missing,'需要补来源的园区'),event(ready,'已交付园区 <img src=x onerror=alert(1)>')],total:2},
   daily_delivery:{news_total:1,task_counts:{source:1,identity:2},records:[
    {event_id:ready,delivery_lane:'news',last_processed_at:'2026-10-06T08:00:00Z',tasks:[{owner:'Spark 发布器',next_action:'动态已交付，容量等待研究核验'}]},
    {event_id:missing,delivery_lane:'source',tasks:[{owner:'inews / M5 补源',next_action:'查 sources.json'}]}]}}}));
  await page.locator('#refresh').click();await page.waitForFunction(()=>document.querySelector('.progress-overview')?.textContent.includes('127'));await page.locator('#delivery-lane').waitFor({state:'attached'});
  await page.getByRole('heading',{name:'已交付什么',exact:true}).waitFor();
  assert.match(await page.locator('.progress-columns').innerText(),/正式项目已更新 · 1 个/);
  assert.match(await page.locator('.progress-columns').innerText(),/最近 6 条/);
  assert.equal(await page.getByRole('link',{name:'正式采用园区',exact:true}).getAttribute('href'),'/project.html?site=fi-reviewed');
  assert.equal(await page.getByRole('link',{name:/已交付园区/}).first().getAttribute('href'),'/supply.html?event='+ready+'#matching');
  assert.match(await page.locator('.progress-overview').innerText(),/127/);
  assert.match(await page.locator('.progress-overview').innerText(),/16:00/);
  assert.equal(await page.locator('.progress-overview img,.progress-results img').count(),0);
  await page.locator('.progress-results summary').first().click();
  assert.match(await page.locator('.progress-results').innerText(),/已提取的合同信息/);
  assert.match(await page.locator('.progress-results').innerText(),/原件第 17 页/);
  assert.match(await page.locator('.progress-results').innerText(),/未读页：2/);
  await page.locator('.progress-results summary').nth(1).click();
  assert.match(await page.locator('.progress-results').innerText(),/原件第 1 页/);
  assert.doesNotMatch(await page.locator('.progress-results').innerText(),/原件第 0 页/);
  assert.match(await page.locator('.progress-results').innerText(),/正文阅读 · 图片未读/);
  assert.match(await page.locator('.progress-results').innerText(),/第 3 页没有文字层/);
  assert.match(await page.locator('.progress-overview').innerText(),/默认读正文、跳过图片 OCR/);
  for(const width of [390,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  if(process.env.UI_QA_DIR){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:process.env.UI_QA_DIR+'/supply-progress.png',fullPage:true});}
  await page.locator('#matching-demands > summary').click();
  await page.locator('#matching-events > summary').click();
  await page.getByRole('heading',{name:'本批材料阅读',exact:true}).waitFor();
  assert.match(await page.locator('[aria-label="本批材料阅读"]').innerText(),/131 \/ 133/);
  assert.equal(await page.locator('[aria-label="本批材料阅读"] img').count(),0,'executor text is escaped');
  await page.locator('#delivery-lane').selectOption('news');
  assert.match(await page.locator('#daily-shown').innerText(),/显示 1 \/ 1/);
  assert.match(await page.locator('#daily-events').innerText(),/已交付园区/);
  assert.equal(await page.locator('#daily-events img').count(),0,'external title remains plain text');
  await page.locator('#daily-events details').first().evaluate(e=>e.open=true);
  assert.match(await page.locator('#daily-events').innerText(),/Spark 发布器/);
  assert.ok((await page.locator('#daily-events a[href*="view=pipeline"]').count())>0);
  await page.locator('#delivery-lane').selectOption('source');
  assert.match(await page.locator('#daily-events').innerText(),/需要补来源/);
  assert.doesNotMatch(await page.locator('#daily-events').innerText(),/已交付园区/);
  await page.unroute('**/api/supply');await page.locator('#refresh').click();await page.waitForFunction(()=>!document.querySelector('.progress-results')?.textContent.includes('已完成日报'));
  await page.locator('#matching-demands > summary').click();
  await page.locator('#matching-events > summary').click();
  await page.locator('#match-search').fill('transformer');
  assert.match(await page.locator('#match-demands').innerText(),/P\.transformer/);
  await page.locator('#daily-search').fill('Huntingwood');
  assert.match(page.url(),/#matching$/);
  await page.setViewportSize({width:390,height:950});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'matching view fits narrow screen');
  await page.setViewportSize({width:1280,height:950});
  await page.getByRole('button',{name:'作战总览',exact:true}).click();
  await page.getByRole('heading',{name:'目的与当前进展',exact:true}).waitFor();
  assert.match(page.url(),/#overview$/);
  assert.match(await page.locator('#counts').innerText(),/7 个供应入口/);
  await page.getByRole('button',{name:'广度与深度',exact:true}).click();
  assert.match(page.url(),/#coverage$/);assert.match(await page.locator('#list').innerText(),/第 0 批：验证闭环/);
  await page.goto(base+'/supply.html#resources');await page.getByRole('heading',{name:'资源分工',exact:true}).waitFor();
  assert.match(await page.locator('#list').innerText(),/Spark/);
  await page.getByRole('button',{name:'供应方与任务',exact:true}).click();
  await page.getByRole('button',{name:/fetchspec/}).waitFor();
  for(const team of ['fetchstat','fetchfilings','fetchreports','fetchquotes','inews.today'])await page.getByRole('button',{name:new RegExp(team)}).waitFor();
  await page.getByRole('button',{name:'研究需求',exact:true}).click();
  await page.locator('#create-panel').waitFor();
  assert.ok(await page.locator('#question option').count()>1);
  await page.locator('#execution-mode').selectOption('assisted');
  assert.equal(await page.locator('#execution-mode').inputValue(),'assisted');
  await page.getByRole('button',{name:'交付与验收',exact:true}).click();
  assert.match(await page.locator('#list').innerText(),/等待第一份交付包/);
  await page.getByRole('heading',{name:'跨产品资料检索',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'检索已接收资料',exact:true}).count());
  for(const width of [390,1280]){
   await page.setViewportSize({width,height:950});
   for(const theme of ['light','dark']){
    await page.locator('#ui-appearance').selectOption(theme);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   }
  }
  // 演示页 supply-demo.html 已退役（2026-09-28）
  const demo=await page.request.get(base+'/supply-demo.html',{maxRedirects:0});assert.notEqual(demo.status(),200,'demo page retired');
  await page.setViewportSize({width:390,height:950});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.unroute('**/api/supply');
  const periodEvent=(id,title,day)=>({...event(id,title),document_refs:[{report_date:day}],sources:[{urls:['https://example.org/original']}],structured_evidence_status:'quotes_verified',editorial_event:{gaps:['容量未披露']}});
  await page.route('**/api/supply',route=>route.fulfill({json:{...original,
    daily_events:{records:[periodEvent(ready,'两个园区 <img src=x>','2026-10-07'),periodEvent(missing,'旧日报事件','2026-10-06')],total:2},
    project_updates:['fi-one','fi-two'].map(site_id=>({site_id,name:site_id,event_id:ready,verified_date:'2026-10-07',fields:['园区身份'],scope:'容量未披露'})),
    ecosystem_updates:[{contract_id:'power-one',event_id:ready,name:'已采用供电协议',parties:['constellation-energy'],scope:'发电计划，不计IT'}],
    daily_delivery:{records:[],news_total:0,task_counts:{}}}}));
  await page.goto(base+'/supply.html?day=2026-10-07#matching');
  const edition=page.locator('[aria-label="本期日报交付"]');
  await edition.waitFor();
  assert.match(await edition.innerText(),/1 条事件已用于 2 个正式园区记录/);
  assert.equal(await edition.locator('a[href*="project.html"]').count(),2);
  assert.equal(await edition.locator('img').count(),0);
  assert.equal(await edition.locator('a[href*="product-catalog.html"]').count(),1);
  await page.locator('#matching-events > summary').click();
  assert.match(await page.locator('#daily-shown').innerText(),/显示 1 \/ 1/);
  assert.doesNotMatch(await page.locator('#daily-events').innerText(),/旧日报事件/);
  await page.locator('#daily-edition-date').selectOption('2026-10-06');
  assert.match(page.url(),/day=2026-10-06/);
  assert.match(await edition.innerText(),/旧日报事件/);
  assert.match(await edition.innerText(),/0 条事件已用于 0 个正式园区记录/);
  assert.deepEqual(errors,[]);
  if(process.env.UI_QA_DIR){await page.goto(base+'/supply.html');await page.getByRole('button',{name:/fetchspec/}).waitFor();await page.setViewportSize({width:1280,height:1000});await page.screenshot({path:process.env.UI_QA_DIR+'/supply.png',fullPage:true});}
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
