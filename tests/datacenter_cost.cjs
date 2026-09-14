const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/cost.html');await page.locator('#cost-total').waitFor();
 assert.equal(await page.locator('#cost-total').textContent(),'$1.168B');assert.equal(await page.locator('#cost-per-hour').textContent(),'$4.10');
 assert.equal(await page.locator('#metric-energy').textContent(),'766.5 GWh');
 assert.equal(await page.locator('#metric-water').textContent(),'490.6k m³');
 assert.equal(await page.locator('.bar-row').count(),8);assert.equal(await page.locator('.matrix td').count(),18);
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'cost-desktop.png'),fullPage:true});}
 await page.locator('#input-productive').fill('32.5');assert.equal(await page.locator('#cost-per-hour').textContent(),'$8.20');
 await page.getByRole('button',{name:'恢复研究基准'}).click();assert.equal(await page.locator('#cost-per-hour').textContent(),'$4.10');
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 if(process.env.UI_QA_DIR)await page.screenshot({path:path.join(process.env.UI_QA_DIR,'cost-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS cost baseline, formula, sensitivity, reset and mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
