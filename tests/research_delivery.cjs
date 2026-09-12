const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL;
(async () => {
  const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    const report = await (await page.request.get(base+'/api/report')).json();
    await page.goto(base+'/report.html#M01-F1');
    await page.locator('.finding').first().waitFor();
    assert.equal(await page.locator('.finding').count(), report.finding_count);
    assert.equal(report.chapters.length,15);
    assert.deepEqual(await page.locator('.finding').evaluateAll(nodes=>nodes.map(node=>node.id)),
      report.chapters.flatMap(ch=>ch.findings.map(f=>f.id)));
    assert.match(await page.locator('.cover .meta').innerText(), /兼容研究结论/);
    const tasks = await (await page.request.get(base+'/api/tasks')).json();
    const snapshot = await (await page.request.get(base+'/api/research')).json();
    assert.deepEqual(tasks.orders.map(o=>o.wid).sort(),snapshot.tasks.map(o=>o.wid).sort());
    await page.goto(base+'/team.html'); await page.locator('#tb tr').nth(1).waitFor();
    assert.match(await page.locator('#sub').innerText(),new RegExp(String(tasks.orders.length)));
    assert.deepEqual(errors,[]);
    console.log('PASS report content, source model, current task parity and team rendering');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
