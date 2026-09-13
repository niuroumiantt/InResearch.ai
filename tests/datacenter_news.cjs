const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];let fullRequests=0;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/news',r=>r.fulfill({json:{reader:{status:'idle',stale:false},feed:{status:'success',exported_at:new Date().toISOString(),items:[{title:'Datacenter opens',title_zh:'数据中心开业',publisher:'Example',published_at:Date.parse('2026-09-06T02:30:00Z'),url:'https://example.com/news',category:'数据中心'},{title:'unsafe',url:'javascript:alert(1)'},...Array.from({length:15},(_,i)=>({title:'Data center '+i,title_zh:'数据中心 '+i,url:'https://example.com/'+i,published_at:Date.parse(i===0?'2026-09-05T16:10:00Z':'2026-09-05T15:50:00Z')}))]}}}));
 await page.route('**/api/research',r=>{fullRequests++;return r.fulfill({status:500,body:'unexpected full snapshot'});});
 for(const file of ['index.html','ops.html']){
 await page.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/'+file);
 await page.getByRole('link',{name:'数据中心开业',exact:true}).waitFor();
 assert.equal(await page.locator('.dc-news a').count(),16);
 assert.ok(await page.locator('.dc-news-list').evaluate(el=>el.scrollHeight>el.clientHeight));
 assert.equal(await page.locator('.dc-news details').count(),0);assert.equal(await page.locator('.dc-news small').first().textContent(),'example.com');assert.equal(await page.getByText('Datacenter opens',{exact:true}).count(),0);
 assert.deepEqual(await page.locator('.dc-news-day').allTextContents(),['2026-09-06','2026-09-05']);
 assert.deepEqual((await page.locator('.dc-news-time').allTextContents()).slice(0,3),['10:30','00:10','23:50']);
 assert.equal(await page.locator('.dc-news-time').first().getAttribute('datetime'),'2026-09-06T02:30:00.000Z');
 assert.equal(await page.locator('.dc-news-timezone').textContent(),'北京时间');
 if(file==='index.html'){await page.getByRole('button',{name:'folk',exact:true}).click();await page.locator('.dc-news').screenshot({path:'/tmp/news-timeline.png'});}
 for(const skin of ['folk','Attio'])await page.getByRole('button',{name:skin,exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1280,height:900});
 }
 assert.equal(fullRequests,0);assert.deepEqual(errors,[]);console.log('PASS homepage and ops shared news: scrolling, titles, safe links, skins, mobile');
 const race = await browser.newPage();
 await race.addInitScript(()=>{
   const originalFetch=window.fetch, originalInterval=window.setInterval;
   window.newsRequests=[];
   // Ignore abort: a completed transport can still deliver a delayed JSON body.
   window.fetch=(url,options)=>url==='/api/news'
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
 await race.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/index.html');
 await race.waitForFunction(()=>window.newsRequests.length===1);
 await race.evaluate(()=>window.refreshNews());
 await race.evaluate(value=>window.deliverNews(1,value),news('new'));
 await race.getByRole('link',{name:'new',exact:true}).waitFor();
 await race.evaluate(value=>window.deliverNews(0,value),news('old'));
 await race.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));
 assert.equal(await race.getByRole('link',{name:'old',exact:true}).count(),0);
 await race.evaluate(()=>{window.refreshNews();window.newsRequests[2].reject(new Error('offline'));});
 await race.getByText('新闻暂时无法同步，请稍后重试。',{exact:true}).waitFor();
 assert.equal(await race.getByRole('link',{name:'new',exact:true}).count(),1);
 await race.evaluate(value=>{window.refreshNews();window.deliverNews(3,value);},news('recovered'));
 await race.getByRole('link',{name:'recovered',exact:true}).waitFor();
 assert.equal(await race.locator('.dc-news-meta').isHidden(),true);
 for(const [reader,message] of [
   [{status:'not_connected'},'尚未连接阅读服务'],
   [{status:'degraded'},'新闻快照暂不可用，请稍后重试。']
 ]) {
   await race.evaluate(reader=>{window.refreshNews();window.deliverNews(window.newsRequests.length-1,{feed:null,reader});},reader);
   await race.getByText(message,{exact:true}).waitFor();
   assert.equal(await race.locator('.dc-news a').count(),0);
 }
 await race.evaluate(value=>{window.refreshNews();window.deliverNews(window.newsRequests.length-1,value);},news('stale',{reader:{status:'idle',stale:true}}));
 await race.getByText('更新延迟',{exact:true}).waitFor();
 await race.close();
 console.log('PASS no full snapshot polling; missing/stale/retry and late response rejection');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
