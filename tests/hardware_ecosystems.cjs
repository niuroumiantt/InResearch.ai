const {chromium}=require('playwright'); const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({channel:'chrome',headless:true});try{
 const p=await b.newPage({viewport:{width:1440,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const base=process.env.UI_BASE_URL||'http://127.0.0.1:8881';
 await p.goto(base+'/research.html?node=ecosystem:storage&view=R');await p.locator('#researchHardware').waitFor();
 assert.equal(await p.locator('#researchHardware button').count(),8);assert.match(await p.locator('.rg-section').innerText(),/SSD 内部研究/);
 await p.locator('.rg-overview-group').getByRole('button',{name:'NAND 闪存',exact:true}).click();assert.match(p.url(),/part%3Anand/);assert.match(await p.locator('.rg-section').innerText(),/NAND 单元类型/);
 await p.goto(base+'/research.html?node=part:cpu&view=P');await p.locator('.rg-overview-group').waitFor();assert.equal(await p.locator('.rg-overview-group button').count(),4);
 await p.goto(base+'/research.html?node=part:ssd-drive&view=R&tab=products');await p.locator('.rg-product-card').first().waitFor();assert.ok(await p.locator('.rg-vendor-index button').count()>5);
 await p.locator('.rg-vendor-index button').last().click();assert.equal(await p.evaluate(()=>document.activeElement.classList.contains('rg-product-card')),true);
 await p.goto(base+'/research.html?node=part:ssd&view=P&tab=relations');await p.locator('.rg-node h2').waitFor();assert.match(await p.locator('.rg-node h2').innerText(),/历史合并入口/);
 for(const skin of ['folk','Attio']){await p.getByRole('button',{name:skin,exact:true}).click();await p.goto(base+'/research.html?node=ecosystem:storage&view=R');await p.locator('.rg-section').waitFor();await p.screenshot({path:'/tmp/hardware-'+skin+'.png',fullPage:true});await p.setViewportSize({width:360,height:800});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.setViewportSize({width:1440,height:1000});}
 assert.deepEqual(errors,[]);console.log('PASS ecosystem drilldown, CPU depth, vendor jump, legacy links, skins and mobile');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
