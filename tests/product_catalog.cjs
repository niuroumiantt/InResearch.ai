const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const cell=(text,colspan=1)=>({text,colspan,rowspan:1,header:false});
  const product={id:'nvidia-aaaaaaaaaaaaaaaaaaaa',name:'NVIDIA H200',category:'Data Center',kind:'named_product',observed_at:'2026-09-27',source_url:'https://www.nvidia.com/en-us/data-center/h200/',source_sha256:'a'.repeat(64),official_pages:[{url:'https://www.nvidia.cn/data-center/h200/',sha256:'b'.repeat(64)}],website_sitemap:{matched:true,roles:['en_us']},attachments:[],tables:[{index:1,section:'Specifications',notes:'* Sparse, per GPU',source_refs:[{url:'https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/h200.pdf',sha256:'c'.repeat(64)}],rows:[[cell(''),cell('SXM'),cell('NVL')],[cell('Memory'),cell('141 GB',2)]]}]};
  product.navigation={group:'datacenter',family:'accelerators',family_label:'GPU / CPU / 超级芯片',role:'catalog'};
  const groups=[['datacenter','数据中心与网络'],['consumer','游戏与消费产品'],['professional','专业图形与工作站'],['embedded','嵌入式与汽车'],['software','软件与云服务']].map(([id,label])=>({id,label}));
  const gaming={...product,id:'gaming',name:'GeForce RTX 5090',navigation:{group:'consumer',family:'geforce-50',family_label:'GeForce RTX 50 系列',role:'catalog'}};
  const auxiliary={...product,id:'training',name:'NVIDIA Training',navigation:{group:'',family:'',family_label:'待归类',role:'auxiliary'}};
  const unavailable={...product,id:'gtx-660-oem',name:'GeForce GTX 660 OEM',tables:[],extraction_status:'official_specification_source_unavailable',navigation:{group:'',family:'',family_label:'待归类',role:'auxiliary'}};
  const unpublished={...product,id:'titan-z',name:'GeForce GTX TITAN Z',tables:[],extraction_status:'official_specification_not_published_on_observed_page',navigation:{group:'',family:'',family_label:'待归类',role:'auxiliary'}};
  const more=Array.from({length:17},(_,i)=>({...product,id:'extra'+i,name:'ZZZ GPU '+i}));
  const products=[product,gaming,auxiliary,unavailable,unpublished,...more];
  const coverage={directory_entries:48,entity_counts:{named_product:22},with_spec_tables:20,pending_pages:4,failed_pages:0,unavailable_pages:35,policy_blocked_pages:2,website_sitemap:{candidate_urls:7062,product_path_candidates:427,product_path_observed:423,matched_catalog_sources:1},limitations:['Not exhaustive']};
  let indexRequests=0,detailRequests=0;
  await page.route('**/api/product-catalog/nvidia*',r=>{
    const url=new URL(r.request().url()),id=url.searchParams.get('product_id');
    if(id){detailRequests++;return r.fulfill({json:{available:true,product:products.find(p=>p.id===id)}});}
    indexRequests++;
    return r.fulfill({json:{available:true,view:'index',generated_at:'2026-09-27',coverage,navigation:{groups},products:products.map(p=>({id:p.id,name:p.name,parent_id:p.parent_id,category:p.category,kind:p.kind,availability:p.availability,extraction_status:p.extraction_status,observed_at:p.observed_at,map_change_status:p.map_change_status,table_count:p.tables.length,navigation:p.navigation}))}});
  });
  await page.goto(process.env.UI_BASE_URL+'/product-catalog.html');
  await page.getByRole('heading',{name:'NVIDIA H200',exact:true}).waitFor();
  assert.equal(indexRequests,1);assert.equal(detailRequests,1);
  await page.locator('#detail details summary').first().click();
  assert.match(await page.locator('#detail').innerText(),/141 GB/);
  assert.equal(await page.locator('#detail td[colspan="2"]').innerText(),'141 GB');
  assert.match(await page.locator('#detail').innerText(),/Sparse/);
  assert.match(await page.locator('#detail').innerText(),/表格来源：查看原始附件/);
  assert.equal(await page.locator('#detail').getByRole('link',{name:'查看原始附件'}).getAttribute('href'),'https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/h200.pdf');
  await page.locator('#detail details').nth(1).locator('summary').click();
  assert.match(await page.locator('#detail details').nth(1).locator('a').getAttribute('href'),/nvidia\.cn/);
  assert.match(await page.locator('#detail').innerText(),/en_us/);
  assert.match(await page.locator('#status').innerText(),/官方 sitemap 候选 7062/);
  await page.locator('main details').first().locator('summary').click();
  assert.match(await page.locator('#status').innerText(),/具体型号规格 20 \/ 22/);
  assert.match(await page.locator('#metrics').innerText(),/20 \/ 22[\s\S]*具体型号规格覆盖[\s\S]*2[\s\S]*官网明确规格缺口/);
  assert.match(await page.locator('#metrics').innerText(),/423 \/ 427[\s\S]*已核对产品 URL/);
  assert.match(await page.locator('#metrics').innerText(),/0[\s\S]*访问失败（可重试）[\s\S]*35[\s\S]*官网已删除旧页[\s\S]*2[\s\S]*策略阻止跳转/);
  assert.match(await page.locator('#export-map').getAttribute('href'),/export=map/);
  assert.equal(await page.locator('#groups button').count(),5);
  assert.equal(await page.locator('.product').count(),15);
  assert.ok(!(await page.locator('#products').innerText()).includes('Training'));
  await page.locator('#next').click();assert.equal(await page.locator('.product').count(),3);
  await page.locator('#previous').click();
  await page.locator('[data-group="consumer"]').click();
  assert.match(await page.locator('#breadcrumb').innerText(),/游戏与消费产品.*GeForce/);
  assert.equal(await page.locator('.product').count(),1);
  assert.match(await page.locator('#export-products').getAttribute('href'),/group=consumer.*family=geforce-50/);
  await page.locator('#auxiliary').click();assert.match(await page.locator('#products').innerText(),/Training/);
  await page.getByRole('button',{name:/GeForce GTX 660 OEM/}).click();
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('官网规格来源不可用'));
  assert.match(await page.locator('#detail').innerText(),/官网规格来源不可用[\s\S]*官网型号专属规格页已删除或不可用/);
  await page.getByRole('button',{name:/GeForce GTX TITAN Z/}).click();
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('官网未发布型号规格'));
  assert.match(await page.locator('#detail').innerText(),/官网未发布型号规格[\s\S]*未发布型号专属规格表或附件/);
  await page.locator('[data-group="datacenter"]').click();
  await page.locator('#compare').click();assert.equal(await page.locator('#comparison').isVisible(),true);
  await page.locator('#query').fill('unmatched');assert.match(await page.locator('#matches').innerText(),/^0/);
  await page.locator('#query').fill('H200');assert.match(await page.locator('#export-specs').getAttribute('href'),/q=h200/);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.equal(await page.locator('.product').first().evaluate(el=>getComputedStyle(el).borderRadius),'0px');
  await page.unroute('**/api/product-catalog/nvidia*');
  await page.route('**/api/product-catalog/nvidia*',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.locator('#retry').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('暂时不可用'));
  // Micron (vendor taxonomy): part numbers are browsed by official series, each series one comparison table.
  await page.setViewportSize({width:1280,height:900});
  const nav=(group,family,role='catalog')=>({group,family,family_label:family==='ssd'?'SSD':'Obsolete Lpddr',role});
  const ssd=[{slug:'storage',name:'Storage'},{slug:'ssd',name:'SSD'},{slug:'data-center-ssd',name:'Data center SSD'},{slug:'7600-ssd',name:'7600 NVMe SSD'}];
  const series={id:'micron-'+'1'.repeat(20),name:'7600 NVMe SSD',kind:'family_or_directory',listing:'directory',taxonomy:ssd,category:'Storage / SSD',table_count:0,navigation:nav('storage','ssd','auxiliary')};
  const parts=['MTFDLAL1T6THS','MTFDLAL3T2THS'].map((name,i)=>({id:'micron-'+String(i+2).repeat(20),name,parent_id:series.id,kind:'named_product',listing:'active',official_status:'Production',taxonomy:ssd,category:'Storage / SSD',table_count:1,extraction_status:'native_tables_extracted',navigation:nav('storage','ssd')}));
  const old={id:'micron-'+'9'.repeat(20),name:'MT53B256M32D1',parent_id:'',kind:'named_product',listing:'obsolete',taxonomy:[{slug:'obsolete',name:'Obsolete part catalogs'}],category:'Obsolete',table_count:0,extraction_status:'not_collected_obsolete',navigation:nav('obsolete','obsolete-lpddr')};
  const comparison={id:series.id,name:series.name,taxonomy:ssd,source_url:'https://www.micron.com/products/storage/ssd/data-center-ssd/7600-ssd',source_sha256:'d'.repeat(64),observed_at:'2026-10-01',
    parts:parts.map((p,i)=>({id:p.id,name:p.name,official_status:'Production',listing:'active',extraction_status:p.extraction_status,values:{Capacity:['1600GB','3200GB'][i]}})),
    columns:['Capacity'],common:[{label:'Technology',value:'TLC'}],shared_tables:[],counts:{parts:2,with_specifications:2,by_official_status:{Production:2},by_listing:{active:2}}};
  const partDetail={...parts[0],source_url:'https://www.micron.com/x',source_sha256:'e'.repeat(64),attachments:[],official_resources:[],official_pages:[],tables:[{index:1,section:'MTFDLAL1T6THS',rows:[[cell('Capacity'),cell('1600GB')]]}]};
  let seriesRequests=0;
  await page.route('**/api/product-catalog/micron*',r=>{
    const url=new URL(r.request().url());
    if(url.searchParams.get('series_id')){seriesRequests++;return r.fulfill({json:{available:true,series:comparison}});}
    if(url.searchParams.get('product_id'))return r.fulfill({json:{available:true,product:partDetail}});
    return r.fulfill({json:{available:true,view:'index',generated_at:'2026-10-01',coverage:{},navigation:{groups:[{id:'obsolete',label:'Obsolete part catalogs'},{id:'storage',label:'Storage'}],official_source:'https://www.micron.com/products'},products:[series,...parts,old]}});
  });
  await page.goto(process.env.UI_BASE_URL+'/product-catalog.html?c=micron');
  await page.getByRole('heading',{name:'7600 NVMe SSD',exact:true}).waitFor();
  assert.match(await page.locator('#groups button').first().innerText(),/存储 · Storage/);
  assert.match(await page.locator('#groups button').last().innerText(),/停产型号/);
  assert.match(await page.locator('#matches').innerText(),/1 个系列 · 2 个料号/);
  assert.match(await page.locator('.product[data-series]').innerText(),/Data center SSD · 2 个料号 · 有规格 2 · 量产 2/);
  await page.locator('#detail .series-table').waitFor();
  assert.equal(seriesRequests,1);
  assert.deepEqual(await page.locator('#detail .series-table tbody tr td:last-child').allInnerTexts(),['1600GB','3200GB']);
  assert.match(await page.locator('#detail .series-common').innerText(),/Technology\s+TLC/);
  await page.locator('#detail .part-link').first().click();
  await page.locator('#back-series').waitFor();
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('1600GB'));
  await page.locator('#back-series').click();
  await page.locator('#detail .series-table').waitFor();
  await page.locator('[data-group="obsolete"]').click();
  assert.equal(await page.locator('.product[data-series]').count(),0);
  assert.match(await page.locator('#products').innerText(),/MT53B256M32D1/);
  await page.goto(process.env.UI_BASE_URL+'/product-catalog.html?c=micron&series='+series.id);
  await page.locator('#detail .series-table').waitFor();
  // Real empty receiver endpoints distinguish registered companies from delivered products.
  for(const [cid,label] of [['intel','Intel'],['amd','AMD'],['supermicro','Supermicro'],['sk-hynix','SK hynix']]){
    await page.goto(process.env.UI_BASE_URL+'/product-catalog.html?c='+cid);
    await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('等待 Fetchspec 首次交付'));
    assert.equal(await page.locator('#catalog-title').innerText(),label+' 产品规格库');
    assert.equal(await page.locator('#company-switch a').count(),6);
    assert.equal(await page.locator('#company-switch [aria-current="page"]').getAttribute('data-company'),cid);
    assert.equal(await page.locator('.product').count(),0);
    assert.ok(!/NVIDIA/.test(await page.locator('#groups-note').innerText()));
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
