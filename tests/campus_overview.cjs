/* TA18 actual geometry/public observer. This file never starts a server.
 * Interactive invocations require public HTTPS; the separately authorized CI
 * runner may supply its own loopback HTTP origin when CI=true. This task only
 * runs actual production HTTPS after deployment; no local product test is run.
 * Runtime assertions do not replace individual visual review/publication.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const net = require('node:net');

function publicHttps(value) {
  const u = new URL(value), host = u.hostname.toLowerCase().replace(/\.$/, '');
  if(process.env.CI==='true' && u.protocol==='http:' && u.hostname==='127.0.0.1' && u.port)return u;
  assert.equal(u.protocol, 'https:', 'Interactive targets and all browser requests must use public HTTPS');
  assert.ok(!u.username && !u.password, 'Do not embed credentials in a target URL');
  assert.ok(!net.isIP(host.replace(/^\[|\]$/g, '')), 'Public DNS hostname required; IP literals are disallowed');
  assert.ok(host.includes('.') && !/(^|\.)(localhost|local|internal|localdomain|test|invalid)$/.test(host),
    'Local/internal/test hosts are disallowed');
  assert.ok(!/(^|\.)(nip\.io|sslip\.io|localtest\.me|lvh\.me)$/.test(host),
    'Loopback wildcard hosts are disallowed');
  assert.ok(!u.port || u.port === '443', 'Public HTTPS default port required');
  return u;
}
assert.ok(process.env.UI_BASE_URL, 'UI_BASE_URL is required; no local fallback');
const baseURL = publicHttps(process.env.UI_BASE_URL);
assert.equal(baseURL.pathname, '/', 'UI_BASE_URL must be an origin');
assert.ok(!baseURL.search && !baseURL.hash, 'UI_BASE_URL must not contain query/hash');
const base = baseURL.origin;
const scenario = process.argv[2] || 'all';
assert.ok(['all', 'views', 'assembly'].includes(scenario), 'Use views, assembly or all');
const root = process.env.TA18_SOURCE_ROOT || path.resolve(__dirname, '..');
const out = process.env.REVIEW_SCREENSHOTS || path.join(require('node:os').tmpdir(), 'ta18-campus-public-' + Date.now());
fs.mkdirSync(out, {recursive:true});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const assetNames = ['campus-overview-v1.svg', 'campus-overview-v1.png'];
const expectedAssets = Object.fromEntries(assetNames.map(name => {
  const file = path.join(root, 'web/assets/technical-atlas', name);
  assert.ok(fs.existsSync(file), 'Set TA18_SOURCE_ROOT to the reviewed source tree: ' + file);
  return [name, {sha256:sha(fs.readFileSync(file)), bytes:fs.statSync(file).size}];
}));
const {chromium} = require('playwright');
const {PNG} = require('pngjs');
const results = [], sources = [], errors = [], routeErrors = [], researchResponses = [];
const expectedByPart = {shell:4, ups:1, 'rack-frame':8, 'room-cooling':5, cdu:3,
  cabling:1, chiller:3, transformer:2, 'backup-power':3, bess:2};
const expectedIDs = ['building-base','building-frame','retained-wall-sections','retained-roof-sections','UPS-bank']
  .concat([1,2].flatMap(r => [1,2,3,4].map(c => 'rack-r' + r + '-c' + c)),
    [1,2,3,4,5].map(i => 'room-cooling-' + i),
    [1,2,3].map(i => 'CDU-' + i), ['overhead-service-trays'],
    [1,2,3].map(i => 'air-chiller-' + i),
    [1,2].map(i => 'transformer-' + i),
    [1,2,3].map(i => 'standby-generator-' + i),
    [1,2].map(i => 'battery-cabinet-' + i)).map(id => 'campus/' + id);
const expectedRights = [
  ['land','land'], ['water-rights','water'], ['grid','grid'],
  ['gas-supply','fuel-supply'], ['network-access','network-access'], ['permits','permits']
];
let browser, page, failure;
const sameCamera = (a,b,label) => {
  for (const key of ['position','target']) {
    assert.equal(a[key].length, b[key].length);
    a[key].forEach((n,i) => assert.ok(Math.abs(n-b[key][i]) < 1e-6, label + ' ' + key));
  }
};
const note = (label,data={}) => results.push({label,...data});

(async () => {
  try {
    browser = await chromium.launch({headless:process.env.UI_HEADED !== '1',
      args:process.env.UI_HEADED === '1' ? [] : ['--enable-unsafe-swiftshader']});
    const context = await browser.newContext({viewport:{width:1280,height:900},
      deviceScaleFactor:1,reducedMotion:'reduce',acceptDownloads:true});
    await context.route('**/*', async route => {
      try {
        const u = publicHttps(route.request().url());
        assert.equal(u.origin, base, 'Observer may request only the explicitly selected public origin');
        await route.continue();
      } catch (error) {
        routeErrors.push(error.message);
        await route.abort('blockedbyclient');
      }
    });
    page = await context.newPage();
    page.setDefaultTimeout(30000);
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {
      const u = new URL(response.url());
      if (['/api/research','/api/research-summary'].includes(u.pathname))
        researchResponses.push({url:u.origin+u.pathname,status:response.status()});
    });
    async function original(route) {
      const u = publicHttps(route.request().url());
      assert.equal(u.origin,base);
      const headers = {...route.request().headers()};
      delete headers['if-none-match'];
      delete headers['if-modified-since'];
      const response = await route.fetch({headers,maxRedirects:0});
      const body = await response.text();
      sources.push({url:route.request().url(),status:response.status(),
        bytes:Buffer.byteLength(body),sha256:sha(Buffer.from(body)),conditional_headers_removed:true});
      assert.equal(response.status(),200,'Observation source must be actual full HTTP 200');
      assert.ok(body.trim().length > 0,'Observation source must not be empty/304/login redirect');
      return {response,body};
    }
    async function observe(route, marker, replacement) {
      try {
        const {response,body} = await original(route);
        assert.equal(body.split(marker).length-1,1,'Observation marker must match exactly once: ' + marker);
        await route.fulfill({response,body:body.replace(marker,replacement)});
      } catch (error) {
        routeErrors.push(error.message);
        await route.abort('failed');
      }
    }
    await page.route(/\/assets\/part-inspector\.js(?:\?[^#]*)?$/, route =>
      observe(route, 'return {canvas: iCv,',
        'return {objectsForTest:()=>iGroup?.children||[],viewForTest:()=>({camera:iCam,canvas:iCv,objects:[iGroup]}),canvas: iCv,'));
    await page.route(/\/assets\/campus-assembly\.js(?:\?[^#]*)?$/, route =>
      observe(route, 'return {root,instances,counts:CAMPUS_COUNTS',
        'return {resourcesForTest:()=>({geometries:[...geometries],materials:[...materials]}),root,instances,counts:CAMPUS_COUNTS'));
    const exposure = 'globalThis.__campusTest={THREE,atlasDrawing,campusMode,campusAssembly,scene,canvas,camera,controls,pickables,PART,RIGHTS,BOM,DOMAINS,PARTMESH,inspector,sceneView,sceneModels,sceneEnvironment,texturePool,composer,renderer,currentPartMeshes,showDossier,showCampusObject,resolveScenePart,focusCampus,campusInsets,clearDomain,enterDomain,walkChain,animateSlider,flyTo,disposePage,dimmed,state:()=>({selectedInstance:campusSelectedInstance,activeDomain,pageDisposed,stage:+slider.value})};\n</script>\n</body>';
    await page.route(/\/bom3d\.html(?:\?[^#]*)?$/, route =>
      observe(route,'</script>\n</body>',exposure));

    async function settled() {
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      assert.deepEqual(routeErrors,[], 'Observation/network guard failure');
    }
    async function go(suffix='/bom3d.html') {
      const response = await page.goto(base+suffix,{waitUntil:'domcontentloaded'});
      assert.equal(response.status(),200,'Public scene document must be HTTP 200');
      await page.waitForFunction(() => !!globalThis.__campusTest);
      await settled();
    }
    async function controlsOpen(open=true) {
      const panel = page.locator('[data-responsive-panel]');
      const summary=page.getByLabel('展开或收起场景控制');
      if (!await summary.isVisible()) {
        assert.ok(page.viewportSize().width>700,'Mobile controls summary must actually be visible');
        assert.equal(await panel.evaluate(el=>el.open),true,'Desktop controls remain open; hidden summary cannot collapse them');
        await settled();return;
      }
      if (await panel.evaluate(el => el.open) !== open) await summary.click();
      await settled();
    }
    const camera = () => page.evaluate(() => {
      const v=__campusTest;
      return {position:v.camera.position.toArray(),target:v.controls.target.toArray()};
    });
    const stage = t => page.locator('#explode').evaluate((el,value) => {
      el.value=String(value); el.dispatchEvent(new Event('input',{bubbles:true}));
    },t);
    async function closeDossier() {
      if (await page.locator('#dossier').isVisible())
        await page.getByRole('button',{name:'关闭部件档案'}).click();
      await settled();
    }
    async function fit() {
      await controlsOpen();
      await page.locator('#fit-view').click();
      await settled();
    }
    async function measure(parts=null) {
      return page.evaluate(parts => {
        const v=__campusTest, rect=v.canvas.getBoundingClientRect();
        v.scene.updateMatrixWorld(true); v.camera.updateMatrixWorld(true);
        const objects=parts ? parts.flatMap(p=>v.campusAssembly.objectsFor(p)) : v.pickables;
        let count=0,left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity,minZ=1,maxZ=-1;
        const seen=new Set();
        for (const root of objects) root.traverseVisible(o => {
          if (!o.isMesh || seen.has(o)) return;
          seen.add(o);
          if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
          const b=o.geometry.boundingBox;
          for (const x of [b.min.x,b.max.x]) for (const y of [b.min.y,b.max.y]) for (const z of [b.min.z,b.max.z]) {
            const p=new v.THREE.Vector3(x,y,z).applyMatrix4(o.matrixWorld).project(v.camera);
            count++; left=Math.min(left,rect.left+(p.x+1)*rect.width/2);
            right=Math.max(right,rect.left+(p.x+1)*rect.width/2);
            top=Math.min(top,rect.top+(1-p.y)*rect.height/2);
            bottom=Math.max(bottom,rect.top+(1-p.y)*rect.height/2);
            minZ=Math.min(minZ,p.z); maxZ=Math.max(maxZ,p.z);
          }
        });
        const plain=r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height});
        const hud=plain(document.querySelector('.hud').getBoundingClientRect());
        const legend=plain(document.querySelector('.campus-legend').getBoundingClientRect());
        const headers=[document.querySelector('#ui-skinbar'),document.querySelector('.topbar')].filter(Boolean);
        const labels=[...document.querySelectorAll('.atlas-scene-labels text')].filter(e=>e.style.display!=='none')
          .map(e=>({text:e.textContent,rect:plain(e.getBoundingClientRect())}));
        return {count,left,right,top,bottom,minZ,maxZ,canvas:plain(rect),hud,legend,
          headerBottom:Math.max(0,...headers.map(e=>e.getBoundingClientRect().bottom)),
          legendTexts:[...document.querySelectorAll('.campus-legend-grid span')].map(e=>e.textContent),
          markerSources:[...v.atlasDrawing.labels].map(sprite=>{const a=sprite.userData.atlasLabel,p=sprite.parent.localToWorld(new v.THREE.Vector3(...a.anchorPosition)).project(v.camera);return {label:a.text,instance:a.anchorInstance,parent:sprite.parent.userData.instanceId,x:rect.left+(p.x+1)*rect.width/2,y:rect.top+(1-p.y)*rect.height/2};}),
          markerLeaders:[...document.querySelectorAll('.atlas-label-leader')].filter(g=>g.style.display!=='none').map(g=>({label:g.dataset.label,instance:g.dataset.instance,x:rect.left+Number(g.querySelector('circle').getAttribute('cx')),y:rect.top+Number(g.querySelector('circle').getAttribute('cy'))})),
          legendColors:{background:getComputedStyle(document.querySelector('.campus-legend')).backgroundColor,
            foreground:[...document.querySelectorAll('.campus-legend b,.campus-legend-grid span')].map(e=>getComputedStyle(e).color)},
          labels,aspect:v.camera.aspect,buffer:[v.canvas.width,v.canvas.height],
          viewport:[innerWidth,innerHeight],stage:v.state().stage,
          legendScroll:[document.querySelector('.campus-legend').scrollWidth,document.querySelector('.campus-legend').clientWidth]};
      },parts);
    }
    function clearsGeometry(r, label) {
      const eps=1.5;
      assert.ok(r.count>0,label+' has no actual geometry');
      assert.ok(r.left>=r.canvas.left-eps && r.right<=r.canvas.right+eps &&
        r.top>=r.canvas.top-eps && r.bottom<=r.canvas.bottom+eps &&
        r.minZ>=-1-eps/1000 && r.maxZ<=1+eps/1000,label+' clipped '+JSON.stringify(r));
      const apart = box => r.right<=box.left+eps || r.left>=box.right-eps ||
        r.bottom<=box.top+eps || r.top>=box.bottom-eps;
      assert.ok(apart(r.hud),label+' geometry overlaps HUD '+JSON.stringify(r));
      assert.ok(apart(r.legend),label+' geometry overlaps legend '+JSON.stringify(r));
      assert.ok(r.canvas.top>=r.headerBottom-.5,label+' canvas under top header');
      assert.ok(Math.abs(r.aspect-r.canvas.width/r.canvas.height)<.005,label+' aspect mismatch');
    }
    async function downloadFrom(locator,filename,saveName=filename) {
      const pending=page.waitForEvent('download');
      await locator.click();
      const download=await pending;
      assert.equal(await download.failure(),null);
      assert.equal(download.suggestedFilename(),filename);
      const bytes=fs.readFileSync(await download.path());
      const destination=path.join(out,saveName);
      await download.saveAs(destination);
      return {bytes,sha256:sha(bytes),length:bytes.length,saved:destination};
    }
    async function currentSVG(id) {
      await controlsOpen();
      const d=await downloadFrom(page.locator('#atlas-export'),'bom3d-technical-atlas.svg',id.replace(/[^a-z0-9_-]/gi,'-')+'-current.svg');
      const parsed=await page.evaluate(raw => {
        const doc=new DOMParser().parseFromString(raw,'image/svg+xml');
        if (doc.querySelector('parsererror')) throw Error('Invalid current SVG');
        return {metadata:JSON.parse(doc.querySelector('metadata').textContent),
          leader:doc.querySelector('[data-object-id]')?.getAttribute('data-object-id'),
          image:doc.querySelector('image')?.getAttribute('href'),
          editable:doc.querySelectorAll('#editable-labels text').length,
          markers:[...doc.querySelectorAll('.atlas-label-leader')].map(g=>({label:g.dataset.label,instance:g.dataset.instance,circle:!!g.querySelector('circle'),path:!!g.querySelector('path')}))};
      },d.bytes.toString('utf8'));
      assert.equal(parsed.metadata.object_id,id);
      assert.equal(parsed.metadata.style,'white-technical-atlas-v1');
      assert.equal(parsed.leader,id);
      assert.ok(parsed.editable>=10);
      assert.equal(parsed.markers.length,9);assert.ok(parsed.markers.every(m=>m.circle&&m.path));
      assert.equal(parsed.markers.find(m=>m.label==='08').instance,'campus/standby-generator-2');assert.equal(parsed.markers.find(m=>m.label==='09').instance,'campus/battery-cabinet-2');
      const pixels=PNG.sync.read(Buffer.from(parsed.image.split(',')[1],'base64'));
      assert.deepEqual([...pixels.data.subarray(0,4)],[250,249,242,255]);
      note('Actual current-view SVG local identity/PNG paper/editable labels',
        {id,sha256:d.sha256,bytes:d.length,metadata:parsed.metadata,editable:parsed.editable});
    }

    if (scenario!=='assembly') {
      for (const width of [1280,390]) for (const theme of ['light','dark']) {
        await page.setViewportSize({width,height:width===390?844:900});
        await go('/bom3d.html');
        assert.equal(await page.evaluate(()=>__campusTest.campusMode),true);
        assert.equal(await page.locator('#explode').inputValue(),'0');
        await page.locator('#ui-appearance').selectOption(theme);
        await settled();
        const initial=await measure();
        clearsGeometry(initial,'Default assembled '+width+' '+theme);
        assert.ok(initial.hud.top>=initial.headerBottom+1,'HUD summary must be below the actual two-row header/navigation');
        assert.equal(initial.legendTexts.length,9);
        assert.ok(initial.legendScroll[0]<=initial.legendScroll[1]+1,'Legend text overflow');
        const luminance=color=>{const rgb=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
        assert.equal(initial.legendColors.foreground.length,10);
        assert.equal(initial.markerSources.length,9);assert.equal(initial.markerLeaders.length,9);
        for(const leader of initial.markerLeaders){const source=initial.markerSources.find(s=>s.label===leader.label);assert.equal(leader.instance,source.instance);assert.equal(source.parent,source.instance);assert.ok(Math.hypot(leader.x-source.x,leader.y-source.y)<.02,'Leader must terminate at actual same-instance projection '+leader.label);}
        assert.equal(initial.markerSources.find(s=>s.label==='08').instance,'campus/standby-generator-2');
        assert.equal(initial.markerSources.find(s=>s.label==='09').instance,'campus/battery-cabinet-2');
        const bg=luminance(initial.legendColors.background);
        for(const color of initial.legendColors.foreground){const fg=luminance(color);assert.ok((Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)>=4.5,'Actual legend text contrast below4.5 '+theme+' '+color+' on '+initial.legendColors.background);}
        assert.deepEqual(initial.labels.map(x=>x.text).sort(),
          ['01','02','03','04','05','06','07','08','09']);
        for (const label of initial.labels) assert.ok(label.rect.left>=0 && label.rect.right<=width+1 &&
          label.rect.top>=initial.canvas.top-1 && label.rect.bottom<=initial.canvas.bottom+1,
          'Actual visible label cut: '+JSON.stringify(label));
        await page.screenshot({path:path.join(out,'campus-default-'+width+'-'+theme+'.png')});
        const pixels=PNG.sync.read(Buffer.from((await page.evaluate(()=>{
          __campusTest.composer.render();return __campusTest.canvas.toDataURL('image/png');
        })).split(',')[1],'base64'));
        const colors=new Set();let dark=0;
        for (let n=0;n<pixels.data.length;n+=16) {
          const rgb=[...pixels.data.subarray(n,n+3)];colors.add(rgb.join(','));
          if (Math.min(...rgb)<150) dark++;
        }
        assert.ok(colors.size>50 && dark>100,'Actual canvas is empty/flat');
        note('Default assembled actual corners/UI/labels/pixels',
          {width,theme,...initial,pngSize:[pixels.width,pixels.height],colors:colors.size,dark});
        await fit();
        clearsGeometry(await measure(),'Explicit fit with open HUD '+width+' '+theme);
        if (width===390) {
          await controlsOpen(false);
          const closed=await measure();clearsGeometry(closed,'Phone close-after-fit');
          assert.equal(await page.locator('[data-responsive-panel]').evaluate(e=>e.open),false);
          await page.screenshot({path:path.join(out,'campus-hud-close-'+width+'-'+theme+'.png')});
          await controlsOpen();await fit();
          const phoneExport=await downloadFrom(page.locator('#atlas-export'),'bom3d-technical-atlas.svg','campus-phone-'+theme+'-current.svg');
          const phoneMarkers=await page.evaluate(raw=>{const doc=new DOMParser().parseFromString(raw,'image/svg+xml');if(doc.querySelector('parsererror'))throw Error('Invalid phone SVG');return [...doc.querySelectorAll('.atlas-label-leader')].map(g=>({label:g.dataset.label,instance:g.dataset.instance,path:g.querySelector('path').getAttribute('d'),circle:[g.querySelector('circle').getAttribute('cx'),g.querySelector('circle').getAttribute('cy')]}))},phoneExport.bytes.toString('utf8'));
          assert.equal(phoneMarkers.length,9);assert.equal(phoneMarkers.find(m=>m.label==='08').instance,'campus/standby-generator-2');assert.equal(phoneMarkers.find(m=>m.label==='09').instance,'campus/battery-cabinet-2');
          note('Actual phone current SVG retains nine same-instance editable marker leaders',{theme,sha256:phoneExport.sha256,bytes:phoneExport.length,markers:phoneMarkers});
          await controlsOpen(false);
          note('Phone HUD open/fit/close refresh keeps current available rectangle',closed);
        }
      }
    }

    if (scenario!=='views') {
      await page.setViewportSize({width:1280,height:900});
      await go('/bom3d.html?x=0');
      const structure=await page.evaluate(()=>{
        const v=__campusTest,a=v.campusAssembly;
        return {campus:v.campusMode,stage:v.state().stage,picks:v.pickables.length,
          uniquePicks:new Set(v.pickables).size,models:v.sceneModels.objects().length,
          instances:a.instances.map(i=>{
            const meshes=[];i.object.traverse(o=>{if(o.isMesh)meshes.push(o)});
            return {id:i.id,part:i.part,position:i.object.position.toArray(),home:i.home.toArray(),
              featureCounts:i.object.userData.featureCounts,packing:i.object.userData.geometryPacking,
              meshes:meshes.map(m=>({part:m.userData.part,instance:m.userData.campusInstance,
                vertices:m.geometry.attributes.position.count,finite:Array.from(m.geometry.attributes.position.array).every(Number.isFinite)}))};
          }),nonphysical:v.pickables.filter(m=>v.PART[m.userData.part]?.kind!=='part').length,
          contextGround:(()=>{const a=[];v.campusAssembly.root.traverse(o=>{if(o.isMesh&&!o.userData.part)a.push({name:o.name,skip:!!o.userData.atlasSkip})});return a})()};
      });
      assert.equal(structure.campus,true);assert.equal(structure.stage,0);
      assert.equal(structure.instances.length,32);assert.equal(new Set(structure.instances.map(i=>i.id)).size,32);
      assert.deepEqual(structure.instances.map(i=>i.id).sort(),expectedIDs.slice().sort());
      assert.deepEqual(structure.instances.reduce((a,i)=>(a[i.part]=(a[i.part]||0)+1,a),{}),expectedByPart);
      assert.equal(structure.picks,152);assert.equal(structure.uniquePicks,structure.picks);
      assert.equal(structure.nonphysical,0);assert.equal(structure.models,0);
      assert.deepEqual(structure.contextGround,[{name:'pale-context-ground',skip:true}]);
      for (const i of structure.instances) {
        assert.deepEqual(i.position,i.home);
        assert.ok(i.packing.inputVertices>0 && i.packing.sourceMeshes>i.packing.drawMeshes);
        assert.equal(i.packing.inputVertices,i.packing.packedVertices,'Packing lost/duplicated vertices '+i.id);
        assert.equal(i.packing.drawMeshes,i.meshes.length);
        assert.equal(i.meshes.reduce((n,m)=>n+m.vertices,0),i.packing.packedVertices);
        assert.ok(i.meshes.every(m=>m.part===i.part && m.instance===i.id && m.finite));
      }
      for (const i of structure.instances.filter(i=>i.part==='rack-frame')) {
        assert.equal(i.featureCounts['closed-server-front'],12);
        assert.equal(i.featureCounts['perforated-closed-rack-door'],1);
      }
      for (const i of structure.instances.filter(i=>i.part==='chiller')) assert.equal(i.featureCounts['fan-hub'],2);
      assert.equal(structure.instances.find(i=>i.part==='ups').featureCounts['door-handle'],4);
      for (const i of structure.instances.filter(i=>i.part==='backup-power')) {
        assert.equal(i.featureCounts['external-horizontal-muffler'],1);
        assert.ok(i.featureCounts['continuous-inlet-duct']>=2 && i.featureCounts['continuous-outlet-duct']>=3);
      }
      note('Actual32 deterministic physical instances; per-instance packing and finite geometry',structure);
      const surfaces=await page.evaluate(()=>{const v=__campusTest,out=[];v.scene.updateMatrixWorld(true);for(const sprite of v.atlasDrawing.labels){const spec=sprite.userData.atlasLabel,anchor=sprite.parent.localToWorld(new v.THREE.Vector3(...spec.anchorPosition)),a=new v.THREE.Vector3(),b=new v.THREE.Vector3(),c=new v.THREE.Vector3(),nearest=new v.THREE.Vector3(),triangle=new v.THREE.Triangle();let distance=Infinity,triangles=0;sprite.parent.traverse(mesh=>{if(!mesh.isMesh)return;const position=mesh.geometry.getAttribute('position'),index=mesh.geometry.index;for(let n=0;n<(index?index.count:position.count);n+=3){a.fromBufferAttribute(position,index?index.getX(n):n).applyMatrix4(mesh.matrixWorld);b.fromBufferAttribute(position,index?index.getX(n+1):n+1).applyMatrix4(mesh.matrixWorld);c.fromBufferAttribute(position,index?index.getX(n+2):n+2).applyMatrix4(mesh.matrixWorld);triangle.set(a,b,c).closestPointToPoint(anchor,nearest);distance=Math.min(distance,nearest.distanceTo(anchor));triangles++;}});out.push({label:spec.text,instance:spec.anchorInstance,parent:sprite.parent.userData.instanceId,anchor:anchor.toArray(),distance,triangles});}return out});
      assert.equal(surfaces.length,9);for(const surface of surfaces){assert.equal(surface.instance,surface.parent);assert.ok(surface.triangles>0&&surface.distance<.00001,'Anchor must lie on actual same-instance triangle surface '+JSON.stringify(surface));}
      note('Nine annotation anchors lie on actual packed same-instance triangle surfaces',surfaces);
      await fit();

      // Real Raycaster locates a visible surface; the actual page mouse click,
      // gesture handling and dossier must agree. No direct showCampusObject call.
      async function actualPick(id) {
        await closeDossier();await controlsOpen(false);await settled();
        const hit=await page.evaluate(id=>{
          const v=__campusTest,i=v.campusAssembly.instances.find(i=>i.id===id);
          if(!i)throw Error('Missing intended instance '+id);
          v.scene.updateMatrixWorld(true);v.camera.updateMatrixWorld(true);
          const rect=v.canvas.getBoundingClientRect(),box=new v.THREE.Box3().setFromObject(i.object),
            corners=[];
          for(const x of[box.min.x,box.max.x])for(const y of[box.min.y,box.max.y])for(const z of[box.min.z,box.max.z])
            corners.push(new v.THREE.Vector3(x,y,z).project(v.camera));
          const xs=corners.map(p=>rect.left+(p.x+1)*rect.width/2),
            ys=corners.map(p=>rect.top+(1-p.y)*rect.height/2),ray=new v.THREE.Raycaster();
          const candidates=[[.5,.5],[.5,.35],[.5,.65],[.3,.5],[.7,.5]];
          for(let y=1;y<8;y++)for(let x=1;x<8;x++)candidates.push([x/8,y/8]);
          for(const [u,w]of candidates){
            const x=Math.min(...xs)+(Math.max(...xs)-Math.min(...xs))*u,
              y=Math.min(...ys)+(Math.max(...ys)-Math.min(...ys))*w;
            if(document.elementFromPoint(x,y)!==v.canvas)continue;
            ray.setFromCamera(new v.THREE.Vector2((x-rect.left)/rect.width*2-1,-(y-rect.top)/rect.height*2+1),v.camera);
            const picked=ray.intersectObjects(v.pickables,false).find(h=>{for(let p=h.object;p;p=p.parent)if(!p.visible)return false;return true})?.object;
            if(picked?.userData.campusInstance===id){
              const meshes=[];i.object.traverse(o=>{if(o.isMesh)meshes.push(o)});
              return {x,y,id,part:i.part,meshCount:meshes.length,geometryIDs:meshes.map(m=>m.geometry.uuid).sort()};
            }
          }
          return null;
        },id);
        assert.ok(hit,'No genuinely visible pick point for '+id);
        await page.mouse.move(hit.x,hit.y);
        await page.mouse.click(hit.x,hit.y);
        await page.locator('#dossier .insp canvas').waitFor();
        const actual=await page.evaluate(()=>({state:__campusTest.state(),
          clones:__campusTest.inspector.objectsForTest().map(m=>m.geometry.uuid).sort(),
          selected:__campusTest.currentPartMeshes(document.querySelector('#dossier').dataset.partId).length}));
        assert.equal(actual.state.selectedInstance,id);assert.equal(actual.selected,hit.meshCount);
        assert.deepEqual(actual.clones,hit.geometryIDs,'Inspector must borrow exactly the clicked instance geometry');
        assert.match(await page.locator('#dossier').textContent(),/通用.*实例|单个示例/);
        await settled();await page.locator('#dossier .insp').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,id.replaceAll('/','-')+'-dossier.png')});
        await currentSVG(id);
        note('Actual surface mouse pick selects one repeated or distinct instance',hit);
      }
      for (const id of ['campus/rack-r2-c2','campus/rack-r2-c3','campus/CDU-2',
        'campus/air-chiller-2','campus/transformer-1','campus/standby-generator-2'])
        await actualPick(id);
      await closeDossier();await controlsOpen();
      await page.locator('#campus-whole-dossier').click();
      await page.locator('#dossier .insp canvas').waitFor();
      const whole=await page.evaluate(()=>({state:__campusTest.state(),
        picks:__campusTest.pickables.length,clones:__campusTest.inspector.objectsForTest().length}));
      assert.equal(whole.state.selectedInstance,'campus/whole');assert.equal(whole.clones,whole.picks);
      await settled();await page.locator('#dossier .insp').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'campus-whole-inspector-1280.png')});await page.setViewportSize({width:390,height:844});await settled();await page.locator('#dossier .insp').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'campus-whole-inspector-390.png')});await page.setViewportSize({width:1280,height:900});await settled();
      await currentSVG('campus/whole');note('Whole campus inspector aggregates every real picked mesh',whole);
      await closeDossier();

      // Six canonical site nodes and legacy IDs really navigate to the new scene;
      // no successful research content claim is made for an anonymous API401.
      for(const [canonical,legacy]of expectedRights)for(const query of[
        '?node='+encodeURIComponent('site:'+canonical),'?p='+encodeURIComponent(legacy)]) {
        await go('/bom3d.html'+query);
        await page.locator('#dossier h2').waitFor();
        const r=await page.evaluate(()=>{
          const v=__campusTest,id=document.querySelector('#dossier').dataset.partId,p=v.PART[id];
          return {campus:v.campusMode,kind:p.kind,id,canonical:p.site_right_id,
            modeled:v.campusAssembly.objectsFor(id).length,meshes:v.currentPartMeshes(id).length,
            inspector:document.querySelectorAll('#dossier .insp canvas').length,
            nodeLinks:[...document.querySelectorAll('#dossier a')].map(a=>a.getAttribute('href'))};
        });
        assert.equal(r.campus,true);assert.equal(r.kind,'site_right');assert.equal(r.canonical,canonical);
        assert.equal(r.modeled,0);assert.equal(r.meshes,0);assert.equal(r.inspector,0);
        assert.ok(r.nodeLinks.some(h=>h.includes('node.html?id='+encodeURIComponent('site:'+canonical))));
        assert.ok(r.nodeLinks.some(h=>h.includes('supply.html?node='+encodeURIComponent('site:'+canonical))));
        note('Actual nonphysical canonical/legacy site entry',{query,...r});
      }
      await go('/bom3d.html?node=part:dcim');
      await page.locator('#dossier h2').waitFor();
      assert.equal(await page.evaluate(()=>__campusTest.campusMode),true);
      assert.equal(await page.locator('#dossier .insp canvas').count(),0);
      assert.equal(await page.evaluate(()=>__campusTest.campusAssembly.objectsFor('dcim').length),0);
      assert.match(await page.locator('#dossier').textContent(),/软件.*不画物理硬件/);
      note('DCIM remains a software entry with zero physical mesh');

      // Campus domains retain the assembled stage and focus only real categories.
      for(const width of[1280,390]) {
        await page.setViewportSize({width,height:width===390?844:900});
        await go('/bom3d.html');await controlsOpen();
        for(const domain of['power','thermal','facility','control']) {
          await page.locator('#dchip-'+domain).click();await settled();
          assert.equal(await page.locator('#explode').inputValue(),'0','Campus domain must not inherit legacy explode t');
          const r=await page.evaluate(key=>{
            const v=__campusTest,d=v.DOMAINS.find(d=>d.key===key);
            const parts=d.parts.map(p=>p.id),represented=parts.filter(p=>v.campusAssembly.objectsFor(p).length);
            return {parts:represented,selectedDim:v.pickables.filter(m=>parts.includes(m.userData.part)&&v.dimmed.has(m)).length};
          },domain);
          assert.equal(r.selectedDim,0,'Own canonical domain equipment was dimmed');
          const bounds=await measure(r.parts.length?r.parts:null);
          clearsGeometry(bounds,'Actual '+width+' '+domain+' domain');
          note('Campus domain safe-fit, canonical ownership, unchanged assembly stage',{width,domain,...bounds});
        }
      }
      await page.setViewportSize({width:1280,height:900});await go('/bom3d.html');await controlsOpen();
      await page.locator('#campus-static-plate').evaluate(el=>el.open=true);await settled();
      for(const filename of assetNames) {
        const d=await downloadFrom(page.locator('a[download="'+filename+'"]'),filename);
        assert.equal(d.sha256,expectedAssets[filename].sha256);
        assert.equal(d.length,expectedAssets[filename].bytes);
        if(filename.endsWith('.png')) {
          const png=PNG.sync.read(d.bytes);assert.deepEqual([png.width,png.height],[1536,1024]);
        } else {
          const s=await page.evaluate(raw=>{
            const doc=new DOMParser().parseFromString(raw,'image/svg+xml');
            if(doc.querySelector('parsererror'))throw Error('Invalid native static SVG');
            return {data:doc.querySelector('image').getAttribute('href'),
              labels:doc.querySelectorAll('g.callout[data-label]').length};
          },d.bytes.toString('utf8'));
          assert.equal(s.labels,9);
          assert.equal(sha(Buffer.from(s.data.split(',')[1],'base64')),expectedAssets['campus-overview-v1.png'].sha256);
        }
        note('Actual native UI download full byte SHA',{filename,sha256:d.sha256,bytes:d.length,saved:d.saved});
      }
      const popupPending=page.waitForEvent('popup');await page.locator('#campus-static-plate>a').click();const popup=await popupPending;await popup.waitForLoadState('domcontentloaded');await popup.setViewportSize({width:1536,height:1024});await popup.evaluate(()=>document.fonts.ready);assert.equal(await popup.locator('g.callout[data-label]').count(),9);assert.equal(sha(Buffer.from((await popup.locator('svg image').getAttribute('href')).split(',')[1],'base64')),expectedAssets['campus-overview-v1.png'].sha256);await popup.screenshot({path:path.join(out,'campus-full-svg-1536.png')});note('Actual independent native SVG popup',{url:popup.url(),labels:9,pixels:[1536,1024]});await popup.close();
      await page.locator('#campus-static-plate').evaluate(el=>el.open=false);await settled();

      // Normal animation is actually started. Explicit fit must cancel all
      // writers, including a scheduled chain step beyond its 1500ms boundary.
      await page.emulateMedia({reducedMotion:'no-preference'});
      await stage(0);await page.locator('#play').click();await page.waitForTimeout(80);
      await fit();const stopped=await page.locator('#explode').inputValue();
      await page.waitForTimeout(180);assert.equal(await page.locator('#explode').inputValue(),stopped);
      note('Explicit fit stops normal slider writer',{stopped});
      await page.evaluate(()=>{const v=__campusTest;v.flyTo([80,45,70],[5,4,3],1000)});
      await page.waitForTimeout(80);await fit();const cameraStopped=await camera();
      await page.waitForTimeout(1100);sameCamera(await camera(),cameraStopped,'Old camera motion resumed after explicit fit');
      note('Explicit fit cancels a running camera motion writer');
      await stage(0);await page.locator('#dchip-power').click();await settled();
      await page.locator('#walkBtn').click();await fit();
      const afterFit=await camera();await page.waitForTimeout(1650);
      sameCamera(await camera(),afterFit,'Old chain writer resumed after explicit fit');
      note('Explicit fit cancels scheduled chain camera writer');

      await page.evaluate(()=>__campusTest.clearDomain());await fit();await controlsOpen(false);
      const beforeDrag=await camera();
      const c=await page.locator('#c').boundingBox();
      await page.mouse.move(c.x+c.width-30,c.y+30);await page.mouse.down();
      await page.mouse.move(c.x+c.width-100,c.y+80,{steps:6});await page.mouse.up();
      // Drain only OrbitControls' residual damping after the real gesture. This
      // prevents residual inertia from being misreported as a new camera owner.
      await page.evaluate(()=>{const v=__campusTest;v.controls.enableDamping=false;v.controls.update()});
      await settled();const owned=await camera();
      assert.notDeepEqual(owned,beforeDrag,'Real orbit gesture did not own/move camera');
      await page.setViewportSize({width:1000,height:800});
      await page.evaluate(async()=>{const v=__campusTest;await v.sceneModels.reload();v.sceneView.refresh();});
      await stage(0);await settled();sameCamera(await camera(),owned,'Manual camera lost ownership after resize/stage/model refresh');
      note('Real manual orbit owns camera through resize and model/UI refresh');
      await page.emulateMedia({reducedMotion:'reduce'});

      // Exercise page cleanup with cloned inspector/dim materials and active
      // camera/slider/chain writers, without inventing protected product data.
      await controlsOpen();await page.locator('#campus-whole-dossier').click();
      await page.locator('#dossier .insp canvas').waitFor();
      await page.locator('#dchip-power').click();await settled();
      await page.emulateMedia({reducedMotion:'no-preference'});
      const released=await page.evaluate(async()=>{
        const v=__campusTest,owned=v.campusAssembly.resourcesForTest(),counts=new Map();
        const derived=[...v.dimmed.values()].flatMap(x=>x.copies)
          .concat(v.inspector.objectsForTest().flatMap(m=>[].concat(m.material)));
        const tracked=[...new Set([...owned.geometries,...owned.materials,...derived])];
        for(const o of tracked) {
          counts.set(o.uuid,0);o.addEventListener('dispose',()=>counts.set(o.uuid,counts.get(o.uuid)+1));
        }
        let renders=0,renderer=0,composer=0;
        const draw=v.composer.render.bind(v.composer),rd=v.renderer.dispose.bind(v.renderer),cd=v.composer.dispose.bind(v.composer);
        v.composer.render=(...a)=>{renders++;return draw(...a)};
        v.renderer.dispose=()=>{renderer++;rd()};v.composer.dispose=()=>{composer++;cd()};
        const power=v.DOMAINS.find(d=>d.key==='power');v.walkChain(power);
        v.animateSlider(100,2000);v.flyTo([90,40,70],[3,4,5],1100);
        v.disposePage();v.disposePage();const atDispose=renders;
        const stateAtDispose=v.state(),cameraAtDispose=v.camera.position.toArray();
        await new Promise(resolve=>setTimeout(resolve,1700));
        return {resources:counts.size,counts:[...counts.values()],renderer,composer,
          after:renders-atDispose,picks:v.pickables.length,parent:!!v.campusAssembly.root.parent,
          labels:document.querySelectorAll('.atlas-scene-labels').length,state:v.state(),
          environment:v.sceneEnvironment.current(),stateAtDispose,cameraAtDispose,
          cameraAfter:v.camera.position.toArray(),derivedMaterials:derived.length};
      });
      assert.ok(released.resources>152 && released.counts.every(n=>n===1));
      assert.equal(released.renderer,1);assert.equal(released.composer,1);assert.equal(released.after,0);
      assert.equal(released.picks,0);assert.equal(released.parent,false);assert.equal(released.labels,0);
      assert.equal(released.environment,null);assert.equal(released.state.pageDisposed,true);
      assert.ok(released.derivedMaterials>0);assert.deepEqual(released.state,released.stateAtDispose);
      assert.deepEqual(released.cameraAfter,released.cameraAtDispose);
      note('Factory cached/packed resources released once, main renderer loop stopped',released);

      // These are retained legacy routes, not TA19/TA20 new-view acceptance.
      for(const suffix of['?x=35','?p=server','?node=part:gpu','?view=legacy']) {
        await go('/bom3d.html'+suffix);
        const r=await page.evaluate(()=>({campus:__campusTest.campusMode,assembly:!!__campusTest.campusAssembly,
          racks:__campusTest.pickables.filter(m=>m.userData.part==='rack-frame').length,
          count:__campusTest.pickables.length}));
        assert.equal(r.campus,false);assert.equal(r.assembly,false);assert.equal(r.racks,28);assert.ok(r.count>28);
        if(suffix.includes('server'))await page.locator('#dossier .insp canvas').waitFor();
        note('Explicit retained legacy route',{suffix,...r});
      }
    }
    assert.deepEqual(routeErrors,[]);assert.deepEqual(errors,[]);
    note('Research response statuses only; anonymous401 is not content success',{responses:researchResponses});
    console.log('PASS TA18 public '+scenario+' observer; native screenshots still require independent visual review');
  } catch (error) {
    failure={message:error.message,stack:error.stack};process.exitCode=1;
    console.error(error);
  } finally {
    fs.writeFileSync(path.join(out,'campus-overview-results-'+scenario+'.json'),JSON.stringify({
      observed_at:new Date().toISOString(),scenario,base,
      browser_mode:process.env.UI_HEADED==='1'?'headed-default-graphics':'headless-software-graphics',
      source_root:root,expected_assets:expectedAssets,results,sources,page_errors:errors,
      route_errors:routeErrors,research_responses:researchResponses,failure,
      evidence_boundary:'Actual runtime assertions only when this script is explicitly run. Screenshots require individual visual review. No CI/deploy/published count inference.'
    },null,2)+'\n');
    if(browser)await browser.close();
  }
})();
