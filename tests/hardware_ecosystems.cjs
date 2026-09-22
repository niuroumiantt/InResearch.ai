const {chromium}=require('playwright'); const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
 const p=await b.newPage({viewport:{width:1440,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const base=process.env.UI_BASE_URL||'http://127.0.0.1:8881';
 await p.goto(base+'/research.html?node=ecosystem:storage&view=R&tab=overview');await p.locator('.rg-node h2').waitFor();await p.locator('.rg-workbench-overview > summary').click();await p.locator('#researchHardware').waitFor();
 assert.equal(await p.locator('#researchHardware button').count(),8);assert.match(await p.locator('.rg-section').innerText(),/SSD 内部研究/);
 await p.locator('.rg-overview-group').getByRole('button',{name:'NAND 闪存',exact:true}).click();assert.match(p.url(),/part%3Anand/);assert.equal(await p.getByRole('button',{name:'以 NAND 单元类型 为中心',exact:true}).count(),1);
 await p.goto(base+'/research.html?node=part:cpu&view=P&tab=overview');await p.locator('.rg-overview-group').waitFor();assert.equal(await p.locator('.rg-overview-group button').count(),4);
 await p.goto(base+'/research.html?node=part:ssd-drive&view=R&tab=products');await p.locator('.rg-product-card').first().waitFor();assert.ok(await p.locator('.rg-vendor-index button').count()>5);
 await p.locator('.rg-vendor-index button').last().click();assert.equal(await p.evaluate(()=>document.activeElement.classList.contains('rg-product-card')),true);
 await p.goto(base+'/research.html?node=part:ssd&view=P&tab=relations');await p.locator('.rg-node h2').waitFor();assert.equal(await p.locator('.rg-node h2').innerText(),'SSD 固态硬盘');assert.match(p.url(),/part%3Assd-drive/);
 for(const mode of ['light','dark']){await p.locator('#ui-appearance').selectOption(mode);await p.goto(base+'/research.html?node=ecosystem:storage&view=R&tab=overview');await p.locator('.rg-section').waitFor();await p.screenshot({path:'/tmp/hardware-'+mode+'.png',fullPage:true});await p.setViewportSize({width:360,height:800});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.setViewportSize({width:1440,height:1000});}
 assert.deepEqual(errors,[]);console.log('PASS ecosystem drilldown, CPU depth, vendor jump, legacy links, skins and mobile');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
