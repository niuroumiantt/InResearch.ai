const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {mkdirSync}=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE?{executablePath:process.env.UI_BROWSER_EXECUTABLE}:{})});
 try{
  const base=process.env.UI_BASE_URL;if(process.env.UI_QA_DIR)mkdirSync(process.env.UI_QA_DIR,{recursive:true});
  // Font checks use actual HTTP cache bytes; only the stylesheet-delay case holds a request.
  const fontErrors=[],readerEntries=[
   {label:'home',url:'/',ready:'#world-map .site-point'},
   {label:'index',url:'/index.html',ready:'#world-map .site-point'},
   {label:'project',url:'/project.html?site=us-tx-abilene',ready:'#site-observation-timeline'},
   {label:'projects',url:'/projects.html',ready:'#project-rows tbody tr'},
   {label:'company',url:'/industry.html?c=meta',ready:'#world-map .site-point'},
   {label:'market',url:'/market.html',ready:'#market-detail table'}
  ];
  const newFontContext=async()=>{
   const context=await browser.newContext({viewport:{width:1440,height:900}});
   context.on('page',p=>p.on('pageerror',e=>fontErrors.push(e.message)));return context;
  };
  const readEntry=async(page,entry)=>{
   await page.goto(base+entry.url,{waitUntil:'domcontentloaded',timeout:10000});
   await page.locator(entry.ready).first().waitFor({timeout:10000});
   if(['home','index'].includes(entry.label))await page.locator('#update-track > .update-items:first-child .update-item').first().waitFor({timeout:10000});
   if(entry.label==='project')assert.match(await page.locator('#capacity-estimate').innerText(),/运营约 421 MW IT[\s\S]*建设中未披露[\s\S]*2026-07-28/);
   assert.equal(await page.locator('#home-fonts').getAttribute('media'),'not all',entry.label+' keeps full font CSS inactive');
   assert.equal(await page.locator('#ui-skinbar').count(),1,entry.label+' navigation mounted');
  };
  const nativeReaderScreenshots=async(page,entry,state)=>{
   for(const [width,height] of [[1440,900],[390,844]]){
    await page.setViewportSize({width,height});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${entry.label} ${state} ${width} has no page overflow`);
    await page.screenshot({...(process.env.UI_QA_DIR?{path:process.env.UI_QA_DIR+`/reader-fonts-${entry.label}-${state}-${width}.png`}:{}),timeout:10000});
   }
  };
  const fontContext=await newFontContext();
  try{
   for(const entry of readerEntries){
    // Every alias starts with a separate empty real browser cache.
    const context=entry.label==='home'?fontContext:await newFontContext();
    try{
     const cold=await context.newPage(),coldFontResponses=[];
     cold.on('response',r=>{if(/\.woff2(?:\?|$)/.test(r.url()))coldFontResponses.push(r.url());});
     await cold.addInitScript(()=>{
      const original=window.fetch.bind(window);window.readerFetches=[];
      window.fetch=(url,options)=>{window.readerFetches.push({url:String(url),cache:options?.cache,mode:options?.mode,at:performance.now()});return original(url,options);};
     });
     await readEntry(cold,entry);
     await cold.waitForFunction(()=>document.getElementById('home-fonts').dataset.fonts==='fallback');
     assert.deepEqual(coldFontResponses,[],entry.label+' cold font cache produces no font response or network payload');
     assert.equal(await cold.evaluate(()=>[...document.fonts].filter(f=>f.status==='loaded').length),0,entry.label+' cold cache uses system fallback');
     const order=await cold.evaluate(()=>window.readerFetches),fontAttempts=order.filter(r=>r.url.includes('.woff2'));
     assert.ok(fontAttempts.length>0,entry.label+' attempted font cache reuse');
     const publicStarts=['/assets/world.geo.json','/api/industry?','/api/news'].map(prefix=>order.find(r=>r.url.startsWith(prefix))?.at);
     assert.ok(publicStarts.every(Number.isFinite),entry.label+' starts public content requests');
     assert.ok(fontAttempts.every(r=>r.cache==='only-if-cached'&&r.mode==='same-origin'&&r.at>=Math.max(...publicStarts)),entry.label+' cache-only font work follows public requests');
     assert.ok(await cold.evaluate(()=>performance.getEntriesByType('resource').filter(r=>r.name.includes('.woff2')).every(r=>r.transferSize===0)),entry.label+' cold font transfers stay zero');
     await nativeReaderScreenshots(cold,entry,'cold');
     if(entry.label==='home'){
      for(const [width,height] of [[1366,768],[1440,900],[390,844],[320,740]]){
       await cold.setViewportSize({width,height});
       for(const mode of ['light','dark']){
        await cold.locator('#ui-appearance').selectOption(mode);
        assert.ok(await cold.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'system-font layout '+width+' '+mode);
        if(width>1000)assert.ok(await cold.locator('#world-map').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight),'cold atlas stays completely above fold '+width);
        if(process.env.UI_QA_DIR)await cold.screenshot({path:process.env.UI_QA_DIR+`/homepage-cold-fonts-${width}-${mode}.png`,fullPage:width<1000,timeout:10000});
       }
      }
      // Prime actual original Inter bytes in this one browser cache for the warm matrix.
      await cold.evaluate(async()=>{const r=await fetch('/assets/fonts/inter-variable.woff2',{cache:'force-cache'});if(!r.ok)throw Error('Font cache priming failed');await r.arrayBuffer();});
     }
    }finally{if(context!==fontContext)await context.close();}
   }
   for(const entry of readerEntries){
    const warm=await fontContext.newPage();await readEntry(warm,entry);
    await warm.waitForFunction(()=>document.getElementById('home-fonts').dataset.fonts==='cached');
    assert.ok(await warm.evaluate(()=>[...document.fonts].some(f=>f.family==='Inter'&&f.status==='loaded')),entry.label+' reuses an original binary Inter FontFace');
    const inter=await warm.evaluate(()=>performance.getEntriesByType('resource').find(r=>r.name.endsWith('/inter-variable.woff2'))?.toJSON());
    assert.ok(inter&&inter.encodedBodySize>300000&&inter.transferSize===0,entry.label+' reads real cached Inter bytes with zero network transfer');
    await nativeReaderScreenshots(warm,entry,'cached');await warm.close();
   }
  }finally{await fontContext.close();}
  for(const entry of readerEntries){
   const context=await newFontContext(),slow=await context.newPage();let releaseStyle;
   const heldStyle=new Promise(resolve=>{releaseStyle=resolve;});
   await slow.route('**/assets/fonts/fonts.css',async route=>{await heldStyle;await route.continue();});
   try{
    await readEntry(slow,entry);
    assert.equal(await slow.evaluate(()=>document.getElementById('home-fonts').sheet),null,entry.label+' descriptor CSS is still held');
    assert.ok(await slow.evaluate(()=>performance.getEntriesByType('resource').filter(r=>r.name.includes('.woff2')).every(r=>r.transferSize===0)),entry.label+' held font CSS produces no font transfers');
    await nativeReaderScreenshots(slow,entry,'held-css');
   }finally{releaseStyle();await context.close();}
  }
  assert.deepEqual(fontErrors,[]);
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let overviewRequests=0;page.on('request',r=>{if(r.url().includes('/api/industry?')&&new URL(r.url()).searchParams.get('overview')==='1')overviewRequests++;});
  await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:{reader:{status:'idle',stale:false},feed:{status:'success',exported_at:new Date().toISOString(),items:[
   {title_zh:'微软项目精选',url:'https://example.com/ms',published_at:Date.now(),editorial_pick:true,object_ids:['actor:microsoft']},
   {title_zh:'Meta 扩建精选',url:'https://example.com/meta',published_at:Date.now(),editorial_pick:true,object_ids:['actor:meta']},
   {title_zh:'未精选的线索',url:'https://example.com/other',published_at:Date.now(),editorial_pick:false},
   {title_zh:'危险链接',url:'javascript:alert(1)',editorial_pick:true}
  ]},pipeline:{available:true,records:[{id:'lead-one',title:'微软项目长期线索',state:'lead',company_ids:['microsoft'],site_id:'us-va-boydton',reported_stage:'reported',match_method:'name_and_actor',first_seen:'2026-09-01',events:[{title_zh:'原始报道',url:'https://example.com/ms'}]}]}}}));
  await page.goto(base+'/');await page.locator('#company-chips [data-company="microsoft"]').waitFor();
  await page.getByRole('heading',{name:'全球数据中心',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(250, 249, 246)');
  await page.getByRole('link',{name:'微软项目精选',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'未精选的线索',exact:true}).count(),1,'homepage defaults to all daily news');
  for(const id of ['amazon','microsoft','alphabet-google','meta','oracle','bytedance','alibaba'])assert.equal(await page.locator('#company-chips [data-company="'+id+'"]').count(),1,'explicit company shortcut '+id);
  assert.equal(await page.locator('#home-updates').count(),1);assert.ok(overviewRequests>0,'homepage uses bounded industry projection');
  const publicObservations=await (await page.request.get(base+'/api/observations?limit=100')).json();
  const publicHome=await (await page.request.get(base+'/api/industry?overview=1')).json();
  assert.equal(publicObservations.audience,'public');
  assert.equal(publicObservations.total,publicHome.research_updates.total);
  const publishedById=new Map(publicObservations.records.map(row=>[row.id,row]));
  let nextOffset=publicObservations.next_offset;
  const visitedOffsets=new Set([0]);
  while(nextOffset!==null&&publicHome.research_updates.changes.some(row=>!publishedById.has(row.id))){
   assert.ok(!visitedOffsets.has(nextOffset),'public pagination must advance');visitedOffsets.add(nextOffset);
   const response=await page.request.get(base+'/api/observations?limit=100&offset='+nextOffset);
   assert.equal(response.status(),200);
   const nextPage=await response.json();assert.equal(nextPage.total,publicObservations.total);
   for(const row of nextPage.records){assert.ok(!publishedById.has(row.id),'public pages do not duplicate observations');publishedById.set(row.id,row);}
   nextOffset=nextPage.next_offset;
  }
  for(const row of publicHome.research_updates.changes){
   assert.deepEqual(publishedById.get(row.id),row,'homepage and API use identical publication fields across pages');
   assert.deepEqual(Object.keys(row.source).sort(),['published_at','url']);
   for(const hidden of ['review','proposal_sha256','claim_sha256'])assert.equal(hidden in row,false);
  }
  if(publicObservations.total){
   assert.ok(await page.locator('#update-track > .update-items:first-child [data-update-kind="research"]').count()>0,'research information shares the compact update stream');
   const objectID=publicHome.research_updates.changes[0].object_id;
   const expanded=await (await page.request.get(base+'/api/observations?object='+encodeURIComponent(objectID)+'&limit=100')).json();
   assert.ok(expanded.records.length>0&&expanded.records.every(row=>row.object_id===objectID),'public object history remains available after compacting the homepage');
  }
  assert.equal(await page.getByRole('link',{name:'危险链接',exact:true}).count(),0);
  await page.waitForFunction(()=>document.querySelectorAll('#world-map .site-point').length>20);
  assert.ok((await page.locator('#market-band').textContent()).includes('预测'));
  assert.equal(await page.locator('#atlas-tools, #filters, #stats, #basis, #coverage, #map-summary, #news-selection, #research-updates, #daily-pulse, #research-arrivals, #leaders-section, main > footer').count(),0,'homepage removes detailed tools, cards and footer');
  assert.equal(await page.locator('table').count(),0,'homepage has no detailed tables');
  assert.equal(await page.locator('#pipeline-section').count(),0);
  assert.ok((await page.locator('#market-band').innerText()).includes('约 95'));
  assert.ok((await page.locator('#market-band').innerText()).includes('2025 估算'));
  await page.locator('#world-map .news-ring').first().waitFor();
  assert.equal(await page.locator('#pipeline-summary, #trends-section').count(),0);
  assert.equal(await page.locator('[data-news-count]').count(),0,'headline panel has no snapshot counters');
  assert.equal(await page.locator('.dc-news-list article').count(),3);
  assert.equal(await page.locator('.dc-news-list :is(time,small,button,.dc-news-day,.dc-news-capacity,.dc-news-state,.dc-news-mark)').count(),0,'homepage news contains titles only');
  await page.goto(base+'/projects.html?view=pipeline');
  await page.locator('#pipeline-rows summary').first().waitFor();
  assert.equal(await page.locator('#project-list').isVisible(),false);
  await page.goto(base+'/');await page.locator('#company-chips [data-company="microsoft"]').waitFor();await page.locator('#world-map .site-point').first().waitFor();await page.getByRole('link',{name:'微软项目精选',exact:true}).waitFor();
  const homeURL=page.url(),pointCount=await page.locator('.site-point').count();
  const baseline=await (await page.request.get(base+'/api/industry')).json();
  assert.ok(await page.getByRole('region',{name:'最新研究与项目动态',exact:true}).isVisible());
  assert.equal(await page.locator('.tracking-metrics, #tracking-overview, #daily-metrics, #refresh-tracking').count(),0);
  assert.doesNotMatch(await page.locator('main').innerText(),/今日接收|采用更新|站点复核待更新|查看核验进展|新闻接收|运行同步/);
  const realChanges=page.locator('#update-track > .update-items:first-child [data-update-kind="project"]');
  assert.ok(await realChanges.count()>0,'project updates share the same title stream');
  const shownProject=await realChanges.first().getAttribute('data-effective-at');
  assert.ok(baseline.tracking.changes.some(item=>item.effective_at===shownProject),'ticker preserves the source observation time');
  const currentObservation=baseline.tracking.changes.find(item=>item.effective_at==='2026-07-28');
  const forecastObservation=baseline.tracking.changes.find(item=>item.effective_at==='2026-11-01');
  assert.equal(currentObservation.kind,'estimated');assert.equal(currentObservation.fields.capacity_it_mw,421);
  assert.equal(forecastObservation.kind,'forecast');assert.equal(forecastObservation.fields.capacity_it_mw,843);
  assert.equal(await page.locator('#update-track .update-items[aria-hidden="true"] .update-item:not([tabindex="-1"])').count(),0,'duplicate animation content does not duplicate keyboard links');
  await page.locator('#update-toggle').click();
  assert.equal(await page.locator('#update-toggle').getAttribute('aria-pressed'),'true');
  assert.ok(await page.locator('#home-updates').evaluate(el=>el.classList.contains('paused')));
  await page.locator('#update-toggle').click();
  assert.equal(await page.locator('#update-toggle').getAttribute('aria-pressed'),'false');
  await page.locator('.hero h1').click();await page.locator('.hero h1').hover();
  await page.locator('#update-track').evaluate(el=>{const animation=el.getAnimations()[0];if(!animation)throw Error('Ticker animation is not active');animation.currentTime=animation.effect.getComputedTiming().duration*.6;});
  assert.ok(await page.evaluate(()=>document.querySelector('#update-track .update-item').getBoundingClientRect().right<document.querySelector('#update-viewport').getBoundingClientRect().left),'fixture reaches a title outside the visible marquee');
  await page.locator('#update-viewport').focus();
  assert.equal(await page.locator('#update-track').evaluate(el=>getComputedStyle(el).animationName),'none','keyboard focus restores a static title list');
  await page.keyboard.press('Tab');
  assert.ok(await page.evaluate(()=>{const link=document.activeElement,viewport=document.querySelector('#update-viewport').getBoundingClientRect(),box=link.getBoundingClientRect();return link.matches('#update-track > .update-items:first-child .update-item')&&box.left>=viewport.left-1&&box.right<=viewport.right+1;}),'real Tab reveals the headline after it has scrolled out of view');
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('#update-track').evaluate(el=>getComputedStyle(el).animationName),'none','reduced motion disables the ticker animation');
  await page.emulateMedia({reducedMotion:'no-preference'});
  for(const selector of ['#company-chips [data-company="microsoft"]','#company-chips [data-company="meta"]']){
   const id=await page.locator(selector).getAttribute('data-company');
   await page.locator(selector).click();
   assert.equal(page.url(),homeURL);assert.equal(await page.evaluate(()=>window.industryFilter?.company||''),'');
   assert.equal(await page.locator('.site-point').count(),pointCount);
   const expected=baseline.rows.filter(p=>!p.portfolio&&p.coordinates&&[...p.developer,...p.tenant].includes(id)).map(p=>p.site_id).sort();
   assert.deepEqual(await page.locator('.site-point.highlighted').evaluateAll(es=>es.map(e=>e.dataset.id).sort()),expected);
   assert.equal(await page.locator('.dc-news-list article').count(),3,'highlight keeps news conditions unchanged');
  }
  await page.locator('#company-chips [data-company=""]').click();assert.equal(await page.locator('.site-point.dimmed').count(),0);
  await page.goto(base+'/industry.html');await page.locator('#filters select[name=c] option[value="microsoft"]').waitFor({state:'attached'});
  await page.locator('#filters select[name=c]').selectOption('microsoft');
  await page.waitForFunction(()=>window.industryFilter?.company==='microsoft');
  const api=await (await page.request.get(base+'/api/industry?c=microsoft&stage=construction')).json();
  await page.locator('#stats a').nth(1).click();
  await page.waitForFunction(()=>document.querySelector('#list-title')?.textContent.startsWith('建设中'));
  assert.equal(await page.locator('#home-fonts').getAttribute('media'),'not all','project list shares the reader cache-only font rule');
  await page.waitForFunction(()=>['cached','fallback'].includes(document.getElementById('home-fonts').dataset.fonts));
  assert.ok(await page.evaluate(async()=>{await document.fonts.ready;return [...document.fonts].filter(f=>f.status==='loaded').every(f=>['Inter','Noto Sans SC'].includes(f.family));}),'project aliases reuse only available shared fonts');
  assert.equal(await page.locator('#project-rows tbody tr').count(),api.rows.length);
  assert.deepEqual(await page.locator('#project-rows thead th').allInnerTexts(),['国家','省／州','区域地址','园区','开发／建设','运营／使用','规划 IT 容量','已投运 IT 容量','信息时间','最后核实日期']);
  const projectLink=page.locator('#project-rows tbody tr td:nth-child(4) a').first();
  await projectLink.click();await page.locator('#detail h2').first().waitFor();
  assert.ok(await page.getByRole('heading',{name:'来源与核验'}).isVisible());
  assert.ok(await page.getByRole('heading',{name:'进展时间线'}).isVisible());
  await page.getByRole('link',{name:'← 返回同条件项目列表'}).click();
  assert.equal(new URL(page.url()).searchParams.get('stage'),'construction');
  await page.goto(base+'/projects.html?country=CN&province='+encodeURIComponent('河北'));
  await page.locator('#project-rows tbody tr').first().waitFor();
  assert.equal(await page.getByRole('combobox',{name:'国家',exact:true}).inputValue(),'CN');
  assert.equal(await page.locator('#project-rows tbody tr').count(),1);
  assert.deepEqual(await page.locator('#project-rows tbody tr td').evaluateAll(cells=>cells.slice(0,3).map(c=>c.textContent)),['中国','河北','张家口']);
  assert.doesNotMatch(await page.locator('#project-rows').innerText(),/省.*未登记|城市未登记|街区未登记|地址未登记|已登记规划分期；总量待核|来源地点描述/);
  await page.locator('#project-rows tbody tr td.num .table-note').first().click();
  assert.ok(await page.locator('#project-note').isVisible());
  assert.ok(await page.locator('#project-note .note-body a').count()>0,'collapsed note retains original source links');
  await page.keyboard.press('Escape');
  assert.ok(!await page.locator('#project-note').isVisible());
  await page.getByRole('combobox',{name:'国家',exact:true}).selectOption('IN');
  await page.waitForFunction(()=>window.industryFilter?.country==='IN'&&window.industryFilter?.province==='');
  await page.getByRole('combobox',{name:'省／州',exact:true}).selectOption('Telangana');
  await page.waitForFunction(()=>window.industryFilter?.province==='Telangana');
  assert.ok((await page.locator('#project-rows tbody tr td:first-child').allInnerTexts()).every(v=>v==='印度'));
  await page.getByRole('combobox',{name:'区域地址',exact:true}).selectOption('Hyderabad');
  await page.waitForFunction(()=>window.industryFilter?.address==='Hyderabad');
  assert.ok(await page.locator('#project-rows tbody tr').count()>0);
  assert.ok((await page.locator('#project-rows tbody tr td:nth-child(3)').allInnerTexts()).every(v=>v==='Hyderabad'));
  await page.goto(base+'/industry.html?c=meta');await page.getByRole('heading',{name:'Meta · 全球布局',exact:true,level:1}).waitFor();
  await page.getByRole('link',{name:'Meta 扩建精选',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'微软项目精选',exact:true}).count(),0);
  await page.goto(base+'/market.html');await page.locator('#market-detail table').waitFor();assert.ok((await page.locator('#capacity').textContent()).includes('不是截至今天已投运'));assert.ok((await page.locator('#capacity').textContent()).includes('不能用 95 GW'));assert.ok((await page.locator('#capacity').textContent()).includes('Frontier'));
  assert.ok((await page.locator('#market-detail').textContent()).includes('内部原件未在本站公开'));
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  assert.equal(await page.locator('#world-map .atlas-grid').count(),1);
  const marker=page.locator('#world-map .site-point').last();
  const markerBox=await marker.boundingBox(),pointer={x:markerBox.x+markerBox.width/2,y:markerBox.y+markerBox.height/2};
  await marker.hover();
  assert.equal(await page.locator('#map-tooltip').evaluate(el=>el.hidden),false,'custom hover hint appears on the pointer event without waiting for a native tooltip');
  assert.equal(await page.locator('#map-popup').evaluate(el=>el.hidden),true,'hover does not open the detailed project dialog');
  assert.equal(await marker.locator('title').count(),0,'homepage markers do not show a second native tooltip');
  assert.equal(await page.locator('#map-tooltip').textContent(),await marker.getAttribute('data-tooltip'));
  const tooltipBefore=await page.locator('#map-tooltip').boundingBox();
  assert.ok(tooltipBefore.width<=280&&tooltipBefore.height<=96,'hover hint stays compact');
  assert.ok(Math.min(Math.abs(tooltipBefore.x-pointer.x),Math.abs(tooltipBefore.x+tooltipBefore.width-pointer.x))<=20,'hover hint is positioned beside the mouse');
  await page.mouse.move(pointer.x+1,pointer.y+1);
  const tooltipMoved=await page.locator('#map-tooltip').boundingBox();
  assert.ok(Math.abs(tooltipMoved.x-tooltipBefore.x-1)<1&&Math.abs(tooltipMoved.y-tooltipBefore.y-1)<1,'hover hint follows pointer movement');
  await page.locator('.hero h1').hover();
  assert.equal(await page.locator('#map-tooltip').evaluate(el=>el.hidden),true,'leaving a marker immediately hides the hint');
  const edgeIndex=await page.locator('#world-map .site-point').evaluateAll(points=>points.map((point,index)=>({index,right:point.getBoundingClientRect().right})).sort((a,b)=>b.right-a.right)[0].index);
  await page.locator('#world-map .site-point').nth(edgeIndex).hover();
  const edgeHint=await page.locator('#map-tooltip').boundingBox(),hintFrame=await page.locator('.map-frame').boundingBox();
  assert.ok(edgeHint.x>=hintFrame.x&&edgeHint.x+edgeHint.width<=hintFrame.x+hintFrame.width+1&&edgeHint.y>=hintFrame.y&&edgeHint.y+edgeHint.height<=hintFrame.y+hintFrame.height+1,'hover hint stays inside the map at its edge');
  await page.locator('.hero h1').hover();
  await marker.click();await page.locator('#map-popup').waitFor();
  assert.equal(await page.locator('#map-tooltip').evaluate(el=>el.hidden),true,'click replaces the compact hint with the detail dialog');
  await page.locator('#close-site').click();
  await page.locator('#zoom-reset').focus();await marker.focus();
  assert.equal(await page.locator('#map-tooltip').evaluate(el=>el.hidden),false,'keyboard focus receives the same compact hint');
  assert.equal(await page.locator('#map-popup').evaluate(el=>el.hidden),true,'focus alone does not open the detail dialog');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#map-tooltip').evaluate(el=>el.hidden),true,'Escape hides the compact hint');
  const size=()=>marker.evaluate(el=>{const r=el.getBoundingClientRect();return [r.width,r.height];});
  const initialSize=await size();
  assert.equal(await page.locator('#world-map').getAttribute('data-detail'),'false','global first view keeps the light base without fetching detailed vectors');
  await page.locator('#zoom-in').click();await page.locator('#zoom-in').click();
  await page.locator('#world-map[data-detail=true]').waitFor();
  await page.locator('.admin1-boundaries').waitFor();
  assert.ok(await page.locator('.admin1-boundaries').isVisible(),'zoom shows real state/province boundaries');
  assert.equal(await page.locator('.admin1-boundaries').evaluate(el=>getComputedStyle(el).vectorEffect),'non-scaling-stroke','state lines stay thin while zooming');
  const enlargedSize=await size();
  assert.ok(initialSize.every((v,i)=>Math.abs(v-enlargedSize[i])<.1),'zoom keeps marker size');
  assert.ok(await marker.evaluate(el=>{const m=el.transform.baseVal.consolidate().matrix;return Math.abs(m.e-Number(el.dataset.x))<.01&&Math.abs(m.f-Number(el.dataset.y))<.01;}),'coordinate anchor remains unchanged');
  await page.locator('#zoom-reset').click();
  assert.equal(await page.locator('.admin1-boundaries').isVisible(),false,'global view hides internal boundaries');
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
  await page.route('**/assets/world-detail.geo.json',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#zoom-in').click();
  await page.getByRole('button',{name:'精细底图暂不可用 · 点击重试'}).waitFor();
  assert.ok(await page.locator('#world-map .land').count()>0,'detail failure preserves the usable base');
  assert.ok(await page.locator('#world-map .site-point').count()>0,'detail failure preserves project points');
  await page.unroute('**/assets/world-detail.geo.json');
  await page.getByRole('button',{name:'精细底图暂不可用 · 点击重试'}).click();
  await page.locator('#world-map[data-detail=true]').waitFor();
  assert.equal(await page.locator('#map-detail-status').isVisible(),false,'retry replaces the fallback without a stale error');
  await page.locator('#zoom-in').click();
  await page.locator('.admin1-boundaries').waitFor();
  assert.ok(await page.locator('.admin1-boundaries').isVisible());
  await page.route('**/assets/map-admin1-*.geo.json',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#zoom-in').click();await page.locator('#zoom-in').click();
  await page.locator('#world-map[data-detail=true]').waitFor();
  await page.getByRole('button',{name:'精细底图暂不可用 · 点击重试'}).waitFor();
  assert.equal(await page.locator('.admin1-boundaries').count(),0,'state chunk failure retains the detailed country outline');
  const preservedMarker=await page.locator('.site-point').first().getAttribute('data-id');
  await page.unroute('**/assets/map-admin1-*.geo.json');
  await page.getByRole('button',{name:'精细底图暂不可用 · 点击重试'}).click();
  await page.locator('.admin1-boundaries').waitFor();
  assert.equal(await page.locator('.site-point').first().getAttribute('data-id'),preservedMarker,'state retries preserve project markers');
  await page.goto(base+'/industry.html');await page.locator('#world-map .site-point').first().waitFor();
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
  await page.unroute(/\/api\/news(?:\?.*)?$/);
  await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:{pipeline:{available:true,progress:{leads:100,events:100,linked:0,constraints:{}},records:[{
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

  // Reader history exposes the stated interval and source date, with no inferred midpoint or private workflow clocks.
  const homeProjection=await (await page.request.get(base+'/api/industry?overview=1')).json();
  await page.route(/\/api\/industry(?:\?.*)?$/,r=>r.fulfill({json:{...homeProjection,tracking:{...homeProjection.tracking,changes:[]},research_updates:{...homeProjection.research_updates,changes:[]}}}));
  await page.goto(base+'/');await page.locator('#home-updates .update-empty').waitFor();
  assert.equal(await page.locator('#update-track .update-item').count(),0,'empty source history never invents a change');
  await page.unroute(/\/api\/industry(?:\?.*)?$/);
  const rangeRow=homeProjection.rows.find(p=>p.capacity_known&&p.coordinates);
  for(const stage of Object.keys(homeProjection.stages))homeProjection.totals[stage]-=rangeRow.capacity[stage];
  const nativeRange={value_range:[1,2],unit:'GW',assumptions:['来源规划区间']};
  Object.assign(rangeRow,{phases:[],capacity:{operating:0,construction:0,planning:0},total_mw:0,capacity_known:false,capacity_ranged:true,
   quantity_fields:{capacity_it_mw:nativeRange},capacity_ranges:[{field:'capacity_it_mw',stage:'construction',level:'L6',...nativeRange}]});
  homeProjection.totals.ranged_sites=1;
  homeProjection.research_updates={...homeProjection.research_updates,changes:[]};
  homeProjection.tracking={observations:777,review_overdue_sites:888,conflicting_sites:999,changes:[{
   id:'reader-interval',site_id:rangeRow.site_id,name:'有依据的区间项目',kind:'forecast',scope:'phase:two',effective_at:'2027',
   recorded_at:'2026-10-11T00:00:00Z',reviewed_at:'2098-01-01T00:00:00Z',basis:'来源说明规划区间，尚未实现',assumptions:['不得取区间中点'],
   fields:{capacity_it_mw:nativeRange,capacity_it_mw_by_status:{},capacity_assessment:null},
   source_versions:[{published_at:'2026-10',first_received_at:'2097-01-01T00:00:00Z'}],sources:[{url:'https://example.com/range-source'}]
  }]};
  await page.route(/\/api\/industry(?:\?.*)?$/,r=>r.fulfill({json:homeProjection}));
  await page.goto(base+'/');await page.locator('#update-track > .update-items:first-child [data-update-kind="project"]').waitFor();await page.locator('#world-map .range-point rect').waitFor();
  const intervalUpdate=page.locator('#update-track > .update-items:first-child [data-update-kind="project"]');
  assert.equal(await intervalUpdate.getAttribute('data-effective-at'),'2027','information time stays separate from the update timestamp');
  assert.match(await intervalUpdate.innerText(),/预测[\s\S]*1–2 GW/);
  assert.match(await intervalUpdate.locator('time').getAttribute('datetime'),/2026-10-11/);
  assert.match(await intervalUpdate.innerText(),/有依据的区间项目/);
  assert.doesNotMatch(await page.locator('main').innerText(),/2098|2097|777|888|999|站点复核待更新/);
  assert.equal(await page.locator('.range-point rect').count(),1,'range has its own fixed marker, not an area based on a midpoint');
  await page.locator('.range-point').press('Enter');
  assert.match(await page.locator('#map-popup').innerText(),/1–2 GW/);
  assert.doesNotMatch(await page.locator('#map-popup').innerText(),/未披露|1,500|1.5 GW/);
  homeProjection.detail={...structuredClone(baseline.rows.find(p=>p.site_id===rangeRow.site_id)),...rangeRow,adoption:null,observations:homeProjection.tracking.changes};
  await page.goto(base+'/project.html?site='+encodeURIComponent(rangeRow.site_id));
  await page.locator('#site-observation-timeline .timeline li').waitFor();
  assert.match(await page.locator('#site-observation-timeline').innerText(),/2027[\s\S]*预测[\s\S]*分期 two[\s\S]*1–2 GW/);
  assert.match(await page.locator('#site-observation-timeline').innerText(),/来源发表 2026-10/);
  assert.equal(await page.locator('#site-observation-timeline a[href="https://example.com/range-source"]').count(),1);
  assert.doesNotMatch(await page.locator('#site-observation-timeline').innerText(),/2098|2097|1,500|1.5 GW/);
  for(const stamp of ['2026','2026-10']){
   homeProjection.tracking.changes[0].recorded_at=stamp;
   await page.goto(base+'/');
   const preciseTime=page.locator('#update-track > .update-items:first-child [data-update-kind="project"] time');
   await preciseTime.waitFor();
   assert.equal(await preciseTime.getAttribute('aria-label'),stamp+' 更新','update timestamps retain the supplied year or month precision');
   assert.equal(await preciseTime.getAttribute('datetime'),null,'partial timestamps do not acquire an invented full date');
  }
  // Missing stages are unknown; an explicitly supplied zero remains a zero, including estimates.
  const zeroRow={...structuredClone(baseline.rows.find(p=>p.site_id===rangeRow.site_id)),
   site_id:'fixture-explicit-zero',name:'显式零容量fixture',adoption:null,observations:[],
   capacity:{operating:0,construction:0,planning:0},total_mw:0,phases:[{level:'L8',stage:'operating',label:'已投运',mw:0}],capacity_ranges:[],capacity_ranged:false,
   capacity_known:true,capacity_estimated:true,quantity_fields:{capacity_it_mw:0},
   capacity_assessment:{kind:'estimate',status:'reviewed',as_of:'2026-07-28'}};
  homeProjection.rows.push(zeroRow);
  await page.goto(base+'/projects.html');await page.locator('#project-rows tbody tr').first().waitFor();
  const rangeCells=page.locator('#project-rows tbody tr').filter({has:page.locator('a[href*="site='+rangeRow.site_id+'"]')}).locator('td.num');
  assert.deepEqual(await rangeCells.evaluateAll(cells=>cells.map(cell=>cell.childNodes[0].textContent)),['未披露','未披露']);
  const zeroCells=page.locator('#project-rows tbody tr').filter({has:page.locator('a[href*="site=fixture-explicit-zero"]')}).locator('td.num');
  assert.deepEqual(await zeroCells.evaluateAll(cells=>cells.map(cell=>cell.childNodes[0].textContent)),['未披露','0 MW']);
  homeProjection.detail=zeroRow;
  await page.goto(base+'/project.html?site=fixture-explicit-zero');await page.locator('#capacity-estimate').waitFor();
  assert.match(await page.locator('#capacity-estimate').innerText(),/运营约 0 MW IT/);
  assert.match(await page.locator('#capacity-estimate').innerText(),/建设中未披露[\s\S]*筹备未披露/);
  await page.unroute(/\/api\/industry(?:\?.*)?$/);

  // Raw daily events remain visible without a headline feed; original dates, bases and locations stay separate.
  await page.unroute(/\/api\/news(?:\?.*)?$/);
  const rawPayload={reader:{status:'idle',stale:false,received_at:'2026-10-11T03:00:00Z'},feed:null,pipeline:{available:true,progress:{leads:3,linked:0}},raw_atlas:{research_total:3,daily:{today:'2026-10-11',published_events:0,received_events:1,capacity_observations:2,located_events:1,research_published_records:2},latest_published_at:null,latest_received_at:'2026-10-11T00:15:00Z',records:[
    {id:'raw-megawatt',origin:'daily_html',title:'微软新园区日报线索',url:'https://example.com/raw-mw',report_date:'2026-10-10',published_at:0,company_ids:['microsoft'],coordinates:[35,139],location:'东京',location_precision:'site',capacity_observations:[{quoted_value:'1,000 MW',mw:1000,basis:'it'}],verification_status:'raw'},
    {id:'raw-no-location',origin:'daily_html',title:'新项目供电消息',url:'https://example.com/raw-grid',published_at:0,company_ids:[],coordinates:null,location_precision:'unknown',capacity_observations:[{quoted_value:'75 MW',mw:75,basis:'facility_or_grid'}],verification_status:'raw'},
    {id:'research-a',origin:'research_publication',title:'美国资料项目甲',url:'https://example.com/research-a',publication_date:'2026-10-11',published_at:0,company_ids:['bytedance'],country_code:'US',coordinates:[39,-98],location:'美国',location_precision:'country',capacity_text:'计划 2 GW / 设施 3 GW',verification_status:'raw'},
    {id:'research-b',origin:'research_publication',title:'美国资料项目乙',url:'https://example.com/research-b',publication_date:'2026-10-11',published_at:0,company_ids:['alibaba'],country_code:'US',coordinates:[39,-98],location:'美国',location_precision:'country',capacity_text:'容量未披露',verification_status:'raw'},
    {id:'research-c',origin:'research_publication',title:'新加坡资料项目',url:'https://example.com/research-c',publication_date:'2026-10-11',published_at:0,company_ids:['alibaba'],country_code:'SG',coordinates:null,location:'新加坡',location_precision:'country',capacity_text:'容量未披露',verification_status:'raw'}
  ],country_groups:[{country_code:'US',country_name:'美国',coordinates:[39,-98],count:2},{country_code:'SG',country_name:'新加坡',coordinates:null,count:1}]}};
  await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:rawPayload}));
  // A stalled member identity endpoint must never block public news.
  await page.route('**/api/whoami',()=>new Promise(()=>{}));
  await page.goto(base+'/');await page.getByRole('link',{name:'微软新园区日报线索',exact:true}).waitFor();await page.locator('#world-map .country-point').waitFor({state:'visible',timeout:10000});
  assert.equal(await page.locator('.dc-news-list article').count(),2,'raw headlines remain available without a feed');
  assert.equal(await page.locator('.dc-news-list :is(time,small,button,.dc-news-day,.dc-news-capacity,.dc-news-state,.dc-news-mark)').count(),0);
  assert.equal(await page.locator('.dc-news-original[href="https://example.com/raw-mw"]').count(),1,'original article links remain available');
  assert.doesNotMatch(await page.locator('main').innerText(),/今日接收|今日新闻|采用更新|站点复核待更新|查看核验进展|新闻接收|运行同步|已接收日报事件/);
  if(process.env.UI_QA_DIR){
   await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>scrollTo(0,0));
   await page.screenshot({path:process.env.UI_QA_DIR+'/fixture-daily-capacity-1440x900.png'});
   await page.locator('#ui-appearance').selectOption('dark');await page.screenshot({path:process.env.UI_QA_DIR+'/fixture-daily-capacity-dark-1440x900.png'});await page.locator('#ui-appearance').selectOption('light');
  }
  assert.equal(await page.locator('.country-point').count(),1,'country research records cluster without fake site positions');
  assert.equal(await page.locator('.country-point text').textContent(),'2');
  assert.equal(await page.locator('#world-map [data-raw-id="research-c"], #world-map [data-raw-id="raw-no-location"]').count(),0,'unlocated observations do not invent map coordinates');
  const sampleBefore=await page.locator('.site-point').evaluateAll(points=>points.map(p=>[p.dataset.id,p.querySelector('circle')?.getAttribute('r')]));
  await page.locator('.raw-point[data-raw-id="raw-megawatt"]').press('Enter');await page.locator('#map-popup').waitFor();
  assert.match(await page.locator('#map-popup').innerText(),/1,000 MW[\s\S]*IT/);
  assert.match(await page.locator('#map-popup').innerText(),/报道数字不并入项目 IT 容量/);
  await page.locator('#close-site').click();
  await page.locator('.country-point').press('Enter');
  assert.match(await page.locator('#map-popup').innerText(),/国家级示意，非城市或园区位置/);
  assert.match(await page.locator('#map-popup').innerText(),/计划 2 GW \/ 设施 3 GW/);
  await page.locator('#close-site').click();
  await page.locator('#company-chips [data-company="bytedance"]').click();assert.equal(await page.locator('.country-point.highlighted').count(),1);
  assert.deepEqual(await page.locator('.site-point').evaluateAll(points=>points.map(p=>[p.dataset.id,p.querySelector('circle')?.getAttribute('r')])),sampleBefore,'raw capacity and highlighting do not alter adopted capacity marker areas');
  // News refresh updates overlays while keeping base geography and project DOM nodes.
  await page.evaluate(()=>new Promise(resolve=>{window.oldLand=document.querySelector('#map-land-layer');window.oldProject=document.querySelector('.site-point');window.addEventListener('inresearch:news-data',()=>resolve(true),{once:true});window.dispatchEvent(new CustomEvent('inresearch:industry-filter',{detail:{...window.industryFilter,force:true}}));}));
  assert.ok(await page.evaluate(()=>window.oldLand===document.querySelector('#map-land-layer')&&window.oldProject===document.querySelector('.site-point')));
  await page.unroute('**/api/whoami');

  // Rendering counts describe only safe, displayed rows in the current API snapshot.
  for(const payload of [{reader:{status:'not_connected'},feed:null},
    {feed:{status:'success',exported_at:new Date().toISOString(),items:[]}}]){
   await page.unroute(/\/api\/news(?:\?.*)?$/);
   await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:payload}));
   await page.goto(base+'/');await page.locator('#world-map .site-point').first().waitFor();
   await page.waitForFunction(()=>document.querySelector('.dc-news-meta').textContent || document.querySelector('.dc-news-list').textContent);
   assert.equal(await page.locator('[data-news-count]').count(),0);
   if(!payload.feed)assert.match(await page.locator('.dc-news-meta').innerText(),/暂无可显示的近期报道/);
   else assert.match(await page.locator('.dc-news-list').innerText(),/当前范围暂无已整理的中文新闻/);
   assert.doesNotMatch(await page.locator('main').innerText(),/尚未连接阅读服务|等待新闻同步|查看核验进展/);
  }
  await page.unroute(/\/api\/news(?:\?.*)?$/);
  await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({status:503,body:'unavailable'}));
  await page.goto(base+'/');await page.getByText('近期报道暂不可用，请稍后重试。',{exact:true}).waitFor();
  assert.equal(await page.locator('[data-news-count]').count(),0);
  await page.goto(base+'/project.html?site=us-tx-abilene');
  await page.locator('#capacity-estimate').waitFor();
  assert.match(await page.locator('#capacity-estimate').innerText(),/运营约 421/);
  assert.match(await page.locator('#capacity-estimate').innerText(),/建设中未披露[\s\S]*筹备未披露/);
  assert.doesNotMatch(await page.locator('#capacity-estimate').innerText(),/建设中约 0|筹备约 0/);
  assert.match(await page.locator('#capacity-estimate').innerText(),/有效时点：2026-07-28/);
  assert.doesNotMatch(await page.locator('#capacity-estimate').innerText(),/422|843/);
  const actualTimeline=page.locator('#site-observation-timeline .timeline li');
  assert.equal(await actualTimeline.count(),2,'current estimate and future forecast keep separate observations');
  assert.match(await actualTimeline.filter({hasText:'2026-07-28'}).innerText(),/估算[\s\S]*IT容量：421 MW/);
  assert.match(await actualTimeline.filter({hasText:'2026-11-01'}).innerText(),/预测[\s\S]*IT容量：843 MW/);
  assert.match(await actualTimeline.first().innerText(),/来源发表 2026-10-05/);
  assert.doesNotMatch(await page.locator('#site-observation-timeline').innerText(),/首次接收|审核时点|05:12:03/);
  assert.equal(await page.locator('#detail a[href*="undefined"]').count(),0,'reader adoption never invents a daily event ID');
  const observationLink=page.getByRole('link',{name:'查看观测与来源 →',exact:true});
  assert.equal(await observationLink.getAttribute('href'),'#site-observation-timeline');
  await observationLink.click();
  assert.equal(new URL(page.url()).hash,'#site-observation-timeline');
  assert.ok(await page.locator('#site-observation-timeline').isVisible());
  assert.ok(await actualTimeline.locator('a[href^="https://"]').count()>=2,'observation anchor exposes original source links');

  if(process.env.UI_QA_DIR){
   for(const [width,height] of [[1440,900],[390,844]]){
    await page.setViewportSize({width,height});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'real timeline no overflow '+width);
    await page.screenshot({path:process.env.UI_QA_DIR+`/abilene-${width}x${height}.png`,fullPage:true});
   }
  }
  await page.goto(base+'/project.html?site=fi-salo-atnorth-fin05');
  await page.getByRole('button',{name:'重试新闻同步',exact:true}).waitFor();
  assert.equal(await page.locator('#project-dossier tbody tr').count(),12,'all project angles are visible, including unknown roles');
  assert.match(await page.getByRole('link',{name:'查看对应日报事件与原件定位 →',exact:true}).getAttribute('href'),/^\/supply.html\?event=daily-event-[a-f0-9]{64}#matching$/,'daily adoption keeps its real source event link');
  assert.equal(await page.locator('#detail a[href*="undefined"]').count(),0);

  assert.match(await page.locator('#project-dossier').innerText(),/辖区政府不自动视为地主/);
  assert.match(await page.locator('#project-dossier').innerText(),/IT、设施功率、接电额度、发电 MW/);
  assert.ok((await page.locator('#detail').innerText()).includes('160 MW'));
  await page.unroute(/\/api\/news(?:\?.*)?$/);
  await page.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:{pipeline:{available:true,records:[{
    id:'recovered-fin05',title:'FIN05 restored news',state:'linked',site_id:'fi-salo-atnorth-fin05',company_ids:['atnorth'],events:[]
  }]}}}));
  await page.getByRole('button',{name:'重试新闻同步',exact:true}).click();
  await page.getByText('FIN05 restored news',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'重试新闻同步',exact:true}).count(),0);
  assert.ok((await page.locator('#detail').innerText()).includes('160 MW'));
  await page.unroute(/\/api\/news(?:\?.*)?$/); // screenshots below use real local endpoints only
  if(process.env.UI_QA_DIR)mkdirSync(process.env.UI_QA_DIR,{recursive:true});
  const measurements=[];
  for(const [width,height] of [[1366,768],[1440,900],[1920,1080],[390,844],[320,740]]){
   await page.setViewportSize({width,height});await page.goto(base+'/');
   await page.locator('#world-map .site-point').first().waitFor();
   await page.evaluate(()=>document.fonts.ready);
   await page.locator('.country-point').first().waitFor();await page.locator('#update-track > .update-items:first-child .update-item').first().waitFor();
   const layout=await page.evaluate(()=>{
    const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};
    const map=rect('#world-map'),matrix=document.querySelector('#world-map').getScreenCTM();
    const screen=(x,y)=>{const p=new DOMPoint(x,y).matrixTransform(matrix);return {x:p.x,y:p.y};};
    return {map,world:[screen(0,0),screen(1000,490)],market:rect('#market-band'),atlas:rect('.atlas-panel'),news:rect('.news-panel'),ticker:rect('#home-updates'),
     controls:['.company-picker','#company-chips','#company-coverage'].map(rect),
     overflow:document.documentElement.scrollWidth-innerWidth,scroll:scrollY,viewBox:document.querySelector('#world-map').getAttribute('viewBox'),
     numberSize:parseFloat(getComputedStyle(document.querySelector('.macro-card strong')).fontSize),
     metaSize:parseFloat(getComputedStyle(document.querySelector('.macro-card small')).fontSize)};
   });
   measurements.push({width,height,...layout});
   assert.equal(layout.scroll,0);assert.ok(layout.overflow<=1,`overflow at ${width}`);
   assert.equal(layout.viewBox,'0 0 1000 490');
   assert.ok(Math.abs(layout.map.width/layout.map.height-1000/490)<.01,'full aspect ratio');
   assert.ok(layout.world[0].y>=layout.map.top-1 && layout.world[1].y<=layout.map.bottom+1,'no SVG clipping');
   assert.ok(layout.controls.every(r=>r.top>=layout.map.bottom&&r.bottom<=layout.atlas.bottom+1),'company shortcuts sit below the map inside its panel');
   assert.ok(layout.ticker.height<=64,'updates occupy one compact title strip');
   assert.ok(layout.ticker.top>=layout.market.bottom&&layout.ticker.bottom<=layout.atlas.top,'one update stream sits between market figures and the atlas');
   assert.ok(layout.metaSize>=13);
   if(width>1000){
    assert.ok(layout.market.top>0 && layout.market.bottom<layout.map.top);
    assert.ok(layout.map.bottom<=height && layout.map.top>=0,`entire map visible at ${width}×${height}`);
    assert.ok(layout.map.width>=850 && layout.numberSize>=40,'retain large readable graphics');
    assert.ok(layout.news.left>=layout.map.right && Math.abs(layout.news.top-layout.atlas.top)<=1,'news on the right, aligned to the atlas');
    assert.ok(Math.abs(layout.news.bottom-layout.atlas.bottom)<=1,'news panel matches the complete map panel height');
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
  if(process.env.UI_QA_DIR){
   await page.setViewportSize({width:1440,height:900});await page.goto(base+'/');await page.locator('#update-track > .update-items:first-child .update-item').first().waitFor();await page.locator('.country-point').first().waitFor();await page.evaluate(()=>document.fonts.ready);await page.locator('#ui-appearance').selectOption('dark');await page.screenshot({path:process.env.UI_QA_DIR+'/homepage-dark-1440x900.png'});await page.locator('#ui-appearance').selectOption('light');
  }
  if(process.env.UI_QA_DIR)require('node:fs').writeFileSync(process.env.UI_QA_DIR+'/layout.json',JSON.stringify(measurements,null,2));
  await page.setViewportSize({width:1366,height:768});await page.goto(base+'/index.html');
  await page.locator('#world-map .site-point').first().waitFor();
  await page.locator('#zoom-in').click();assert.notEqual(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');
  await page.locator('#zoom-reset').click();assert.equal(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');
  const mapBox=await page.locator('#world-map').boundingBox();
  await page.mouse.move(mapBox.x+mapBox.width*.4,mapBox.y+mapBox.height*.8);await page.mouse.down();await page.mouse.move(mapBox.x+mapBox.width*.4+60,mapBox.y+mapBox.height*.8+20);await page.mouse.up();
  assert.notEqual(await page.locator('#world-map').getAttribute('viewBox'),'0 0 1000 490');await page.locator('#zoom-reset').click();
  await page.goto(base+'/industry.html');await page.locator('#filters select[name=region] option').nth(1).waitFor({state:'attached'});
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
