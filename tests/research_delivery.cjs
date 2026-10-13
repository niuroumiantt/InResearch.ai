const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.env.UI_BASE_URL;
(async () => {
  const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined, headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    if(process.env.UI_ADMIN_COOKIE){const cookie=process.env.UI_ADMIN_COOKIE,split=cookie.indexOf('=');await page.context().addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:base}]);}
    // The default is a delivered snapshot; operational dispatch stays in the team API.
    const snap = await (await page.request.get(base+'/api/report')).json();
    assert.deepEqual(snap.chapters.map(c=>c.id),['q1','q2','q3','q4']);
    const chapters=Object.fromEntries(snap.chapters.map(c=>[c.id,c]));
    const targets = await (await page.request.get(base+'/data/tco_targets.json')).json();
    assert.equal(chapters.q4.teams.reduce((n,t)=>n+t.rows,0),targets.targets.length,'internal API retains the actual team workload');
    assert.equal(chapters.q4.not_connected,snap.boundary.targets.not_connected);
    assert.equal(chapters.q4.teams.reduce((n,t)=>n+t.needed,0),chapters.q4.by_status.needed||0);
    assert.ok(Number.isInteger(chapters.q4.due_30d),'internal API retains actual due-window state');
    assert.ok(chapters.q4.teams.every(t=>typeof t.connected==='boolean'));
    await page.goto(base+'/report.html');await page.locator('#cover').waitFor();
    assert.equal(await page.locator('section.chapter').count(),4,'three research chapters and delivered source guidance');
    assert.match(await page.locator('#cover').innerText(),/可信边界/);
    assert.match(await page.locator('#cover').innerText(),/不是完整历史版本库/);
    assert.doesNotMatch(await page.locator('#docroot').innerText(),/目标行|目标表|待建队|下一到期|抓取登记|Git 内载体/);
    assert.equal(await page.locator('#docroot a[href*="legacy"], .topbar a[href*="doc.html"], .topbar a[href*="github.com"]').count(),0);
    assert.equal(await page.locator('#q3 th').count(),6);
    assert.equal(await page.locator('#q3 tr').count(),chapters.q3.factors.length+1);
    assert.deepEqual(await page.locator('#q1 table').first().locator('tr td:first-child').allTextContents(),chapters.q1.account.map(a=>a.label));
    assert.equal(await page.locator('#q4 a[href="/guide.html?view=method"]').count(),1);
    assert.equal(await page.locator('#q4 a[href="/guide.html?view=sources"]').count(),1);
    const structure=await page.locator('#docroot > section').evaluateAll(nodes=>nodes.map(n=>({id:n.id,heading:n.querySelector('h1,h2')?.textContent})));
    await page.evaluate(()=>{window.reportPrintCalls=0;window.print=()=>window.reportPrintCalls++;});
    await page.locator('#print-report').click();assert.equal(await page.evaluate(()=>window.reportPrintCalls),1);
    assert.equal((await page.pdf({format:'A4',printBackground:true})).subarray(0,5).toString(),'%PDF-','the delivered snapshot has a real printable PDF');
    const reordered=structuredClone(snap);reordered.chapters=[chapters.q4,chapters.q2,{id:'future',title:'unrelated chapter'},chapters.q3,chapters.q1];
    const reorderedResponse=route=>route.fulfill({contentType:'application/json',body:JSON.stringify(reordered)});
    await page.route('**/api/report?*',reorderedResponse);
    await page.goto(base+'/report.html');await page.locator('#q3').waitFor();
    assert.deepEqual(await page.locator('#docroot > section').evaluateAll(nodes=>nodes.map(n=>({id:n.id,heading:n.querySelector('h1,h2')?.textContent}))),structure,'new or reordered chapters do not change the stable reading sections');
    await page.unroute('**/api/report?*',reorderedResponse);
    if(process.env.UI_CUSTOMER_COOKIE){
      const customer=await browser.newPage({viewport:{width:1440,height:1000}}),cookie=process.env.UI_CUSTOMER_COOKIE,split=cookie.indexOf('=');
      customer.on('pageerror',error=>errors.push(error.message));
      await customer.context().addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:base}]);
      const response=await customer.request.get(base+'/api/report');assert.equal(response.status(),200);const delivered=await response.json();
      const forbidden=new Set(['teams','due_30d','due_targets','not_connected','carriers','fetch','target_id','target_ids','assignee']);
      const check=value=>{if(!value||typeof value!=='object')return;for(const [key,child] of Object.entries(value)){assert.ok(!forbidden.has(key),'customer API contains internal '+key);check(child);}};
      check(delivered);
      assert.equal((await customer.request.get(base+'/assets/markdown-inline.js')).status(),200,'the real customer can load the report renderer dependency');
      await customer.goto(base+'/report.html');await customer.locator('#q3').waitFor();
      assert.deepEqual(await customer.locator('#docroot > section').evaluateAll(nodes=>nodes.map(n=>({id:n.id,heading:n.querySelector('h1,h2')?.textContent}))),structure);
      assert.doesNotMatch(await customer.locator('#docroot').innerText(),/目标行|目标表|待建队|下一到期|抓取登记|Git 内载体/);
      assert.equal(await customer.locator('#q1 table').first().innerText(),await page.locator('#q1 table').first().innerText(),'customer retains the real baseline account values and source counts');
      assert.equal((await customer.request.get(base+'/api/report?legacy=1')).status(),403);
      assert.equal((await customer.request.get(base+'/report.html?legacy=1')).status(),403);
      await customer.setViewportSize({width:390,height:844});assert.ok(await customer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await customer.context().close();
    }
    const studyLink = page.locator('#datacenter-capacity-study');
    assert.equal(await studyLink.getAttribute('href'), '/research/data-centers-2026.html');
    assert.ok(await studyLink.isVisible());
    const report = await (await page.request.get(base+'/api/report?legacy=1')).json();
    assert.equal(report.finding_count,snap.topics.finding_count,'legacy conclusions stay in their original internal source');
    await page.goto(base+'/report.html?legacy=1#M01-F1');
    await page.locator('.finding').first().waitFor();
    assert.equal(await page.locator('.finding').count(), report.finding_count);
    assert.equal(report.chapters.length,15);
    assert.deepEqual(await page.locator('.finding').evaluateAll(nodes=>nodes.map(node=>node.id)),
      report.chapters.flatMap(ch=>ch.findings.map(f=>f.id)));
    assert.match(await page.locator('.cover .meta').innerText(), /兼容研究结论/);
    assert.equal(await page.locator('#datacenter-capacity-study').getAttribute('href'), '/research/data-centers-2026.html');
    await page.locator('#datacenter-capacity-study').click();
    await page.locator('article h1').waitFor();
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('article figure svg').count(), 12);
    assert.equal(await page.locator('article h2').filter({hasText:/^第[一二三四五六]章/}).count(), 6);
    const labels = await page.locator('article svg text').evaluateAll(nodes => nodes.map(node => {
      const box = node.getBBox(), view = node.ownerSVGElement.viewBox.baseVal;
      return {text:node.textContent, x:box.x, y:box.y, right:box.x+box.width, bottom:box.y+box.height, width:view.width, height:view.height};
    }));
    assert.ok(labels.length > 100);
    const clipped = labels.filter(t => t.x < -2 || t.y < -2 || t.right > t.width+2 || t.bottom > t.height+2);
    assert.deepEqual(clipped, [], 'SVG text must fit the rendered viewBox');
    for (const width of [1440,390,320]) {
      await page.setViewportSize({width,height:1000});
      assert.ok(await page.locator('article h1').isVisible());
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), 'article page overflow at '+width);
    }
    for (const region of ['us','sea','cn']) {
      await page.goto(base+'/research/data-centers-2026-'+region+'.html');
      await page.locator('article h1').waitFor();
      assert.ok(await page.locator('article h3, article h4').count() > 5);
    }
    await page.goto(base+'/research/data-centers-2026-projects.html');
    await page.locator('#ledger-rows tr').nth(167).waitFor();
    assert.equal(await page.locator('#ledger-status').innerText(), '显示 168 / 168 条记录');
    await page.locator('#region-filter').selectOption('us');
    assert.equal(await page.locator('#ledger-rows tr').count(), 47);
    await page.locator('#search-filter').fill('Abilene');
    assert.equal(await page.locator('#ledger-rows tr').count(), 2);
    assert.match(await page.locator('#ledger-rows').innerText(), /0\.672 GW critical IT/);
    assert.match(await page.locator('#ledger-rows').innerText(), /0\.9 GW/);
    await page.locator('#search-filter').fill('');
    await page.locator('#region-filter').selectOption('sea');
    await page.locator('#country-filter').selectOption('SG');
    assert.equal(await page.locator('#ledger-rows tr').count(), 7);
    await page.locator('#country-filter').selectOption('');
    await page.locator('#region-filter').selectOption('cn');
    assert.equal(await page.locator('#ledger-rows tr').count(), 52);
    await page.locator('#search-filter').fill('<script>alert(1)</script>');
    assert.equal(await page.locator('#ledger-rows tr').count(), 0);
    const downloadURL = await page.getByRole('link',{name:'下载项目台账（JSON）',exact:true}).getAttribute('href');
    const ledger = await (await page.request.get(base+downloadURL)).json();
    assert.equal(ledger.records.length,168);
    assert.equal(ledger.aggregation_allowed,false);
    await page.setViewportSize({width:1440,height:1000});
    const tasks = await (await page.request.get(base+'/api/tasks')).json();
    const snapshot = await (await page.request.get(base+'/api/research')).json();
    assert.deepEqual(tasks.orders.map(o=>o.wid).sort(),snapshot.tasks.map(o=>o.wid).sort());
    await page.goto(base+'/research-workbench.html');
    await page.locator('#grid .board').first().waitFor();
    // 2026-09-28：派工面板读目标表（目标行数），不再显示工单数
    assert.match(await page.locator('#grid').innerText(), new RegExp(String(targets.targets.length)+' 行目标'));
    // 2026-09-28：团队看板并入采集页的「研究问题任务」标签
    await page.goto(base+'/supply.html#tasks'); await page.locator('#tk-table tr').nth(1).waitFor();
    assert.match(await page.locator('#tk-sub').innerText(),new RegExp(String(tasks.orders.length)));
    assert.deepEqual(errors,[]);
    console.log('PASS report content, source model, current task parity and team rendering');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
