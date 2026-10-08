/* Real WebGL pixels/export and edge ownership, separate from visual review. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
  try {
    for(const density of [1,2]) {
    const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:density,reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')console.error('Browser:',message.text());});
    await page.goto(process.env.UI_BASE_URL+'/rack3d.html?x=90&node=part:ssd#ssd');
    await page.locator('#atlas-export').waitFor();
    const ownership=await page.evaluate(async()=>{
      const THREE=await import('three'), {createAtlasDrawing}=await import('/assets/scene-atlas.js');
      const scene=new THREE.Scene(), geometry=new THREE.BoxGeometry(), material=new THREE.MeshStandardMaterial();
      const a=new THREE.Mesh(geometry,material),b=new THREE.Mesh(geometry,material);scene.add(a,b);
      let sources=0,edges=0;geometry.addEventListener('dispose',()=>sources++);
      const drawing=createAtlasDrawing({THREE,scene});drawing.sync();drawing.sync();
      if(a.children.length!==1 || a.children[0].geometry!==b.children[0].geometry) throw Error('duplicate outlines or failed reuse');
      a.children[0].geometry.addEventListener('dispose',()=>edges++);
      const raycast={calls:0};a.children[0].raycast(null,raycast); // no intercepted pick
      a.removeFromParent();drawing.sync();
      if(a.children.length) throw Error('removed model kept atlas edges');
      drawing.dispose();drawing.dispose();return {sources,edges,remaining:b.children.length};
    });
    assert.deepEqual(ownership,{sources:0,edges:1,remaining:0});
    for (const name of ['rack3d','bom3d']) {
      const part=name==='bom3d' ? 'server' : 'ssd';
      await page.setViewportSize({width:1280,height:900});
      await page.goto(process.env.UI_BASE_URL+`/${name}.html?x=90&node=part:${part}&p=${part}#${part}`, {waitUntil:'domcontentloaded'});
      await page.locator('#dossier .insp canvas').waitFor();
      await page.locator('.rg-scene-model-status[data-state="ready"]').waitFor({state:'attached'});
      for (const width of [1280,390]) for (const mode of ['light','dark']) {
        await page.setViewportSize({width,height:900});await page.locator('#ui-appearance').selectOption(mode);
        console.log('EXPORT',name,width,mode);
        const downloadPromise=page.waitForEvent('download');
        await page.getByRole('button',{name:'导出当前图册',exact:true}).click();
        const download=await downloadPromise;assert.equal(await download.failure(),null);
        assert.equal(download.suggestedFilename(),name+'-technical-atlas.svg');
        const raw=fs.readFileSync(await download.path(),'utf8');
        const result=await page.evaluate(async raw=>{
          const doc=new DOMParser().parseFromString(raw,'image/svg+xml');
          if(doc.querySelector('parsererror'))throw Error('invalid exported SVG');
          const image=new Image();image.src=doc.querySelector('image').getAttribute('href');await image.decode();
          const probe=document.createElement('canvas');probe.width=image.width;probe.height=image.height;
          const context=probe.getContext('2d');context.drawImage(image,0,0);
          return {paper:[...context.getImageData(0,0,1,1).data],
            size:[image.width,image.height],meta:JSON.parse(doc.querySelector('metadata').textContent),
            labels:doc.querySelectorAll('#editable-labels text').length,
            positionedLabels:[...doc.querySelectorAll('#editable-labels text[stroke]')].map(text=>({font:Number(text.getAttribute('font-size')),paper:text.getAttribute('stroke')})),
            leader:doc.querySelector('[data-object-id]')?.getAttribute('data-object-id'),
            liveLabels:[...document.querySelectorAll('.atlas-scene-labels text')].filter(el=>getComputedStyle(el).display!=='none').map(el=>parseFloat(getComputedStyle(el).fontSize)),
            oldInspector:!!document.querySelector('#dossier .insp canvas')};
        },raw);
        assert.deepEqual(result.paper,[250,249,242,255],name+' actual exported paper');
        assert.equal(result.meta.style,'white-technical-atlas-v1');
        assert.equal(result.meta.object_id,'part:'+part);
        if(result.leader)assert.equal(result.leader,'part:'+part);
        assert.ok(result.labels>=2);assert.ok(result.oldInspector);
        assert.ok(result.positionedLabels.length>0);
        assert.ok(result.positionedLabels.every(text=>text.font>=14*density && text.paper==='#FAF9F2'));
        assert.ok(result.liveLabels.every(size=>size>=14));
        assert.ok(result.size[0]>0 && result.size[1]>0);
        assert.equal(await page.locator('#atlas-export').textContent(),'导出图册');
      }
      await page.locator('#dossier .close').click();
      await page.setViewportSize({width:1280,height:900});
      if(name==='bom3d') {
        await page.locator('#covChip').click();
        const pending=page.waitForEvent('download');await page.locator('#atlas-export').click();
        const raw=fs.readFileSync(await (await pending).path(),'utf8');
        const meta=await page.evaluate(raw=>JSON.parse(new DOMParser().parseFromString(raw,'image/svg+xml').querySelector('metadata').textContent),raw);
        assert.match(meta.diagnostics,/红0\/4.*绿4\/4.*非硬件状态/);
        assert.ok(raw.includes('非硬件状态'));await page.locator('#covChip').click();
      }
      await page.locator('#explode').evaluate(input=>{input.value='45';input.dispatchEvent(new Event('input',{bubbles:true}));});
      assert.equal(await page.locator('#explode').inputValue(),'45');
      if(process.env.REVIEW_SCREENSHOTS)await page.screenshot({path:process.env.REVIEW_SCREENSHOTS+'/'+name+'-atlas-recipe.png'});
    }
    assert.deepEqual(errors,[]);
    await page.close();
    }
    console.log('PASS neutral atlas: actual PNG paper, editable SVG/current view, both themes/sizes, retained inspector/stages, shared edge ownership/disposal');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
