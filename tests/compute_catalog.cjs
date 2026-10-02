const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const companies=[{id:'nvidia',label:'NVIDIA',country:'US'},{id:'metax',label:'沐曦',country:'CN'},{id:'huawei-ascend',label:'昇腾',country:'CN',parent_company_id:'huawei'},{id:'hygon-dcu',label:'海光 DCU',country:'CN'}];
  const product=(name,category,form,id)=>({id,name,kind:form==='series'?'family_or_directory':'named_product',category:'原厂分类',taxonomy:[{slug:'vendor',name:'原厂系列'}],compute:{category,form,architecture:''},table_count:1,observed_at:'2026-10-02T00:00:00Z'});
  const samples={nvidia:[product('H200','gpu','unknown','nvidia-test')],metax:[product('C500','gpu','board','metax-test')],'huawei-ascend':[product('Atlas 350','accelerator','board','ascend-test')]};
  await page.route('**/api/product-catalog/*',r=>{const c=new URL(r.request().url()).pathname.split('/').pop();return r.fulfill({json:{registered_companies:companies,available:c!=='hygon-dcu',products:samples[c]||[]}});});
  await page.goto(process.env.UI_BASE_URL+'/compute-catalog.html');
  await page.waitForFunction(()=>document.getElementById('compute-status').textContent.includes('已读取 3'));
  assert.equal(await page.locator('#compute-products tr').count(),3);
  await page.locator('#compute-category').selectOption('cpu');assert.match(await page.locator('#compute-counts').innerText(),/条目 0：/);
  await page.locator('#compute-category').selectOption('');
  assert.match(await page.locator('#gaps').innerText(),/海光 DCU：尚未收到目录/);
  await page.locator('#compute-region').selectOption('CN');assert.equal(await page.locator('#compute-products tr').count(),2);
  await page.locator('#compute-category').selectOption('gpu');assert.match(await page.locator('#compute-products').innerText(),/C500/);assert.doesNotMatch(await page.locator('#compute-products').innerText(),/H200|Atlas/);
  assert.match(await page.locator('#compute-products').innerText(),/原厂系列/);
  const download=page.waitForEvent('download');await page.locator('#compute-export').click();assert.equal((await download).suggestedFilename(),'compute-catalog.csv');
  await page.locator('#compute-category').selectOption('accelerator');assert.match(await page.locator('#compute-products').innerText(),/母公司：huawei/);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.ok(await page.locator('.table-wrap').evaluate(el=>el.scrollWidth>el.clientWidth),'mobile table scrolls instead of squeezing names into single characters');
  await page.unroute('**/api/product-catalog/*');await page.route('**/api/product-catalog/*',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.locator('#compute-retry').click();await page.waitForFunction(()=>document.getElementById('compute-status').textContent.includes('读取失败'));
  assert.doesNotMatch(await page.locator('#compute-products').innerText(),/Atlas 350|C500/);
  // A slow initial registry response must not consume the later companies' budget.
  await page.clock.install();await page.unroute('**/api/product-catalog/*');
  const pending=[];
  await page.route('**/api/product-catalog/*',r=>{pending.push(r);});
  await page.locator('#compute-retry').click();
  await page.waitForFunction(()=>document.getElementById('compute-status').textContent.includes('正在读取'));
  while(pending.length<1)await new Promise(r=>setTimeout(r,10));
  await page.clock.runFor(19000);
  await pending.shift().fulfill({json:{registered_companies:companies,available:true,products:samples.nvidia}});
  while(pending.length<3)await new Promise(r=>setTimeout(r,10));
  await page.clock.runFor(2000);
  for(const r of pending.splice(0)){const c=new URL(r.request().url()).pathname.split('/').pop();await r.fulfill({json:{available:c!=='hygon-dcu',products:samples[c]||[]}});}
  await page.waitForFunction(()=>document.getElementById('compute-status').textContent.includes('已读取 3'));
  // A single stalled vendor times out without cancelling a completed vendor.
  await page.locator('#compute-retry').click();
  while(pending.length<1)await new Promise(r=>setTimeout(r,10));
  await pending.shift().fulfill({json:{registered_companies:companies,available:true,products:samples.nvidia}});
  while(pending.length<3)await new Promise(r=>setTimeout(r,10));
  const success=pending.splice(pending.findIndex(r=>r.request().url().includes('/metax?')),1)[0];
  await success.fulfill({json:{available:true,products:samples.metax}});
  await page.clock.runFor(30001);
  await page.waitForFunction(()=>document.getElementById('compute-status').textContent.includes('已读取 2'));
  assert.match(await page.locator('#gaps').innerText(),/昇腾：读取失败/);
  console.log('compute catalog filters, forms, request budgets, failure, export and mobile: OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
