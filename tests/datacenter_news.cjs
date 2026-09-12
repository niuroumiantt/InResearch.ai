const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/research',r=>r.fulfill({json:{reader:{acquisition:{news_feed:{status:'success',exported_at:new Date().toISOString(),items:[{title:'Datacenter opens',title_zh:'数据中心开业',publisher:'Example',published_at:Date.parse('2026-09-06T02:30:00Z'),url:'https://example.com/news',category:'数据中心'},{title:'unsafe',url:'javascript:alert(1)'},...Array.from({length:15},(_,i)=>({title:'Data center '+i,title_zh:'数据中心 '+i,url:'https://example.com/'+i,published_at:Date.parse(i===0?'2026-09-05T16:10:00Z':'2026-09-05T15:50:00Z')}))]}}}}}));
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
 assert.deepEqual(errors,[]);console.log('PASS homepage and ops shared news: scrolling, titles, safe links, skins, mobile');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
