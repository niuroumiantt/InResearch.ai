const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));const base=process.env.UI_BASE_URL||'http://127.0.0.1:8883';
const start=()=>page.goto(base+'/research.html?node=part:ssd-drive&view=R&tab=network');
await start();const node=()=>page.locator('.rg-network-node[data-node-id="part:hdd"]');const popup=()=>page.getByRole('dialog',{name:'产品厂商入口'});
await node().hover();await popup().waitFor();for(const name of ['希捷','西部数据','东芝电子'])assert.equal(await popup().getByRole('button',{name,exact:true}).count(),1);
await popup().getByRole('button',{name:'希捷',exact:true}).click();await page.locator('.rg-product-card[data-company-id="seagate"]').waitFor();assert.equal(await page.locator('.rg-product-card').count(),1);assert.ok(page.url().includes('company=seagate'));assert.equal(await page.locator('.rg-node h2').textContent(),'近线HDD');
await page.reload();await page.locator('.rg-product-card').first().waitFor();assert.equal(await page.locator('.rg-product-card').count(),1);assert.equal(await page.getByRole('combobox',{name:'按厂商筛选产品线'}).inputValue(),'seagate');
await start();await node().click();await page.locator('.rg-network-center[data-node-id="part:hdd"]').waitFor();assert.ok(page.url().includes('node=part%3Ahdd'));assert.equal(await page.locator('.rg-node h2').textContent(),'近线HDD');
await start();await node().focus();await node().press('ArrowDown');assert.ok(await popup().isVisible());assert.ok(await popup().evaluate(e=>e.contains(document.activeElement)));await page.keyboard.press('Escape');assert.ok(!await popup().isVisible());
// Keep long menus inside the visible viewport, including after scrolling/resizing.
await start();const center=page.locator('.rg-network-center[data-node-id="part:ssd-drive"]');
await center.waitFor();await center.evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().bottom-innerHeight+50));
await center.focus();await center.press('ArrowDown');await popup().waitFor();
async function inside(){const b=await popup().boundingBox();const v=page.viewportSize();assert.ok(b&&b.x>=7&&b.y>=7&&b.x+b.width<=v.width-7&&b.y+b.height<=v.height-7,JSON.stringify({b,v}));}
await inside();await page.screenshot({path:'/tmp/compact-ui-viewport.png'});assert.ok((await popup().boundingBox()).y<(await center.boundingBox()).y,'bottom menu flips above node');
await page.evaluate(()=>window.scrollBy(0,80));await page.waitForTimeout(80);await inside();
await page.setViewportSize({width:1000,height:720});await page.waitForTimeout(80);if(await popup().isVisible())await inside();
assert.equal(await center.locator('rect').first().evaluate(e=>getComputedStyle(e).vectorEffect),'non-scaling-stroke');
assert.equal(await center.locator('rect').first().evaluate(e=>getComputedStyle(e).strokeWidth),'1px');
await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(80);assert.ok(!await popup().isVisible(),'offscreen anchor closes menu');
await page.setViewportSize({width:390,height:844});await start();await page.getByRole('button',{name:'查看 近线HDD 厂商',exact:true}).click();await popup().waitFor();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await popup().getByRole('button',{name:'东芝电子',exact:true}).click();await page.locator('.rg-product-card[data-company-id="toshiba-electronic-devices"]').waitFor();
assert.deepEqual(errors,[]);console.log('PASS hover manufacturers, HDD navigation, vendor filter reload, keyboard Escape, touch and mobile');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
