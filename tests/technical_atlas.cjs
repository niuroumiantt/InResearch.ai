/* Check the real dossier entry and a self-contained, editable exported figure. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless: true, args: ['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}, reducedMotion: 'reduce'});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    for (const url of ['/bom.html#ssd', '/rack3d.html?x=55&node=part:ssd#ssd']) {
      await page.goto(process.env.UI_BASE_URL + url, {waitUntil: 'domcontentloaded'});
      const atlas = page.locator('.technical-atlas[data-figure="TA-01"]');
      await atlas.waitFor(); await atlas.scrollIntoViewIfNeeded();
      await atlas.locator('img').evaluate(image => image.decode());
      assert.match(await atlas.locator('figcaption').textContent(), /通用.*不代表某个厂商型号/);
      assert.equal(await page.locator('.technical-atlas').count(), 1);
      assert.equal(await page.locator('link[data-technical-atlas]').count(), 1);
      if (url.includes('rack3d')) assert.equal(await page.locator('#dossier .insp canvas').count(), 1);
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
    assert.deepEqual(errors, []);
    console.log('Technical atlas: real SSD entry, SVG labels, zoom, both downloads, narrow/light/dark and retained 3D canvas passed');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
