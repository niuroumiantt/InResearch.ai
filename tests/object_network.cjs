const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{const b=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});try{
 const p=await b.newPage({viewport:{width:1440,height:1100},acceptDownloads:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));const base=process.env.UI_BASE_URL||'http://127.0.0.1:8882';
 const center=()=>p.locator('.rg-network-center');
 await p.goto(base+'/research.html?node=part:server&view=R');await center().waitFor();assert.equal(await center().getAttribute('data-node-id'),'part:server');
 await p.getByRole('button',{name:'以 SSD 固态硬盘 为中心',exact:true}).click();assert.equal(await center().getAttribute('data-node-id'),'part:ssd-drive');assert.match(p.url(),/tab=network/);
 for(const name of ['NAND 闪存','SSD 控制器','SSD 固件与 FTL','SSD 电路板与板级器件'])assert.equal(await p.getByRole('button',{name:'以 '+name+' 为中心',exact:true}).count(),1);
 await p.getByRole('button',{name:'以 NAND 闪存 为中心',exact:true}).press('Enter');assert.equal(await center().getAttribute('data-node-id'),'part:nand');
 await p.getByRole('button',{name:'后退一步',exact:true}).click();assert.equal(await center().getAttribute('data-node-id'),'part:ssd-drive');
 await p.getByRole('button',{name:'以 NAND 闪存 为中心',exact:true}).click();await p.reload();await center().waitFor();assert.equal(await center().getAttribute('data-node-id'),'part:nand');
 await p.getByLabel('图谱关系筛选').selectOption('topics');assert.equal(await p.locator('.rg-network-node:not(.rg-network-center)').count(),9);
 await p.getByRole('button',{name:'研究角度：市场规模与周期',exact:true}).click();assert.match(p.url(),/topic=T05/);assert.match(await p.locator('.rg-section').innerText(),/此角度尚无已分类问题/);
 await p.goto(base+'/research.html?node=part:ssd-drive&view=R');await center().waitFor();
 const dl=p.waitForEvent('download');await p.getByRole('button',{name:'导出本页 SVG',exact:true}).click();const d=await dl;await d.saveAs('/tmp/ssd-research-network.svg');const xml=fs.readFileSync('/tmp/ssd-research-network.svg','utf8');assert.match(xml,/<metadata>/);assert.match(xml,/part:ssd-controller/);assert.match(xml,/research_navigation/);assert.doesNotMatch(xml,/var\(--/);
 for(const skin of ['folk','Attio']){await p.getByRole('button',{name:skin,exact:true}).click();assert.equal(await p.locator('.rg-network-center rect').evaluate(e=>getComputedStyle(e).rx),skin==='folk'?'0px':'8px');await p.locator('.rg-section').screenshot({path:'/tmp/ssd-network-'+skin+'.png'});}
 await p.setViewportSize({width:360,height:800});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.ok(await p.locator('.rg-network-canvas').evaluate(e=>e.scrollWidth>e.clientWidth));
 await p.goto(base+'/research.html?node=ecosystem:compute&view=R');await center().waitFor();assert.ok(await p.locator('.rg-network-node:not(.rg-network-center)').count()<=12);await p.getByRole('button',{name:'下一页',exact:true}).click();assert.match(await p.locator('.rg-section').innerText(),/第 2\//);
 const isolated=await p.evaluate(async()=>{const {objectNetwork}=await import('/assets/object-network.js');const g={objects:[{id:'a'},{id:'b'},{id:'c'}],relations:[{id:'ab',source:'a',target:'b',type:'uses',evidence_ids:['e1']},{id:'bc',source:'b',target:'c',type:'uses'}]};return {a:objectNetwork(g,'a'),b:objectNetwork(g,'b'),missing:objectNetwork(g,'missing')};});
 assert.deepEqual(isolated.a.nodes.map(n=>n.id),['b']);assert.equal(isolated.b.edges[0].source,'a');assert.deepEqual(isolated.b.edges[0].evidence_ids,['e1']);assert.equal(isolated.missing.center,null);
 assert.deepEqual(errors,[]);console.log('PASS server→SSD→NAND, keyboard, back, reload, topics, SVG, skins, mobile, pagination');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
