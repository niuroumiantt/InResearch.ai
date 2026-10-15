/* Dashboard: one tree, five columns, four questions. Root matrix, system drill-down, part page, no page errors. */
const {chromium}=require('playwright');const assert=require('assert');
(async()=>{
 const base=process.env.UI_BASE_URL||'http://127.0.0.1:8882';
 const browser=await chromium.launch();const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/research-workbench.html');await page.locator('#matrix tbody tr').first().waitFor();
 assert.equal(await page.locator('#matrix tbody tr:visible').count(),6,'five systems plus the site-rights row; IT collapsed');
 assert.equal(await page.locator('#matrix td.cell').count(),55,'eleven rows (IT and storage descendants hidden) by five variable classes');
 await page.locator('#matrix .it-toggle').click();await page.locator('#matrix.it-open').waitFor();
 assert.equal(await page.locator('#matrix tbody tr:visible').count(),11,'IT expands into three subsystems and storage into two');
 assert.equal(await page.locator('#matrix a[href="research-workbench.html?id=system%3Astorage-group"]').count()>0,true);
 assert.equal(await page.locator('.acct').count(),3,'cost, revenue and return above the five columns');
 assert.equal(await page.locator('#five .col').count(),5);
 assert.equal(await page.locator('#account a[href="ledger.html"]').count(),1,'price column links to the one ledger expansion');
 await page.locator('#grid .board').waitFor();
 assert.match(await page.locator('#grid .board').innerText(),/目标表就是任务书/,'delivery board reads the target table, not workorders');
 assert.equal(await page.locator('#readings a').count(),4,'four readings (build / compose / operate / earn) under the account');
 assert.match(await page.locator('#matrix thead th').nth(1).innerText(),/目标 已有 \d+ · 缺 \d+/,'column coverage in the matrix header');
 assert.equal(await page.locator('.acct .evidence').count(),3,'each ledger level shows the evidence status of its inputs');
 assert.ok(await page.locator('#news').isVisible(),'news timeline on the root node');
 for(const id of ['p1','p2','p3','p4'])assert.ok(await page.locator('#'+id+' > h2').isVisible(),id);
 assert.ok((await page.locator('#matrix td.cell.needed').count())>0,'grey cells are the acquisition worklist');
 assert.ok((await page.locator('#matrix td.cell.registered').count())>0,'our own counts (parts, suppliers) are registered, never sourced');
 assert.equal(await page.locator('#matrix td.cell.sourced .c').filter({hasText:/部件数|供应商数|权利条目|持有方/}).count(),0,'no count cell is painted green');
 assert.match(await page.locator('#p2 .cov').last().innerText(),/已交付、未成序列.*只有登记数/,'legend names the four states plus registered');
 await page.locator('#targets table tbody tr').first().waitFor({state:'attached'});
 assert.equal(await page.locator('#targets td').filter({hasText:'待建队'}).count(),0,'all six actual channels are connected; scope is not adoption');
 // Preserve the disconnected deadline guard with an explicit isolated target policy.
 const disconnectedTargets=await (await page.request.get(base+'/data/tco_targets.json')).json();
 const disconnectedQuote=disconnectedTargets.targets.find(t=>t.team==='fetchquotes');assert.ok(disconnectedQuote);
 const previousDue=disconnectedQuote.next_due;assert.ok(previousDue);
 disconnectedQuote.team_state='not_connected';disconnectedQuote.next_due=null;
 await page.route('**/data/tco_targets.json*',route=>route.fulfill({json:disconnectedTargets}));
 await page.reload();await page.locator('#targets table tbody tr').first().waitFor({state:'attached'});
 await page.locator('#targets > details > summary').click();
 const disconnectedRow=page.locator('#targets table tbody tr').filter({has:page.getByText(disconnectedQuote.id,{exact:true})});
 assert.match(await disconnectedRow.innerText(),/待建队/,'disconnected target has no due date');
 assert.ok(!(await disconnectedRow.innerText()).includes(previousDue),'old due date is not shown for a disconnected target');
 await page.unroute('**/data/tco_targets.json*');
 await page.reload();await page.locator('#targets table tbody tr').first().waitFor({state:'attached'});
 assert.equal(await page.locator('#targets td').filter({hasText:'待建队'}).count(),0,'restored live policy remains connected');
 assert.ok((await page.locator('#targets td').filter({hasText:'人工登记'}).count())>0,'sourced rows say whether the series came from the registry');
 assert.match(await page.locator('#q4').innerText(),/已交付未成序列 \d+.*归待建队/,'root q4 counts delivered and not-connected rows');
 for(const [id,count] of [['it',3],['storage-group',2]]) {
  await page.goto(base+'/research-workbench.html?id=system:'+id);
  await page.locator('#children table tbody tr').first().waitFor();
  assert.equal(await page.locator('#children table tbody tr').count(),count);
  assert.match(await page.locator('#q4').innerText(),/全部部件/);
 }
 await page.goto(base+'/research-workbench.html?it=1');await page.locator('#matrix.it-open').waitFor();
 await page.locator('#matrix a[href="research-workbench.html?id=system%3Apower&col=4"]').click();
 await page.locator('#col-4.hl').waitFor();
 const url=new URL(page.url());assert.equal(url.searchParams.get('col'),'4');assert.match(url.searchParams.get('id'),/^system:/);
 await page.locator('#children table tbody tr').first().waitFor();
 assert.match(new URL(page.url()).searchParams.get('id'),/^system:power$/);
 assert.deepEqual((await page.locator('#children tr.chain-row th').allTextContents()).slice(0,3),['电网接入','变电','发电与储能'],'parts grouped along the energy-flow chain');
 await page.goto(base+'/research-workbench.html?col=4');await page.locator('#timeline .stage').first().waitFor();
 assert.equal(await page.locator('#timeline .stage').count(),6,'it怎么建: six build stages');
 assert.match(await page.locator('#timeline .stage').first().innerText(),/权利与审批/);
 assert.ok((await page.locator('#timeline .stage a.kv').count())>60,'every part and right sits in a stage');
 await page.goto(base+'/research-workbench.html?id=system:it');await page.locator('#children table tbody tr').first().waitFor();
 assert.equal(await page.locator('#children table tbody tr').count(),3,'IT lists compute, storage and network');
 await page.goto(base+'/research-workbench.html?id=part:transformer');await page.locator('#five .col').first().waitFor();
 assert.match(await page.locator('#head h1').textContent(),/变压器/);
 assert.match(await page.locator('#head .kind').first().textContent(),/变电/,'part page names its chain');
 assert.ok((await page.locator('#col-4 .kv').count())>0,'transformer lead time is a sourced time cell');
 assert.ok((await page.locator('#col-5 a.chip[href^="product-catalog.html?c="]').count())>0,'suppliers on the fifth column open the actor page');
 assert.ok((await page.locator('#targets table tbody tr').count())>=4,'spec, operation, price and lead-time targets');
 assert.equal(await page.locator('#five a[href^="supply.html?"]').count(),5,'every column links to the acquisition page prefiltered by node and column');
 await page.locator('#evidence .ev-grid').waitFor();
 assert.equal(await page.locator('#evidence .col').count(),3,'questions, candidate evidence and one-hop relations on the part node');
 assert.ok((await page.locator('#evidence .chip a').count())>0,'suppliers and the chain are one hop away');
 assert.equal(await page.locator('a[href^="research.html"]').count(),0,'no link to the retired research page');
 assert.ok((await page.locator('#factors .factor').count())>=1);
 await page.goto(base+'/product-catalog.html?view=products&c=hitachi-energy');await page.locator('#catalog-title').waitFor();
 await page.locator('#relationship-diagram a[href^="/node.html?id=part%3A"]').first().waitFor();
 assert.equal(await page.locator('#research-details').count(),0,'reader company pages do not embed the internal research annex');
 const cookie=process.env.UI_ADMIN_COOKIE;assert.ok(cookie,'internal company annex requires a real admin session');
 const [cookieName,...cookieValue]=cookie.split('=');await page.context().addCookies([{name:cookieName,value:cookieValue.join('='),url:base}]);
 await page.goto(base+'/admin/company.html?c=hitachi-energy');await page.locator('#research-details summary').click();await page.locator('#root .grid').waitFor();
 assert.ok((await page.locator('#root a[href^="node.html?id=part:"]').count())>0,'the internal company annex retains supplied-part research links');
 assert.equal(await page.locator('.kpi').count(),0,'no KPI grid, map or module blocks on the actor page');
 await page.goto(base+'/admin/company.html?c=constellation-energy#ecosystem');await page.locator('#research-details summary').click();await page.locator('#ecosystem').waitFor();
 assert.equal(await page.locator('#ecosystem article').count(),2,'new generation and existing supply are separate agreements');
 assert.match(await page.locator('#ecosystem').innerText(),/890 MW.*发电口径.*计划或预测/);
 assert.match(await page.locator('#ecosystem').innerText(),/2700 MW.*发电口径.*公告披露.*既有PJM电源供给组合，非新增/);
 assert.equal(await page.locator('#ecosystem [aria-label="地域对照"] tr').count(),4,'three states without inferred state allocations');
 assert.match(await page.locator('#ecosystem').innerText(),/不自动增加数据中心 IT GW/);
 assert.ok(await page.locator('#ecosystem a[href*="product-catalog.html?c=alphabet-google"]').count());
 for(const width of [390,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 await page.goto(base+'/research-workbench.html?id=site:grid');await page.locator('#five .col').first().waitFor();
 assert.match(await page.locator('#head h1').textContent(),/并网/);
 await page.goto(base+'/ledger.html');await page.locator('#calibration-table tbody tr').first().waitFor();
 assert.ok((await page.locator('#calibration-table tbody tr').count())>=8,'the three calibration anchors replace the old assumption bridge');
 assert.equal(await page.locator('#calibration-table .flag.no').count(),0,'one model reproduces all three');
 assert.equal(await page.locator('#column-tabs a').count(),4,'four product columns on the one model');
 assert.ok(await page.locator('#basis').isVisible());await page.locator('#column-tabs a[data-column=returns]').click();await page.locator('#view-ledgers.on').waitFor();
 assert.equal(await page.locator('#model-inputs details').count(),5,'inputs grouped by the five variable classes');
 assert.equal(await page.locator('#presets button.active').textContent(),'基准 · AI 自建 · 北弗吉尼亚','the root account and the ledger share the one baseline');
 await page.goto(base+'/research-workbench.html?id=nope');await page.locator('#error .err').waitFor();
 const targetSnapshot=await(await page.request.get(base+'/data/tco_targets.json')).json();
 for(const canonical of ['land','water-rights','grid','gas-supply','network-access','permits']){
  await page.goto(base+'/research-workbench.html?id='+encodeURIComponent('site:'+canonical));
  await page.locator('#targets table tbody tr').first().waitFor();
  const expectedTargets=targetSnapshot.targets.filter(row=>row.site_right_id===canonical).map(row=>row.id).sort();
  assert.deepEqual((await page.locator('#targets tbody tr td:first-child code').allTextContents()).sort(),expectedTargets,'all and only canonical right targets remain internal');
  assert.equal(await page.locator('#five a[href*="supply.html?node='+encodeURIComponent('site:'+canonical)+'&"]').count(),3,'rights have price, time and actor targets; no fabricated structure/operation demand');
  for(const col of ['3','4','5'])assert.equal(await page.locator('#col-'+col+' a[href*="supply.html?node='+encodeURIComponent('site:'+canonical)+'&"]').count(),1);
 }
 assert.deepEqual(errors,[]);
 // The delivered research page is identical for IT and customers, including old column links.
 const customerCookie=process.env.UI_CUSTOMER_COOKIE;assert.ok(customerCookie,'delivery research requires a real customer session');
 const projection=await (await page.request.get(base+'/api/navigation')).json();
 assert.ok(projection.delivery_pages.includes('/node.html'),'delivered research is actually authorized');
 const privateRequests=[],customerErrors=[];
 const customerContext=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 const split=customerCookie.indexOf('=');await customerContext.addCookies([{name:customerCookie.slice(0,split),value:customerCookie.slice(split+1),url:base}]);
 const customer=await customerContext.newPage();customer.on('pageerror',error=>customerErrors.push(error.message));
 const privatePath=path=>/tco_targets|research-(summary|materials|adopted)|research-graph\.js|object-network\.js/.test(path);
 customer.on('request',request=>{if(privatePath(new URL(request.url()).pathname))privateRequests.push(request.url());});
 const deliveryRoutes=['/node.html','/node.html?col=4','/node.html?col=1','/node.html?col=2','/node.html?col=3','/node.html?col=5','/node.html?id=system:it','/node.html?id=system:storage-group','/node.html?id=system:power&col=4','/node.html?id=part:transformer','/node.html?id=part:gpu','/node.html?id=site','/node.html?id=site:grid'];
 const snapshots=new Map();
 for(const reader of [page,customer])for(const path of deliveryRoutes){
  assert.equal((await reader.goto(base+path)).status(),200,path);
  await reader.locator('#five .col').last().waitFor();
  assert.equal(await reader.locator('#five .col').count(),5);
  assert.equal(await reader.locator('#targets,#grid,#evidence,#materials,#p4').count(),0,'work details stay in the workbench');
  assert.equal(await reader.locator('main a[href*="supply.html"],main a[href*="bom3d.html"],main a[href*="rack3d.html"],main a[href*="doc.html"]').count(),0);
  const visible=await reader.locator('main').innerText();
  assert.doesNotMatch(visible,/待建队|归待建队|30 天内到期|队 \/ 主机|兼容模块/);
  if(reader===page)snapshots.set(path,visible);else assert.equal(visible,snapshots.get(path),'same delivered reading: '+path);
  const col=new URL(reader.url()).searchParams.get('col');if(col)assert.ok(await reader.locator('#col-'+col+'.hl').count(),'legacy column still focuses its value category');
  if(path==='/node.html'){
   assert.equal(await reader.locator('.acct').count(),3);assert.equal(await reader.locator('#matrix td.cell').count(),55);
   assert.equal(await reader.locator('#matrix td.cell.sourced .c').filter({hasText:/部件数|供应商数|权利条目|持有方/}).count(),0,'registered counts retain their physical meaning');
   await reader.locator('#matrix .it-toggle').click();assert.equal(await reader.locator('#matrix tbody tr:visible').count(),11);
  }
  if(path==='/node.html?col=4'){assert.equal(await reader.locator('#timeline .stage').count(),6);assert.ok(await reader.locator('#timeline .stage a.kv').count()>60);}
  if(path.includes('system:power'))assert.deepEqual((await reader.locator('#children tr.chain-row th').allTextContents()).slice(0,3),['电网接入','变电','发电与储能']);
  if(path.includes('part:transformer'))assert.ok(await reader.locator('#col-4 .kv').count()>0,'sourced transformer lead time remains');
  for(const href of await reader.locator('main a[href]').evaluateAll(links=>links.map(link=>link.href))){const u=new URL(href);if(u.origin===new URL(base).origin)assert.ok(projection.delivery_pages.includes(u.pathname),'delivered link is authorized: '+href);}
 }
 // Exact image files still open and download under the customer's actual ACL.
 const {readFileSync}=require('node:fs'),{join}=require('node:path'),{createHash}=require('node:crypto');
 const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
 let adminDossier;
 for(const reader of [page,customer]){
  assert.equal((await reader.goto(base+'/bom.html#gpu')).status(),200);await reader.locator('#dossier .spark-wrap').waitFor();
  assert.equal(await reader.locator('#dossier .dossier-targets,#dossier .rg-3d-panel,#dossier .insp').count(),0);
  assert.equal(await reader.locator('#dossier a[href*="supply"]').count(),0);
  for(const href of await reader.locator('.topbar a[href*="3d"],.go3d,#selected-atlas a[href*="3d"]').evaluateAll(links=>links.map(link=>link.href)))assert.ok(projection.delivery_pages.includes(new URL(href).pathname),'3D switches use the same authorized page registry');
  assert.match(await reader.locator('#dossier').innerText(),/概念示意.*不代表真实现场配置/s);
  assert.ok(await reader.locator('#dossier a[href*="product-catalog.html"]').count()>0,'company anchors are preserved');
  const text=await reader.locator('#dossier').innerText();if(reader===page)adminDossier=text;else assert.equal(text,adminDossier);
  const atlas=reader.locator('#selected-atlas .technical-atlas');assert.equal(await atlas.count(),1);
  await atlas.locator('img:not(.ui-brand-watermark)').evaluate(image=>image.decode());
  for(const name of ['下载标注图','下载无字底图']){
   const link=atlas.getByRole('link',{name,exact:true}),href=await link.getAttribute('href');
   const result=await reader.request.get(base+href);assert.equal(result.status(),200,'actual customer file permission');
   const original=readFileSync(join(__dirname,'../web',href));assert.equal(digest(await result.body()),digest(original),'download bytes preserve the registered figure');
   const pending=reader.waitForEvent('download');await link.click();const download=await pending;assert.equal(await download.failure(),null);assert.equal(digest(readFileSync(await download.path())),digest(original));
  }
  await reader.goto(base+'/bom.html#server');await reader.locator('#selected-atlas [data-related-figure="TA-12"]').waitFor();
  assert.equal(await reader.locator('#selected-atlas [data-related-figure="TA-12"]').getAttribute('href'),'/server-plan.html','authorized related structure view remains');
  for(const href of await reader.locator('#dossier a[href],#selected-atlas a[href]').evaluateAll(links=>links.map(link=>link.href))){const u=new URL(href);if(!u.pathname.startsWith('/assets/'))assert.ok(projection.delivery_pages.includes(u.pathname),href);}
  for(const width of [390,1280]){await reader.setViewportSize({width,height:950});assert.ok(await reader.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 }
 for(const path of ['/research-workbench.html','/data/tco_targets.json','/api/research-summary?node=root','/api/research-materials?node=root','/api/research-adopted?node=root'])assert.equal((await customer.request.get(base+path)).status(),403,path);
 assert.deepEqual(privateRequests,[],'delivery node/BOM do not request internal modules or research data');
 assert.deepEqual(customerErrors,[]);assert.deepEqual(errors,[]);await customerContext.close();
 console.log('PASS dashboard: retained workbench research/task assertions; real IT/customer delivery parity, five variables, physical hierarchy and stages, precise BOM image/download closure');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
