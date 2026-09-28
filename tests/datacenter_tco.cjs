/* Ledger view 1: cost structure and levelised cost (the former TCO page). /tco.html now serves the ledger on that view. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL||'http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/tco.html');await page.locator('#kpi-lev strong').waitFor();
 assert.ok(await page.locator('#view-lifecycle.on').isVisible(),'the retired TCO address opens the ledger on the lifecycle view');
 const lev=await page.locator('#kpi-lev strong').textContent();assert.match(lev,/^\$\d+\.\d+[MB]$/);
 assert.equal(await page.locator('#kpi-kw strong').textContent(),'$851','baseline levelised cost per kW·month');
 assert.equal(await page.locator('#presets button.active').count(),1);assert.equal(await page.locator('#presets button.active').textContent(),'基准 · AI 自建 · 北弗吉尼亚');
 assert.ok((await page.locator('#structure svg rect').count())>=10);assert.ok((await page.locator('#timeline svg rect').count())>=100);
 assert.ok((await page.locator('#cost-table tbody tr').count())>=12);assert.equal(await page.locator('#capex-bars .bar-row').count(),10);
 assert.ok((await page.locator('#tornado svg rect').count())>=20);assert.ok((await page.locator('#scenario-table tbody tr').count())>=12);
 assert.ok((await page.locator('#benchmark-compare .bench-verdict').textContent()).includes('市场价高于成本'));
 assert.ok((await page.locator('#timeline-note').textContent()).includes('利用率爬坡 60%/80%'),'revenue-side utilization ramp is separate from the load ramp');
 assert.ok((await page.locator('#kpi-capex .sub').textContent()).includes('拿地到投运 48 个月'),'permit + gate wait + construction');
 // Region switch resets the sourced site numbers and marks the gaps
 await page.locator('#input-site').selectOption('us_texas');
 assert.equal(await page.locator('#input-power_price').inputValue(),'0.0707');assert.equal(await page.locator('#presets button.active').count(),0);
 assert.ok((await page.locator('#region-card .gap-count').textContent()).startsWith('缺'),'Texas still has author placeholders');
 await page.locator('#input-site').selectOption('malaysia_johor');assert.ok((await page.locator('#model-inputs em.gap').count())>=10,'Johor marks its missing numbers');
 // Chip-gated BOT in Inner Mongolia: shorter lead time, partner-held M&E
 await page.getByRole('button',{name:'AI · 内蒙古 · BOT · 芯片门槛'}).click();
 assert.ok((await page.locator('#kpi-capex .sub').textContent()).includes('拿地到投运 16 个月'));
 assert.ok((await page.locator('#capex-note').textContent()).includes('合作方持有机电'));
 assert.equal(await page.locator('#input-gate').inputValue(),'chip');
 // Capex basis switch: generation table instead of parts
 await page.getByRole('button',{name:'恢复基准'}).click();await page.locator('#input-capex_basis').selectOption('generation');
 assert.ok((await page.locator('#capex-note').textContent()).startsWith('按代际'));
 await page.getByRole('button',{name:'批发托管 · 得州 · 风液混合'}).click();assert.ok((await page.locator('#benchmark-compare').textContent()).includes('$/kW·月'));assert.equal(await page.locator('#kpi-gpu strong').textContent(),'非 GPU');
 await page.getByRole('button',{name:'恢复基准'}).click();assert.equal(await page.locator('#kpi-kw strong').textContent(),'$851');
 if(process.env.UI_QA_DIR){fs.mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.UI_QA_DIR,'ledger-lifecycle-desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 if(process.env.UI_QA_DIR)await page.screenshot({path:path.join(process.env.UI_QA_DIR,'ledger-lifecycle-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS ledger lifecycle view: baseline, regions and gaps, BOT and chip gate, capex basis, colo benchmark, mobile');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
