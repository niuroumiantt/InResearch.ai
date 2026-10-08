/* Real HTTP projections feed the same association index; UI requests have owners. */
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {join} = require('node:path');
const {chromium} = require('playwright');
const fixture = JSON.parse(execFileSync(process.env.PYTHON || 'python3', ['-c', `
import json
from test_research import ReaderSnapshotHTTPTests, adopted_knowledge, research
case = ReaderSnapshotHTTPTests()
try:
    case.setUp()
    research.atomic_json(case.curated_path, adopted_knowledge())
    code, full = case.request('GET', '/api/research'); assert code == 200
    code, summary = case.request('GET', '/api/research-summary'); assert code == 200
    code, adopted = case.request('GET', '/api/research-adopted'); assert code == 200
    print(json.dumps({'full':full, 'summary':summary, 'adopted':adopted}))
finally:
    case.doCleanups()
`], {cwd:process.cwd(), env:{...process.env, PYTHONPATH:[join(process.cwd(),'src'),join(process.cwd(),'tests/unit')].join(':')}, maxBuffer:16*1024*1024}));
(async()=>{
 const browser = await chromium.launch({headless:true});
 try {
  const page=await browser.newPage();await page.goto(process.env.UI_BASE_URL+'/login');
  const result=await page.evaluate(async ({full,summary})=>{
   const {buildResearchIndex,loadResearch,loadResearchSummary,mountNodeResearch}=await import('/assets/research-graph.js');
   const check=(ok,message)=>{if(!ok)throw Error(message);};
   const same=(a,b,message)=>check(JSON.stringify(a)===JSON.stringify(b),message);
   const a=buildResearchIndex(full),b=buildResearchIndex(summary);let withEvidence=0;
   const id=row=>row.id||row.wid||row.task_id;
   for(const object of a.objects) {
    const x=a.forNode(object.id),y=b.forNode(object.id);
    for(const key of ['questions','evidence','tasks','statements','answers'])
     same(x[key].map(id),y[key].map(id),object.id+' '+key);
    const relation=row=>[row.id,row.source,row.target,row.type,row.views,row.view_ids,row.view];
    same(x.relations.map(relation),y.relations.map(relation),object.id+' relations');
    same([object.name,object.redirect_to,object.navigation_hidden],
      [b.byId.get(object.id).name,b.byId.get(object.id).redirect_to,b.byId.get(object.id).navigation_hidden],object.id+' identity');
    if(x.evidence.length)withEvidence++;
   }
   check(withEvidence>0,'fixture must exercise actual answer→statement→evidence association');
   const originalFetch=globalThis.fetch, queue=[];
   globalThis.fetch=(path)=>new Promise((resolve,reject)=>queue.push({path,resolve,reject}));
   const response=data=>({ok:true,json:async()=>data});
   const container=document.createElement('div');document.body.append(container);
   const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
   const currentNode=a.objects.find(o=>a.forNode(o.id).evidence.length).id;
   const otherNode=a.objects.find(o=>o.id!==currentNode).id;
   try {
    // An old mount may finish after A→B→A. It cannot replace the newest body.
    const old=loadResearchSummary({refresh:true});mountNodeResearch(container,currentNode);
    const latest=loadResearchSummary({refresh:true});
    mountNodeResearch(container,otherNode);mountNodeResearch(container,currentNode);
    queue[1].resolve(response(summary));await latest;await settle();
    check(container.dataset.state==='ready','new mount not ready');const rendered=container.textContent;
    const empty={...summary,questions:[],tasks:[],knowledge:{evidence:[],answers:[],statements:[]}};
    queue[0].resolve(response(empty));await old;await settle();
    check(container.textContent===rendered,'old success overwrote new mount');
    // A late rejection must neither show an error on the new mount nor clear its cache.
    const stale=loadResearchSummary({refresh:true}).catch(()=>{});mountNodeResearch(container,currentNode);
    const fresh=loadResearchSummary({refresh:true});mountNodeResearch(container,currentNode);
    queue[3].resolve(response(summary));await fresh;await settle();
    queue[2].reject(Error('late old failure'));await stale;await settle();
    check(container.dataset.state==='ready','late error replaced ready data');
    check(loadResearchSummary()===fresh,'late failure cleared newer cache');
    // Explicit failure can be retried from the actual UI.
    const failure=loadResearchSummary({refresh:true}).catch(()=>{});mountNodeResearch(container,currentNode);
    queue[4].resolve({ok:false,status:503});await failure;await settle();
    check(container.dataset.state==='error','failure not visible');
    container.querySelector('button').click();check(queue[5].path==='/api/research-summary','retry wrong endpoint');
    queue[5].resolve(response(summary));await loadResearchSummary();await settle();
    check(container.dataset.state==='ready','retry did not recover');
    mountNodeResearch(container,'unmapped:test');await settle();check(container.dataset.state==='missing','missing object pretended ready');
    const invalid=loadResearchSummary({refresh:true}).catch(()=>{});mountNodeResearch(container,currentNode);
    queue[6].resolve(response({graph:summary.graph,schema_version:0}));await invalid;await settle();
    check(container.dataset.state==='error','malformed summary pretended ready');
    // The full workbench request is a different cache and keeps its full contract.
    const fullRequest=loadResearch({refresh:true});check(queue[7].path==='/api/research','full consumer migrated accidentally');
    queue[7].resolve(response(full));check((await fullRequest).catalog!==undefined,'catalog lost from full view');
   } finally {globalThis.fetch=originalFetch;container.remove();}
   return {objects:a.objects.length,objectsWithEvidence:withEvidence};
  },fixture);
  assert.ok(result.objects>100);assert.ok(result.objectsWithEvidence>0);
  // The actual node page distinguishes formal records without eagerly reading sources.
  const mixed = structuredClone(fixture);
  mixed.adopted.knowledge.statements[0].text = '<img src=x onerror=alert(1)> bounded author claim';
  mixed.adopted.knowledge.statements[0].scope = 'historical author explanation';
  mixed.adopted.knowledge.statements.push({id:'statement:candidate',text:'Still a candidate',status:'candidate'});
  mixed.summary.knowledge.statements.push({id:'statement:candidate',status:'candidate'});
  let fullRequests = 0;
  let materialRequests = 0;
  const materialRows = Array.from({length:43}, (_, i) => ({id:'material:'+i,
    text:'<img src=x onerror=alert(1)> historical source '+i,
    source:{title:'Original 2015 report', url:null}, source_date:'2015-04-01',
    quotes:[{id:'quote:'+i, quote:'Original source quotation '+i, page_index:0}]}));
  await page.route(url => url.pathname === '/api/research-materials', route => {
    materialRequests++;
    if (materialRequests === 1) return route.fulfill({status:503,json:{error:'temporary'}});
    const params = new URL(route.request().url()).searchParams;
    const rows = params.get('q') ? materialRows.slice(0,1) : materialRows;
    const offset = Number(params.get('offset') || 0), limit = 20;
    return route.fulfill({json:{state:'connected',total:rows.length,materials:1,offset,limit,
      next_offset:offset+limit<rows.length?offset+limit:null,records:rows.slice(offset,offset+limit)}});
  });
  await page.route('**/api/research-summary?*', route => route.fulfill({json:mixed.summary}));
  await page.route(url => url.pathname === '/api/research-adopted', route => {
    fullRequests++;
    return fullRequests === 1 ? route.fulfill({status:503,json:{error:'temporary'}}) : route.fulfill({json:mixed.adopted});
  });
  await page.goto(process.env.UI_BASE_URL+'/node.html');
  const materials = page.locator('#materials');
  await materials.getByRole('button',{name:'重试'}).click();
  await materials.locator('[data-material-id="material:0"]').waitFor();
  assert.equal(await materials.locator('[data-material-id]').count(),20);
  assert.equal(await materials.locator('img').count(),0,'material text became active HTML');
  await materials.locator('details').first().locator('summary').click();
  assert.match(await materials.innerText(),/Original source quotation 0/);
  assert.match(await materials.innerText(),/2015-04-01/);
  await materials.getByRole('button',{name:'下一页'}).click();
  await materials.locator('[data-material-id="material:20"]').waitFor();
  assert.equal(await materials.locator('[data-material-id="material:0"]').count(),0);
  await materials.getByRole('button',{name:'上一页'}).click();
  await materials.locator('[data-material-id="material:0"]').waitFor();
  await materials.getByRole('textbox',{name:'搜索资料'}).fill('Historical');
  await materials.getByRole('button',{name:'搜索',exact:true}).click();
  await materials.locator('[data-page="next"][disabled]').waitFor();
  assert.equal(await materials.locator('[data-material-id]').count(),1);
  const detail = page.locator('.adopted-research'); await detail.waitFor();
  assert.equal(fullRequests,0,'first paint fetched the full research source payload');
  assert.match(await page.locator('#evidence').innerText(),/正式采用/);
  assert.match(await page.locator('#evidence').innerText(),/候选/);
  await detail.locator('summary').click(); await detail.locator('button').waitFor();
  assert.equal(await detail.locator('[data-adopted-id]').count(),0,'failed request pretended adopted records loaded');
  await detail.getByRole('button',{name:'重试'}).click();
  await page.locator('[data-adopted-id="statement:reviewed"]').waitFor();
  assert.equal(await detail.locator('[data-adopted-id="statement:candidate"]').count(),0);
  assert.match(await detail.innerText(),/historical author explanation/);
  assert.match(await detail.innerText(),/Original fixture quotation/);
  assert.match(await detail.innerText(),/原件第 1 页/);
  assert.equal(await detail.locator('img').count(),0,'source text became active HTML');
  await page.setViewportSize({width:390,height:950});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:320,height:850});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  console.log('PASS HTTP full/summary association parity for '+result.objects+' objects; nonzero evidence, redirects, stale success/failure, cache ownership, retry and full-view retention');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
