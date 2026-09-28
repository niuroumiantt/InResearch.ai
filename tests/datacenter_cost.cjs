/* Ledger views 3 and 4: unit cost per effective device hour (the former cost page) and the inverse solve with the scenario grid. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/cost.html');await page.locator('#cost-total').waitFor();await page.waitForFunction(()=>document.getElementById('cost-total').textContent!=='');
 assert.ok(await page.locator('#view-unit.on').isVisible(),'the retired cost address opens the ledger on the unit-cost view');
 // Our 2026-09-14 baseline reproduces on the unified input table
 await page.getByRole('button',{name:'校准 · 我们的 2026-09-14 全成本基准'}).click();
 assert.equal(await page.locator('#cost-total').textContent(),'$1.168B');assert.equal(await page.locator('#cost-per-hour').textContent(),'$4.10');
 assert.equal(await page.locator('#metric-energy').textContent(),'766.5 GWh');assert.equal(await page.locator('#metric-water').textContent(),'490.6k m³');
 assert.ok((await page.locator('#unit-table tbody tr').count())>=6);assert.ok((await page.locator('#return-note').textContent()).includes('自用'));
 // Morgan Stanley preset on the same view: revenue $2.291B against a $3.57 all-in hour
 await page.getByRole('button',{name:'校准 · 摩根士丹利 1GW GB300 出租'}).click();
 assert.equal(await page.locator('#return-revenue').textContent(),'$2.291B');assert.equal(await page.locator('#cost-per-hour').textContent(),'$3.57');
 assert.ok((await page.locator('#return-surplus').textContent()).startsWith('+$4.93'));
 // Inverse view: Goldman's hurdle gives 11.6 bn/GW at 34.6% EBIT margin; the grid marks both anchors
 await page.locator('#views button[data-view=inverse]').click();await page.locator('#view-inverse.on').waitFor();
 await page.getByRole('button',{name:'校准 · 高盛 15% 回报门槛'}).click();
 assert.equal(await page.locator('#inv-revenue strong').textContent(),'$11.65B');
 assert.ok((await page.locator('#inv-revenue .sub').textContent()).includes('EBIT 利润率 34.6%'));
 assert.ok((await page.locator('#inv-line').textContent()).includes('平均年资本开支 = 总额 ÷ 2 年'));
 assert.equal(await page.locator('#grid-table tbody tr').count(),5);assert.equal(await page.locator('#grid-table tbody td').count(),25);
 assert.ok((await page.locator('#grid-table td.anchor').count())>=1,'the report anchors are marked on the grid');
 await page.locator('#grid-util').selectOption('0');assert.equal(await page.locator('#grid-table tbody td').count(),25);
 // Back on the baseline the inverse solve reports how far current revenue is from the hurdle
 await page.getByRole('button',{name:'恢复基准'}).click();assert.match(await page.locator('#inv-price strong').textContent(),/^\$\d+\.\d\d\/h$/);
 assert.match(await page.locator('#inv-gap').textContent(),/当前收入(超过|比目标少)/);
 assert.ok((await page.locator('#gap-list tbody tr').count())>=8);assert.ok((await page.locator('#gap-summary').textContent()).includes('作者假设'));
 assert.ok((await page.locator('.benchmark-row').count())>=8);assert.ok((await page.locator('#benchmark-updated').textContent()).includes('价格库更新至 2026-'));
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'ledger-inverse-desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);console.log('PASS ledger unit-cost and inverse views: 2026-09-14 baseline, MS revenue, GS hurdle, grid anchors, gaps, benchmarks, mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
