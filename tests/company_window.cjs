/* Rendering fixtures only; prices/news are illustrative and never published as production data. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}), errors=[], forbidden=[];
 const facts=require('../data/companies.json').records.find(c=>c.company_id==='supermicro');
 const disclosures=require('../data/company_disclosures.json').records[0];
 const data={company:facts,companies:[{id:'supermicro',name:'Supermicro'}],product_lines:disclosures.product_lines,financials:disclosures.financials,checked_at:disclosures.checked_at,catalog:{available:true,groups:[{id:'servers',label:'Servers',entities:5}]}};
 let newsMode='success',quoteMode='cached',profileMode='ok';
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/\/api\/product-catalog\/|\/data\/(products|contracts|projects|event_cards)\.json|\.pdf(?:\?|$)/.test(r.url()))forbidden.push(r.url());});
 await page.route('**/api/whoami',r=>r.fulfill({json:{role:'reader'}}));
 await page.route('**/api/company-window?*',r=>profileMode==='missing'?r.fulfill({status:404,body:'{}'}):r.fulfill({json:data}));
 await page.route('**/api/company-quote?*',r=>r.fulfill({json:quoteMode==='cached'||quoteMode==='stale'?{status:quoteMode,price:123.45,market_cap:12e9,change_percent:1.25,provider:'界面验证数据',as_of:'示例时间（非实际行情）',source_url:'https://example.test/quote'}:{status:quoteMode,refreshing:quoteMode==='pending'}}));
 await page.route('**/api/news?*',r=>{
  const u=new URL(r.request().url());assert.equal(u.searchParams.get('company'),'supermicro');assert.equal(u.searchParams.get('limit'),'6');
  return newsMode==='error'?r.fulfill({status:503,body:'{}'}):r.fulfill({json:{reader:{stale:newsMode==='stale'},feed:newsMode==='disconnected'?null:{status:'success',items:newsMode==='empty'?[]:[
   {title_zh:'界面验证新闻 · AI 服务器与整柜基础设施',url:'https://example.test/news',domain:'界面验证数据',published_at:1791327600000},
   {title:'Original English headline for rendering only',url:'https://example.test/english',domain:'example.test',published_at:1791320000000},
   {title_zh:'不应显示的危险链接',url:'javascript:alert(1)'},
   {title_zh:'<img src=x onerror=alert(1)>',url:'https://example.test/safe'}]}}});
 });
 const url=process.env.UI_BASE_URL+'/product-catalog.html?c=supermicro';
 await page.goto(url);await page.waitForFunction(()=>document.querySelector('#quote-price').textContent==='$123.45');
 await page.waitForFunction(()=>document.querySelectorAll('#company-news-list li').length===3);
 assert.equal(await page.locator('#catalog-title').innerText(),'Supermicro');
 assert.equal(await page.locator('.product-line-card').count(),6);
 assert.match(await page.locator('#company-facts').innerText(),/1993.*980 Rock.*7,000\+/s);
 assert.equal(await page.locator('#company-links a').first().getAttribute('href'),'https://supermicro.com/');
 assert.equal(await page.locator('#financial-reports .report-row').count(),4);
 await page.locator('[data-reports=quarterly]').click();assert.equal(await page.locator('#financial-reports .report-row').count(),5);
 assert.match(await page.locator('#financial-reports').innerText(),/FY2026 Q3/);
 await page.locator('[data-reports=annual]').click();
 assert.match(await page.locator('#company-news-list').innerText(),/原文标题/);
 assert.equal(await page.locator('#company-news-list img').count(),0);
 assert.equal(await page.locator('#company-news-list a[href^="javascript:"]').count(),0);
 assert.match(await page.locator('.product-line-card').first().getAttribute('href'),/view=products/);
 assert.equal(forbidden.length,0,'homepage never loads specs, report bodies or internal annexes');
 const directory=process.env.UI_QA_DIR;if(directory)fs.mkdirSync(directory,{recursive:true});
 for(const theme of ['light','dark']){
  await page.evaluate(t=>{document.documentElement.dataset.uiTheme=t;document.documentElement.dataset.uiMode=t;},theme);
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1100});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),theme+' '+width+' no overflow');
   if(directory)await page.screenshot({path:directory+'/company-window-'+theme+'-'+width+'.png',fullPage:true});
  }
 }
 await page.setViewportSize({width:1440,height:1100});
 for(const mode of ['empty','disconnected','stale','error']){
  newsMode=mode;await page.reload();await page.waitForFunction(()=>!document.querySelector('#news-status').textContent.includes('正在读取'));
  const status=await page.locator('#news-status').innerText();assert.match(status,{empty:/没有此公司/,disconnected:/尚未接通/,stale:/已过期/,error:/读取失败/}[mode]);
 }
 newsMode='success';await page.locator('#news-retry').click();await page.waitForFunction(()=>document.querySelectorAll('#company-news-list li').length===3);
 for(const mode of ['unregistered','unsupported','unavailable','stale']){
  quoteMode=mode;await page.reload();await page.waitForFunction(()=>!document.querySelector('#quote-time').textContent.includes('正在读取'));
  assert.match(await page.locator('#quote-time').innerText(),{unregistered:/代码未登记/,unsupported:/暂未接通/,unavailable:/暂不可用/,stale:/已过期/}[mode]);
 }
 quoteMode='pending';await page.reload();await page.waitForFunction(()=>document.querySelector('#quote-time').textContent.includes('更新较慢'),{},{timeout:18000});
 assert.equal(await page.locator('#quote-price').innerText(),'—','slow provider never leaves a false quote');
 profileMode='missing';await page.goto(process.env.UI_BASE_URL+'/product-catalog.html?c=%3Cscript%3Ex%3C%2Fscript%3E');
 await page.waitForFunction(()=>document.querySelector('#company-profile').textContent.includes('公司不存在'));
 assert.equal(await page.locator('#company-profile script').count(),0);
 assert.deepEqual(errors,[]);console.log('company window: four sections, bounded requests, safe sources, reports and failure states OK');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
