/* Read the whole system before its parts; exercise real skeleton navigation and layout. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
const bom=require('../framework/bom.json');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.UI_BASE_URL+'/bom.html');
  await page.locator('.equipment[data-part="ssd"]').waitFor();
  await page.evaluate(()=>document.fonts.ready);
  const physical=bom.parts.filter(p=>(p.kind||'part')==='part');
  assert.equal(await page.locator('.equipment').count(),physical.length);
  assert.equal(await page.locator('[data-overview-system]').count(),5);
  assert.equal(await page.locator('.it-branches a').count(),4);
  assert.ok(await page.locator('#detail-panel').evaluate(e=>e.hidden));
  assert.ok(await page.locator('#overview').evaluate(e=>!!(e.compareDocumentPosition(document.querySelector('.equipment'))&Node.DOCUMENT_POSITION_FOLLOWING)));
  for(const width of [1920,1440,1280,900,390,320]){
   await page.setViewportSize({width,height:1000});
   for(const mode of ['light','dark']){
    await page.locator('#ui-appearance').selectOption(mode);
    const layout=await page.evaluate(()=>{
     const wrap=document.querySelector('.wrap').getBoundingClientRect(),stack=document.getElementById('stack').getBoundingClientRect();
     return {width:document.documentElement.scrollWidth,viewport:innerWidth,wrap:wrap.width,stack:stack.width,columns:getComputedStyle(document.querySelector('.chain-grid')).gridTemplateColumns.split(' ').length};
    });
    assert.ok(layout.width<=width,`${width}/${mode} no page overflow`);
    assert.ok(layout.stack>layout.wrap*.9,`${width}/${mode} no reserved empty sidebar`);
    assert.equal(layout.columns,width>900?2:1);
    if(process.env.REVIEW_SCREENSHOTS && [1440,390,320].includes(width)){
     await page.evaluate(()=>scrollTo(0,0));
     await page.screenshot({path:path.join(process.env.REVIEW_SCREENSHOTS,`bom-layout-${width}-${mode}.png`)});
    }
   }
  }
  // Top diagram links must land below both sticky navigation rows on a phone.
  for(const id of ['facility','power','thermal','it','control']){
   await page.locator(`[data-overview-system="${id}"]`).click();
   await page.waitForFunction(id=>location.hash==='#system-'+id,id);
   const pos=await page.locator('#system-'+id+' .sysh').boundingBox();
   const bar=await page.locator('.system-index').boundingBox();
   assert.ok(pos.y>=bar.y+bar.height-1,`${id} heading not hidden by sticky index`);
  }
  await page.locator('.it-branches a[href="#it-memory"]').click();
  assert.equal(new URL(page.url()).hash,'#it-memory');
  await page.locator('.equipment[data-part="ssd"]').click();
  await page.locator('#selected-atlas .technical-atlas').waitFor();
  assert.ok(await page.locator('#detail-panel').isVisible());
  assert.ok(await page.locator('#selected-atlas').evaluate(e=>e.nextElementSibling.id==='detail-panel'));
  await page.keyboard.press('Escape');
  assert.ok(await page.locator('#detail-panel').evaluate(e=>e.hidden));
  assert.ok(await page.locator('#selected-atlas').evaluate(e=>e.hidden));
  assert.equal(new URL(page.url()).hash,'');
  assert.equal(await page.locator('.equipment[data-part="ssd"]').evaluate(e=>document.activeElement===e),true);
  await page.locator('[data-mode="scale"]').click();
  assert.ok(await page.locator('#scale-map').isVisible());
  assert.ok(await page.locator('#system-map').evaluate(e=>e.hidden));
  assert.equal(await page.locator('#scale-map a').count(),bom.scales.length);
  await page.locator('#scale-map a[href="#scale-S3"]').click();
  assert.equal(new URL(page.url()).hash,'#scale-S3');
  await page.locator('[data-mode="system"]').click();
  assert.equal(await page.locator('.equipment').count(),physical.length);
  assert.deepEqual(errors,[]);
  console.log('PASS BOM layout: overview, full-width content, 6 widths × light/dark, navigation, inline detail and Escape');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
