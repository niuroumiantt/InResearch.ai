const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));const base=process.env.UI_BASE_URL||'http://127.0.0.1:8883';
const start=()=>page.goto(base+'/research.html?node=part:ssd-drive&view=R&tab=network');
await start();const node=()=>page.locator('.rg-network-node[data-node-id="part:hdd"]');const popup=()=>page.getByRole('dialog',{name:'产品厂商入口'});
await node().hover();await popup().waitFor();for(const name of ['希捷','西部数据','东芝电子'])assert.equal(await popup().getByRole('button',{name,exact:true}).count(),1);
await popup().getByRole('button',{name:'希捷',exact:true}).click();await page.locator('.rg-product-card[data-company-id="seagate"]').waitFor();assert.equal(await page.locator('.rg-product-card').count(),1);assert.ok(page.url().includes('company=seagate'));assert.equal(await page.locator('.rg-node h2').textContent(),'近线HDD');
await page.reload();await page.locator('.rg-product-card').first().waitFor();assert.equal(await page.locator('.rg-product-card').count(),1);assert.equal(await page.getByRole('combobox',{name:'按厂商筛选产品线'}).inputValue(),'seagate');
await start();await node().click();await page.locator('.rg-network-center[data-node-id="part:hdd"]').waitFor();assert.ok(page.url().includes('node=part%3Ahdd'));assert.equal(await page.locator('.rg-node h2').textContent(),'近线HDD');
await start();await node().focus();await node().press('ArrowDown');assert.ok(await popup().isVisible());assert.ok(await popup().evaluate(e=>e.contains(document.activeElement)));await page.keyboard.press('Escape');assert.ok(!await popup().isVisible());
await page.setViewportSize({width:390,height:844});await start();await page.getByRole('button',{name:'查看 近线HDD 厂商',exact:true}).click();await popup().waitFor();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await popup().getByRole('button',{name:'东芝电子',exact:true}).click();await page.locator('.rg-product-card[data-company-id="toshiba-electronic-devices"]').waitFor();
assert.deepEqual(errors,[]);console.log('PASS hover manufacturers, HDD navigation, vendor filter reload, keyboard Escape, touch and mobile');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
