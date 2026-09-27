const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const cell=(text,colspan=1)=>({text,colspan,rowspan:1,header:false});
  const product={id:'nvidia-aaaaaaaaaaaaaaaaaaaa',name:'NVIDIA H200',category:'Data Center',kind:'named_product',observed_at:'2026-09-27',source_url:'https://www.nvidia.com/en-us/data-center/h200/',source_sha256:'a'.repeat(64),attachments:[],tables:[{index:1,section:'Specifications',notes:'* Sparse, per GPU',rows:[[cell(''),cell('SXM'),cell('NVL')],[cell('Memory'),cell('141 GB',2)]]}]};
  await page.route('**/api/product-catalog/nvidia',r=>r.fulfill({json:{available:true,generated_at:'2026-09-27',coverage:{directory_entries:48,entity_counts:{named_product:1},with_spec_tables:1,pending_pages:4,failed_pages:0,limitations:['Not exhaustive']},products:[product]}}));
  await page.goto(process.env.UI_BASE_URL+'/product-catalog.html');
  await page.getByRole('heading',{name:'NVIDIA H200',exact:true}).waitFor();
  assert.match(await page.locator('#detail').innerText(),/141 GB/);
  assert.equal(await page.locator('#detail td[colspan="2"]').innerText(),'141 GB');
  assert.match(await page.locator('#detail').innerText(),/Sparse/);
  await page.locator('#compare').click();assert.equal(await page.locator('#comparison').isVisible(),true);
  await page.locator('#query').fill('unmatched');assert.match(await page.locator('#matches').innerText(),/^0/);
  await page.locator('#query').fill('H200');assert.match(await page.locator('#export-specs').getAttribute('href'),/q=h200/);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.unroute('**/api/product-catalog/nvidia');
  await page.route('**/api/product-catalog/nvidia',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.locator('#retry').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('暂时不可用'));
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
