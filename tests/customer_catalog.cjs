/* Real authenticated HTTP boundary over isolated received catalogs. TEST_VALUE
 * cells and injected unknown metadata are fixtures, never research claims. */
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const {chromium}=require('playwright');
(async()=>{
 const fixture=spawn(process.env.PYTHON||'python3',['-u','-c',`
import os,sys,tempfile,threading,json
from pathlib import Path
sys.path.insert(0,'src')
with tempfile.TemporaryDirectory(prefix='inresearch-customer-catalog-browser-') as temporary:
 os.environ['INRESEARCH_RUNTIME_ROOT']=temporary
 os.environ['INRESEARCH_MARKET_ENABLED']='0'
 from inresearch.storage.layout import initialize_runtime,workspace_path
 initialize_runtime()
 from inresearch.paths import project_root
 from inresearch.workflow import product_catalog as catalog,company_window,catalog_browse,catalog_materials
 from inresearch.delivery import source_publication
 from inresearch.adapters import company_quotes
 from inresearch.knowledge.object_observations import object_record
 from tests.unit.test_catalog_supplement import historical_fixture
 from tests.unit.test_customer_catalog import series_bundle,poisoned,SECRET
 root=project_root()
 base,supplement=historical_fixture()
 catalog.receive(root,base,'supermicro');catalog.receive(root,supplement,'supermicro')
 nvidia=series_bundle();catalog.receive(root,nvidia,'nvidia')
 native=company_window.snapshot(root,'supermicro')
 quote=company_quotes.normalize('SMCI',{'symbol':'SMCI','marketStatus':'Closed',
       'primaryData':{'lastSalePrice':'$123.45','lastTradeTimestamp':'Oct 13, 2026',
                      'netChange':'-1.25','percentageChange':'-1.0%'}},
       {'symbol':'SMCI','summaryData':{'MarketCap':{'value':'$20,000,000,000'}}})
 quote_path=workspace_path('data/raw/company-quotes/supermicro.json',root)
 quote_path.parent.mkdir(parents=True,exist_ok=True);quote_path.write_text(json.dumps(quote))
 quote=company_quotes.snapshot(root,native['company'])
 exports={company:{mode:catalog.csv_export(catalog.snapshot(root,company),mode,company=company)
            for mode in ('products','map','specs')} for company in ('nvidia','supermicro')}
 publication=source_publication.empty()
 obj=object_record('company',{'company_id':'fixture-runtime-company'},'SYNTHETIC Runtime Company')
 publication['objects'][obj['id']]=obj
 registry=workspace_path(source_publication.PATH,root)
 assert registry.is_relative_to(Path(temporary).resolve())
 registry.parent.mkdir(parents=True,exist_ok=True);registry.write_text(json.dumps(publication))
 # Inject future fields at the internal response boundary, including ordinary
 # disclosure/business-line records, so customer HTTP hooks must actually run.
 def inject(module,name):
  original=getattr(module,name)
  setattr(module,name,lambda *args,**kwargs:poisoned(original(*args,**kwargs)))
 for name in ('snapshot','index_snapshot','summary_snapshot','product_snapshot','series_snapshot'):inject(catalog,name)
 inject(company_window,'snapshot');inject(company_quotes,'snapshot');inject(catalog_browse,'query');inject(catalog_materials,'query')
 from inresearch.interfaces import http as serve,auth
 for username,role in [('catalog-admin','admin'),('catalog-customer','customer')]:auth.add_user(username,'Only-test-catalog-729461',role)
 serve.AUTH_ON=True;serve.Handler.log_message=lambda *args:None;serve.log_run=lambda *args:None
 server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 try:
  print(json.dumps({'port':server.server_port,'secret':SECRET,'home':native,'quote':quote,'exports':exports,
                   'supermicro_product':base['products'][0]['id'],'material_product':supplement['products'][1]['id'],
                   'nvidia_product':nvidia['products'][1]['id'],'nvidia_series':nvidia['products'][0]['id']}),flush=True)
  sys.stdin.readline()
 finally:server.shutdown();server.server_close();worker.join(timeout=2)
`],{stdio:['pipe','pipe','inherit']});
 const lines=createInterface({input:fixture.stdout});let browser;
 try{
  const info=await new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});fixture.once('error',reject);fixture.once('exit',code=>reject(Error('Catalog fixture exited '+code)));});
  const base='http://127.0.0.1:'+info.port;browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[],failures=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.url().startsWith(base)&&response.status()>=400)failures.push(response.status()+' '+new URL(response.url()).pathname);});
  await page.goto(base+'/login');await page.locator('[name=username]').fill('catalog-customer');await page.locator('[name=password]').fill('Only-test-catalog-729461');await Promise.all([page.waitForURL(base+'/'),page.locator('form button').click()]);await page.locator('#ui-skinbar[data-role=customer][data-navigation-ready=true]').waitFor();
  const headers={Cookie:(await context.cookies()).map(cookie=>cookie.name+'='+cookie.value).join('; ')};const request={get:url=>context.request.get(url,{headers})};
  const clean=async path=>{const response=await request.get(base+path);assert.equal(response.status(),200,path);const text=await response.text();assert.ok(!text.includes(info.secret)&&!text.includes('future_private'),'no unknown metadata '+path);return JSON.parse(text);};
  const endpoints=[
   '/api/company-window?c=supermicro', '/api/company-quote?c=supermicro',
   '/api/product-catalog/supermicro', '/api/product-catalog/supermicro?view=index', '/api/product-catalog/supermicro?view=summary',
   '/api/product-catalog/supermicro?view=browse', '/api/product-catalog/supermicro?view=materials',
   '/api/product-catalog/supermicro?product_id='+info.supermicro_product,
   '/api/product-catalog/nvidia', '/api/product-catalog/nvidia?view=index', '/api/product-catalog/nvidia?view=summary',
   '/api/product-catalog/nvidia?product_id='+info.nvidia_product, '/api/product-catalog/nvidia?series_id='+info.nvidia_series];
  for(const path of endpoints)await clean(path);
  assert.deepEqual(await clean('/api/company-quote?c=supermicro'),info.quote);const window=await clean('/api/company-window?c=supermicro');assert.deepEqual(window.financials,info.home.financials);assert.deepEqual(window.company,info.home.company);assert.deepEqual(window.catalog.summary,info.home.catalog.summary);assert.equal(window.catalog.material_count,2);assert.ok(!('run_id' in window.catalog));
  for(const company of ['supermicro','nvidia'])for(const mode of ['products','map','specs']){
   const response=await request.get(base+'/api/product-catalog/'+company+'?export='+mode);assert.equal(response.status(),200);assert.match(response.headers()['content-type'],/^text\/csv/);const text=await response.text();assert.equal(text.replace(/^\uFEFF/,''),info.exports[company][mode].replace(/^\uFEFF/,''),'exact received CSV '+company+'/'+mode);assert.ok(!text.includes(info.secret)&&!text.includes('future_private'));}
  const series=await clean('/api/product-catalog/nvidia?series_id='+info.nvidia_series);assert.equal(series.series.parts[0].values.Memory,'141 GB');assert.equal(series.series.parts[1].values.Memory,'282 GB');assert.equal(series.series.shared_tables[0].notes,'per GPU');
  const detail=await clean('/api/product-catalog/supermicro?product_id='+info.supermicro_product);assert.equal(detail.product.tables[0].rows[0][1].text,'TEST_VALUE');assert.equal(detail.product.tables[0].rows[0][0].rowspan,1);assert.equal(detail.product.tables[0].rows[0][0].colspan,1);assert.match(detail.product.source_url,/supermicro\.com/);
  // The same injected internal values remain available to an actual admin.
  const admin=await browser.newContext(),adminPage=await admin.newPage();await adminPage.goto(base+'/login');await adminPage.locator('[name=username]').fill('catalog-admin');await adminPage.locator('[name=password]').fill('Only-test-catalog-729461');await Promise.all([adminPage.waitForURL(base+'/'),adminPage.locator('form button').click()]);const adminHeaders={Cookie:(await admin.cookies()).map(cookie=>cookie.name+'='+cookie.value).join('; ')};assert.match(await (await admin.request.get(base+'/api/company-window?c=supermicro',{headers:adminHeaders})).text(),new RegExp(info.secret));await admin.close();
  console.log('PASS real customer JSON all catalog branches/company-window and six exact CSV exports reject nested future fields; internal admin retains originals');
  await page.goto(base+'/company.html?c=supermicro');await page.locator('#catalog-summary strong').first().waitFor();assert.equal(new URL(page.url()).pathname,'/product-catalog.html');assert.equal(await page.locator('#catalog-title').innerText(),'Supermicro');assert.deepEqual(await page.locator('#catalog-summary strong').allTextContents(),[String(info.home.catalog.summary.named_products),String(info.home.catalog.summary.named_with_tables),String(info.home.catalog.summary.specification_tables)]);assert.match(await page.locator('#company-facts').innerText(),/1993.*980 Rock.*7,000/s);await page.waitForFunction(()=>document.getElementById('quote-price').textContent.includes('123.45'));assert.match(await page.locator('#quote-price').innerText(),/123.45/);assert.equal(await page.locator('#financial-reports .report-row').count(),4);await page.locator('[data-reports=quarterly]').click();assert.equal(await page.locator('#financial-reports .report-row').count(),5);assert.match(await page.locator('#financial-reports').innerText(),/FY2026 Q3/);assert.equal(await page.locator('#product-lines .product-line-entry').count(),info.home.product_lines.length);
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'customer company window width '+width);}
  await page.locator('#company-materials-link').click();await page.waitForFunction(()=>document.querySelector('#material-status')?.textContent.includes('2 份已索引'));assert.equal(await page.locator('#material-list li').count(),2);assert.match(await page.locator('#material-status').innerText(),/1 份型号待关联/);
  await page.locator('#material-query').fill('unassigned');await page.locator('#material-search button').click();await page.waitForFunction(()=>document.querySelector('#material-status').textContent.includes('当前匹配 1 份'));assert.match(await page.locator('#material-list').innerText(),/型号待关联/);await page.reload();await page.waitForFunction(()=>document.querySelector('#material-status').textContent.includes('当前匹配 1 份'));
  await page.locator('#material-query').fill('Test Report');await page.locator('#material-search button').click();await page.waitForFunction(()=>document.querySelector('#material-list').textContent.includes('Test Report'));await page.locator('#material-list p a').click();await page.locator('#detail h2').waitFor();assert.match(await page.locator('#detail').innerText(),/SYS-6039P-TXRT.*OLD_TEST_VALUE/s);assert.match(await page.locator('#detail a[href^="https://www.supermicro.com/"]').first().getAttribute('href'),/^https:\/\//);
  await page.goto(base+'/product-catalog.html?c=supermicro&view=categories');await page.locator('#browse-rows .model-link').first().waitFor();assert.equal(await page.locator('.browser-tools a[href*="view=research"]').count(),0);await page.locator('#query').fill('SYS-6039P-TXRT');await page.waitForFunction(()=>document.querySelectorAll('#browse-rows .model-link').length===1);const csv=await (await request.get(base+await page.locator('#export-products').getAttribute('href'))).text();assert.ok(csv.includes('SYS-6039P-TXRT')&&!csv.includes('SYS-821GE-TNHR'));await page.locator('#browse-rows .model-link').click();await page.locator('#detail h2').waitFor();assert.equal(await page.locator('#detail h2').innerText(),'SYS-6039P-TXRT');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'customer original specification width '+width);}
  await page.goto(base+'/product-catalog.html?c=nvidia&view=products&product_id='+info.nvidia_product);await page.locator('#detail h2').waitFor();assert.match(await page.locator('#detail').innerText(),/FIXTURE-2.*141 GB/s);
  await page.goto(base+'/workspace.html?section=companies&view=companies&q=SYNTHETIC%20Runtime');await page.locator('#workspace-app[aria-busy=false]').waitFor();assert.match(await page.locator('#workspace-content').innerText(),/SYNTHETIC Runtime Company/);await page.locator('#workspace-content a').first().click();await page.locator('#catalog-title').waitFor();await page.waitForFunction(()=>document.getElementById('catalog-title').textContent==='SYNTHETIC Runtime Company');assert.equal(await page.locator('#catalog-link[href],#all-products[href],#research-link[href]').count(),0,'unregistered company has no unavailable product navigation');await page.goto(base+'/product-catalog.html?c=fixture-runtime-company&view=products');await page.waitForFunction(()=>document.getElementById('catalog-title').textContent.includes('SYNTHETIC Runtime Company'));await page.waitForFunction(()=>document.getElementById('status').textContent==='尚未登记产品目录。');assert.ok(!(await page.locator('body').innerText()).includes('公司不存在'));assert.equal(await page.locator('[id^=export-][href]').count(),0);await page.goto(base+'/product-catalog.html?c=fixture-runtime-company&view=materials');await page.waitForFunction(()=>document.getElementById('material-status').textContent==='尚未登记产品目录。');assert.equal(await page.locator('#material-search').isVisible(),false);
  assert.deepEqual(errors,[]);assert.deepEqual(failures,[],'all genuine customer page assets/API requests authorized');await context.close();console.log('PASS real customer legacy company redirect, financial tabs, product counts, material filtering/refresh/model sources, catalog search/filtered CSV, NVIDIA parameters, mobile widths and runtime identity consistency');
 }finally{if(browser)await browser.close();fixture.stdin.end('\n');lines.close();if(fixture.exitCode===null)await new Promise(resolve=>fixture.once('exit',resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
