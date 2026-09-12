/* Self-contained browser regression: URL values must remain text. */
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json'};

(async () => {
  const server = http.createServer(async (req, res) => {
    try {
      const file = path.resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
      if (!file.startsWith(root + path.sep)) throw Error('outside test root');
      const data = await fs.readFile(file);
      res.writeHead(200, {'Content-Type':types[path.extname(file)] || 'application/octet-stream'});
      res.end(data);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true,
      ...(process.env.UI_BROWSER_CHANNEL ? {channel:process.env.UI_BROWSER_CHANNEL} : {}),
      args:['--enable-unsafe-swiftshader']});
    const page = await browser.newPage();
    const base = `http://127.0.0.1:${server.address().port}`;
    const payload = '<img src=x onerror="window.__urlExecuted=true">';
    await page.goto(`${base}/company.html?c=${encodeURIComponent(payload)}`);
    await page.locator('#root .err').waitFor();
    assert.equal(await page.locator('#root .err').textContent(), `加载失败：公司不存在: ${payload}`);
    assert.equal(await page.locator('#root .err img').count(), 0);
    assert.equal(await page.evaluate(() => Boolean(window.__urlExecuted)), false);
    await page.goto(`${base}/compare.html?f=${encodeURIComponent(payload)}`);
    await page.locator('.meta b').first().waitFor();
    assert.equal(await page.locator('.meta b').first().textContent(), payload);
    assert.equal(await page.locator('.meta img').count(), 0);
    assert.equal(await page.evaluate(() => Boolean(window.__urlExecuted)), false);
    console.log('PASS company error and comparison filename render URL input as text');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
