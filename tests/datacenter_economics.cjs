const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/economics.html');await page.locator('#kpi-compute').waitFor();await page.waitForFunction(()=>document.getElementById('kpi-compute').textContent!=='—');
 // Morgan Stanley GB300 leasing calibration (100 MW): ROIC 31%, breakeven $3.57, revenue $2.29B, NOPAT $1.20B
 assert.equal(await page.locator('#kpi-compute').textContent(),'30.9%');
 assert.ok((await page.locator('#kpi-compute-sub').textContent()).includes('$3.57/h'));
 assert.ok((await page.locator('#waterfall-note').textContent()).includes('ROIC 30.9%'));
 assert.equal(await page.locator('#presets button.active').count(),1);
 assert.ok((await page.locator('#capex-stack svg rect').count())>=20);assert.ok((await page.locator('#waterfall svg rect').count())>=8);
 assert.equal(await page.locator('.split-row').count(),4);assert.ok((await page.locator('#tornado svg rect').count())>=14);
 assert.equal(await page.locator('#heatmap td').count(),30);assert.ok((await page.locator('#scenario-table tbody tr').count())>=6);
 assert.ok((await page.locator('.benchmark-row').count())>=10);assert.ok((await page.locator('#benchmark-updated').textContent()).includes('价格库更新至 2026-'));
 // Model API own infrastructure: NOPAT margin ~59%, ROIC ~46%
 await page.getByRole('button',{name:'模型 API · 自有基础设施'}).click();
 assert.ok((await page.locator('#kpi-model-sub').textContent()).includes('ROIC 46.'));
 // Powered shell: 19% yield on cost; landlord row appears in the split
 await page.getByRole('button',{name:'带电壳三净租约（矿企转型）'}).click();
 assert.equal(await page.locator('#kpi-shell').textContent(),'19.0%');
 assert.ok((await page.locator('#shell-table').textContent()).includes('DSCR'));assert.ok((await page.locator('#shell-table').textContent()).includes('含 15 年期权'));assert.ok((await page.locator('#shell-table').textContent()).includes('税后'));
 await page.getByRole('button',{name:'新兴云 H100 租壳（2026 合约价）'}).click();assert.ok((await page.locator('#compute-table').textContent()).includes('租金年变动 -10.0%'));assert.ok((await page.locator('#compute-table').textContent()).includes('0.41×'));
 // China colocation: 11% yield
 await page.getByRole('button',{name:'中国托管（万国数据口径）'}).click();assert.equal(await page.locator('#kpi-shell').textContent(),'11.0%');
 // Changing an input drops the preset highlight and recomputes
 await page.getByRole('button',{name:'恢复研报基准'}).click();assert.equal(await page.locator('#kpi-compute').textContent(),'30.9%');
 await page.locator('#input-gpu_price').fill('7');assert.equal(await page.locator('#presets button.active').count(),0);assert.equal(await page.locator('#kpi-compute').textContent(),'22.7%');
 await page.locator('#input-generation').selectOption('h100');assert.equal(await page.locator('#input-gpus_per_mw').inputValue(),'635.3');
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'economics-desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 if(process.env.UI_QA_DIR)await page.screenshot({path:path.join(process.env.UI_QA_DIR,'economics-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS economics calibration, presets, charts, inputs and mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
