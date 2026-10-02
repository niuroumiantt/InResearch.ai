const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {mkdirSync}=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE?{executablePath:process.env.UI_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base=process.env.UI_BASE_URL;
  await page.route('**/api/news',r=>r.fulfill({json:{reader:{status:'idle',stale:false},feed:{status:'success',exported_at:new Date().toISOString(),items:[
   {title_zh:'微软项目精选',url:'https://example.com/ms',published_at:Date.now(),editorial_pick:true,object_ids:['actor:microsoft']},
   {title_zh:'Meta 扩建精选',url:'https://example.com/meta',published_at:Date.now(),editorial_pick:true,object_ids:['actor:meta']},
   {title_zh:'未精选的线索',url:'https://example.com/other',published_at:Date.now(),editorial_pick:false},
   {title_zh:'危险链接',url:'javascript:alert(1)',editorial_pick:true}
  ]},pipeline:{available:true,records:[{id:'lead-one',title:'微软项目长期线索',state:'lead',company_ids:['microsoft'],site_id:'us-va-boydton',reported_stage:'reported',match_method:'name_and_actor',first_seen:'2026-09-01',events:[{title_zh:'原始报道',url:'https://example.com/ms'}]}]}}}));
  await page.goto(base+'/');await page.locator('#company-chips button[data-company="microsoft"]').waitFor();
  await page.getByRole('heading',{name:'全球数据中心',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(250, 249, 246)');
  await page.getByRole('link',{name:'微软项目精选',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'未精选的线索',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'危险链接',exact:true}).count(),0);
  await page.waitForFunction(()=>document.querySelectorAll('#world-map .site-point').length>20);
  assert.ok((await page.locator('#market-band').textContent()).includes('预测'));
  assert.ok((await page.locator('.leader').filter({hasText:'亚马逊'}).innerText()).includes('容量未披露'));
  assert.equal(await page.locator('table').count(),0,'homepage has no detailed tables');
  assert.equal(await page.locator('#pipeline-section').isVisible(),false);
  assert.ok((await page.locator('#market-band').innerText()).includes('约 95'));
  assert.ok((await page.locator('#market-band').innerText()).includes('2025 估算'));
  await page.locator('#world-map .news-ring').first().waitFor();
  await page.locator('#pipeline-summary').getByRole('link',{name:'全部动态 →'}).click();
  await page.locator('#pipeline-rows summary').first().waitFor();
  assert.equal(await page.locator('#project-list').isVisible(),false);
  await page.goto(base+'/');await page.locator('#company-chips button[data-company="microsoft"]').waitFor();
  const before=await page.locator('#stats').innerText();
  await page.locator('#company-chips button[data-company="microsoft"]').click();
  await page.waitForFunction(()=>document.querySelector('#map-title').textContent.includes('微软'));
  await page.getByRole('link',{name:'微软项目精选',exact:true}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('.dc-news').textContent.includes('Meta 扩建精选'));
  assert.notEqual(await page.locator('#stats').innerText(),before);
  assert.equal(new URL(page.url()).searchParams.get('c'),'microsoft');
  const api=await (await page.request.get(base+'/api/industry?c=microsoft&stage=construction')).json();
  await page.locator('#stats a').nth(1).click();
  await page.waitForFunction(()=>document.querySelector('#list-title')?.textContent.startsWith('建设中'));
  assert.equal(await page.locator('#project-rows tbody tr').count(),api.rows.length);
  const projectLink=page.locator('#project-rows tbody tr td:first-child a').first();
  await projectLink.click();await page.locator('#detail h2').first().waitFor();
  assert.ok(await page.getByRole('heading',{name:'来源与核验'}).isVisible());
  assert.ok(await page.getByRole('heading',{name:'进展时间线'}).isVisible());
  await page.getByRole('link',{name:'← 返回同条件项目列表'}).click();
  assert.equal(new URL(page.url()).searchParams.get('stage'),'construction');
  await page.goto(base+'/industry.html?c=meta');await page.getByRole('heading',{name:'Meta · 全球布局',exact:true,level:1}).waitFor();
  await page.getByRole('link',{name:'Meta 扩建精选',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'微软项目精选',exact:true}).count(),0);
  await page.goto(base+'/market.html');await page.locator('#market-detail table').waitFor();assert.ok((await page.locator('#capacity').textContent()).includes('不是截至今天已投运'));
  assert.ok((await page.locator('#market-detail').textContent()).includes('内部原件未在本站公开'));
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#world-map .site-point').first().focus();await page.keyboard.press('Enter');
  await page.getByRole('link',{name:'查看项目与来源 →'}).waitFor();
  await page.locator('#news-selection').selectOption('all');await page.getByRole('link',{name:'未精选的线索',exact:true}).waitFor();
  await page.locator('#news-selection').selectOption('selected');
  if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:process.env.UI_QA_DIR+'/industry-desktop.png',fullPage:true});}
  for(const mode of ['dark','light']){
   await page.locator('#ui-appearance').selectOption(mode);
   assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),mode==='dark'?'rgb(27, 28, 25)':'rgb(250, 249, 246)');
   for(const width of [390,768,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),mode+' '+width);}
  }
  await page.setViewportSize({width:390,height:844});
  if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+'/industry-mobile.png',fullPage:true});
  await page.goto(base+'/project.html?site=missing');await page.getByText('未找到对应的项目或主体。',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS industry: company/map/news filters, capacity drilldown, project sources, market forecast, keyboard, mobile and dark mode');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
