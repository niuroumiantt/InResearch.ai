/* Real signed roles and actual HTTP projections; no production writes. */
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {createInterface}=require('node:readline');
const {chromium}=require('playwright');
const {mkdirSync,writeFileSync}=require('node:fs');
const energyEngine=require('../web/components/datacenter-model.js'),model=require('../data/datacenter_model.json'),energyBridge=require('../data/site_model_bridges.json').sites[0];
const initial=energyEngine.withPreset(model,'baseline');initial.site='us_texas';energyEngine.applyTable(initial,'site',model);Object.assign(initial,energyBridge.demo_assumptions,{it_mw:421,demand_rate:0});
const energy=energyEngine.energyCase(initial),sensitivity=energyEngine.energySensitivity(initial,energyBridge.energy_review.sensitivity);
assert.equal(energy.facility_kwh,3304412160);assert.equal(energy.it_kwh,2581572000);assert.equal(energy.actual_site_bill_usd,null);assert.equal(energy.ramp_applied,false);
assert.equal(energyEngine.energyCase(initial,4380).facility_kwh,energy.facility_kwh/2);
assert.equal(energyEngine.energyCase({...initial,ramp_year1:.1}).facility_kwh,energy.facility_kwh,'do not count deployment ramp twice');
assert.equal(energyEngine.energyCase({...initial,energy_quota_mw:200}).facility_kwh/energy.facility_kwh,200/421);
for(const bad of [{demand_rate:3.8},{pue:.9},{load_factor:1.2},{power_price:NaN}])assert.throws(()=>energyEngine.energyCase({...initial,...bad}));
assert.equal(sensitivity.combined.length,27);assert.equal(sensitivity.one_at_a_time.length,9);assert.equal(sensitivity.capacity_timing.length,2);
assert.ok(sensitivity.combined.every(r=>r.actual_site_bill_usd===null&&r.demand_added_usd===0));
assert.equal(Math.min(...sensitivity.combined.map(r=>r.facility_kwh)),2212776000);assert.equal(Math.max(...sensitivity.combined.map(r=>r.facility_kwh)),4646829600);
assert.ok(Math.abs(energyEngine.compute(initial,model).energy-energy.proxy_cost_usd)<.001);
const server=spawn(process.env.PYTHON||'python3',['-u','-c',String.raw`
import sys,json,tempfile,secrets
from pathlib import Path
sys.path.insert(0,'src')
from inresearch.interfaces import http,auth
with tempfile.TemporaryDirectory(prefix='campus-browser-') as folder:
 auth.USERS_FILE=Path(folder)/'users.json';auth.SECRET_FILE=Path(folder)/'.secret'
 for name,role in [('campus-admin','admin'),('campus-customer','customer')]:auth.add_user(name,secrets.token_urlsafe(32),role)
 http.AUTH_ON=True;http.Handler.log_message=lambda *args:None;http.log_run=lambda *args:None
 server=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler)
 print(json.dumps({'port':server.server_port,'admin':auth.make_cookie('campus-admin').split(';')[0],'customer':auth.make_cookie('campus-customer').split(';')[0]}),flush=True)
 server.serve_forever()
`],{cwd:require('node:path').resolve(__dirname,'..'),env:process.env,stdio:['ignore','pipe','inherit']});
const lines=createInterface({input:server.stdout});
const ready=new Promise((resolve,reject)=>{lines.once('line',s=>{try{resolve(JSON.parse(s));}catch{reject(Error('readiness invalid'));}});server.once('error',reject);server.once('exit',()=>reject(Error('server stopped')));});
(async()=>{
 let browser;
 try{
  const credentials=await ready,base='http://127.0.0.1:'+credentials.port;
  browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_EXECUTABLE?{executablePath:process.env.UI_BROWSER_EXECUTABLE}:{})});
  const anon=await browser.newContext();
  for(const route of ['/project.html?site=us-tx-abilene','/ledger.html?site=us-tx-abilene','/api/industry?site=us-tx-abilene']){
   const r=await anon.request.get(base+route,{maxRedirects:0});assert.ok([302,401].includes(r.status()),route+' protected');
  }await anon.close();
  for(const role of ['customer','admin']){
   const context=await browser.newContext({viewport:{width:1440,height:1000}}),cookie=credentials[role].split('=');
   await context.addCookies([{name:cookie.shift(),value:cookie.join('='),url:base}]);
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'/project.html?site=us-tx-abilene#campus-equipment');
   await page.getByText('现场配置映射',{exact:true}).waitFor();
   const text=await page.locator('#campus-equipment').innerText();assert.ok(text.includes('201600'));assert.ok(text.includes('320'));assert.ok(text.includes('候选'));assert.ok(text.includes('未知'));
   await page.locator('#campus-equipment a[href*="scope="]').click();
   await page.locator('#bridge-apply').waitFor();assert.ok((await page.locator('#site-model-bridge').innerText()).includes('尚未应用'));
   assert.notEqual(Number(await page.locator('#input-it_mw').inputValue()),421);
   assert.ok((await page.locator('#bridge-dependency-notice').textContent()).includes('不能互相作为独立证据'));assert.equal(await page.locator('[data-document-check]').count(),10);assert.ok((await page.locator('#bridge-document-checks').textContent()).includes('四个翼区不是四栋'));
   await page.locator('#bridge-apply').click();assert.equal(await page.locator('#input-it_mw').inputValue(),'421');
   assert.equal(await page.locator('#input-pue').inputValue(),'1.28');assert.equal(await page.locator('#input-demand_rate').inputValue(),'0');assert.ok(await page.locator('#input-demand_rate').isDisabled());assert.equal(await page.locator('[data-energy-check]').count(),4);assert.ok((await page.locator('#bridge-energy-checks').textContent()).includes('Lancium QSE I'));assert.ok((await page.locator('#bridge-result').textContent()).includes('不是2026自然年'));assert.ok((await page.locator('#bridge-energy-sensitivity').textContent()).includes('27组联合情景'));assert.equal(await page.locator('#input-load_factor').inputValue(),'70');
   assert.ok((await page.locator('#bridge-result').innerText()).includes('$233.6M'));
   assert.ok((await page.locator('[data-bridge-basis=it_mw]').innerText()).includes('第三方估算'));
   const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#bridge-export').click()]);
   const fs=require('node:fs');const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
   assert.equal(exported.schema,'site-model-scenario-v4');assert.equal(exported.energy_review.billing.mode,'retail_average_proxy');assert.equal(exported.inputs.demand_rate,0);assert.equal(exported.input_basis.demand_rate.kind,'analysis_choice');assert.equal(exported.energy_sensitivity.combined.length,27);assert.deepEqual(energyEngine.energySensitivity(exported.inputs,exported.energy_review.sensitivity),exported.energy_sensitivity);assert.equal(exported.annual_energy.actual_grid_purchase_kwh,null);assert.equal(exported.site_id,'us-tx-abilene');assert.equal(exported.inputs.it_mw,421);assert.equal(exported.input_basis.it_mw.kind,'observation');
   assert.equal(exported.input_basis.pue.kind,'assumption');assert.equal(exported.input_basis.power_price.kind,'regional_reference');
   assert.equal(exported.readiness.project_feasibility,'not_verified');assert.ok(exported.model_spec.inputs);assert.ok(exported.unknowns.length);assert.equal(exported.observation_sha256.length,64);assert.equal(exported.review.derivations.length,13);assert.equal(exported.blockers.length,3);assert.ok(exported.blockers.every(b=>b.automatic_fill===false));assert.equal(exported.inputs.energy_quota_mw,0);assert.equal(exported.input_basis.pue.actual_state,'unknown');assert.equal(exported.model_source_sha256.length,64);assert.equal(exported.annual_energy.facility_kwh,3304412160);assert.equal(exported.input_basis.energy_quota_mw.kind,'unknown_unset');assert.equal(exported.input_basis.gate_wait_years.kind,'assumption');assert.equal(exported.input_basis.permit_months.kind,'assumption');assert.equal(exported.input_basis.construction_years.kind,'generic_reference');assert.equal(exported.input_basis.it_class.kind,'scenario_choice');assert.equal(exported.dependency_notice.status,'shared_upstream_assumptions');assert.equal(exported.document_checks.length,10);assert.ok(exported.document_checks.every(d=>!d.model_eligible&&!d.actual_site_verified));assert.equal(Object.keys(exported.input_basis).length,83);assert.ok(Math.abs(exported.annual_energy.proxy_cost_usd-233621939.712)<.001);assert.ok(!JSON.stringify(exported).includes('/Users/'));
   const engine=require('./../web/components/datacenter-model.js');assert.ok(Math.abs(engine.run(exported.inputs,exported.model_spec).ledgers.compute.revenue-exported.results.ledgers.compute.revenue)<.01);
   if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});writeFileSync(process.env.UI_QA_DIR+'/abilene-scenario-'+role+'.json',JSON.stringify(exported,null,2));await page.locator('#site-model-bridge').screenshot({path:process.env.UI_QA_DIR+'/preview-'+role+'.png'});}
   await page.locator('#input-it_mw').fill('');assert.equal(await page.locator('#bridge-export').count(),0);assert.equal(await page.locator('#copy-results').isDisabled(),true);assert.ok((await page.locator('#bridge-result').innerText()).includes('输入无效'));
   await page.locator('#input-it_mw').fill('400');assert.ok((await page.locator('[data-bridge-basis=it_mw]').innerText()).includes('用户假设'));
   page.once('dialog',dialog=>dialog.dismiss());await page.locator('#input-site').selectOption('us_virginia');assert.equal(await page.locator('#input-site').inputValue(),'us_texas');
   page.once('dialog',dialog=>dialog.accept());await page.locator('#input-site').selectOption('us_virginia');assert.equal(await page.locator('#input-site').inputValue(),'us_virginia');assert.equal(await page.locator('#input-demand_rate').inputValue(),'0');assert.ok(await page.locator('#input-demand_rate').isDisabled());
   await page.waitForFunction(()=>document.querySelector('[data-bridge-basis=power_price]')?.textContent.includes('用户假设'));
   assert.ok((await page.locator('[data-bridge-basis=power_price]').textContent()).includes('用户假设')); 
   await page.locator('#input-energy_quota_mw').evaluate(el=>el.closest('details').open=true);await page.locator('#input-energy_quota_mw').fill('200');
   const [boundedDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#bridge-export').click()]);const bounded=JSON.parse(fs.readFileSync(await boundedDownload.path(),'utf8'));assert.equal(bounded.annual_energy.effective_it_mw,200);assert.equal(bounded.input_basis.energy_quota_mw.kind,'user_assumption');
   const before=JSON.stringify(exported);await page.locator('#column-tabs a[data-column=cost]').click();assert.ok(page.url().includes('site=us-tx-abilene'));
   assert.equal(await page.locator('#input-it_mw').inputValue(),'400');assert.equal(JSON.stringify(exported),before);
   for(const width of [320,390,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no overflow '+width);}
   if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:process.env.UI_QA_DIR+'/site-bridge-'+role+'.png',fullPage:true});}
   await page.goto(base+'/ledger.html?site=us-tx-abilene&scope=wrong');await page.getByText(/所请求的观察范围不匹配/).waitFor();assert.notEqual(Number(await page.locator('#input-it_mw').inputValue()),421);
   assert.deepEqual(errors,[]);await context.close();
  }
  const fs=require('node:fs'),path=require('node:path'),os=require('node:os');const local=fs.mkdtempSync(path.join(os.tmpdir(),'site-preview-'));
  try{
   const output=path.join(local,'preview.html');execFileSync(process.env.PYTHON||'python3',['scripts/export_site_model_preview.py','--output',output],{cwd:path.resolve(__dirname,'..')});
   const page=await browser.newPage({viewport:{width:390,height:900}}),network=[],errors=[];page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});page.on('pageerror',e=>errors.push(e.message));
   await page.goto('file://'+output);await page.locator('#bridge-apply').waitFor();assert.notEqual(await page.locator('#input-it_mw').inputValue(),'421');await page.locator('#bridge-apply').click();
   assert.ok((await page.locator('#bridge-result').innerText()).includes('$233.6M'));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#bridge-export').click()]);const data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(data.annual_energy.facility_kwh,3304412160);assert.equal(data.blockers.length,3);
   await page.locator('#bridge-energy-checks summary').click();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.locator('#bridge-energy-checks summary').click();await page.locator('#column-tabs a[data-column=returns]').click();assert.equal(await page.locator('#input-it_mw').inputValue(),'421');assert.deepEqual(errors,[]);assert.deepEqual(network,[]);await page.close();
  }finally{fs.rmSync(local,{recursive:true,force:true});}
  console.log('site_model_bridge: roles, stable identity, preview/confirmation, provenance, immutable export, preset cancellation, scope guard and mobile passed');
 }finally{if(browser)await browser.close();lines.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
