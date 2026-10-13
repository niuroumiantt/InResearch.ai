/* Four product columns share the existing ledger state and calculation engine. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {mkdtempSync, rmSync, mkdirSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join, resolve} = require('node:path');
const {createInterface} = require('node:readline');
const {chromium} = require('playwright');

(async () => {
  const root = resolve(__dirname, '..');
  let server, lines, directory, browser;
  try {
    let base = process.env.UI_BASE_URL, cookie = process.env.UI_ADMIN_COOKIE, customerCookie = process.env.UI_CUSTOMER_COOKIE;
    if (!base) {
      directory = mkdtempSync(join(tmpdir(), 'inresearch-economics-nav-'));
      const code = "import sys,os,json,secrets; from pathlib import Path; sys.path.insert(0,'src'); from inresearch.storage.layout import initialize_runtime; initialize_runtime(); from inresearch.interfaces import http,auth; http.AUTH_ON=True; auth.USERS_FILE=Path(os.environ['INRESEARCH_INTAKE_ROOT'])/'users.json'; auth.SECRET_FILE=Path(os.environ['INRESEARCH_INTAKE_ROOT'])/'.secret'; auth.add_user('economics-admin',secrets.token_urlsafe(32),'admin'); auth.add_user('economics-customer',secrets.token_urlsafe(32),'customer'); s=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler); print(json.dumps({'port':s.server_port,'cookie':auth.make_cookie('economics-admin').split(';')[0],'customer_cookie':auth.make_cookie('economics-customer').split(';')[0]}),flush=True); s.serve_forever()";
      server = spawn(process.env.PYTHON || 'python3', ['-u', '-c', code], {cwd:root, env:{...process.env, INRESEARCH_INTAKE_ROOT:directory, INRESEARCH_MARKET_ENABLED:'0'}, stdio:['ignore','pipe','inherit']});
      lines = createInterface({input:server.stdout});
      const ready = await new Promise((resolveReady, reject) => {
        const timer = setTimeout(() => reject(Error('Economics server did not become ready')), 15000);
        lines.once('line', line => {clearTimeout(timer); try {resolveReady(JSON.parse(line));} catch (error) {reject(error);}});
        server.once('error', error => {clearTimeout(timer); reject(error);});
        server.once('exit', code => {clearTimeout(timer); reject(Error('Economics server exited: '+code));});
      });
      base = 'http://127.0.0.1:'+ready.port; cookie = ready.cookie; customerCookie = ready.customer_cookie;
    }
    assert.ok(cookie, 'use a real authorized session for protected model pages');
    browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1000}}), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const separator = cookie.indexOf('=');
    await page.context().addCookies([{name:cookie.slice(0,separator),value:cookie.slice(separator+1),url:base}]);
    let modelRequests = 0;
    page.on('request', request => {if(new URL(request.url()).pathname === '/data/datacenter_model.json')modelRequests++;});
    const ready = async () => page.waitForFunction(() => document.querySelector('#model-app')?.getAttribute('aria-busy') === null);
    const capture = async name => {if(process.env.UI_QA_DIR){mkdirSync(process.env.UI_QA_DIR,{recursive:true});await page.screenshot({path:join(process.env.UI_QA_DIR,name+'.png'),fullPage:true});}};
    const column = async name => {
      await page.locator('#column-tabs a[data-column='+name+']').click();
      assert.equal(await page.locator('#model-app').getAttribute('data-column'), name);
      assert.equal(new URL(page.url()).searchParams.get('view'), name);
      assert.equal(await page.locator('#column-tabs [aria-current=page]').count(), 1);
    };
    await page.goto(base+'/ledger.html?view=basis'); await ready();
    assert.ok(await page.locator('#basis').isVisible());
    const basisText = await page.locator('#basis').innerText();
    const readinessText = await page.locator('#region-card .readiness-note').innerText();
    assert.match(await page.locator('#basis').innerText(), /不是同一种年成本公式/);
    assert.equal(await page.locator('a[href*="doc.html?f=framework"]').count(), 0);
    assert.equal(await page.locator('#calibration-table .flag.no').count(), 0);
    assert.doesNotMatch(await page.locator('#gap-list thead').innerText(), /抓取类型|要找什么/);
    await capture('economics-basis-desktop');
    await page.evaluate(() => {window.economicsDocumentMarker = 'same-document';});
    await page.locator('#input-it_mw').fill('77');
    await column('cost');
    assert.ok(await page.locator('#view-lifecycle.on').isVisible());
    await page.locator('#views button[data-view=unit]').click();
    assert.ok(await page.locator('#view-unit.on').isVisible());
    const unitCost = await page.locator('#cost-total').textContent();
    await column('returns'); assert.ok(await page.locator('#view-ledgers.on').isVisible());
    await column('scenarios'); assert.ok(await page.locator('#view-inverse.on').isVisible());
    assert.ok(await page.locator('#tornado').isVisible());
    assert.ok(await page.locator('#scenario-table').isVisible());
    assert.equal(await page.locator('#grid-table tbody td').count(), 25);
    await column('basis');
    assert.equal(await page.locator('#input-it_mw').inputValue(), '77');
    await column('cost');
    assert.ok(await page.locator('#view-unit.on').isVisible(), 'returning to cost keeps the selected cost reading');
    assert.equal(await page.locator('#cost-total').textContent(), unitCost);
    assert.equal(await page.evaluate(() => window.economicsDocumentMarker), 'same-document');
    assert.equal(modelRequests, 1, 'changing columns does not reload or refetch the model');
    await page.getByRole('button',{name:'校准 · 我们的 2026-09-14 全成本基准'}).click();
    assert.equal(await page.locator('#cost-total').textContent(), '$1.168B');
    assert.equal(await page.locator('#cost-per-hour').textContent(), '$4.10');
    await page.getByRole('button',{name:'校准 · 摩根士丹利 1GW GB300 出租'}).click();
    assert.equal(await page.locator('#cost-per-hour').textContent(), '$3.57');
    await column('returns');
    assert.equal(await page.locator('#kpi-compute strong').textContent(), '30.9%');
    await column('scenarios');
    await page.getByRole('button',{name:'校准 · 高盛 15% 回报门槛'}).click();
    assert.equal(await page.locator('#inv-revenue strong').textContent(), '$11.65B');
    await capture('economics-scenarios-desktop');
    const currentInputs = await page.locator('#model-inputs').evaluate(form => [...form.querySelectorAll('input,select')].map(input => [input.id,input.value]));
    await page.goBack();
    assert.equal(await page.locator('#model-app').getAttribute('data-column'), 'returns');
    assert.deepEqual(await page.locator('#model-inputs').evaluate(form => [...form.querySelectorAll('input,select')].map(input => [input.id,input.value])), currentInputs);
    for (const [hash, name, reading] of [['lifecycle','cost','lifecycle'],['unit','cost','unit'],['ledgers','returns','ledgers'],['inverse','scenarios','inverse']]) {
      await page.goto(base+'/ledger.html#'+hash); await ready();
      assert.equal(await page.locator('#model-app').getAttribute('data-column'), name);
      assert.ok(await page.locator('#view-'+reading+'.on').isVisible(), 'legacy '+hash+' opens its calculation reading');
    }
    for (const [alias, reading] of [['tco','lifecycle'],['cost','unit'],['economics','ledgers']]) {
      await page.goto(base+'/'+alias+'.html'); await ready();
      assert.ok(await page.locator('#view-'+reading+'.on').isVisible());
    }
    await page.goto(base+'/ledger.html?view=basis'); await ready();
    await page.locator('#column-tabs a[data-column=basis]').focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#model-app').getAttribute('data-column'), 'cost');
    await page.setViewportSize({width:390,height:844});
    for (const name of ['basis','cost','returns','scenarios']) {
      await column(name);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), name+' fits the mobile viewport');
    }
    await capture('economics-columns-mobile');
    if (customerCookie) {
      const customer = await browser.newPage({viewport:{width:1440,height:1000}}), writes = [];
      customer.on('pageerror', error => errors.push(error.message));
      customer.on('request', request => {if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url());});
      const split = customerCookie.indexOf('=');
      await customer.context().addCookies([{name:customerCookie.slice(0,split),value:customerCookie.slice(split+1),url:base}]);
      await customer.goto(base+'/ledger.html?view=basis');
      await customer.waitForFunction(() => document.querySelector('#model-app')?.getAttribute('aria-busy') === null);
      assert.equal(await customer.locator('#basis').innerText(), basisText, 'customer and IT use the same delivered model explanation');
      assert.equal(await customer.locator('#region-card .readiness-note').innerText(), readinessText, 'missing internal governance metadata must not be displayed as zero unverified requirements');
      await customer.locator('#column-tabs a[data-column=cost]').click();
      await customer.locator('#views button[data-view=unit]').click();
      await customer.getByRole('button',{name:'校准 · 摩根士丹利 1GW GB300 出租'}).click();
      assert.equal(await customer.locator('#cost-per-hour').textContent(), '$3.57');
      await customer.locator('#input-it_mw').fill('50');
      await customer.locator('#column-tabs a[data-column=returns]').click();
      assert.equal(await customer.locator('#input-it_mw').inputValue(), '50');
      assert.deepEqual(writes, [], 'customer simulation never writes the official model or research data');
      await customer.context().close();
    }
    assert.deepEqual(errors, []);
    console.log('PASS economics columns: explicit basis, shared state, history, legacy URLs, calibration outputs, scenario tools and mobile'+(customerCookie?', customer local simulation':''));
  } finally {
    if (browser) await browser.close();
    if (server) server.kill();
    if (lines) lines.close();
    if (directory) rmSync(directory,{recursive:true,force:true});
  }
})().catch(error => {console.error(error);process.exitCode=1;});
