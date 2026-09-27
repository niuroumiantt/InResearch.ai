const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/tco.html');await page.locator('#kpi-lev strong').waitFor();
 const lev=await page.locator('#kpi-lev strong').textContent();assert.match(lev,/^\$\d+\.\d+[MB]$/);
 assert.equal(await page.locator('#kpi-kw strong').textContent(),'$852');
 assert.equal(await page.locator('#kpi-lev .delta').textContent(),'= 基准');
 assert.equal(await page.locator('#presets button.active').count(),1);
 assert.ok((await page.locator('#structure svg rect').count())>=20);assert.ok((await page.locator('#timeline svg rect').count())>=100);
 assert.ok((await page.locator('#cost-table tbody tr').count())>=12);assert.ok((await page.locator('#capex-bars .bar-row').count())===8);
 assert.ok((await page.locator('#tornado svg rect').count())>=20);assert.ok((await page.locator('#scenario-table tbody tr').count())>=6);
 assert.ok((await page.locator('#gap-list tbody tr').count())>=8);assert.ok((await page.locator('#gap-summary').textContent()).includes('作者假设'));
 assert.ok((await page.locator('.benchmark-row').count())>=8);assert.ok((await page.locator('#benchmark-updated').textContent()).includes('价格库更新至 2026-'));
 assert.ok((await page.locator('#benchmark-compare .bench-verdict').textContent()).includes('市场价高于成本'));
 // Site change shows deltas against the baseline everywhere
 await page.locator('#input-site').selectOption('us_texas');
 assert.equal(await page.locator('#input-power_price').inputValue(),'0.071');
 assert.ok((await page.locator('#kpi-lev .delta').textContent()).startsWith('−'));assert.ok((await page.locator('#cost-table tbody tr.total .delta').textContent()).startsWith('−'));
 assert.equal(await page.locator('#presets button.active').count(),0);
 // Capacity change compares per MW by default: a 10 MW build keeps the same per-MW cost, so the levelised delta stays flat
 await page.getByRole('button',{name:'恢复基准情景'}).click();await page.locator('#input-it_mw').fill('10');assert.equal(await page.locator('#kpi-lev .delta').textContent(),'= 基准');assert.ok((await page.locator('#baseline-label').textContent()).includes('100 MW'));
 await page.locator('#compare-mode').selectOption('absolute');assert.ok((await page.locator('#kpi-lev .delta').textContent()).includes('−90.0%'));await page.locator('#compare-mode').selectOption('unit');
 await page.locator('#input-site').selectOption('us_texas');
 // Setting a new baseline zeroes the deltas
 await page.getByRole('button',{name:'把当前设为对比基准'}).click();assert.equal(await page.locator('#kpi-lev .delta').textContent(),'= 基准');
 // Lease preset removes building capex; colo model benchmarks facility-only cost per kW-month
 await page.getByRole('button',{name:'AI 租壳 · 柔佛'}).click();assert.ok((await page.locator('#capex-bars').textContent()).includes('0.00 $M/MW'));
 await page.getByRole('button',{name:'批发托管 · 得州 · 风液混合'}).click();assert.ok((await page.locator('#benchmark-compare').textContent()).includes('$/kW·月'));assert.equal(await page.locator('#kpi-gpu strong').textContent(),'非 GPU');
 await page.getByRole('button',{name:'恢复基准情景'}).click();assert.equal(await page.locator('#kpi-kw strong').textContent(),'$852');
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'tco-desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 if(process.env.UI_QA_DIR)await page.screenshot({path:path.join(process.env.UI_QA_DIR,'tco-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS tco baseline, deltas, charts, presets, gaps and mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
