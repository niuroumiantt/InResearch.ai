/* Called by the existing ui_skin suite against its real isolated HTTP server. */
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');

module.exports = async function checkPresentationLayout(page) {
  const fixture = spawnSync(process.env.PYTHON || 'python3', ['-c',
    "import sys; sys.path.insert(0,'src'); from tests.unit.test_presentation_layout import fixture; sys.stdout.buffer.write(fixture())"]);
  assert.equal(fixture.status, 0, fixture.stderr.toString());
  const input = page.locator('#ppt-file');
  await input.setInputFiles({name:'client-deck.pptx', mimeType:'application/vnd.openxmlformats-officedocument.presentationml.presentation', buffer:fixture.stdout});
  await page.locator('#ppt-submit').click();
  await page.locator('#ppt-download:not([hidden])').waitFor();
  assert.match(await page.locator('#ppt-result').innerText(), /内容校验通过：共 1 页，1 页重新排版/);
  assert.equal(await page.locator('#ppt-submit').isEnabled(), true);
  const downloaded = page.waitForEvent('download');
  await page.locator('#ppt-download').click();
  const result = await downloaded;
  assert.equal(result.suggestedFilename(), 'inresearch-formatted.zip');
  const file = await result.path();
  const verify = spawnSync(process.env.PYTHON || 'python3', ['-c',
    "import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); r=json.loads(z.read('layout-report.json')); assert r['slides']==1 and r['content_check']=='passed'; assert z.read('inresearch-formatted.pptx').startswith(b'PK')", file]);
  assert.equal(verify.status, 0, verify.stderr.toString());
  await page.locator('#ppt-mode').selectOption('fonts');
  assert.equal(await page.locator('#ppt-download').isVisible(), false);
  await page.locator('#ppt-submit').click();
  await page.locator('#ppt-download:not([hidden])').waitFor();
  assert.match(await page.locator('#ppt-result').innerText(), /0 页重新排版，1 页仅统一文本框字体/);
  await input.setInputFiles({name:'corrupt.pptx', mimeType:'application/octet-stream', buffer:Buffer.from('PRIVATE TEXT NOT A ZIP')});
  assert.equal(await page.locator('#ppt-download').isVisible(), false);
  await page.locator('#ppt-submit').click();
  await page.locator('#ppt-result[data-error=true]').waitFor();
  assert.doesNotMatch(await page.locator('#ppt-result').innerText(), /PRIVATE TEXT/);
  assert.equal(await page.locator('#ppt-submit').isEnabled(), true);
  assert.equal(await page.locator('#ppt-download').isVisible(), false);
  await input.setInputFiles({name:'wrong.pdf', mimeType:'application/pdf', buffer:Buffer.from('%PDF')});
  await page.locator('#ppt-submit').click();
  assert.match(await page.locator('#ppt-result').innerText(), /请选择.*\.pptx/);
  await input.setInputFiles([]);
  console.log('PASS marketing PPT upload, real worker/download, fonts mode, invalid files and result reset');
};
