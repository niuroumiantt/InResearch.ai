const {setAppearance} = require('./ui_helpers.cjs');
const assert = require('node:assert/strict');
const {execFileSync, spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {chromium} = require('playwright');
const pages = JSON.parse(execFileSync(process.env.PYTHON || 'python3', ['-c',
  "import sys,json;sys.path.insert(0,'src');from inresearch.interfaces import pages as auth;print(json.dumps({n:getattr(auth,n) for n in ('LOGIN_PAGE','PASSWD_PAGE','FORBIDDEN_PAGE')}))"], {encoding:'utf8'}));
(async () => {
  const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});
  try {
    const page = await browser.newPage();
    for (const [name,html] of Object.entries(pages)) {
      const url = process.env.UI_BASE_URL + '/__auth/' + name;
      await page.route(url, route=>route.fulfill({contentType:'text/html',body:html}));
      await page.goto(url); await page.locator('#ui-skinbar').waitFor();
      assert.equal(await page.locator('.ui-navigation').count(),0);
      assert.ok(await page.locator('form label').evaluateAll(labels=>labels.every(label=>label.control)));
      assert.equal(await page.locator('[data-ui-choice]').count(),0,'no skin switch on auth pages');
      for (const mode of ['light','dark']) for (const width of [360,1440]) {
        await page.setViewportSize({width,height:800});
        await setAppearance(page, mode);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name);
        assert.ok(await page.locator('form,.ui-auth-message').isVisible(),name);
      }
    }
    console.log('PASS 12 auth appearances, field labels and public navigation boundary');
    // Exercise the actual production gate and session cookies, without writing
    // task state or modifying repository accounts/runtime logs.
    const fixture = spawn(process.env.PYTHON || 'python3', ['-u', '-c', `
import sys, tempfile, threading
from pathlib import Path
sys.path.insert(0, 'src')
from inresearch.interfaces import http as serve, auth
with tempfile.TemporaryDirectory() as temporary:
    auth.USERS_FILE = Path(temporary) / 'users.json'
    auth.SECRET_FILE = Path(temporary) / '.hub_secret'
    for username, role in [('admin', 'admin'), ('member', 'member'), ('intern', 'intern'), ('customer', 'customer')]:
        auth.add_user(username, 'Only-test-private-site-8391', role)
    serve.AUTH_ON = True
    serve.Handler.log_message = lambda *args: None
    serve.log_run = lambda *args: None
    server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        print(server.server_port, flush=True)
        sys.stdin.readline()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
`], {stdio:['pipe', 'pipe', 'inherit']});
    const lines = createInterface({input:fixture.stdout});
    try {
      const port = await new Promise((resolve, reject) => {
        lines.once('line', line => /^\d+$/.test(line) ? resolve(line) : reject(Error('Invalid private-site fixture')));
        fixture.once('error', reject);
        fixture.once('exit', code => reject(Error('Private-site fixture exited: ' + code)));
      });
      const base = 'http://127.0.0.1:' + port;
      const context = await browser.newContext({viewport:{width:1280,height:900}});
      const home = await context.newPage(); const errors=[];
      home.on('pageerror', error => errors.push(error.message));
      const response = await home.goto(base + '/');
      assert.equal(response.status(), 200);
      assert.equal(response.headers()['cache-control'], 'no-cache');
      await home.locator('.ui-login').waitFor();
      await home.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
      await home.locator('#world-map .site-point').first().waitFor();
      assert.deepEqual(await home.locator('.ui-navigation a').allTextContents(), ['地图首页', '任务']);
      assert.equal(await home.locator('.ui-appearance-controls .ui-login').getAttribute('href'), '/login');
      assert.equal(await home.locator('.ui-navigation a[href="/login"], .ui-navigation a[href="/account"], .ui-navigation a[href="/ops.html"]').count(), 0);
      for (const width of [320,390,1280]) {
        await home.setViewportSize({width,height:900});
        const login = await home.locator('.ui-login').boundingBox();
        const appearance = await home.locator('#ui-appearance').boundingBox();
        const bar = await home.locator('#ui-skinbar').boundingBox();
        assert.ok(login.x >= appearance.x + appearance.width, 'login is on the right of appearance');
        assert.ok(login.x + login.width <= width && bar.height <= 90, 'anonymous header fits ' + width);
        assert.ok(await home.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      }
      assert.equal(await home.locator('.local-nav').isVisible(), false);
      assert.equal(await home.locator('#layout-link').isVisible(), false);
      for (const method of ['GET', 'HEAD']) {
        for (const path of ['/projects.html', '/ledger.html', '/research/data-centers-2026-project-ledger.json', '/assets/technical-atlas/chip-package-v1.svg']) {
          const result = await context.request.fetch(base + path, {method, maxRedirects:0});
          assert.equal(result.status(), 302, method + ' ' + path);
          assert.equal(result.headers()['location'], '/login');
          assert.equal(result.headers()['cache-control'], 'private, no-store');
        }
        for (const path of ['/api/industry', '/api/news?company=nvidia', '/api/research-tasks?revision=0', '/api/research-task-examples?private=1']) {
          const result = await context.request.fetch(base + path, {method});
          assert.equal(result.status(), 401, method + ' ' + path);
        }
        for (const path of ['/api/industry?overview=1', '/api/news?overview=1']) {
          assert.equal((await context.request.fetch(base + path, {method})).status(), 200);
        }
        assert.equal((await context.request.fetch(base + '/tasks.html', {method, maxRedirects:0})).status(), 200);
        const tasks = await context.request.fetch(base + '/api/research-tasks', {method});
        assert.equal(tasks.status(), 200);
        assert.equal(tasks.headers()['cache-control'], 'private, no-store');
        assert.match(tasks.headers()['vary'], /Cookie/);
        if (method === 'HEAD') assert.equal((await tasks.body()).length, 0);
        else {
          const projection = await tasks.json();
          assert.deepEqual(Object.keys(projection).sort(), ['actor', 'can_create', 'map_register', 'mission', 'package_progress', 'packages', 'public_view', 'revision', 'role', 'site_progress', 'target_site_basis', 'target_site_count', 'target_site_set_at', 'version'].sort());
          assert.equal(projection.role, 'reader');
          assert.equal(projection.actor, '');
          assert.equal(projection.public_view, true);
          assert.equal(projection.can_create, false);
          assert.equal(projection.site_progress.target, projection.target_site_count);
          assert.equal(projection.site_progress.target_basis, projection.target_site_basis);
          assert.equal(projection.site_progress.target_set_at, projection.target_site_set_at);
          assert.ok(projection.target_site_count === null || (Number.isInteger(projection.target_site_count) && projection.target_site_count > 0));
          for (const key of ['published_sites', 'reviewed_reports', 'published_statements']) {
            assert.ok(Number.isInteger(projection.site_progress[key]) && projection.site_progress[key] >= 0, key);
          }
          assert.ok(projection.packages.length > 0);
          for (const item of projection.packages) {
            assert.deepEqual(Object.keys(item).sort(), ['id', 'title', 'region', 'scope', 'sources', 'status'].sort());
          }
          assert.deepEqual(Object.keys(projection.package_progress).sort(), projection.packages.map(item => item.id).sort());
          for (const packageId of Object.keys(projection.package_progress)) {
            const work = projection.package_progress[packageId];
            assert.ok(Number.isInteger(work.published_sites) && work.published_sites >= 0);
            assert.ok(Number.isInteger(work.current_task.version) && work.current_task.version >= 1);
            for (const event of work.events) {
              assert.deepEqual(Object.keys(event).sort(), ['received_at','reviewed_at','last_activity_at','submitter','material','outcome','feedback','next_action','published_statements','held','findings'].sort());
            }
          }
        }
      }
      assert.equal((await context.request.post(base + '/api/research-tasks', {headers:{'X-Requested-With':'research-tasks'},data:{}})).status(), 401);
      await home.goto(base + '/tasks.html');
      assert.equal(new URL(home.url()).pathname, '/tasks.html');
      await home.locator('[data-task-view="task-guide"]').click();
      await home.locator('#work-packages > summary').click();
      await home.locator('#package-rows tr').first().waitFor();
      assert.equal(await home.locator('#new-package').isVisible(), false);
      assert.equal(await home.locator('#package-rows [data-edit]').count(), 0);
      assert.match(await home.locator('#task-role-note').innerText(), /登录后可见/);
      await home.goto(base + '/login');
      await home.locator('input[name=username]').fill('member');
      await home.locator('input[name=password]').fill('Only-test-private-site-8391');
      await Promise.all([home.waitForURL(base + '/'), home.locator('form button').click()]);
      await home.locator('.ui-navigation-backstage [data-nav-section=production]').waitFor();
      assert.equal(await home.locator('#layout-link').isVisible(), true);
      // The request client does not apply Chromium's loopback Secure-cookie exception.
      const memberHeaders = {Cookie:(await context.cookies()).map(cookie => cookie.name + '=' + cookie.value).join('; ')};
      assert.equal((await context.request.get(base + '/tasks.html', {headers:memberHeaders, maxRedirects:0})).status(), 200);
      assert.equal((await context.request.get(base + '/data/raw/research-tasks/ledger.json', {headers:memberHeaders, maxRedirects:0})).status(), 404);
      const whoami = await context.request.get(base + '/api/whoami', {headers:memberHeaders});
      assert.equal(whoami.headers()['cache-control'], 'private, no-store');
      assert.match(whoami.headers()['vary'], /Cookie/);
      assert.equal((await whoami.json()).role, 'member');
      const memberTasks = await (await context.request.get(base + '/api/research-tasks', {headers:memberHeaders})).json();
      assert.equal(memberTasks.role, 'member');
      assert.equal(memberTasks.actor, 'member');
      assert.equal(memberTasks.public_view, false);
      assert.equal(memberTasks.can_create, true);
      for (const field of ['assignee', 'machine', 'model', 'note', 'delivery_pointer', 'due']) {
        assert.ok(field in memberTasks.packages[0], 'member task field ' + field);
      }
      const customer = await browser.newContext();
      const customerPage = await customer.newPage();
      customerPage.on('pageerror', error => errors.push(error.message));
      await customerPage.goto(base + '/login');
      await customerPage.locator('input[name=username]').fill('customer');
      await customerPage.locator('input[name=password]').fill('Only-test-private-site-8391');
      await Promise.all([customerPage.waitForURL(base + '/'), customerPage.locator('form button').click()]);
      await customerPage.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
      assert.equal(await customerPage.locator('.ui-navigation-delivery [data-nav-section]').count(),7);
      assert.equal(await customerPage.locator('.ui-navigation-backstage,.ui-footer-runtime').count(),0);
      const customerHeaders = {Cookie:(await customer.cookies()).map(cookie => cookie.name + '=' + cookie.value).join('; ')};
      const customerNavigation = await (await customer.request.get(base + '/api/navigation?page=/ledger.html?view=cost',{headers:customerHeaders})).json();
      assert.equal(customerNavigation.identity.kind,'customer');
      assert.equal(customerNavigation.navigation.backstage.length,0);
      assert.deepEqual(customerNavigation.search.scopes,['delivery']);
      for(const path of ['/ops.html','/supply.html','/admin/company.html','/workspace.html?section=production']) assert.equal((await customer.request.get(base + path,{headers:customerHeaders,maxRedirects:0})).status(),403,'customer denial '+path);
      async function checkAccount(accountPage, username, role) {
        const summary = accountPage.locator('.ui-account-menu > summary');
        await summary.waitFor();
        assert.equal(await accountPage.locator('.ui-account-name').textContent(), username);
        assert.equal(await accountPage.locator('.ui-account-role').textContent(), role);
        assert.equal(await accountPage.locator('.ui-navigation a[href="/login"], .ui-navigation a[href="/account"], .ui-navigation a[href="/ops.html"], .ui-navigation .ui-admin-link').count(), 0);
        for (const mode of ['light','dark']) for (const width of [1280,390,320]) {
          await accountPage.setViewportSize({width,height:900});
          await setAppearance(accountPage, mode);
          await summary.focus(); await summary.press('Enter');
          await accountPage.locator('.ui-account-panel a[href="/account"]').waitFor();
          assert.equal(await accountPage.locator('.ui-account-identity').innerText(), username + '\n' + role);
          assert.equal(await accountPage.locator('.ui-account-panel .ui-management-link,.ui-account-panel .ui-admin-link').count(),0);
          assert.deepEqual(await accountPage.locator('.ui-account-panel a').allTextContents(),['个人信息','修改密码','退出登录']);
          const menu = await accountPage.locator('.ui-account-panel').boundingBox();
          const bar = await accountPage.locator('#ui-skinbar').boundingBox();
          assert.ok(menu.x >= 0 && menu.x + menu.width <= width + 1, role + ' menu fits ' + width);
          assert.ok(bar.height <= (width<=700?90:140), role + ' header follows the registered desktop/mobile rows at ' + width);
          await summary.press('Tab');
          assert.equal(await accountPage.evaluate(()=>document.activeElement.getAttribute('href')), '/account');
          await accountPage.keyboard.press('Escape');
          assert.equal(await accountPage.locator('.ui-account-menu').evaluate(e=>e.open), false);
          assert.equal(await summary.evaluate(e=>e===document.activeElement), true);
        }
        await summary.click();
        await accountPage.locator('.ui-account-panel a[href="/account"]').click();
        await accountPage.waitForURL(base + '/account');
        await accountPage.waitForFunction(name=>document.querySelector('[data-ui-account-name]')?.textContent===name,username);
        assert.equal(await accountPage.locator('[data-ui-account-role]').textContent(), role);
        assert.equal(await accountPage.locator('input[name=old_password]').count(), 1, 'password change remains available');
        await accountPage.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
        await accountPage.locator('.ui-account-menu > summary').click();
        await accountPage.locator('.ui-account-panel a[href="/account#password"]').click();
        await accountPage.waitForURL(base + '/account#password');
        await accountPage.locator('#password').waitFor();
        await accountPage.locator('.ui-account-menu > summary').click();
        await accountPage.locator('.ui-logout').click();
        await accountPage.waitForURL(base + '/login');
        await accountPage.locator('.ui-login').waitFor();
        assert.equal(await accountPage.locator('.ui-account-menu').count(), 0);
        assert.deepEqual(await accountPage.evaluate(()=>fetch('/api/whoami').then(r=>r.json())), {ok:true,user:null,role:'reader'});
      }
      await checkAccount(home, 'member', 'member');
      await checkAccount(customerPage, 'customer', 'customer');
      const intern = await browser.newContext();
      const internLogin = await intern.request.post(base + '/api/login', {data:{username:'intern',password:'Only-test-private-site-8391'}});
      assert.equal(internLogin.status(), 200);
      const internHeaders = {Cookie:internLogin.headers()['set-cookie'].split(';')[0]};
      const internPage = await intern.newPage(); await internPage.goto(base + '/tasks.html');
      await internPage.locator('.ui-navigation-backstage [data-nav-section=production]').waitFor();
      assert.equal(await internPage.locator('.ui-navigation-delivery').count(),0);
      assert.deepEqual(await internPage.locator('.ui-navigation-backstage .ui-section-panel a').allTextContents(),['团队任务','采集与接收']);
      assert.equal((await intern.request.get(base + '/api/research-tasks', {headers:internHeaders})).status(), 200);
      assert.equal((await intern.request.get(base + '/ops.html', {headers:internHeaders})).status(), 403);
      await checkAccount(internPage, 'intern', 'intern');
      const admin = await browser.newContext();
      const adminPage = await admin.newPage();
      adminPage.on('pageerror', error => errors.push(error.message));
      await adminPage.goto(base + '/login');
      await adminPage.locator('input[name=username]').fill('admin');
      await adminPage.locator('input[name=password]').fill('Only-test-private-site-8391');
      await Promise.all([adminPage.waitForURL(base + '/'), adminPage.locator('form button').click()]);
      await adminPage.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
      await adminPage.goto(base + '/ops.html');
      await adminPage.locator('.ui-navigation-backstage [data-nav-section=operations] > summary').waitFor();
      assert.equal(await adminPage.locator('.ui-navigation-delivery [data-nav-section]').count(),7);
      assert.equal(await adminPage.locator('.ui-navigation-backstage [data-nav-section]').count(),6);
      assert.equal(await adminPage.locator('.ui-navigation-backstage [data-nav-section=operations] > summary').getAttribute('aria-current'),'page');
      await checkAccount(adminPage, 'admin', 'admin');
      assert.deepEqual(errors, []);
      await admin.close(); await intern.close(); await customer.close(); await context.close();
      console.log('PASS anonymous right login and strict task projection, private GET/HEAD/download gate, real customer/member/admin/intern accounts, profile/logout and keyboard menus in two themes at 320/390/1280');
    } finally {
      fixture.stdin.end('\n'); lines.close();
      await new Promise(resolve => fixture.once('exit', resolve));
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
