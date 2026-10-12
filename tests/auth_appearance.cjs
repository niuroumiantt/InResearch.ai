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
        await page.locator('#ui-appearance').selectOption(mode);
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
    for username, role in [('admin', 'admin'), ('member', 'member'), ('intern', 'intern')]:
        auth.add_user(username, 'Only-test-private-site-8391', role)
    serve.AUTH_ON = True
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
      await home.locator('#world-map .site-point').first().waitFor();
      assert.deepEqual(await home.locator('.ui-navigation a').allTextContents(), ['行业总览', '任务跟踪', '登录']);
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
          assert.deepEqual(Object.keys(projection).sort(), ['actor', 'can_create', 'map_register', 'mission', 'packages', 'public_view', 'revision', 'role', 'version'].sort());
          assert.equal(projection.role, 'reader');
          assert.equal(projection.actor, '');
          assert.equal(projection.public_view, true);
          assert.equal(projection.can_create, false);
          assert.ok(projection.packages.length > 0);
          for (const item of projection.packages) {
            assert.deepEqual(Object.keys(item).sort(), ['id', 'title', 'region', 'scope', 'sources', 'status'].sort());
          }
        }
      }
      assert.equal((await context.request.post(base + '/api/research-tasks', {headers:{'X-Requested-With':'research-tasks'},data:{}})).status(), 401);
      await home.goto(base + '/tasks.html');
      assert.equal(new URL(home.url()).pathname, '/tasks.html');
      await home.locator('#package-rows tr').first().waitFor();
      assert.equal(await home.locator('#new-package').isVisible(), false);
      assert.equal(await home.locator('#package-rows [data-edit]').count(), 0);
      assert.match(await home.locator('#task-role-note').innerText(), /登录后可见/);
      await home.goto(base + '/login');
      await home.locator('input[name=username]').fill('member');
      await home.locator('input[name=password]').fill('Only-test-private-site-8391');
      await Promise.all([home.waitForURL(base + '/'), home.locator('form button').click()]);
      await home.locator('.ui-navigation a[href="/tasks.html"]').waitFor();
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
      const intern = await browser.newContext();
      const internLogin = await intern.request.post(base + '/api/login', {data:{username:'intern',password:'Only-test-private-site-8391'}});
      assert.equal(internLogin.status(), 200);
      const internHeaders = {Cookie:internLogin.headers()['set-cookie'].split(';')[0]};
      const internPage = await intern.newPage(); await internPage.goto(base + '/tasks.html');
      await internPage.locator('.ui-navigation a[href="/supply.html"]').waitFor();
      assert.deepEqual(await internPage.locator('.ui-navigation a').allTextContents(), ['任务跟踪', '采集']);
      assert.equal((await intern.request.get(base + '/api/research-tasks', {headers:internHeaders})).status(), 200);
      assert.equal((await intern.request.get(base + '/ops.html', {headers:internHeaders})).status(), 403);
      assert.deepEqual(errors, []);
      await intern.close(); await context.close();
      console.log('PASS real anonymous homepage/tasks and strict task projection, private GET/HEAD/download gate, member login and intern task access');
    } finally {
      fixture.stdin.end('\n'); lines.close();
      await new Promise(resolve => fixture.once('exit', resolve));
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
