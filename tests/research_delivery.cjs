const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL;
(async () => {
  const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    // 2026-09-28：成果页默认是四问快照；专题全文（兼容研究结论）在 ?legacy=1
    const snap = await (await page.request.get(base+'/api/report')).json();
    assert.deepEqual(snap.chapters.map(c=>c.id),['q1','q2','q3','q4']);
    await page.goto(base+'/report.html');await page.locator('#cover').waitFor();
    assert.equal(await page.locator('section.chapter').count(),4,'four chapters, four questions');
    assert.match(await page.locator('#cover').innerText(),/可信边界/);
    assert.match(await page.locator('#topics').innerText(),new RegExp(String(snap.topics.finding_count)));
    const report = await (await page.request.get(base+'/api/report?legacy=1')).json();
    await page.goto(base+'/report.html?legacy=1#M01-F1');
    await page.locator('.finding').first().waitFor();
    assert.equal(await page.locator('.finding').count(), report.finding_count);
    assert.equal(report.chapters.length,15);
    assert.deepEqual(await page.locator('.finding').evaluateAll(nodes=>nodes.map(node=>node.id)),
      report.chapters.flatMap(ch=>ch.findings.map(f=>f.id)));
    assert.match(await page.locator('.cover .meta').innerText(), /兼容研究结论/);
    const tasks = await (await page.request.get(base+'/api/tasks')).json();
    const snapshot = await (await page.request.get(base+'/api/research')).json();
    assert.deepEqual(tasks.orders.map(o=>o.wid).sort(),snapshot.tasks.map(o=>o.wid).sort());
    await page.goto(base+'/node.html');
    await page.locator('#grid .board').first().waitFor();
    // 2026-09-28：派工面板读目标表（目标行数），不再显示工单数
    const targets = await (await page.request.get(base+'/data/tco_targets.json')).json();
    assert.match(await page.locator('#grid').innerText(), new RegExp(String(targets.targets.length)+' 行目标'));
    // 2026-09-28：团队看板并入采集页的「研究问题任务」标签
    await page.goto(base+'/supply.html#tasks'); await page.locator('#tk-table tr').nth(1).waitFor();
    assert.match(await page.locator('#tk-sub').innerText(),new RegExp(String(tasks.orders.length)));
    assert.deepEqual(errors,[]);
    console.log('PASS report content, source model, current task parity and team rendering');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
