/*
 * TA-28 actual-public-only acceptance. Source reviewed before actual deployed execution.
 * Execution uses existing user-authorized public observation, reviewed
 * source integration, UI_BASE_URL=https://inresearch.ai, TA_CONTROL_SOURCE_ROOT.
 * No local product URL, server, file-page, fallback or CI registration.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const base = 'https://inresearch.ai';
assert.equal(process.env.UI_BASE_URL, base, 'Only the explicitly authorized actual public origin is permitted');
const root = process.env.TA_CONTROL_SOURCE_ROOT;
assert.ok(root && path.isAbsolute(root), 'TA_CONTROL_SOURCE_ROOT must name the reviewed source tree; no inferred /tmp root');
const figure = 'TA-28', domain = 'control', preview = '/assets/technical-atlas/control-domain-v1-preview.svg';
const out = process.env.REVIEW_SCREENSHOTS || '/private/tmp/ta28-control-public-' + Date.now();
assert.ok(path.isAbsolute(out));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'docs/design/technical-atlas/TA-28/asset-manifest-v1.json')));
assert.equal(manifest.figure_id, figure);
fs.mkdirSync(out, {recursive:true});
const results = {
  figure, observed_at:new Date().toISOString(), base,
  scope_proof:{required_origin:base, local_fallback:false, local_product_server:false,
    source_root:root, observation_only_injection:true, browser_requests:[]},
  views:[], controls:[], downloads:[], sources:[], declared_resources:[],
  geometry:[], software_dossiers:[], scope_isolation:[], errors:[], route_errors:[], resource_failures:[]
};
let browser;

(async () => {
  try {
    const {chromium} = require('playwright');
    browser = await chromium.launch({headless:process.env.UI_HEADED !== '1'});
    const context = await browser.newContext({viewport:{width:1280,height:900}, deviceScaleFactor:1,
      reducedMotion:'reduce', acceptDownloads:true, serviceWorkers:'block'});
    await context.route('**/*', async route => {
      try {
        assert.equal(new URL(route.request().url()).origin, base);
        results.scope_proof.browser_requests.push(route.request().url());
        await route.continue();
      } catch (error) {
        results.route_errors.push(error.message);
        await route.abort('blockedbyclient');
      }
    });
    const page = await context.newPage();
    page.on('pageerror', error => results.errors.push(error.message));
    page.on('response', response => {
      if (new URL(response.url()).pathname.startsWith('/assets/') && response.status() >= 400)
        results.resource_failures.push({url:response.url(),status:response.status()});
    });
    async function settle() {
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      });
      assert.deepEqual(results.route_errors, []);
    }
    async function readyAtlas(atlas) {
      await atlas.waitFor();
      await atlas.locator('img').evaluate(image => image.decode());
      await page.waitForFunction(() => {
        const anchor = document.querySelector('.technical-atlas figure>a');
        return !!anchor && getComputedStyle(anchor).backgroundColor === 'rgb(250, 249, 242)';
      });
      await settle();
    }
    async function saveView(kind, file, details={}) {
      await page.screenshot({path:path.join(out,file), ...(kind === 'static' ? {fullPage:true} : {})});
      results.views.push({kind,file,...details});
    }
    async function parseSVG(bytes) {
      return page.evaluate(source => {
        const doc = new DOMParser().parseFromString(source, 'image/svg+xml');
        if (doc.querySelector('parsererror')) throw Error('Invalid exported SVG');
        const meta = doc.querySelector('metadata');
        if (!meta) throw Error('Export has no metadata');
        return {metadata:JSON.parse(meta.textContent), text:[...doc.querySelectorAll('text')].map(t => t.textContent).join(''),
          selected_leaders:[...doc.querySelectorAll('[data-object-id]')].map(e => e.getAttribute('data-object-id')),
          anchored_labels:[...doc.querySelectorAll('.atlas-label-leader')].map(e => ({label:e.getAttribute('data-label'),instance:e.getAttribute('data-instance')}))};
      }, bytes.toString('utf8'));
    }
    async function downloadCurrent(filename) {
      const pending = page.waitForEvent('download');
      await page.locator('#atlas-export').click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      const target = path.join(out,filename);
      await download.saveAs(target);
      const bytes = fs.readFileSync(target);
      return {file:filename,sha256:hash(bytes),bytes:bytes.length,...await parseSVG(bytes)};
    }

    // Actual static page, theme/width captures and real link downloads.
    const first = await page.goto(base + '/control-atlas.html', {waitUntil:'domcontentloaded'});
    assert.equal(first.status(), 200);
    const atlas = page.locator('.technical-atlas[data-figure="TA-28"]');
    await readyAtlas(atlas);
    assert.equal(await page.locator('.technical-atlas').count(), 1);
    assert.match(await atlas.locator('figcaption').textContent(), /软件/);
    for (const width of [1280,390]) for (const theme of ['light','dark']) {
      await page.setViewportSize({width,height:width === 390 ? 844 : 900});
      await page.locator('#ui-appearance').selectOption(theme);
      await settle();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.equal(await atlas.locator('figure>a').evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(250, 249, 242)');
      await page.evaluate(() => scrollTo(0,0));
      await saveView('static', 'control-' + width + '-' + theme + '.png', {width,theme});
    }
    await page.setViewportSize({width:360,height:844});
    const header = await page.locator('#ui-skinbar').boundingBox();
    assert.ok(header && header.height <= 86);
    results.header360 = header;
    for (const name of ['下载标注图','下载无字底图']) {
      const pending = page.waitForEvent('download');
      await atlas.getByRole('link', {name,exact:true}).click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      const filename = download.suggestedFilename();
      const expected = manifest.assets.find(asset => path.basename(asset.file) === filename);
      assert.ok(expected, 'Downloaded filename must belong to the reviewed TA28 manifest');
      const target = path.join(out,filename);
      await download.saveAs(target);
      const bytes = fs.readFileSync(target);
      assert.equal(hash(bytes), expected.sha256);
      assert.equal(bytes.length, expected.bytes);
      results.downloads.push({name,file:filename,bytes:bytes.length,sha256:hash(bytes)});
    }
    const fullURL = base + '/assets/technical-atlas/control-domain-v1.svg';
    const full = await page.goto(fullURL, {waitUntil:'domcontentloaded'});
    assert.equal(full.status(), 200);
    const fullBytes = await full.body();
    const fullExpected = manifest.assets.find(asset => asset.file.endsWith('/control-domain-v1.svg'));
    assert.ok(fullExpected);
    assert.equal(hash(fullBytes), fullExpected.sha256);
    assert.equal(fullBytes.length, fullExpected.bytes);
    await page.setViewportSize({width:1536,height:1024});
    await page.evaluate(() => document.fonts.ready);
    await page.locator('image').evaluateAll(elements => Promise.all(elements.map(element => new Promise((resolve,reject) => {
      const image = new Image(); image.onload=resolve; image.onerror=reject; image.src=element.getAttribute('href');
    }))));
    assert.equal(await page.locator('.callout').count(), 6);
    const texts = await page.locator('text').evaluateAll(elements => elements.map(element => {
      const bounds = element.getBBox();
      return {text:element.textContent,x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height};
    }));
    assert.ok(texts.every(t => t.x>=0 && t.y>=0 && t.x+t.width<=1536 && t.y+t.height<=1024));
    await page.locator('svg').screenshot({path:path.join(out,'control-full-svg-1536.png')});
    results.views.push({kind:'fullSVG',file:'control-full-svg-1536.png',labels:6,texts:texts.length});

    // API requests also obey the same explicit public origin and strict 200.
    async function publicGet(url) {
      assert.equal(new URL(url).origin, base);
      const response = await context.request.get(url, {maxRedirects:0});
      assert.equal(response.status(), 200, url);
      return response;
    }
    for (const name of ['control-atlas','facility-atlas','network-atlas']) {
      const url = base + '/' + name + '.html', response = await publicGet(url), html = await response.text();
      results.declared_resources.push({page:name,url,status:response.status()});
      const declared = [...html.matchAll(/<(?:script|link)\b[^>]+(?:src|href)=["']([^"']+)["']/g)].map(match => match[1]);
      const inlineImports = [...html.matchAll(/\bfrom\s*["']([^"']+)["']/g)].map(match => match[1]);
      assert.ok(!declared.includes('/assets/site-shell.js'));
      for (const resource of new Set([...declared,...inlineImports])) {
        const resourceURL = new URL(resource,url).href, actual = await publicGet(resourceURL);
        results.declared_resources.push({page:name,url:resourceURL,status:actual.status()});
      }
    }

    async function observe(route, marker, replacement) {
      try {
        assert.equal(new URL(route.request().url()).origin, base);
        results.scope_proof.browser_requests.push(route.request().url());
        const headers = {...route.request().headers()};
        delete headers['if-none-match']; delete headers['if-modified-since'];
        const response = await route.fetch({headers,maxRedirects:0}), bytes = await response.body(), source = bytes.toString('utf8');
        assert.equal(response.status(), 200); assert.ok(bytes.length);
        const pathname = new URL(route.request().url()).pathname;
        const local = {'/bom3d.html':'web/pages/bom3d.html','/assets/part-inspector.js':'web/components/part-inspector.js'}[pathname];
        assert.ok(local); assert.equal(hash(bytes), hash(fs.readFileSync(path.join(root,local))), 'Actual deployed source identity');
        assert.equal(source.split(marker).length-1, 1, 'Unique observer insertion point');
        results.sources.push({url:route.request().url(),status:response.status(),bytes:bytes.length,sha256:hash(bytes),observation_only_injection:true});
        await route.fulfill({response,body:source.replace(marker,replacement)});
      } catch (error) {
        results.route_errors.push(error.message); await route.abort('failed');
      }
    }
    await page.route(/\/assets\/part-inspector\.js(?:\?[^#]*)?$/, route => observe(route,
      'return {canvas: iCv,', 'return {objectsForTest:()=>iGroup?.children||[],canvas: iCv,'));
    await page.route(/\/bom3d\.html(?:\?[^#]*)?$/, route => observe(route,
      '</script>\n</body>',
      'globalThis.__controlDomainTest={THREE,BOM,campusAssembly,campusMode,canvas,camera,controls,pickables,PART,RIGHTS,inspector,sceneView,currentPartMeshes,state:()=>({selectedInstance:campusSelectedInstance,activeDomain,stage:+slider.value})};\n</script>\n</body>'));
    async function go(query) {
      const response = await page.goto(base+'/bom3d.html'+query, {waitUntil:'domcontentloaded'});
      assert.equal(response.status(), 200);
      await page.waitForFunction(() => !!globalThis.__controlDomainTest);
      await page.locator('.drill').waitFor({state:'attached'});
      await settle();
    }
    async function openControls() {
      const panel = page.locator('.ui-viewer-controls');
      if (!await panel.evaluate(element => element.open)) await panel.locator(':scope>summary').click();
      return panel;
    }
    async function closeDossier() { await page.locator('#dossier .close').click(); await settle(); }
    async function softwareDossier(label, expectedCache) {
      const software = page.locator('#domainParts .pitem[data-part="dcim"]');
      await software.click(); await settle();
      const art = page.locator('#dossier .technical-atlas');
      assert.equal(await art.count(), 1);
      assert.equal(await art.getAttribute('data-figure'), figure, 'Software uses TA28 domain artwork, not system TA47');
      assert.equal(await art.locator('img').getAttribute('src'), preview);
      assert.equal(await page.locator('#dossier [data-figure="TA-47"]').count(), 0);
      await readyAtlas(art);
      const observed = await page.evaluate(() => {
        const view=__controlDomainTest, dossier=document.querySelector('#dossier'), slot=dossier.querySelector('#inspSlot');
        const inspectorVisible=getComputedStyle(slot).display!=='none', canvasConnected=view.inspector.canvas.isConnected;
        const clones=view.inspector.objectsForTest().length;
        return {id:dossier.dataset.partId,text:dossier.textContent,
          model_badge:document.querySelector('#domainParts .pitem[data-part="dcim"] .nm')?.textContent.trim(),
          instances:view.campusAssembly.objectsFor('dcim').length,
          selected_instance:view.state().selectedInstance,cached_clones:clones,inspector_visible:inspectorVisible,
          canvas_connected:canvasConnected,visible_clones:inspectorVisible&&canvasConnected?clones:0};
      });
      assert.equal(observed.id,'dcim'); assert.match(observed.text,/软件/);
      assert.equal(observed.model_badge,'控制软件');
      assert.doesNotMatch(observed.model_badge,/未建模|待建硬件/);
      assert.match(observed.text,/不是待建硬件/);
      assert.equal(observed.instances,0); assert.equal(observed.selected_instance,null);
      assert.equal(observed.inspector_visible,false); assert.equal(observed.canvas_connected,false); assert.equal(observed.visible_clones,0);
      if (expectedCache !== undefined) assert.equal(observed.cached_clones,expectedCache);
      results.software_dossiers.push({label,...observed});
      return observed;
    }
    for (const width of [1280,390]) for (const theme of ['light','dark']) {
      await page.setViewportSize({width,height:width===390?844:900}); await go('?d=control');
      await page.locator('#ui-appearance').selectOption(theme);
      const panel=await openControls(), plate=page.locator('.facility-domain-plate[data-figure="TA-28"]');
      assert.equal(await plate.count(),1); await plate.locator('img').evaluate(image=>image.decode());
      assert.equal(await plate.locator('img').getAttribute('src'),preview);
      assert.equal(await page.locator('#domainParts .pitem').count(),1);
      assert.equal(await page.locator('#domainParts .pitem').getAttribute('data-part'),'dcim');
      assert.equal(await page.locator('#domainParts .nm').textContent(),'控制软件');
      assert.doesNotMatch(await page.locator('#domainParts .pitem').textContent(),/未建模|待建硬件/);
      const geometry=await page.evaluate(()=>{
        const view=__controlDomainTest;
        return {state:view.state(),campus_mode:view.campusMode,meshes:view.pickables.length,
          control_parts:view.BOM.parts.filter(part=>part.system==='control').map(part=>({id:part.id,kind:part.kind})),
          control_instances:view.campusAssembly.instances.filter(instance=>view.PART[instance.part]?.system==='control').map(instance=>instance.id),
          instances:view.campusAssembly.instances.map(instance=>({id:instance.id,home:instance.home.toArray(),position:instance.object.position.toArray()})),
          rights:view.RIGHTS.map(part=>({id:part.id,instances:view.campusAssembly.objectsFor(part.id).length})),
          dcim_instances:view.campusAssembly.objectsFor('dcim').length};
      });
      assert.equal(geometry.campus_mode,true); assert.equal(geometry.state.activeDomain,'control');
      assert.deepEqual(geometry.control_parts,[{id:'dcim',kind:'software'}]);
      assert.deepEqual(geometry.control_instances,[]); assert.equal(geometry.dcim_instances,0);
      assert.equal(geometry.meshes,152); assert.equal(geometry.instances.length,32);
      for(const instance of geometry.instances) assert.deepEqual(instance.position,instance.home);
      assert.equal(geometry.rights.length,6); assert.ok(geometry.rights.every(right=>right.instances===0));
      results.geometry.push({width,theme,...geometry});
      await page.locator('#fit-view').click(); await settle();
      if(width===390){
        const file='control-domain-controls-'+theme+'.png';
        await page.screenshot({path:path.join(out,file)}); results.controls.push({width,theme,file});
        await panel.locator(':scope>summary').click();
        await page.evaluate(()=>__controlDomainTest.sceneView.fit()); await settle();
      }
      await saveView('domain3D','control-domain-'+width+'-'+theme+'.png',{width,theme});
    }
    await page.setViewportSize({width:1280,height:900}); await go('?d=control'); await openControls();
    await softwareDossier('fresh software context',0); await saveView('softwareDossier','control-software-dossier.png'); await closeDossier();
    await page.locator('#campus-whole-dossier').click(); await settle();
    assert.equal(await page.locator('#dossier .technical-atlas').getAttribute('data-figure'),'TA-36');
    assert.equal(await page.evaluate(()=>__controlDomainTest.inspector.objectsForTest().length),152);
    await saveView('wholeDossier','control-whole-context-dossier.png'); await closeDossier();
    await softwareDossier('whole152 cache retained but software stays hidden',152);
    const softwareExport=await downloadCurrent('control-software-current.svg');
    assert.equal(softwareExport.metadata.object_id,'part:dcim');
    assert.match(softwareExport.metadata.caption,/软件/); assert.match(softwareExport.metadata.caption,/无物理模型/);
    assert.match(softwareExport.text,/软件/); assert.match(softwareExport.text,/无物理模型/);
    // scene-atlas selected leaders use data-object-id; existing anchored background
    // labels use .atlas-label-leader/data-instance. Reject only software identities.
    const isDcimGeometry=id=>typeof id==='string' && /^(?:campus\/)?(?:part:)?dcim(?:$|[/:\-])/.test(id);
    assert.deepEqual(softwareExport.selected_leaders.filter(isDcimGeometry),[], 'DCIM has no selected geometry leader');
    assert.deepEqual(softwareExport.anchored_labels.filter(label=>isDcimGeometry(label.instance)),[], 'DCIM has no anchored geometry label');
    results.software_current_export={...softwareExport,physical_instances:0,not_hardware_geometry:true};
    await closeDossier();

    // Real background instance gesture; software art/caption cannot leak into it.
    await page.locator('#fit-view').click(); await settle();
    const pointer=await page.evaluate(()=>{
      const view=__controlDomainTest, rect=view.canvas.getBoundingClientRect(), hud=document.querySelector('.hud').getBoundingClientRect();
      const legend=document.querySelector('.campus-legend').getBoundingClientRect(), ray=new view.THREE.Raycaster();
      view.campusAssembly.root.updateMatrixWorld(true); view.camera.updateMatrixWorld(true);
      for(let y=Math.max(150,rect.top+10);y<legend.top;y+=5) for(let x=Math.max(340,hud.right+5);x<rect.right-15;x+=5){
        if(document.elementFromPoint(x,y)!==view.canvas) continue;
        ray.setFromCamera(new view.THREE.Vector2((x-rect.left)/rect.width*2-1,-(y-rect.top)/rect.height*2+1),view.camera);
        const hit=ray.intersectObjects(view.pickables,false).find(hit=>{for(let parent=hit.object;parent;parent=parent.parent)if(!parent.visible)return false;return true;});
        if(hit?.object.userData.part==='transformer')return{x,y,instance:view.campusAssembly.instanceFor(hit.object).id};
      }
      throw Error('No user-reachable transformer pointer sample');
    });
    assert.match(pointer.instance,/^campus\/transformer-[12]$/);
    await page.mouse.move(pointer.x,pointer.y); await page.mouse.click(pointer.x,pointer.y); await settle();
    assert.equal(await page.locator('#dossier').getAttribute('data-part-id'),'transformer');
    assert.equal(await page.evaluate(()=>__controlDomainTest.state().selectedInstance),pointer.instance);
    assert.ok(await page.evaluate(()=>__controlDomainTest.inspector.objectsForTest().length)>0);
    assert.equal(await page.locator('#dossier .technical-atlas').count(),0);
    const physicalExport=await downloadCurrent('control-background-instance.svg');
    assert.equal(physicalExport.metadata.object_id,pointer.instance);
    assert.doesNotMatch(physicalExport.metadata.caption,/无物理模型/);
    results.background_pointer={...pointer,part:'transformer',system:'power',not_software:true,export:physicalExport};
    await saveView('dossier','control-background-instance.png'); await closeDossier();
    const panel=page.locator('.ui-viewer-controls');
    if(await panel.evaluate(element=>element.open)&&await panel.locator(':scope>summary').isVisible())await panel.locator(':scope>summary').click();
    await page.evaluate(()=>__controlDomainTest.controls.enableDamping=false);
    const before=await page.evaluate(()=>__controlDomainTest.camera.position.toArray());
    await page.mouse.move(850,420); await page.mouse.down(); await page.mouse.move(925,465,{steps:12}); await page.mouse.up(); await settle();
    const moved=await page.evaluate(()=>__controlDomainTest.camera.position.toArray());
    assert.ok(Math.hypot(...moved.map((value,index)=>value-before[index]))>.01);
    await page.setViewportSize({width:1260,height:900}); await page.waitForTimeout(500);
    const resized=await page.evaluate(()=>__controlDomainTest.camera.position.toArray());
    assert.ok(Math.hypot(...resized.map((value,index)=>value-moved[index]))<1e-8);
    results.manual_camera_retained=true;

    // The old dcim alias now selects the positive software plate and same dossier.
    await go('?d=dcim'); await openControls();
    assert.equal(await page.evaluate(()=>__controlDomainTest.state().activeDomain),'control');
    assert.equal(await page.locator('.facility-domain-plate[data-figure="TA-28"]').count(),1);
    assert.equal(await page.locator('#domainParts .nm').textContent(),'控制软件');
    await softwareDossier('dcim domain alias',0); await closeDossier(); results.dcim_alias_retained=true;
    for(const [query,otherFigure] of [['?d=facility','TA-21'],['?d=network','TA-27']]){
      await go(query);
      assert.equal(await page.locator('.facility-domain-plate[data-figure="'+otherFigure+'"]').count(),1);
      assert.equal(await page.locator('[data-figure="TA-28"]').count(),0);
      results.scope_isolation.push({query,figure:otherFigure,no_control_binding:true});
    }
    for(const query of ['', '?x=70']){
      await go(query); assert.equal(await page.locator('.facility-domain-plate').count(),0);
      assert.equal(await page.locator('[data-figure="TA-28"]').count(),0);
      await saveView('old3D',query?'control-scope-TA19.png':'control-scope-TA18.png');
      results.scope_isolation.push({query,no_domain_plate:true});
    }
    for(const [url,expected] of [['/bom.html#ssd','TA-01'],['/bom.html#nic','TA-07'],['/server-plan.html','TA-12']]){
      const response=await page.goto(base+url,{waitUntil:'domcontentloaded'}); assert.equal(response.status(),200);
      await page.locator('.technical-atlas[data-figure="'+expected+'"]').waitFor();
      assert.equal(await page.locator('[data-figure="TA-28"]').count(),0);
      results.scope_isolation.push({url,figure:expected,no_control_binding:true});
    }
    assert.equal(results.views.filter(view=>view.kind==='static').length,4);
    assert.equal(results.views.filter(view=>view.kind==='domain3D').length,4);
    assert.equal(results.controls.length,2); assert.equal(results.downloads.length,2);
    assert.deepEqual(results.errors,[]); assert.deepEqual(results.route_errors,[]); assert.deepEqual(results.resource_failures,[]);
    results.status='PASS';
    console.log('TA-28 actual-public static4/domain4/controls2/fullSVG6/dualdownload/software0physical/cachehidden/realpointer/alias/scope PASS');
  } catch(error) {
    results.status='FAIL'; results.failure=error.stack||String(error); throw error;
  } finally {
    results.finished_at=new Date().toISOString();
    fs.writeFileSync(path.join(out,'control-domain-results.json'),JSON.stringify(results,null,2)+'\n');
    if(browser)await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1});
