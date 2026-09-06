const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/research',r=>r.fulfill({json:{reader:{acquisition:{news_feed:{status:'success',exported_at:new Date().toISOString(),items:[{title:'Datacenter opens',title_zh:'数据中心开业',publisher:'Example',published_at:Date.now(),url:'https://example.com/news',category:'数据中心'},{title:'unsafe',url:'javascript:alert(1)'},...Array.from({length:15},(_,i)=>({title:'Data center '+i,url:'https://example.com/'+i,published_at:Date.now()}))]}}}}}));
 for(const file of ['index.html','ops.html']){
 await page.goto((process.env.UI_BASE_URL||'http://127.0.0.1:8882')+'/'+file);
 await page.getByRole('link',{name:'数据中心开业',exact:true}).waitFor();
 assert.equal(await page.locator('.dc-news a').count(),16);
 assert.ok(await page.locator('.dc-news-list').evaluate(el=>el.scrollHeight>el.clientHeight));
 await page.getByText('原文标题',{exact:true}).click();assert.ok(await page.getByText('Datacenter opens',{exact:true}).isVisible());
 for(const skin of ['folk','Attio'])await page.getByRole('button',{name:skin,exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1280,height:900});
 }
 assert.deepEqual(errors,[]);console.log('PASS homepage and ops shared news: scrolling, titles, safe links, skins, mobile');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
