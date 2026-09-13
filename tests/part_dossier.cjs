/* Real scene deep links exercise the shared dossier and WebGL inspector. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true, args:['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}, reducedMotion:'reduce'});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    for (const url of ['/bom3d.html?p=server', '/rack3d.html?node=part:gpu']) {
      await page.goto(process.env.UI_BASE_URL + url);
      const dossier = page.locator('#dossier');
      await dossier.locator('h2').waitFor();
      const canvas = dossier.locator('canvas'); await canvas.waitFor();
      assert.equal(await canvas.count(), 1);
      assert.ok(await dossier.getByRole('link', {name:'模块原文'}).isVisible());
      assert.ok(await dossier.getByRole('heading', {name:'类别数据与指标 · 按原记录时点'}).isVisible());
      const box = await canvas.boundingBox();
      await page.mouse.move(box.x+40, box.y+40); await page.mouse.down();
      await page.mouse.move(box.x+90, box.y+65, {steps:4}); await page.mouse.up();
      await page.getByRole('button',{name:'folk',exact:true}).click();
      assert.ok(await canvas.isVisible());
      await dossier.getByRole('button',{name:'关闭部件档案'}).click();
      assert.ok(!await dossier.isVisible());
    }
    assert.deepEqual(errors, []);
    console.log('PASS both real 3D dossiers, deep links, inspector drag, theme preservation and close');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
