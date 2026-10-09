/* Check the real dossier entry and a self-contained, editable exported figure. */
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {chromium} = require('playwright');
const accepted = new Set(JSON.parse(readFileSync(join(__dirname,'../framework/visual_atlas_migration.json'),'utf8')).items
  .filter(row => ['accepted','published'].includes(row.status)).map(row => row.id));
const illustrationCases = [['shell','TA-36','shell','设施'], ['fire','TA-37','fire','设施'], ['security','TA-38','security','设施'], ['rack-frame','TA-39','rack-frame','设施'], ['server','TA-11','server','IT · 计算'], ['gpu','TA-04','gpu-board','IT · 计算'], ['hbm','TA-05','hbm-package','IT · 内存'], ['cpu','TA-06','motherboard','IT · 计算'], ['dram','TA-06','motherboard','IT · 内存'], ['nic','TA-07','nic','IT · 网络'], ['psu','TA-08','psu','电力'], ['server-fan','TA-09','fan-wall','冷却'], ['coldplate','TA-10','coldplate','冷却']]
  .filter(([,figure]) => accepted.has(figure));
(async () => {
  const browser = await chromium.launch({headless: true, args: ['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}, reducedMotion: 'reduce'});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.UI_BASE_URL + '/bom.html', {waitUntil: 'domcontentloaded'});
    await page.locator('.pbox[data-atlas-part="ssd"]').waitFor();
    assert.ok(await page.locator('#selected-atlas').evaluate(el => el.hidden), 'overview opens without an unrelated part detail');
    assert.ok(await page.locator('#selected-atlas').evaluate(el => el.previousElementSibling.matches('.lrow[data-row-parts~="ssd"]')));
    for (const url of ['/bom.html#ssd', '/rack3d.html?x=55&node=part:ssd#ssd']) {
      await page.goto(process.env.UI_BASE_URL + url, {waitUntil: 'domcontentloaded'});
      const atlas = page.locator('.technical-atlas[data-figure="TA-01"]');
      await atlas.waitFor(); await atlas.scrollIntoViewIfNeeded();
      await atlas.locator('img').evaluate(image => image.decode());
      assert.ok((await atlas.locator('img').getAttribute('src')).endsWith('/ssd-v1-preview.svg'));
      assert.match(await atlas.locator('figcaption').textContent(), /通用.*不代表某个厂商型号/);
      assert.equal(await page.locator('.technical-atlas').count(), 1);
      assert.equal(await page.locator('link[data-technical-atlas]').count(), 1);
      if (url.includes('rack3d')) assert.equal(await page.locator('#dossier .insp canvas').count(), 1);
      else {
        assert.equal(await page.locator('#selected-atlas .technical-atlas').count(),1,'SSD illustration belongs in the main drawing area');
        assert.equal(await page.locator('#dossier .technical-atlas').count(),0,'avoid a duplicate sidebar illustration');
        assert.ok((await atlas.boundingBox()).width>500,'desktop SSD figure must be readable outside the sidebar');
        assert.equal(await page.locator('#selected-atlas').evaluate(el => el.parentElement.id), 'stack');
        assert.match(await page.locator('.atlas-context').textContent(), /IT · 存储 → 企业级 SSD/);
        for (const mode of ['scale','system']) {
          await page.locator(`[data-mode="${mode}"]`).click();
          assert.ok(await page.locator('#selected-atlas').evaluate(el => el.previousElementSibling.matches('.lrow[data-row-parts~="ssd"]')),
            'detail must follow its own system/scale row rather than precede the whole overview');
          assert.equal(await page.locator('#selected-atlas .technical-atlas').count(),1,'mode change retains the selected SSD detail');
          assert.equal(await page.locator('#c-ssd.sel').count(),1);
          assert.equal(await page.locator('.pbox[data-part="ssd"] path').count(),0,'adopted SSD must not remain a classification box');
          assert.match(await page.locator('.pbox[data-atlas-part="ssd"] image').getAttribute('href'),/ssd-v1-preview\.svg$/);
        }
        await page.locator('#c-hdd').click();
        assert.ok(await page.locator('#selected-atlas').evaluate(el=>el.hidden),'other parts must not inherit the SSD figure');
        await page.locator('[data-mode="scale"]').click();
        assert.ok(await page.locator('#selected-atlas').evaluate(el=>el.hidden),'mode change must retain the non-SSD selection');
        await page.locator('.pbox[data-atlas-part="ssd"]').click();
        assert.equal(await page.locator('.technical-atlas').count(),1);
      }
      for (const width of [1280, 390]) {
        await page.setViewportSize({width, height: 900});
        for (const mode of ['light', 'dark']) {
          await page.locator('#ui-appearance').selectOption(mode);
          assert.equal(await atlas.locator('figure > a').evaluate(node => getComputedStyle(node).backgroundColor), 'rgb(250, 249, 242)');
          assert.equal(await atlas.locator('figcaption').evaluate(node => getComputedStyle(node).fontSize), '14px');
          await atlas.locator('summary').click();
          assert.equal(await atlas.locator('li').count(), 6);
          assert.ok(await atlas.locator('li').first().isVisible());
          await atlas.locator('summary').click();
          assert.ok(await atlas.locator('img').evaluate(node => node.complete && node.naturalWidth === 1536));
          const box = await atlas.boundingBox(); assert.ok(box.width <= width);
        }
      }
      const popupPromise = page.waitForEvent('popup');
      await atlas.getByRole('link', {name: '放大查看', exact: true}).click();
      const popup = await popupPromise;
      await popup.waitForLoadState('domcontentloaded');
      assert.equal(await popup.locator('svg #editable-labels text').count(), 9);
      assert.equal(await popup.locator('svg image').count(), 1);
      assert.match(await popup.locator('svg image').getAttribute('href'), /^data:image\/png;base64,/);
      await popup.close();
      for (const [name, suffix] of [['下载标注图', '.svg'], ['下载无字底图', '.png']]) {
        const pending = page.waitForEvent('download');
        await atlas.getByRole('link', {name, exact: true}).click();
        const download = await pending;
        assert.ok(download.suggestedFilename().endsWith(suffix));
        assert.equal(await download.failure(), null);
      }
      if (process.env.REVIEW_SCREENSHOTS) await atlas.screenshot({path: process.env.REVIEW_SCREENSHOTS + '/' + (url.includes('rack3d') ? 'atlas-rack.png' : 'atlas-bom.png')});
    }
    for (const [part, figure, asset, context] of illustrationCases) {
      await page.goto(process.env.UI_BASE_URL + '/bom.html#' + part, {waitUntil:'domcontentloaded'});
      const atlas = page.locator(`#selected-atlas .technical-atlas[data-figure="${figure}"]`);
      await atlas.waitFor(); await atlas.locator('img').scrollIntoViewIfNeeded();
      await atlas.locator('img').evaluate(img => img.decode());
      assert.ok((await atlas.locator('img').getAttribute('src')).endsWith(`/${asset}-v1-preview.svg`));
      assert.ok((await page.locator('.atlas-context').textContent()).startsWith(context + ' →'));
      if (figure === 'TA-10') {
        assert.match(await atlas.locator('h3').textContent(), /冷板与接头.*内部液路与快接/);
        assert.match(await atlas.locator('figcaption').textContent(), /双端口.*示例.*非额外回路.*不表示可拆维护或热插拔/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-09"]').count(), 0, 'coldplate selection clears the previous fan illustration');
      }
      if (figure === 'TA-09') {
        assert.match(await atlas.locator('h3').textContent(), /服务器风扇墙.*模组与安装位/);
        assert.match(await atlas.locator('figcaption').textContent(), /三就位、一上提.*不表示气流或热插拔/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-08"]').count(), 0, 'fan selection clears the previous PSU illustration');
      }
      if (figure === 'TA-08') {
        assert.match(await atlas.locator('h3').textContent(), /服务器电源模块.*接口与抽拉结构/);
        assert.match(await atlas.locator('figcaption').textContent(), /通用服务器 AC–DC.*以产品资料为准/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-07"]').count(), 0, 'PSU selection clears the previous NIC illustration');
      }
      if (figure === 'TA-07') {
        assert.match(await atlas.locator('h3').textContent(), /网卡.*PCIe.*网络接口/);
        assert.match(await atlas.locator('figcaption').textContent(), /双端口.*不概括所有 DPU/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-06"]').count(), 0, 'NIC selection clears the previous motherboard assembly');
      }
      if (figure === 'TA-11') {
        assert.match(await atlas.locator('h3').textContent(), /加速器服务器.*整机剖视/);
        assert.match(await atlas.locator('figcaption').textContent(), /双 CPU.*八 DIMM.*仅为示例.*非新增卡.*非拆修步骤/);
        assert.match(await page.locator('.pbox[data-atlas-part="server"] title').textContent(), /加速器服务器/);
        assert.equal(await atlas.locator('[data-related-figure="TA-03"]').getAttribute('href'), '/assets/technical-atlas/chassis-v1.svg', 'retained chassis subassembly remains reachable');
      }
      if (figure === 'TA-04') {
        assert.match(await atlas.locator('h3').textContent(), /GPU 加速基板.*模组装配/);
        assert.ok(await page.locator('#dossier .spark-wrap').count()>0, 'GPU price series and the complete 2D dossier render without aborting the drawing');
        assert.match(await atlas.locator('figcaption').textContent(), /多 GPU 模组与基板/);
        assert.match(await page.locator('.pbox[data-atlas-part="gpu"] title').textContent(), /GPU 加速基板/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-11"]').count(), 0, 'GPU selection clears the previous whole-server illustration');
      }
      if (figure === 'TA-05') {
        assert.match(await atlas.locator('figcaption').textContent(), /四堆栈.*仅为图示/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-04"]').count(), 0, 'HBM package clears the previous board assembly');
      }
      if (figure === 'TA-06') {
        assert.match(await atlas.locator('h3').textContent(), /服务器主板.*CPU 与 DIMM/);
        assert.match(await atlas.locator('figcaption').textContent(), /RDIMM.*不代表 MRDIMM/);
        assert.equal(await page.locator('.technical-atlas[data-figure="TA-05"]').count(), 0, 'CPU/DRAM assembly must not retain a GPU/HBM package diagram');
        assert.equal(await page.locator(`.pbox[data-atlas-part="${part}"]`).count(), 1, 'each existing category has its own assembly-context entry');
      }
      assert.equal(await page.locator('.technical-atlas').count(),1,'a selection must not retain the previous object diagram');
      for (const mode of ['scale','system']) {
        await page.locator(`[data-mode="${mode}"]`).click();
        assert.ok(await page.locator('#selected-atlas').evaluate((el,id) => el.previousElementSibling.matches(`.lrow[data-row-parts~="${id}"]`),part));
        assert.equal(await page.locator(`.pbox[data-part="${part}"] path`).count(),0);
        assert.ok((await page.locator(`.pbox[data-atlas-part="${part}"] image`).getAttribute('href')).endsWith(`/${asset}-v1-preview.svg`));
        for (const width of [1280,390]) {
          await page.setViewportSize({width,height:900});
          for (const theme of ['light','dark']) {
            await page.locator('#ui-appearance').selectOption(theme);
            assert.equal(await atlas.locator('figure > a').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(250, 249, 242)');
            assert.ok((await atlas.boundingBox()).width<=width);
          }
        }
      }
      const popupPending=page.waitForEvent('popup');
      await atlas.getByRole('link',{name:'放大查看',exact:true}).click();
      const popup=await popupPending; await popup.waitForLoadState('domcontentloaded');
      assert.ok(await popup.locator('svg #editable-labels text').count()>=6);
      assert.match(await popup.locator('svg image').getAttribute('href'), /^data:image\/png;base64,/);
      await popup.close();
      for (const name of ['下载标注图','下载无字底图']) {
        const pending=page.waitForEvent('download'); await atlas.getByRole('link',{name,exact:true}).click();
        assert.equal(await (await pending).failure(),null);
      }
    }
    await page.locator('#c-hdd').click();
    assert.ok(await page.locator('#selected-atlas').evaluate(el=>el.hidden),'an unfinished object must not inherit another object diagram');
    assert.deepEqual(errors, []);
    console.log(`Technical atlas: SSD and ${illustrationCases.length} accepted category illustrations, system/scale context, editable SVG, zoom/downloads, narrow/light/dark and retained 3D passed`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
