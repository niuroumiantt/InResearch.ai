const {setAppearance} = require('./ui_helpers.cjs');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];let fullRequests=0;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/news',r=>r.fulfill({json:{daily_publications:[{title:'Confirmed current daily',report_date:'2026-10-14',url:'https://inews.today/c/101',pinned:true,highlight:true},{title:'Previous daily retained',report_date:'2026-10-13',url:'https://inews.today/c/100',pinned:false,highlight:false}],reader:{status:'idle',stale:false},feed:{status:'success',exported_at:new Date().toISOString(),items:[{title:'Datacenter opens',title_zh:'数据中心开业',publisher:'Example',published_at:Date.parse('2026-09-06T02:30:00Z'),url:'https://example.com/news',category:'数据中心'},{title:'unsafe',url:'javascript:alert(1)'},...Array.from({length:15},(_,i)=>({title:'Data center '+i,title_zh:'数据中心 '+i,url:'https://example.com/'+i,published_at:Date.parse(i===0?'2026-09-05T16:10:00Z':'2026-09-05T15:50:00Z')}))]}}}));
 await page.route('**/api/research',r=>{fullRequests++;return r.fulfill({status:500,body:'unexpected full snapshot'});});
 for(const file of ['research-workbench.html']){  // 2026-09-28：管理页不再重复新闻时间线
 await page.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/'+file);
 await page.getByRole('link',{name:'数据中心开业',exact:true}).waitFor();
 assert.equal(await page.locator('.dc-news-list a').count(),16);
 assert.equal(await page.locator('.dc-news-daily').count(),2);assert.equal(await page.locator('.dc-news-daily-pinned').count(),1);assert.equal(await page.locator('.dc-news-daily-highlight').count(),1);assert.equal(await page.locator('.dc-news-daily-pinned a').textContent(),'Confirmed current daily');assert.equal(await page.getByRole('link',{name:'Previous daily retained',exact:true}).getAttribute('href'),'https://inews.today/c/100');
 assert.ok(await page.locator('.dc-news-list').evaluate(el=>el.scrollHeight>el.clientHeight));
 assert.equal(await page.locator('.dc-news details').count(),0);assert.equal(await page.locator('.dc-news-list small').first().textContent(),'example.com');assert.equal(await page.getByText('Datacenter opens',{exact:true}).count(),0);
 assert.deepEqual(await page.locator('.dc-news-day').allTextContents(),['2026-09-06','2026-09-05']);
 assert.deepEqual((await page.locator('.dc-news-time').allTextContents()).slice(0,3),['10:30','00:10','23:50']);
 assert.equal(await page.locator('.dc-news-time').first().getAttribute('datetime'),'2026-09-06T02:30:00.000Z');
 assert.equal(await page.locator('.dc-news-timezone').textContent(),'北京时间');
 if(file==='index.html'){await page.locator('.dc-news').screenshot({path:'/tmp/news-timeline.png'});}
 for(const mode of ['dark','light'])await setAppearance(page, mode);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1280,height:900});
 }
 assert.equal(fullRequests,0);assert.deepEqual(errors,[]);console.log('PASS shared research news timeline: scrolling, titles, safe links, skins, mobile');
 const home=await browser.newPage({viewport:{width:1440,height:1000}}),homeErrors=[];let identityRequests=0,navigationRequests=0,markRequests=0;
 home.on('pageerror',e=>homeErrors.push(e.message));
 await home.route('**/api/whoami',r=>{identityRequests++;return r.fulfill({json:{role:'admin'}});});
 await home.route('**/api/navigation?*',r=>{navigationRequests++;return r.continue();});
 await home.route(/\/api\/news\/marks?$/,r=>{markRequests++;return r.fulfill({json:{marks:{}}});});
 await home.route(/\/api\/news(?:\?.*)?$/,r=>r.fulfill({json:{reader:{status:'idle',stale:false},feed:{status:'success',exported_at:new Date().toISOString(),items:[
  {title:'A selected campus',title_zh:'已精选园区新闻',url:'https://example.com/selected',cluster_id:77,editorial_pick:true},
  {title:'A non-selected campus',title_zh:'未精选园区新闻',url:'https://example.com/unselected',cluster_id:88,editorial_pick:false},
  {id:'12345',title_zh:'仅有本地台账号',url:'https://example.com/local',editorial_pick:true},
  {title_zh:'已有专栏链接',url:'https://inews.today/c/123'},
  {title_zh:'危险脚本链接',url:'javascript:alert(1)'},
  {title_zh:'含有凭据的链接',url:'https://user:password@example.com/private'},
  ...Array.from({length:15},(_,i)=>({title_zh:'更多数据中心新闻 '+i,url:'https://example.com/more/'+i}))
 ]},raw_atlas:{records:[
  {id:'daily-news',origin:'daily_html',title:'日报的项目标题',url:'https://example.com/daily',capacity_text:'500 MW',coordinates:[105,30],location_precision:'country'},
  {id:'research-copy',origin:'research_publication',title:'不混入新闻的研究副本',url:'https://example.com/research'}
 ]}}}));
 await home.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/');
 await home.getByRole('link',{name:'已精选园区新闻',exact:true}).waitFor();
 assert.equal(await home.locator('[data-datacenter-news]').getAttribute('data-news-presentation'),'headlines');
 assert.equal(await home.locator('.dc-news-headlines-scroll>.dc-news-list').count(),1,'compact scroll area reserves normal-flow status space');
 assert.equal(await home.getByRole('link',{name:'已精选园区新闻',exact:true}).getAttribute('href'),'https://inews.today/s/77');
 for(const [title,query] of [['未精选园区新闻','A non-selected campus'],['仅有本地台账号','仅有本地台账号'],['日报的项目标题','日报的项目标题']]){
  const destination=new URL(await home.getByRole('link',{name:title,exact:true}).getAttribute('href'));
  assert.equal(destination.origin,'https://inews.today');assert.equal(destination.pathname,'/');assert.equal(destination.searchParams.get('q'),query);
 }
 assert.equal(await home.getByRole('link',{name:'已有专栏链接',exact:true}).getAttribute('href'),'https://inews.today/c/123');
 assert.equal(await home.locator('.dc-news-original[href="https://example.com/selected"]').count(),1,'original source remains directly accessible');
 assert.equal(await home.locator('.dc-news-headline').count(),20);assert.equal(await home.locator('.dc-news-original').count(),20);
 assert.equal(await home.locator('.dc-news time,.dc-news small,.dc-news-day,.dc-news-timezone,.dc-news-mark,.dc-news-capacity,.dc-news-locate').count(),0);
 assert.equal(await home.getByRole('link',{name:'危险脚本链接',exact:true}).count(),0);assert.equal(await home.getByRole('link',{name:'含有凭据的链接',exact:true}).count(),0);
 assert.equal(await home.getByRole('link',{name:'不混入新闻的研究副本',exact:true}).count(),0);
 assert.ok(await home.locator('.dc-news-list').evaluate(el=>el.scrollHeight>el.clientHeight),'compact headlines scroll within the map-height panel');
 assert.equal(navigationRequests,1,'the shared shell gets identity and menu from the one authorized projection');assert.equal(identityRequests,0,'headlines do not request a separate identity');assert.equal(markRequests,0,'headlines do not request member marks');
 for(const theme of ['dark','light']){await setAppearance(home, theme);await home.setViewportSize({width:390,height:844});assert.ok(await home.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 assert.deepEqual(homeErrors,[]);await home.close();
 console.log('PASS homepage headlines: verified inews story/search links, original sources, no metadata or mark requests, mobile');
 for(const file of ['research-workbench.html','']){
 const race = await browser.newPage();
 await race.addInitScript(()=>{
   const originalFetch=window.fetch, originalInterval=window.setInterval;
   window.newsRequests=[];
   // Ignore abort: a completed transport can still deliver a delayed JSON body.
   window.fetch=(url,options)=>/^\/api\/news(?:\?.*)?$/.test(url)
     ? new Promise((resolve,reject)=>window.newsRequests.push({resolve,reject}))
     : originalFetch(url,options);
   window.setInterval=(fn,delay,...args)=>delay===60000
     ? (window.refreshNews=fn,0) : originalInterval(fn,delay,...args);
   window.deliverNews=(i,value)=>window.newsRequests[i].resolve(new Response(JSON.stringify(value)));
 });
 function news(title,extra={}) {
   return {schema_version:1,reader:{status:'idle',stale:false},
     feed:{status:'success',exported_at:new Date().toISOString(),items:[{title_zh:title,url:'https://example.test/'+title}]},...extra};
 }
 await race.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/'+file);
 await race.waitForFunction(()=>window.newsRequests.length===1);
 if(!file)assert.equal(await race.locator('.dc-news-meta').innerText(),'正在读取新闻…');
 await race.evaluate(()=>window.refreshNews());
 await race.evaluate(value=>window.deliverNews(1,value),news('new'));
 await race.getByRole('link',{name:'new',exact:true}).waitFor();
 await race.evaluate(value=>window.deliverNews(0,value),news('old'));
 await race.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));
 assert.equal(await race.getByRole('link',{name:'old',exact:true}).count(),0);
 await race.evaluate(()=>{window.refreshNews();window.newsRequests[2].reject(new Error('offline'));});
 await race.getByText(file?'新闻暂时无法同步，请稍后重试。':'近期报道暂不可用，请稍后重试。',{exact:true}).waitFor();
 assert.equal(await race.getByRole('link',{name:'new',exact:true}).count(),1);
 if(!file){const status=await race.locator('.dc-news-meta').boundingBox(),headlines=await race.locator('.dc-news-list').boundingBox();assert.ok(status.y+status.height<=headlines.y+1,'failure status does not overlap retained headlines');}
 await race.evaluate(value=>{window.refreshNews();window.deliverNews(3,value);},news('recovered'));
 await race.getByRole('link',{name:'recovered',exact:true}).waitFor();
 assert.equal(await race.locator('.dc-news-meta').isHidden(),true);
 for(const [reader,message] of [
   [{status:'not_connected'},'尚未连接阅读服务'],
   [{status:'degraded'},'新闻快照暂不可用，请稍后重试。']
 ]) {
   await race.evaluate(reader=>{window.refreshNews();window.deliverNews(window.newsRequests.length-1,{feed:null,reader});},reader);
   await race.getByText(file?message:'暂无可显示的近期报道，项目与研究资料仍可浏览。',{exact:true}).waitFor();
   assert.equal(await race.locator('.dc-news a').count(),0);
 }
 await race.evaluate(value=>{window.refreshNews();window.deliverNews(window.newsRequests.length-1,value);},news('stale',{reader:{status:'idle',stale:true}}));
 await race.getByText('更新延迟',{exact:true}).waitFor();
 if(!file){
  await race.evaluate(()=>{window.refreshNews();window.deliverNews(window.newsRequests.length-1,{feed:null,reader:{status:'idle'},raw_atlas:{records:[{id:'raw-only',origin:'daily_html',title:'仅日报的标题',url:'https://example.test/raw-only'}]}});});
  await race.getByRole('link',{name:'仅日报的标题',exact:true}).waitFor();
  assert.equal(await race.locator('.dc-news-meta').isHidden(),true,'healthy daily-only headlines have no source metadata');
 }
 await race.close();
 }
 console.log('PASS no full snapshot polling; missing/stale/retry and late response rejection');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
