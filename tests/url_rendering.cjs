/* Untrusted URL values and Markdown remain text or validated links. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL;
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.UI_BROWSER_CHANNEL || undefined,
    args:['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage();
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

    const markdown = `# Fixture\n\n## ${payload}\n\n## Second\n\n## Third\n\n` +
      '[unsafe](javascript:window.__urlExecuted=true)\n\n' +
      '[quoted](https://example.test/"onpointerenter="window.__urlExecuted=true)\n\n' +
      '[valid](https://example.test/?a=1&b=2)\n\n' +
      '[current](../framework/CURRENT.md)\n\n' +
      '`https://example.test/code`\n\n**Strong & clear**';
    await page.route('**/research/M08.md?*', route => route.fulfill({body:markdown,contentType:'text/plain'}));
    await page.goto(base+'/doc.html?f=research/M08.md');
    await page.locator('#toc a').nth(2).waitFor();
    assert.equal(await page.locator('#toc a').first().textContent(), payload);
    assert.equal(await page.locator('#content img, #toc img, #content [onpointerenter], #content [onerror]').count(), 0);
    assert.equal(await page.locator('#content a[href^="javascript:"]').count(), 0);
    assert.equal(await page.locator('#content code a').count(), 0);
    assert.equal(await page.getByRole('link',{name:'valid',exact:true}).getAttribute('href'), 'https://example.test/?a=1&b=2');
    assert.match(await page.getByRole('link',{name:'current',exact:true}).getAttribute('href'), /doc\.html\?f=framework%2FCURRENT\.md$/);
    assert.equal(await page.locator('#content b').textContent(), 'Strong & clear');
    assert.equal(await page.evaluate(() => Boolean(window.__urlExecuted)), false);

    const report = await (await page.request.get(base+'/api/report')).json();
    const finding = report.chapters[0].findings[0];
    finding.title = payload;
    finding.body = ['- **结论**：[unsafe](javascript:window.__urlExecuted=true)',
      '  - [quoted](https://example.test/"onpointerenter="window.__urlExecuted=true)',
      '  - `https://example.test/code`'];
    await page.route('**/api/report?*', route => route.fulfill({json:report}));
    await page.goto(base+'/report.html');
    await page.locator('.finding').first().waitFor();
    assert.match(await page.locator('.finding h3').first().textContent(), /<img src=x/);
    assert.equal(await page.locator('#docroot img, #docroot [onpointerenter], #docroot a[href^="javascript:"], #docroot code a').count(), 0);
    assert.equal(await page.evaluate(() => Boolean(window.__urlExecuted)), false);
    console.log('PASS URL text, Markdown links, code spans and document table of contents');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
