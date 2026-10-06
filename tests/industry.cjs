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
  await page.goto(base+'/');await page.locator('#company-chips [data-company="microsoft"]').waitFor();
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
  assert.equal(await page.locator('#pipeline-summary, #trends-section').count(),0);
  assert.equal(await page.locator('[data-news-count]').innerText(),'本次快照 · 当前筛选精选 2 条');
  await page.getByRole('link',{name:'查看全部项目新闻线索 →'}).click();
  await page.locator('#pipeline-rows summary').first().waitFor();
  assert.equal(await page.locator('#project-list').isVisible(),false);
  await page.goto(base+'/');await page.locator('#company-chips [data-company="microsoft"]').waitFor();
  const before=await page.locator('#stats').innerText(),homeURL=page.url(),pointCount=await page.locator('.site-point').count();
  const baseline=await (await page.request.get(base+'/api/industry')).json();
  for(const selector of ['#company-chips [data-company="microsoft"]','#leaders [data-company="meta"]']){
   const id=await page.locator(selector).getAttribute('data-company');
   await page.locator(selector).click();
   assert.equal(page.url(),homeURL);assert.equal(await page.locator('#stats').innerText(),before);
   assert.equal(await page.locator('.site-point').count(),pointCount);
   const expected=baseline.rows.filter(p=>!p.portfolio&&p.coordinates&&[...p.developer,...p.tenant].includes(id)).map(p=>p.site_id).sort();
   assert.deepEqual(await page.locator('.site-point.highlighted').evaluateAll(es=>es.map(e=>e.dataset.id).sort()),expected);
   assert.equal(await page.locator('[data-news-count]').innerText(),'本次快照 · 当前筛选精选 2 条');
  }
  await page.locator('#company-chips [data-company=""]').click();assert.equal(await page.locator('.site-point.dimmed').count(),0);
  await page.locator('#filters select[name=c]').selectOption('microsoft');
  await page.waitForFunction(()=>window.industryFilter?.company==='microsoft');
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
  await page.goto(base+'/market.html');await page.locator('#market-detail table').waitFor();assert.ok((await page.locator('#capacity').textContent()).includes('不是截至今天已投运'));assert.ok((await page.locator('#capacity').textContent()).includes('不能用 95 GW'));assert.ok((await page.locator('#capacity').textContent()).includes('Frontier'));
  assert.ok((await page.locator('#market-detail').textContent()).includes('内部原件未在本站公开'));
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#world-map .site-point').first().press('Enter');
  await page.locator('#map-popup').waitFor();
  assert.equal(new URL(page.url()).pathname,'/');
  const chosen=await page.locator('#map-popup strong').innerText();
  await page.locator('#pin-site').click();
  await page.locator('#world-map .site-point').nth(1).press('Enter');
  assert.equal(await page.locator('#map-popup strong').innerText(),chosen,'pin preserves selected project');
  await page.locator('#zoom-in').click();
  assert.equal(await page.locator('#map-popup').isVisible(),true,'pin survives outside interaction');
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('inresearch:news-data',{detail:{pipeline:{records:[]}}})));
  assert.equal(await page.locator('#pin-site').getAttribute('aria-pressed'),'true','pin survives news redraw');
  await page.locator('#pin-site').click();
  await page.locator('#world-map .site-point').nth(1).press('Enter');
  assert.notEqual(await page.locator('#map-popup strong').innerText(),chosen);
  await page.locator('#map-popup a').click();
  await page.getByRole('heading',{name:'来源与核验'}).waitFor();
  assert.equal(new URL(page.url()).pathname,'/project.html');
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#news-selection').selectOption('all');await page.getByRole('link',{name:'未精选的线索',exact:true}).waitFor();
  assert.equal(await page.locator('[data-news-count]').innerText(),'本次快照 · 当前筛选线索 3 条');
  await page.locator('#news-selection').selectOption('selected');
  await page.waitForFunction(()=>document.querySelector('[data-news-count]').textContent.includes('精选 2 条'));
  for(const mode of ['dark','light']){
   await page.locator('#ui-appearance').selectOption(mode);
   assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),mode==='dark'?'rgb(27, 28, 25)':'rgb(250, 249, 246)');
   for(const width of [390,768,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),mode+' '+width);}
  }
  await page.setViewportSize({width:390,height:844});

  // A curated project link must survive an older publisher's association counter.
  await page.unroute('**/api/news');
  await page.route('**/api/news',r=>r.fulfill({json:{pipeline:{available:true,progress:{leads:100,events:100,linked:0,constraints:{}},records:[{
   id:'daily-adopted',title:'已核验的日报项目',origin:'daily_html',report_date:'2026-10-06',state:'linked',
   site_id:'fi-salo-atnorth-fin05',company_ids:['atnorth'],reported_stage:'announced',
   events:[{title:'原文供电口径',url:'https://www.atnorth.com/',reported_capacity:'75 MW'}]
  }]}}}));
  await page.goto(base+'/projects.html?view=pipeline');
  const linked=page.locator('.pipeline-item').filter({hasText:'已核验的日报项目'});
  await linked.locator('summary').click();
  assert.ok((await linked.locator('summary').innerText()).includes('已关联项目'));
  assert.ok((await linked.innerText()).includes('采用口径见项目明细'));
  assert.ok(!(await linked.innerText()).includes('未计入'));
  assert.equal(await linked.locator('a[href*="fi-salo-atnorth-fin05"]').count(),1);
  assert.ok((await page.locator('#pipeline-rows').innerText()).includes('当前筛选 1 条关联项目'));

  // Rendering counts describe only safe, displayed rows in the current API snapshot.
  for(const payload of [{reader:{status:'not_connected'},feed:null},
    {feed:{status:'success',exported_at:new Date().toISOString(),items:[]}}]){
   await page.unroute('**/api/news');
   await page.route('**/api/news',r=>r.fulfill({json:payload}));
   await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
   await page.waitForFunction(()=>document.querySelector('.dc-news-meta').textContent || document.querySelector('.dc-news-list').textContent);
   assert.ok((await page.locator('[data-news-count]').innerText()).includes('—'));
  }
  await page.unroute('**/api/news');
  await page.route('**/api/news',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.goto(base+'/');await page.getByText('新闻暂时无法同步，请稍后重试。',{exact:true}).waitFor();
  assert.ok((await page.locator('[data-news-count]').innerText()).includes('—'));
  await page.goto(base+'/project.html?site=fi-salo-atnorth-fin05');
  await page.getByRole('button',{name:'重试新闻同步',exact:true}).waitFor();
  assert.ok((await page.locator('#detail').innerText()).includes('160 MW'));
  await page.unroute('**/api/news');
  await page.route('**/api/news',r=>r.fulfill({json:{pipeline:{available:true,records:[{
    id:'recovered-fin05',title:'FIN05 restored news',state:'linked',site_id:'fi-salo-atnorth-fin05',company_ids:['atnorth'],events:[]
  }]}}}));
  await page.getByRole('button',{name:'重试新闻同步',exact:true}).click();
  await page.getByText('FIN05 restored news',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'重试新闻同步',exact:true}).count(),0);
  assert.ok((await page.locator('#detail').innerText()).includes('160 MW'));
  await page.unroute('**/api/news'); // screenshots below use real local endpoints only
  if(process.env.UI_QA_DIR)mkdirSync(process.env.UI_QA_DIR,{recursive:true});
  const measurements=[];
  for(const [width,height] of [[1366,768],[1440,900],[1920,1080],[390,844],[320,740]]){
   await page.setViewportSize({width,height});await page.goto(base+'/');
   await page.locator('#world-map .site-point').first().waitFor();
   await page.evaluate(()=>document.fonts.ready);
   const layout=await page.evaluate(()=>{
    const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};
    const map=rect('#world-map'),matrix=document.querySelector('#world-map').getScreenCTM();
    const screen=(x,y)=>{const p=new DOMPoint(x,y).matrixTransform(matrix);return {x:p.x,y:p.y};};
    return {map,world:[screen(0,0),screen(1000,490)],market:rect('#market-band'),atlas:rect('.atlas-panel'),news:rect('.news-panel'),
     controls:['#filters','#stats','#basis','#coverage','#map-summary','#company-chips','#news-selection'].map(rect),
     overflow:document.documentElement.scrollWidth-innerWidth,scroll:scrollY,viewBox:document.querySelector('#world-map').getAttribute('viewBox'),
     numberSize:parseFloat(getComputedStyle(document.querySelector('.macro-card strong')).fontSize),
     metaSize:parseFloat(getComputedStyle(document.querySelector('.macro-card small')).fontSize)};
   });
   measurements.push({width,height,...layout});
   assert.equal(layout.scroll,0);assert.ok(layout.overflow<=1,`overflow at ${width}`);
   assert.equal(layout.viewBox,'0 0 1000 490');
   assert.ok(Math.abs(layout.map.width/layout.map.height-1000/490)<.01,'full aspect ratio');
   assert.ok(layout.world[0].y>=layout.map.top-1 && layout.world[1].y<=layout.map.bottom+1,'no SVG clipping');
   assert.ok(layout.controls.every(r=>r.top>=layout.map.bottom),'all filters and sample labels below map');
   assert.ok(layout.metaSize>=13);
   if(width>1000){
    assert.ok(layout.market.top>0 && layout.market.bottom<layout.map.top);
    assert.ok(layout.map.bottom<=height && layout.map.top>=0,`entire map visible at ${width}×${height}`);
    assert.ok(layout.map.width>=850 && layout.numberSize>=40,'retain large readable graphics');
    assert.ok(layout.news.left>=layout.map.right && layout.news.top<layout.map.top,'news on the right');
   }else{
    assert.ok(layout.news.top>=layout.atlas.bottom,'mobile news follows map');
   }
   await page.locator('#world-map .site-point').first().press('Enter');
   assert.equal(new URL(page.url()).pathname,'/');
   const popupBox=await page.locator('#map-popup').boundingBox(),frameBox=await page.locator('.map-frame').boundingBox();
   assert.ok(popupBox.x>=frameBox.x && popupBox.x+popupBox.width<=frameBox.x+frameBox.width+1);
   assert.ok(popupBox.y>=frameBox.y && popupBox.y+popupBox.height<=frameBox.y+frameBox.height+1);
   await page.locator('#pin-site').click();await page.locator('#close-site').click();
   assert.equal(await page.locator('#map-popup').isVisible(),false);
   await page.locator('#world-map .site-point').first().press('Enter');await page.keyboard.press('Escape');
   assert.equal(await page.locator('#map-popup').isVisible(),false);
   await page.evaluate(()=>scrollTo(0,0));
   if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+`/homepage-${width}x${height}.png`,fullPage:width<1000});
  }
  if(process.env.UI_QA_DIR)require('node:fs').writeFileSync(process.env.UI_QA_DIR+'/layout.json',JSON.stringify(measurements,null,2));
  await page.setViewportSize({width:1366,height:768});await page.goto(base+'/index.html');
  await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#zoom-in').click();assert.notEqual(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');
  await page.locator('#zoom-reset').click();assert.equal(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');
  const mapBox=await page.locator('#world-map').boundingBox();
  await page.mouse.move(mapBox.x+mapBox.width*.4,mapBox.y+mapBox.height*.8);await page.mouse.down();await page.mouse.move(mapBox.x+mapBox.width*.4+60,mapBox.y+mapBox.height*.8+20);await page.mouse.up();
  assert.notEqual(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');await page.locator('#zoom-reset').click();
  const region=await page.locator('#filters select[name=region] option').nth(1).getAttribute('value');
  await page.locator('#filters select[name=region]').selectOption(region);
  await page.waitForFunction(region=>window.industryFilter?.region===region,region);
  const filtered=await (await page.request.get(base+'/api/industry?region='+region)).json();
  assert.ok((await page.locator('#basis').innerText()).includes(`地图样本 ${filtered.totals.sites} 条项目记录`));
  for(const [key,value] of [['scope','ai'],['role','operator'],['relation','tenant'],['c','microsoft']]){
   await page.locator(`#filters select[name=${key}]`).selectOption(value);
   await page.waitForFunction(([key,value])=>document.querySelector('#filters').elements[key].value===value && !document.querySelector('#load-status').textContent,[key,value]);
   const query=new URL(page.url()).search;
   const result=await (await page.request.get(base+'/api/industry'+query)).json();
   assert.ok((await page.locator('#basis').innerText()).includes(`地图样本 ${result.totals.sites} 条项目记录`),key+' matches API');
   await page.locator(`#filters select[name=${key}]`).selectOption('');
   await page.waitForFunction(key=>document.querySelector('#filters').elements[key].value==='' && !document.querySelector('#load-status').textContent,key);
  }
  await page.locator('#market-band a').first().click();await page.locator('#capacity').waitFor();
  await page.goBack();await page.waitForFunction(region=>window.industryFilter?.region===region,region);
  await page.goto(base+'/project.html?site=missing');await page.getByText('未找到对应的项目或主体。',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS industry: viewport matrix, real-endpoint screenshots, scoped news counts, company/map/news filters, drilldowns, sources, history, zoom/pan, keyboard, mobile and dark mode');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
