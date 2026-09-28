/* Ledger view 2: the four ledgers (the former economics page). /economics.html now serves the ledger on that view. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/economics.html');await page.locator('#kpi-compute strong').waitFor();
 assert.ok(await page.locator('#view-ledgers.on').isVisible(),'the retired economics address opens the ledger on the four-ledger view');
 // Calibration table: the three anchors reproduce their registered values
 assert.ok((await page.locator('#calibration-table tbody tr').count())>=8);
 assert.equal(await page.locator('#calibration-table .flag.no').count(),0,'every calibration anchor reproduces');
 assert.equal(await page.locator('#calibration-table .flag.ok').count(),await page.locator('#calibration-table tbody tr').count());
 // Morgan Stanley preset: ROIC 31% on total capex, breakeven $3.57/h
 await page.getByRole('button',{name:'校准 · 摩根士丹利 1GW GB300 出租'}).click();
 assert.equal(await page.locator('#kpi-compute strong').textContent(),'30.9%');
 assert.ok((await page.locator('#kpi-compute .sub').textContent()).includes('$3.57/h'));
 assert.ok((await page.locator('#waterfall-note').textContent()).includes('ROIC 30.9%'));
 assert.ok((await page.locator('#capex-stack svg rect').count())>=3);assert.equal(await page.locator('#ledger-table tbody tr').count(),4);
 // Denominator switch: Goldman's average annual capex doubles the ROIC of the same year
 await page.locator('#model-inputs details[data-group=actor] summary').click();await page.locator('#input-roic_basis').selectOption('avg_annual_capex');assert.equal(await page.locator('#kpi-compute strong').textContent(),'61.7%');
 assert.ok((await page.locator('#kpi-compute small').textContent()).includes('平均年资本开支'));
 // Model company on rented compute and the landlord ledger stay on the same input table
 await page.getByRole('button',{name:'模型 API · 租用算力'}).click();assert.match(await page.locator('#kpi-model strong').textContent(),/^\d+\.\d%$/);
 await page.getByRole('button',{name:'带电壳三净租约（矿企转型）'}).click();assert.match(await page.locator('#kpi-shell strong').textContent(),/^\d+\.\d%$/);
 assert.ok((await page.locator('#kpi-shell .sub').textContent()).includes('DSCR'));
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'ledger-ledgers-desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);console.log('PASS ledger four-ledger view: calibration anchors, MS 31%, denominator switch, model and shell presets, mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
