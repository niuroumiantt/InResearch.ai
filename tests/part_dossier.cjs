/* Real scene deep links exercise the shared dossier and WebGL inspector. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true, args:['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}, reducedMotion:'reduce', deviceScaleFactor:process.env.CI ? .5 : 1});
    const errors = [], fullRequests=[]; page.on('pageerror', e => errors.push(e.message));
    page.on('request', request=>{if(new URL(request.url()).pathname==='/api/research')fullRequests.push(request.url());});
    // Inspect actual scene objects without shipping debug globals in application code.
    await page.route(/\/(bom3d|rack3d)\.html/, async route => {
      const response = await route.fetch();
      const html = await response.text();
      const instrumented = html.replace('</script>\n</body>',
        'globalThis.__sceneForTest = {scene, pickables, camera, controls};\n</script>\n</body>');
      assert.notEqual(instrumented, html);
      await route.fulfill({response, body:instrumented});
    });
    for (const url of ['/bom3d.html?p=server', '/rack3d.html?node=part:gpu', '/rack3d.html?node=part:hbm', '/rack3d.html?node=part:cpu', '/rack3d.html?node=part:dram']) {
      console.log('Scene contract: loading '+url);
      await page.goto(process.env.UI_BASE_URL + url);
      const dossier = page.locator('#dossier');
      await dossier.locator('h2').waitFor();
      await dossier.locator('.rg-3d-panel[data-state=ready]').waitFor();
      assert.match(await dossier.locator('.rg-3d-panel .rg-chips').textContent(), /个问题.*条证据.*个关联任务/);
      assert.ok(await dossier.locator('.rg-3d-neighbors a').count()>0);
      console.log('Scene contract: research ready '+url);
      if (url.includes('p=server')) {
        const enclosure = dossier.locator('.technical-atlas[data-figure="TA-03"]');
        await enclosure.waitFor();
        assert.match(await enclosure.locator('figcaption').textContent(), /子装配/);
        assert.ok((await enclosure.locator('img').getAttribute('src')).endsWith('/chassis-v1-preview.svg'));
      } else if (url.includes('part:hbm')) {
        const hbm = dossier.locator('.technical-atlas[data-figure="TA-05"]');
        await hbm.waitFor();
        assert.match(await hbm.locator('h3').textContent(), /GPU 与 HBM.*封装层次/);
        assert.match(await hbm.locator('figcaption').textContent(), /硅中介层.*仅为图示/);
        assert.equal(await dossier.locator('.technical-atlas[data-figure="TA-04"]').count(), 0);
      } else if (url.includes('part:cpu') || url.includes('part:dram')) {
        const board = dossier.locator('.technical-atlas[data-figure="TA-06"]');
        await board.waitFor();
        assert.match(await board.locator('h3').textContent(), /服务器主板.*CPU 与 DIMM/);
        assert.match(await board.locator('figcaption').textContent(), /不代表 MRDIMM/);
        assert.ok((await board.locator('img').getAttribute('src')).endsWith('/motherboard-v1-preview.svg'));
        assert.equal(await dossier.locator('.technical-atlas[data-figure="TA-05"]').count(), 0);
      } else {
        assert.equal(await dossier.locator('.technical-atlas[data-figure="TA-03"]').count(), 0, 'GPU must not inherit enclosure diagram');
        const gpu = dossier.locator('.technical-atlas[data-figure="TA-04"]');
        await gpu.waitFor();
        assert.match(await gpu.locator('h3').textContent(), /GPU 加速基板.*模组装配/);
        assert.match(await gpu.locator('figcaption').textContent(), /多 GPU 模组与基板/);
        assert.ok((await gpu.locator('img').getAttribute('src')).endsWith('/gpu-board-v1-preview.svg'));
      }
      const canvas = dossier.locator('canvas'); await canvas.waitFor();
      assert.equal(await canvas.count(), 1);
      assert.ok(await dossier.getByRole('link', {name:'采集：这个部件的目标行'}).isVisible());
      assert.ok(await dossier.getByRole('heading', {name:'类别数据与指标 · 按原记录时点'}).isVisible());
      const box = await canvas.boundingBox();
      await page.mouse.move(box.x+40, box.y+40); await page.mouse.down();
      await page.mouse.move(box.x+90, box.y+65, {steps:4}); await page.mouse.up();
      await page.locator('#ui-appearance').selectOption('dark');
      assert.ok(await canvas.isVisible());
      if (process.env.REVIEW_SCREENSHOTS) await page.screenshot({path:process.env.REVIEW_SCREENSHOTS + '/' + (url.includes('bom3d') ? 'scene-campus.png' : 'scene-rack.png')});
      await dossier.getByRole('button',{name:'关闭部件档案'}).click();
      assert.ok(!await dossier.isVisible());
      await page.waitForFunction(() => Boolean(globalThis.__sceneForTest));
      await page.locator('#ui-appearance').selectOption('light');
      // Reduced-motion playback finishes at the selected end, without background writers.
      await page.locator('#play').click();
      assert.equal(await page.locator('#explode').inputValue(), '100');
      await page.locator('.rg-stage-control').selectOption({index:1});
      const selected = await page.locator('#explode').inputValue();
      await page.locator('#ui-appearance').selectOption('dark');
      assert.equal(await page.locator('#explode').inputValue(), selected);
      // Exercise normal animation too: repeated play then a manual phase owns the state.
      await page.emulateMedia({reducedMotion:'no-preference'});
      await page.locator('#play').click(); await page.locator('#play').click();
      await page.locator('.rg-stage-control').selectOption({index:2});
      const manual = await page.locator('#explode').inputValue();
      await page.waitForTimeout(180);
      assert.equal(await page.locator('#explode').inputValue(), manual);
      await page.emulateMedia({reducedMotion:'reduce'});
      if (url.includes('bom3d')) {
        await page.evaluate(() => { globalThis.__originalMaterials = __sceneForTest.pickables.map(m => m.material); globalThis.__materialState = __originalMaterials.map(m => JSON.stringify((Array.isArray(m)?m:[m]).map(v=>[v.opacity,v.transparent,v.emissive?.getHex(),v.emissiveIntensity]))); });
        await page.locator('#dchip-power').click(); await page.locator('#dchip-thermal').click();
        assert.equal(await page.locator('#explode').inputValue(), '45');
        assert.ok(await page.evaluate(() => __originalMaterials.every((m,i)=>JSON.stringify((Array.isArray(m)?m:[m]).map(v=>[v.opacity,v.transparent,v.emissive?.getHex(),v.emissiveIntensity]))===__materialState[i])));
        assert.ok(await page.evaluate(() => __sceneForTest.pickables.some((m,i) => m.material !== __originalMaterials[i])));
        await page.keyboard.press('Escape');
        assert.ok(await page.evaluate(() => __sceneForTest.pickables.every((m,i) => m.material === __originalMaterials[i])));
        await page.locator('#covChip').click(); await page.locator('#covChip').click();
        assert.ok(await page.evaluate(() => __sceneForTest.pickables.every((m,i) => m.material === __originalMaterials[i])));
      }
      const main = page.locator('#c');
      const mainBox = await main.boundingBox();
      const px = mainBox.x + mainBox.width * .5, py = mainBox.y + mainBox.height * .6;
      await page.mouse.move(px,py); await page.mouse.down();
      await page.mouse.move(px+80,py+30,{steps:5}); await page.mouse.up();
      assert.ok(!await dossier.isVisible(), 'orbit drag does not select a part');
    }
    console.log('Scene contract: motion, picking and material ownership');
    const contracts = await page.evaluate(async () => {
      const THREE = await import('three');
      const {createScenePicking} = await import('/assets/scene-picking.js');
      const {createSceneMotion} = await import('/assets/scene-motion.js');
      const {createPartInspector} = await import('/assets/part-inspector.js');
      const check = (condition, message) => { if (!condition) throw Error(message); };
      let time = 0, next = 0, frames = new Map(), history = [];
      const motion = createSceneMotion({now:()=>time, reducedMotion:()=>false,
        requestFrame:callback=>{frames.set(++next,callback);return next;}, cancelFrame:()=>{}});
      motion.run(100, value=>history.push(['old',value]));
      const oldFrame = frames.get(next); time=20;
      motion.run(100, value=>history.push(['new',value]));
      const currentFrame = frames.get(next), length = history.length;
      oldFrame(100); check(history.length===length, 'superseded frame wrote state');
      currentFrame(70); check(history.at(-1)[0]==='new' && history.at(-1)[1]===.5, 'new timeline progress');
      const pending = frames.get(next); motion.cancel(); pending(200);
      check(history.at(-1)[1]===.5, 'cancelled frame wrote state');
      motion.run(0,value=>history.push(['retry',value])); check(history.at(-1)[1]===1,'restart failed');
      const canvas = document.createElement('canvas'), tip = document.createElement('div');
      canvas.style.cssText='position:fixed;left:100px;top:150px;width:300px;height:300px;z-index:999999';
      tip.style.cssText='position:fixed;pointer-events:none'; document.body.append(canvas,tip);
      const material = new THREE.MeshStandardMaterial({emissive:0,emissiveIntensity:0});
      const geometry = new THREE.BoxGeometry(1,1,1), a = new THREE.Mesh(geometry,material), b = new THREE.Mesh(geometry,material);
      b.position.x=2; const group = new THREE.Group(); group.add(a,b);
      const camera = new THREE.PerspectiveCamera(45,1,.1,100); camera.position.z=5;
      let selections=0, disposedGeometry=false; geometry.addEventListener('dispose',()=>disposedGeometry=true);
      const picking = createScenePicking({THREE,canvas,camera,pickables:[a,b],tip,describe:()=> 'test part',select:()=>selections++});
      const event = (type,x=250,y=300) => canvas.dispatchEvent(new PointerEvent(type,{pointerId:1,isPrimary:true,button:0,clientX:x,clientY:y}));
      event('pointermove'); check(a.children.length===1 && b.children.length===0,'highlight must be local');
      check(a.material===material && b.material===material && material.emissive.getHex()===0 && material.emissiveIntensity===0,'material changed');
      event('pointerdown'); event('pointermove',290); event('pointermove'); event('pointerup');
      check(selections===0,'drag return to origin selected');
      event('pointerdown'); event('pointerup'); check(selections===1,'normal click failed after drag');
      event('pointermove'); check(a.children.length===1,'highlight did not recover');
      event('pointerleave'); check(a.children.length===0,'overlay was not released');
      group.visible=false; event('pointermove'); check(a.children.length===0,'hidden parent picked');
      group.visible=true; event('pointermove');
      const cover=document.createElement('div');cover.style.cssText='position:fixed;left:100px;top:150px;width:300px;height:300px;z-index:1000000';document.body.append(cover);
      event('pointermove'); check(a.children.length===0,'captured pointer picked through overlay');cover.remove();
      picking.dispose(); event('pointerdown'); event('pointerup');
      check(selections===1 && !disposedGeometry && material.emissive.getHex()===0,'cleanup damaged shared scene');
      canvas.remove();tip.remove();
      // Actual inspector and Three materials, with render capture instead of a second GPU context.
      const original = new THREE.MeshStandardMaterial({color:0x123456,opacity:1,emissiveIntensity:.2});
      const dim = original.clone();dim.opacity=.1;dim.transparent=true;a.material=dim;
      let cloned = null;
      class CaptureRenderer {
        setPixelRatio() {} setSize() {} dispose() {}
        render(scene) {scene.traverse(object=>{if(object.isMesh) cloned=object.material;});}
      }
      const inspector = createPartInspector({THREE:{...THREE,WebGLRenderer:CaptureRenderer},
        environment:()=>null,meshesFor:()=>[a],materialFor:()=>original});
      document.body.append(inspector.canvas);check(inspector.show('part'),'inspector failed');inspector.tick();
      check(cloned!==original && cloned.opacity===1 && !cloned.transparent && cloned.color.getHex()===0x123456 && cloned.emissiveIntensity===.2,'inspector used presentation material');
      check(a.material===dim && dim.opacity===.1,'inspector changed main scene');
      let disposed=false;cloned.addEventListener('dispose',()=>disposed=true);inspector.show('part');
      check(disposed && !disposedGeometry,'inspector released shared geometry or leaked old clone');
      inspector.hide();inspector.dispose();check(!disposedGeometry,'inspector dispose released borrowed geometry');inspector.canvas.remove();dim.dispose();original.dispose();
      geometry.dispose();material.dispose();
      return true;
    });
    assert.ok(contracts);
    assert.deepEqual(fullRequests, [], '3D dossier must not fetch full research');
    assert.deepEqual(errors, []);
    console.log('PASS both real 3D scenes: research ready without full snapshot, dossiers, themes, motion takeover, stale frames, materials, picking, drag and cleanup');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
