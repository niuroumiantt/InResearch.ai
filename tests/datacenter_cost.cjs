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
 assert.equal(await page.locator('#return-revenue').textContent(),'—');assert.ok((await page.locator('.benchmark-row').count())>=5);
 await page.getByRole('button',{name:'GB300 出租参照（100MW 折算）'}).click();
 assert.equal(await page.locator('#cost-per-hour').textContent(),'$3.57');assert.equal(await page.locator('#return-revenue').textContent(),'$2.291B');
 assert.equal(await page.locator('#return-surplus-hour').textContent(),'+$4.93/h');assert.equal(await page.locator('#return-coverage').textContent(),'238%');
 assert.ok((await page.locator('#preset-note').textContent()).includes('摩根士丹利'));
 await page.getByRole('button',{name:'H100 合约租金参照'}).click();assert.equal(await page.locator('#return-surplus-hour').textContent(),'−$1.70/h');
 await page.getByRole('button',{name:'恢复研究基准'}).click();assert.equal(await page.locator('#return-revenue').textContent(),'—');
 await page.locator('#input-productive').fill('32.5');assert.equal(await page.locator('#cost-per-hour').textContent(),'$8.20');
 await page.getByRole('button',{name:'恢复研究基准'}).click();assert.equal(await page.locator('#cost-per-hour').textContent(),'$4.10');
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 if(process.env.UI_QA_DIR)await page.screenshot({path:path.join(process.env.UI_QA_DIR,'cost-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS cost baseline, formula, sensitivity, reset and mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
