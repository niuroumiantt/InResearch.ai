const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
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
      for (const skin of ['Attio','folk']) for (const mode of ['light','dark']) for (const width of [360,1440]) {
        await page.setViewportSize({width,height:800});
        await page.getByRole('button',{name:skin,exact:true}).click();
        await page.locator('#ui-appearance').selectOption(mode);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name);
        assert.ok(await page.locator('form,.ui-auth-message').isVisible(),name);
      }
    }
    console.log('PASS 24 auth appearances, field labels and public navigation boundary');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
