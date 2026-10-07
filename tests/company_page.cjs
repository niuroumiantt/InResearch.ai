/* Unified company page: catalog accuracy, navigation, private annexes and visual layout.
   Fixtures exercise rendering only and are never submitted to a receiver. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[], privateRequests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(/\/data\/(products|projects|contracts|event_cards)\.json/.test(r.url()))privateRequests.push(r.url());});
  await page.route('**/api/whoami',r=>r.fulfill({json:{role:'reader'}}));
  const cell=text=>({text,colspan:1,rowspan:1,header:false});
  const models=Array.from({length:5},(_,i)=>({id:'fixture-'+i,name:'服务器型号 '+String.fromCharCode(65+i),kind:'named_product',category:'Servers / 验证分类',availability:'unknown',observed_at:'2026-10-07',extraction_status:'native_tables_extracted',navigation:{group:'servers',family:'servers',family_label:'Servers',role:'catalog'},compute:{form:'system',category:'excluded'},source_url:'https://www.supermicro.com/',source_sha256:'a'.repeat(64),attachments:[],table_count:i===4?0:1,tables:i===4?[]:[{index:1,section:'界面验证参数（非官方规格）',notes:'仅验证排版，不是生产产品或官方参数。',rows:[[cell('Memory'),cell('验证值 '+i)],[cell('配置列'),{...cell('不自动合成'),colspan:2}]]}]}));
  const series={...models[0],id:'series',name:'验证系列',kind:'family_or_directory',table_count:1};
  const fixture={available:true,company:{label:'Supermicro'},registered_companies:[{id:'supermicro',label:'Supermicro'}],generated_at:'2026-10-07',products:[...models,series],navigation:{groups:[{id:'servers',label:'Servers'}]},coverage:{},summary:{},research_alignment:{target_ids:[],part_ids:[]}};
  let mode='ok',detailFailure=false;
  await page.route('**/api/product-catalog/supermicro*',async r=>{
    const u=new URL(r.request().url()),id=u.searchParams.get('product_id');
    if(id)return detailFailure?r.fulfill({status:503,body:'unavailable'}):r.fulfill({json:{available:true,product:models.find(p=>p.id===id)||series}});
    if(mode==='error')return r.fulfill({status:503,body:'unavailable'});
    if(mode==='empty')return r.fulfill({json:{...fixture,available:false,products:[]}});
    return r.fulfill({json:fixture});
  });
  await page.goto(process.env.UI_BASE_URL+'/company.html?c=supermicro&q=服务器&product_id=fixture-2');
  await page.waitForFunction(()=>document.querySelector('#detail h2')?.textContent==='服务器型号 C');
  assert.match(page.url(),/product-catalog.html/);
  assert.match(await page.locator('.key-parameters').innerText(),/Memory.*验证值 2/s);
  assert.match(await page.locator('#coverage-figure').innerText(),/4\s*\/\s*5/,'series must not inflate named coverage');
  assert.match(await page.locator('#distribution-chart').innerText(),/Servers\s+6/);
  assert.equal(await page.locator('#model-rows input').count(),5);
  assert.equal(await page.locator('#company-meta a').first().getAttribute('href'),'https://supermicro.com/');
  await page.waitForFunction(()=>document.querySelector('#relationship-diagram').textContent.includes('部件'));
  assert.equal(await page.locator('#research-details').isVisible(),false);
  assert.equal(privateRequests.length,0,'anonymous readers never fetch internal annex definitions');
  assert.match(new URL(page.url()).searchParams.get('product_id'),/fixture-2/);
  await page.locator('#model-rows input').nth(0).check();
  await page.locator('#model-rows input').nth(1).check();
  await page.waitForFunction(()=>document.querySelector('#comparison-matrix').textContent.includes('验证值 1'));
  assert.equal(await page.locator('#comparison-matrix tbody tr').count(),1,'merged configuration row cannot be collapsed into a value');
  assert.match(await page.locator('#comparison-matrix').innerText(),/Memory.*验证值 0.*验证值 1/s);
  for(let i=2;i<4;i++)await page.locator('#model-rows input').nth(i).check();
  await page.locator('#model-rows input').nth(4).click();
  assert.equal(await page.locator('#model-rows input:checked').count(),4);
  assert.match(await page.locator('#status').innerText(),/最多/);
  await page.locator('#clear-comparison').click();await page.locator('#comparison').waitFor({state:'hidden'});
  // Independent per-product failure must keep successful index and allow retry.
  detailFailure=true;
  await page.locator('#model-rows [data-product="fixture-4"]').click();
  await page.locator('#retry-detail').waitFor();
  assert.equal(await page.locator('#model-rows input').count(),5);
  detailFailure=false;await page.locator('#retry-detail').click();
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('规格待补齐'));
  // Reload keeps the selected product and filters.
  assert.equal(new URL(page.url()).searchParams.get('q'),'服务器');
  await page.reload();await page.waitForFunction(()=>document.querySelector('#detail h2')?.textContent==='服务器型号 E');
  await page.locator('#query').fill('不存在的型号');assert.equal(await page.locator('#model-rows input').count(),0);
  await page.locator('#query').fill('服务器');
  for(const width of [1440,1280,390,320]){
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no document overflow at '+width);
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#model-rows [data-product="fixture-0"]').click();
  await page.waitForFunction(()=>document.querySelector('.key-parameters')?.textContent.includes('验证值 0'));
  await page.locator('#model-rows input').nth(0).check();await page.locator('#model-rows input').nth(1).check();
  await page.waitForFunction(()=>document.querySelector('#comparison-matrix').textContent.includes('验证值 1'));
  await page.evaluate(()=>{window.scrollTo(0,0);document.querySelector('#company-profile').textContent='界面验证样例 · 以下型号与参数仅验证排版，并非生产目录';});
  if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:process.env.UI_QA_DIR+'/company-desktop.png',fullPage:true});}
  await page.setViewportSize({width:390,height:844});
  if(process.env.UI_QA_DIR)await page.screenshot({path:process.env.UI_QA_DIR+'/company-mobile.png',fullPage:true});
  mode='error';await page.locator('#retry').click();
  await page.waitForFunction(()=>document.querySelector('#coverage-caption').textContent.includes('读取失败'));
  assert.equal(await page.locator('#coverage-figure').innerText(),'—');
  mode='empty';await page.locator('#retry').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('首次交付'));
  assert.match(await page.locator('#coverage-caption').innerText(),/不可计算/);
  assert.equal(await page.locator('#model-rows input').count(),0);
  assert.deepEqual(errors,[]);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
