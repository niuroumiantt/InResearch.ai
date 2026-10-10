/* TA29 actual-public acceptance runner: actual https://inresearch.ai only.
 * Owner reviews this runner before deployed public execution. This file is test source,
 * never a claim of browser/visual acceptance. No local product/server fallback.
 * Read-only source bytes are used only to verify fetched public source SHA.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const base = 'https://inresearch.ai';
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(process.env.UI_BASE_URL, base, 'Strict actual public origin required');
const root = process.env.TA29_SOURCE_ROOT;
assert.ok(root && path.isAbsolute(root), 'Explicit reviewed TA29_SOURCE_ROOT required');
const out = process.env.REVIEW_SCREENSHOTS || '/private/tmp/ta29-public-' + Date.now();
assert.ok(path.isAbsolute(out));

// Observer changes may expose references/read-only state, never fake geometry,
// replace materialFor/identityFor/titleFor, or import local product code.
const endModule='</script>\n</body>';
const WIRING = {
  inspector: {marker:'return {canvas: iCv,', replacement:`return {observeForTest:()=>({canvas:iCv,renderer:iRen,scene:iScene,camera:iCam,pivot:iPivot,group:iGroup,drawing,viewport,
    state:{visible:iVisible,spin:iSpin,disposed,enlarged:expanded,drag:!!drag,objectId:currentId,title:currentTitle,rotation:{x:iRotX,y:iRotY}}}),canvas: iCv,`},
  drawing: {marker:'return {sync,update,label,labels,attachLabels,projectedLabels,dispose() {',
    replacement:'return {ownedForTest:()=>({geometries:[...geometries.values()],materials:[lineMaterial],textures:[...labels].map(label=>label.material.map)}),sync,update,label,labels,attachLabels,projectedLabels,dispose() {'},
  bom: {marker:endModule, replacement:`globalThis.__ta29={THREE,BOM,PART,RIGHTS,inspector,camera,controls,canvas,scene,renderer,composer,pickables,currentPartMeshes,campusAssembly,dimmed,sceneView,disposePage,
    showDossier,rawShowDossier,showCampusObject,resolveScenePart,
    baselineMaterialFor:mesh=>dimmed.get(mesh)?.original||mesh.userData.covPrev||mesh.material,
    identityForMesh:mesh=>campusMode?campusAssembly.instanceFor(mesh)?.id||null:'part:'+mesh.userData.part,
    readState:()=>({mode:campusLayeredMode?'campus-layered':campusMode?'campus':'legacy-campus',stage:+slider.value,activeDomain,selectedInstance:campusSelectedInstance,pageDisposed,covOn,productRegistryLoaded:PRODCOUNT!==null})};\n`+endModule},
  rack: {marker:endModule, replacement:`globalThis.__ta29={THREE,BOM,PART,inspector,camera,controls,canvas,scene,renderer,composer,pickables,currentPartMeshes,rackAssembly,chipAssembly,serverAssembly,sceneView,disposePage,
    showDossier,rawShowDossier,showRackObject,showServerObject,showChipObject,
    baselineMaterialFor:mesh=>mesh.material,
    identityForMesh:mesh=>{let instance=mesh;
      if(serverMode){while(instance.parent&&instance.parent!==rack&&!/^(cpu-\\d+|dimm-\\d+|accelerator-\\d+|fan-\\d+|drive-\\d+|rear-psu-\\d+|rear-network-card)$/.test(instance.name))instance=instance.parent;
        return /^(cpu-\\d+|dimm-\\d+|accelerator-\\d+|fan-\\d+|drive-\\d+|rear-psu-\\d+|rear-network-card)$/.test(instance.name)?'server/'+instance.name:'part:'+mesh.userData.part;}
      if(chipMode){while(instance.parent&&instance.parent!==rack&&!/^logic-die$|^hbm-\\d+$|^substrate$|^interposer$/.test(instance.name))instance=instance.parent;return instance.userData.instanceId||'package/'+instance.name;}
      if(rackMode){while(instance.parent&&instance.parent!==rack&&!/^(compute-\\d+|switch-\\d+|power-shelf-\\d+|optional-busbar|optional-manifolds)$/.test(instance.name))instance=instance.parent;return instance.userData.instanceId||null;}
      return 'part:'+mesh.userData.part;},
    readState:()=>({mode:chipMode?'chip':serverMode?'server':rackExplodedMode?'rack-exploded':rackOverviewMode?'rack':'legacy-rack',stage:+slider.value,activeDomain:null,
      selectedInstance:chipSelectedInstance||rackSelectedInstance||serverSelectedInstance,pageDisposed})};\n`+endModule},
  selectors: {
    mini:'#inspSlot canvas, .part-inspector-dialog[open] canvas', host:'#inspSlot', closeDossier:'#dossier .close',
    enlarge:'[data-preview-action="expand"]', shrink:'.part-inspector-dialog[open] .part-inspector-dialog-close',
    fit:'[data-preview-action="fit"]', spin:'[data-preview-action="spin"]',
    exportMini:'[data-preview-action="download"]', enlargedHost:'.part-inspector-dialog[open]'
  }
};
/* Required observation contract (must be built from actual closure references):
 * globalThis.__ta29 = {THREE, inspector, camera, controls, canvas, pickables,
 *   PART, RIGHTS?, currentPartMeshes, campusAssembly?, rackAssembly?, chipAssembly?,
 *   serverAssembly?, dimmed?, sceneView, disposePage,
 *   baselineMaterialFor(mesh), identityForMesh(mesh),
 *   readState:()=>({mode,stage,activeDomain,selectedInstance,pageDisposed})};
 * inspector.observeForTest() => {canvas,renderer,scene,camera,pivot,group,
 *   state:{visible,spin,disposed,enlarged,objectId,title,rotation:{x,y}}};
 * The property names above are an adapter proposal, not asserted product API.
 * identityForMesh is observation-only and must match the real selection branch;
 * do not invent an installed-rack id in the observer to mask a product gap.
 */
const CAMPUS_PARTS = ['shell','ups','rack-frame','room-cooling','cdu','cabling','chiller','transformer','backup-power','bess'];
const CAMPUS_COUNTS = {shell:4,ups:1,'rack-frame':8,'room-cooling':5,cdu:3,cabling:1,chiller:3,transformer:2,'backup-power':3,bess:2};
const CAMPUS_IDS = ['building-base','building-frame','retained-wall-sections','retained-roof-sections','UPS-bank',
  ...[1,2].flatMap(row=>[1,2,3,4].map(col=>'rack-r'+row+'-c'+col)),
  ...[1,2,3,4,5].map(n=>'room-cooling-'+n), ...[1,2,3].map(n=>'CDU-'+n),
  'overhead-service-trays', ...[1,2,3].map(n=>'air-chiller-'+n), ...[1,2].map(n=>'transformer-'+n),
  ...[1,2,3].map(n=>'standby-generator-'+n), ...[1,2].map(n=>'battery-cabinet-'+n)].map(id=>'campus/'+id);
const SERVER_PARTS = ['server','cpu','dram','gpu','ssd','nic','psu','server-fan'];
const RACK_PARTS = ['rack-frame','server','power-shelf','network-switch'];
const CHIP_PARTS = ['gpu','hbm'];
const RIGHTS = [['land','land'],['water-rights','water'],['grid','grid'],['gas-supply','fuel-supply'],['network-access','network-access'],['permits','permits']];
const MODES = [
  {id:'campus0',url:'/bom3d.html',mode:'campus',parts:CAMPUS_PARTS,whole:'#campus-whole-dossier',wholeId:'campus/whole'},
  {id:'campus70',url:'/bom3d.html?view=exploded&x=70',mode:'campus-layered',parts:CAMPUS_PARTS,whole:'#campus-whole-dossier',wholeId:'campus/whole'},
  {id:'rack0',url:'/rack3d.html?view=rack&x=0',mode:'rack',parts:RACK_PARTS,whole:'#rack-overview-dossier',wholeId:'rack/whole'},
  {id:'rack35',url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',parts:RACK_PARTS,whole:'#rack-overview-dossier',wholeId:'rack/whole'},
  {id:'server55',url:'/rack3d.html?view=server&x=55',mode:'server',parts:SERVER_PARTS,whole:null,wholeId:'part:server'},
  {id:'chip90',url:'/rack3d.html?view=chip&x=90',mode:'chip',parts:CHIP_PARTS,whole:'#chip-package-dossier',wholeId:'package/whole'}
];
const results = {figure:'TA-29',stage:'DRAFT_NOT_EXECUTED',required_origin:base,
  local_fallback:false,source_root:root,matrix:MODES,source_responses:[],inventory:[],previews:[],
  gestures:[],exports:[],materials:[],resources:[],views:[],errors:[],route_errors:[],resource_failures:[],
  static_downloads:[],visual_review:{status:'pending_human_original_size_review',note:'Counts, bounds and nonblank pixels do not prove visual quality.'},
  research_content:'not_verified'};

for (const entry of [WIRING.inspector,WIRING.drawing,WIRING.bom,WIRING.rack]) assert.ok(entry.marker && entry.replacement);
for (const key of ['enlarge','shrink','fit','spin','exportMini','enlargedHost']) assert.ok(WIRING.selectors[key], key+' selector pending');

(async()=>{
  let browser;
  try {
    fs.mkdirSync(out,{recursive:true});
    const {chromium} = require('playwright');
    browser=await chromium.launch({headless:process.env.UI_HEADED!=='1'});
    const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,
      reducedMotion:'reduce',acceptDownloads:true,serviceWorkers:'block'});
    await context.route('**/*',async route=>{
      try {assert.equal(new URL(route.request().url()).origin,base);await route.continue();}
      catch(error){results.route_errors.push(error.message);await route.abort('blockedbyclient');}
    });
    const page=await context.newPage();
    page.on('pageerror',error=>results.errors.push(error.message));
    page.on('response',response=>{if(new URL(response.url()).pathname.startsWith('/assets/') && response.status()>=400)
      results.resource_failures.push({url:response.url(),status:response.status()});});
    async function publicGet(url) {
      assert.equal(new URL(url).origin,base);
      const response=await context.request.get(url,{maxRedirects:0});
      assert.equal(response.status(),200,url);return response;
    }
    async function observe(route,relativeFile,hook) {
      try {
        const url=route.request().url();assert.equal(new URL(url).origin,base);
        const headers={...route.request().headers()};
        const removed=['if-none-match','if-modified-since'].filter(key=>key in headers);removed.forEach(key=>delete headers[key]);
        const response=await route.fetch({headers,maxRedirects:0}),bytes=await response.body();
        assert.equal(response.status(),200,url);assert.ok(bytes.length,url+' empty source');
        assert.equal(sha(bytes),sha(fs.readFileSync(path.join(root,relativeFile))),url+' deployed-source SHA');
        const source=bytes.toString('utf8');assert.equal(source.split(hook.marker).length-1,1,'Unique reviewed observer marker');
        results.source_responses.push({url,status:200,bytes:bytes.length,sha256:sha(bytes),removed_conditional_headers:removed,observation_only:true});
        await route.fulfill({response,body:source.replace(hook.marker,hook.replacement)});
      } catch(error){results.route_errors.push(error.stack||String(error));await route.abort('failed');}
    }
    await page.route(/\/assets\/part-inspector\.js(?:\?[^#]*)?$/,route=>observe(route,'web/components/part-inspector.js',WIRING.inspector));
    await page.route(/\/assets\/scene-atlas\.js(?:\?[^#]*)?$/,route=>observe(route,'web/components/scene-atlas.js',WIRING.drawing));
    await page.route(/\/bom3d\.html(?:\?[^#]*)?$/,route=>observe(route,'web/pages/bom3d.html',WIRING.bom));
    await page.route(/\/rack3d\.html(?:\?[^#]*)?$/,route=>observe(route,'web/pages/rack3d.html',WIRING.rack));
    for(const name of ['part-dossier','scene-view','technical-atlas','campus-assembly','campus-exploded-assembly','server-assembly','rack-assembly','chip-package-assembly']) {
      const url=base+'/assets/'+name+'.js',response=await publicGet(url),bytes=await response.body();assert.ok(bytes.length);
      assert.equal(sha(bytes),sha(fs.readFileSync(path.join(root,'web/components',name+'.js'))),url+' public source SHA');
      results.source_responses.push({url,status:200,bytes:bytes.length,sha256:sha(bytes),observation_only:false});
    }
    async function settle() {
      await page.evaluate(async()=>{await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));});
      assert.deepEqual(results.route_errors,[]);
    }
    async function go(url,mode) {
      const target=new URL(url,base);assert.equal(target.origin,base);
      const response=await page.goto(target.href,{waitUntil:'domcontentloaded'});assert.ok(response,'Expected full document navigation');assert.equal(response.status(),200);
      await page.waitForFunction(()=>!!globalThis.__ta29);
      await page.locator('.drill').waitFor({state:'attached'});await settle();
      if(mode)assert.equal(await page.evaluate(()=>__ta29.readState().mode),mode);
    }
    async function controls() {
      const panel=page.locator('details[data-responsive-panel]');
      if(!await panel.evaluate(element=>element.open))await panel.locator(':scope > summary').click();
    }
    async function closeDossier() {await page.locator(WIRING.selectors.closeDossier).click();await settle();}
    async function mainState() {return page.evaluate(()=>({
      camera:__ta29.camera.position.toArray(),target:__ta29.controls.target.toArray(),...__ta29.readState()
    }));}
    function sameMain(before,after,label) {
      for(const key of ['camera','target'])after[key].forEach((number,index)=>assert.ok(Math.abs(number-before[key][index])<1e-7,label+' changed main '+key));
      for(const key of ['mode','stage','activeDomain','selectedInstance'])assert.equal(after[key],before[key],label+' changed main '+key);
    }
    async function save(name,mini=false) {
      const filename=name+'.png';await (mini?page.locator(WIRING.selectors.mini):page).screenshot({path:path.join(out,filename)});
      results.views.push({file:filename,kind:mini?'mini':'page',review:'pending_human_original_size_review'});
    }
    async function snapshotPreview() {return page.evaluate(()=>{
      const v=__ta29,o=v.inspector.observeForTest(),id=document.querySelector('#dossier').dataset.partId;
      const source=v.currentPartMeshes(id)||[],clones=o.group?.children.filter(mesh=>mesh.isMesh)||[];
      const rect=o.canvas.getBoundingClientRect(),box=document.querySelector('#inspSlot');
      const material=m=>({color:m.color?.getHex(),opacity:m.opacity,transparent:m.transparent,
        roughness:m.roughness,metalness:m.metalness,emissive:m.emissive?.getHex(),emissiveIntensity:m.emissiveIntensity,
        map:m.map?.uuid||null,normalMap:m.normalMap?.uuid||null,envMap:m.envMap?.uuid||null});
      const pairs=source.map((mesh,index)=>({geometry_borrowed:clones[index]?.geometry===mesh.geometry,
        material_independent:[].concat(clones[index]?.material||[]).every(m=>![].concat(v.baselineMaterialFor(mesh)||[]).includes(m)),
        baseline:[].concat(v.baselineMaterialFor(mesh)||[]).map(material),clone:[].concat(clones[index]?.material||[]).map(material)}));
      return {part:id,source_meshes:source.length,preview_meshes:clones.length,state:o.state,source_clone_pairs:pairs,
        canvas:{connected:o.canvas.isConnected,width:rect.width,height:rect.height,pixels:[o.canvas.width,o.canvas.height]},
        slot_visible:!!box && getComputedStyle(box).display!=='none',selection:v.readState().selectedInstance};
    });}
    async function assertPhysical(label,expectedPart,expectedId) {
      await page.locator(WIRING.selectors.mini).waitFor();await settle();
      const p=await snapshotPreview();assert.equal(p.part,expectedPart);assert.ok(p.source_meshes>0);
      assert.equal(p.preview_meshes,p.source_meshes);assert.equal(p.slot_visible,true);assert.equal(p.canvas.connected,true);
      assert.ok(p.canvas.width>0 && p.canvas.height>0);assert.equal(p.state.visible,true);
      if(expectedId)assert.equal(p.state.objectId,expectedId);
      assert.ok(p.source_clone_pairs.every(pair=>pair.geometry_borrowed && pair.material_independent));
      for(const pair of p.source_clone_pairs)assert.deepEqual(pair.clone,pair.baseline,'Baseline material rather than dim/heatmap presentation');
      results.previews.push({label,...p});return p;
    }
    async function boundsAndPixels(label) {
      const result=await page.evaluate(()=>{
        const v=__ta29;v.inspector.tick();const o=v.inspector.observeForTest();o.scene.updateMatrixWorld(true);o.camera.updateMatrixWorld(true);
        let count=0,maxX=0,maxY=0,minZ=1,maxZ=-1;
        o.group.traverseVisible(mesh=>{if(!mesh.isMesh)return;mesh.geometry.computeBoundingBox();const b=mesh.geometry.boundingBox;
          for(const x of[b.min.x,b.max.x])for(const y of[b.min.y,b.max.y])for(const z of[b.min.z,b.max.z]){
            const p=new v.THREE.Vector3(x,y,z).applyMatrix4(mesh.matrixWorld).project(o.camera);
            count++;maxX=Math.max(maxX,Math.abs(p.x));maxY=Math.max(maxY,Math.abs(p.y));minZ=Math.min(minZ,p.z);maxZ=Math.max(maxZ,p.z);
          }});
        const png=o.canvas.toDataURL('image/png'),rect=o.canvas.getBoundingClientRect();
        return {count,maxX,maxY,minZ,maxZ,aspect:o.camera.aspect,viewport:[rect.width,rect.height],pixels:[o.canvas.width,o.canvas.height],png};
      });
      assert.ok(result.count>0 && result.maxX<=1 && result.maxY<=1 && result.minZ>=-1 && result.maxZ<=1,label+' rotated geometry clipped');
      assert.ok(Math.abs(result.aspect-result.viewport[0]/result.viewport[1])<.005);assert.ok(result.png.length>100);
      // PNG saved for actual pixel inspection; the byte count does not certify appearance.
      fs.writeFileSync(path.join(out,label+'-actual-mini.png'),Buffer.from(result.png.split(',')[1],'base64'));
      delete result.png;results.gestures.push({label,...result,visual_review:'pending'});
    }
    async function exportSVG(selector,filename,expectedId,mini) {
      const before=await mainState(),pending=page.waitForEvent('download');await page.locator(selector).click();
      const download=await pending;assert.equal(await download.failure(),null);const destination=path.join(out,filename);
      await download.saveAs(destination);const bytes=fs.readFileSync(destination);
      const data=await page.evaluate(async source=>{
        const doc=new DOMParser().parseFromString(source,'image/svg+xml');assertSVG();
        function assertSVG(){if(doc.querySelector('parsererror')||!doc.querySelector('metadata'))throw Error('Invalid SVG export');}
        const metadata=JSON.parse(doc.querySelector('metadata').textContent),image=doc.querySelector('image'),probe=new Image();
        if(!image)throw Error('No actual rendered snapshot');probe.src=image.getAttribute('href');await probe.decode();
        const pixels=document.createElement('canvas');pixels.width=probe.width;pixels.height=probe.height;
        const context=pixels.getContext('2d');context.drawImage(probe,0,0);
        return {metadata,visible_text:[...doc.querySelectorAll('text')].map(text=>text.textContent).join(''),pixels:[probe.width,probe.height],
          paper:[...context.getImageData(0,0,1,1).data],
          selected_leaders:[...doc.querySelectorAll('[data-object-id]')].map(node=>node.getAttribute('data-object-id'))};
      },bytes.toString('utf8'));
      assert.equal(data.metadata.object_id,expectedId);
      if(mini)assert.ok(data.visible_text.includes(expectedId),'Visible independent-preview object identity');
      assert.ok(data.pixels[0]>0 && data.pixels[1]>0);assert.ok(data.metadata.caption && data.visible_text);
      assert.deepEqual(data.paper,[250,249,242,255]);assert.equal(data.metadata.style,'white-technical-atlas-v1');
      if(mini)assert.match(data.metadata.caption,/独立|预览/,'Mini snapshot identifies its own scope');
      sameMain(before,await mainState(),'export');
      results.exports.push({file:filename,sha256:sha(bytes),bytes:bytes.length,scope:mini?'independent_preview':'main_current_view',...data});
      await page.waitForTimeout(250);return data;
    }
    async function miniGestures(label) {
      const before=await mainState(),initial=await snapshotPreview(),canvas=page.locator(WIRING.selectors.mini);
      await canvas.scrollIntoViewIfNeeded();const rect=await canvas.boundingBox();assert.ok(rect);
      await page.mouse.move(rect.x+rect.width*.4,rect.y+rect.height*.4);await page.mouse.down();
      await page.mouse.move(rect.x+rect.width*.67,rect.y+rect.height*.58,{steps:12});await page.mouse.up();await settle();
      const dragged=await snapshotPreview();assert.notDeepEqual(dragged.state.rotation,initial.state.rotation);assert.equal(dragged.state.spin,false);
      sameMain(before,await mainState(),'mini drag');
      await page.locator(WIRING.selectors.fit).click();await settle();
      assert.deepEqual((await snapshotPreview()).state.rotation,dragged.state.rotation,'Explicit fit preserves current preview pose');
      await boundsAndPixels(label+'-dragged-fit');
      await page.locator(WIRING.selectors.spin).click();await settle();assert.equal((await snapshotPreview()).state.spin,true);
      await page.locator(WIRING.selectors.spin).click();await settle();assert.equal((await snapshotPreview()).state.spin,false);
      await page.locator(WIRING.selectors.enlarge).click();await page.locator(WIRING.selectors.enlargedHost).waitFor();await settle();
      const large=await snapshotPreview();assert.equal(large.state.objectId,initial.state.objectId);assert.equal(large.state.enlarged,true);
      sameMain(before,await mainState(),'independent enlargement');await page.locator(WIRING.selectors.fit).click();await settle();
      await boundsAndPixels(label+'-enlarged-fit');await save(label+'-enlarged');
      await exportSVG(WIRING.selectors.exportMini,label+'-own-preview.svg',initial.state.objectId,true);
      await page.keyboard.press('Escape');await settle();assert.equal((await snapshotPreview()).state.enlarged,false);
      sameMain(before,await mainState(),'modal Escape isolation');
      await page.locator(WIRING.selectors.enlarge).click();await settle();
      await page.locator(WIRING.selectors.shrink).click();await settle();assert.equal((await snapshotPreview()).state.enlarged,false);
      sameMain(before,await mainState(),'enlargement close');
      // Pointer cancellation must end a drag without moving the main camera.
      const small=await canvas.boundingBox();await page.mouse.move(small.x+small.width*.4,small.y+small.height*.4);await page.mouse.down();
      await canvas.dispatchEvent('pointercancel',{pointerId:1,bubbles:true});await page.mouse.up();
      const stopped=(await snapshotPreview()).state.rotation;
      await page.mouse.move(small.x+small.width*.7,small.y+small.height*.6);await settle();
      assert.deepEqual((await snapshotPreview()).state.rotation,stopped);sameMain(before,await mainState(),'pointer cancellation');
      results.gestures.push({label,drag_stopped_spin:true,independent_enlargement:true,main_unchanged:true,modal_escape_isolated:true,pointer_cancel:true});
    }
    // Candidate rays are computed from actual visible source meshes; selection is a
    // real DOM-reachable pointer gesture, not showDossier()/showRackObject() calls.
    async function pick(part,identity=null) {
      if(await page.locator('#dossier').isVisible())await closeDossier();await controls();await page.locator('#fit-view').click();await settle();
      if((await page.viewportSize()).width<=700) {
        const panel=page.locator('details[data-responsive-panel]');if(await panel.evaluate(element=>element.open))await panel.locator(':scope > summary').click();await settle();
      }
      const point=await page.evaluate(({part,identity})=>{
        const v=__ta29,rect=v.canvas.getBoundingClientRect(),ray=new v.THREE.Raycaster();
        v.camera.updateMatrixWorld(true);const visible=mesh=>{for(let n=mesh;n;n=n.parent)if(!n.visible)return false;return true;};
        for(let py=rect.top+12;py<rect.bottom-12;py+=5)for(let px=rect.left+12;px<rect.right-12;px+=5){
          if(document.elementFromPoint(px,py)!==v.canvas)continue;
          ray.setFromCamera(new v.THREE.Vector2((px-rect.left)/rect.width*2-1,-(py-rect.top)/rect.height*2+1),v.camera);
          const hit=ray.intersectObjects(v.pickables.filter(visible),false)[0]?.object;
          if(hit && hit.userData.part===part && (!identity||v.identityForMesh(hit)===identity))return{x:px,y:py,id:v.identityForMesh(hit)};
        }return null;
      },{part,identity});
      assert.ok(point,'No reachable actual surface for '+part+' '+identity);await page.mouse.move(point.x,point.y);await page.mouse.click(point.x,point.y);await settle();
      if(identity)assert.equal(await page.evaluate(()=>__ta29.readState().selectedInstance),identity);
      return point;
    }

    // Every mode gets an actual inventory; every declared previewable category is
    // checked once. Separate scopes prevent counts being mistaken for one device.
    for(const mode of MODES) {
      await go(mode.url,mode.mode);
      const inventory=await page.evaluate(()=>{
        const v=__ta29,parts=[...new Set(v.pickables.map(mesh=>mesh.userData.part))].sort();
        return {state:v.readState(),parts,pickables:v.pickables.length,unique:new Set(v.pickables).size,
          instances:v.campusAssembly?.instances.map(instance=>({id:instance.id,part:instance.part,position:instance.object.position.toArray(),home:instance.home.toArray()}))||[]};
      });
      assert.equal(inventory.pickables,inventory.unique);assert.ok(inventory.pickables>0);
      assert.deepEqual(inventory.parts,[...mode.parts].sort());
      if(mode.id.startsWith('campus')) {
        assert.equal(inventory.pickables,152);assert.equal(inventory.instances.length,32);
        assert.deepEqual(inventory.instances.map(instance=>instance.id).sort(),[...CAMPUS_IDS].sort());
        assert.deepEqual(inventory.instances.reduce((map,instance)=>(map[instance.part]=(map[instance.part]||0)+1,map),{}),CAMPUS_COUNTS);
        if(mode.id==='campus0')for(const instance of inventory.instances)assert.deepEqual(instance.position,instance.home);
      }
      results.inventory.push({mode:mode.id,...inventory});
      for(const part of mode.parts) {
        if(mode.id.startsWith('campus'))await go(mode.url+(mode.url.includes('?')?'&':'?')+'p='+encodeURIComponent(part),mode.mode);
        else if(mode.id==='server55')await go(mode.url+'&node='+encodeURIComponent('part:'+part),mode.mode);
        else if(part==='rack-frame') {await controls();await page.locator(mode.whole).click();}
        else await pick(part,mode.id==='chip90' && part==='gpu'?'package/logic-die':null);
        const p=await assertPhysical(mode.id+' '+part,part);
        // Aggregated server categories truthfully keep part identity; rack/chip
        // pointer-selected repeated groups require the implementation's stable ID.
        if(mode.id==='server55')assert.equal(p.state.objectId,'part:'+part);
        await save(mode.id+'-'+part,true);await closeDossier();
      }
      if(mode.whole) {await controls();await page.locator(mode.whole).click();}
      else await go(mode.url+'&node=part:server',mode.mode);
      const whole=await assertPhysical(mode.id+' whole',mode.id==='chip90'?'gpu':mode.id.startsWith('campus')?'shell':mode.id==='server55'?'server':'rack-frame',mode.wholeId);
      assert.equal(whole.preview_meshes,inventory.pickables);
      await miniGestures(mode.id+'-whole');await closeDossier();
    }
    // Exact repeated identities, never silently substitute the first instance.
    for(const sample of [
      {url:'/bom3d.html',mode:'campus',part:'transformer',id:'campus/transformer-2'},
      {url:'/rack3d.html?view=rack&x=0',mode:'rack',part:'server',id:'rack/compute-2'},
      {url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',part:'network-switch',id:'rack/switch-2'},
      {url:'/rack3d.html?view=server&x=55',mode:'server',part:'cpu',id:'server/cpu-2'},
      {url:'/rack3d.html?view=chip&x=90',mode:'chip',part:'hbm',id:'package/hbm-2'}]) {
      await go(sample.url,sample.mode);await pick(sample.part,sample.id);await assertPhysical('nonfirst '+sample.id,sample.part,sample.id);
      await exportSVG(WIRING.selectors.exportMini,sample.id.replaceAll('/','-')+'-preview.svg',sample.id,true);
      await exportSVG('#atlas-export',sample.id.replaceAll('/','-')+'-main.svg',sample.id,false);await closeDossier();
    }
    // Real manual main camera ownership survives mini operations and page resize.
    await go('/bom3d.html?d=power','campus');await pick('rack-frame');await assertPhysical('dimmed-domain baseline','rack-frame');
    const dimmedSelection=await page.evaluate(()=>{const v=__ta29,id=document.querySelector('#dossier').dataset.partId;return (v.currentPartMeshes(id)||[]).filter(mesh=>v.dimmed.has(mesh)).length;});
    assert.ok(dimmedSelection>0,'Actually preview source meshes dimmed by another active domain');
    const sourceBefore=await page.evaluate(()=>__ta29.pickables.map(mesh=>({id:mesh.uuid,material:[].concat(mesh.material).map(m=>m.uuid),
      values:[].concat(mesh.material).map(m=>({color:m.color?.getHex(),opacity:m.opacity,transparent:m.transparent}))})));
    await miniGestures('domain-material');
    assert.deepEqual(await page.evaluate(()=>__ta29.pickables.map(mesh=>({id:mesh.uuid,material:[].concat(mesh.material).map(m=>m.uuid),
      values:[].concat(mesh.material).map(m=>({color:m.color?.getHex(),opacity:m.opacity,transparent:m.transparent}))}))),sourceBefore);
    results.materials.push({domain:true,actually_dimmed_source_meshes:dimmedSelection,baseline_cloned:true,source_material_identity_unchanged:true});
    await closeDossier();await controls();
    const registryState=await page.evaluate(()=>__ta29.readState());
    if(registryState.productRegistryLoaded) {
      await page.locator('#covChip').click();await settle();assert.equal(await page.evaluate(()=>__ta29.readState().covOn),true);
      await pick('transformer');await assertPhysical('actual heatmap baseline','transformer');
      assert.ok(await page.evaluate(()=>__ta29.currentPartMeshes('transformer').some(mesh=>!!mesh.userData.covPrev)));
      results.materials.push({heatmap:'verified_actual',productRegistryLoaded:true,covOn:true,baseline_cloned:true});
      await closeDossier();await page.locator('#covChip').click();assert.equal(await page.evaluate(()=>__ta29.readState().covOn),false);
    } else {
      assert.equal(registryState.covOn,false);
      results.materials.push({heatmap:'not_verified',productRegistryLoaded:false,covOn:false,reason:'Anonymous restricted product registry unavailable; no authentication bypass or mocked coverage values'});
    }
    await go('/bom3d.html?d=power&p=transformer','campus');await closeDossier();await controls();
    const canvas=page.locator('#c'),rect=await canvas.boundingBox();await page.mouse.move(rect.x+rect.width*.6,rect.y+rect.height*.5);await page.mouse.down();
    await page.mouse.move(rect.x+rect.width*.7,rect.y+rect.height*.56,{steps:12});await page.mouse.up();
    await page.evaluate(()=>{__ta29.controls.enableDamping=false;__ta29.controls.update();});await settle();
    const owned=await mainState();await page.locator('#domainParts .pitem[data-part="transformer"]').click();
    await miniGestures('manual-main');await page.setViewportSize({width:1180,height:820});await settle();sameMain(owned,await mainState(),'manual resize');

    // Whole -> part -> software -> physical on one inspector/cache lifetime.
    await go('/bom3d.html?d=control','campus');await controls();await page.locator('#campus-whole-dossier').click();
    assert.equal((await assertPhysical('whole before software','shell','campus/whole')).preview_meshes,152);await closeDossier();
    await page.locator('#domainParts .pitem[data-part="dcim"]').click();await settle();
    const zero=await snapshotPreview();assert.equal(zero.part,'dcim');assert.equal(zero.source_meshes,0);assert.equal(zero.selection,null);
    assert.equal(zero.slot_visible,false);assert.equal(zero.canvas.connected,false);assert.equal(zero.state.visible,false);
    assert.equal(zero.preview_meshes,0,'TA29 deliberately clears old physical clones when a no-mesh software dossier opens');
    const software=await exportSVG('#atlas-export','software-main.svg','part:dcim',false);
    assert.match(software.metadata.caption,/软件/);assert.match(software.metadata.caption,/无物理模型/);
    assert.match(software.visible_text,/软件/);assert.match(software.visible_text,/无物理模型/);
    assert.ok(!software.selected_leaders.includes('part:dcim'));await closeDossier();
    results.previews.push({label:'TA29 whole152 to no-mesh clears cache; differs from TA28 retained-cache behavior',...zero});
    await pick('transformer','campus/transformer-2');await assertPhysical('physical after cleared software','transformer','campus/transformer-2');
    for(const [canonical,legacy] of RIGHTS) {
      await go('/bom3d.html?node='+encodeURIComponent('site:'+canonical),'campus');const right=await snapshotPreview();
      assert.equal(right.source_meshes,0);assert.equal(right.selection,null);assert.equal(right.slot_visible,false);assert.equal(right.canvas.connected,false);
      assert.equal(await page.evaluate(()=>__ta29.PART[document.querySelector('#dossier').dataset.partId].kind),'site_right');
      assert.equal(await page.evaluate(()=>__ta29.PART[document.querySelector('#dossier').dataset.partId].site_right_id),canonical);
      assert.ok((await page.locator('#dossier a').evaluateAll(links=>links.map(link=>link.getAttribute('href')))).some(href=>href.includes('node.html?id='+encodeURIComponent('site:'+canonical))));
      // Retain the existing MAIN part-ID metadata; site identity is canonical in
      // research links. Rights have no own physical preview/export.
      await exportSVG('#atlas-export','site-'+canonical+'-main.svg','part:'+legacy,false);
    }
    // Width/theme pixel captures, reopened identity/orientation and bounded corpus
    // use the same document so an accidental context-per-show leak is observable.
    await go('/bom3d.html?p=transformer','campus');
    for(const width of [1280,390])for(const theme of ['light','dark']) {
      await page.setViewportSize({width,height:width===390?844:900});await page.locator('#ui-appearance').selectOption(theme);await settle();
      await miniGestures('preview-'+width+'-'+theme);await save('preview-'+width+'-'+theme,true);
      const before=await snapshotPreview();await closeDossier();await pick('transformer',before.state.objectId);const reopened=await assertPhysical('reopened '+width+' '+theme,'transformer');
      assert.equal(reopened.state.objectId,before.state.objectId);assert.equal(reopened.state.spin,false,'Reduced motion restored');
      assert.deepEqual(reopened.state.rotation,{x:.25,y:.25},'Reopen restores authored orientation');
    }
    await page.setViewportSize({width:1280,height:900});await page.locator('#ui-appearance').selectOption('light');await settle();
    // Explicit campus view keeps the delivery template/nonphysical category out of
    // old legacy hardware routing. No invented preview or geometry is permitted.
    await go('/bom3d.html?view=campus&p=modular-dc','campus');
    const template=await snapshotPreview();assert.equal(template.source_meshes,0);assert.equal(template.preview_meshes,0);
    assert.equal(template.slot_visible,false);assert.equal(template.selection,null);assert.match(await page.locator('#dossier').textContent(),/模板|配置基型/);
    results.previews.push({label:'modular delivery template stays nonphysical',...template});

    // A narrow old detailed scene uses the same preview component without claiming
    // reacceptance of all legacy/OEM/adopted-model geometry or authenticated data.
    await go('/bom3d.html?view=legacy&x=45&p=server','legacy-campus');
    await assertPhysical('retained legacy server category','server','part:server');
    assert.equal(await page.locator('.facility-domain-plate').count(),0);
    await miniGestures('legacy-server-smoke');await closeDossier();

    // Stage changes preserve a user-owned main camera. A dossier reopened at the
    // new stage must rebuild from current world transforms rather than stale clones.
    for(const sample of [
      {url:'/bom3d.html?view=exploded&x=70',mode:'campus-layered',part:'transformer',id:'campus/transformer-2'},
      {url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',part:'network-switch',id:'rack/switch-2'},
      {url:'/rack3d.html?view=server&x=55',mode:'server',part:'cpu',id:'server/cpu-2'},
      {url:'/rack3d.html?view=chip&x=90',mode:'chip',part:'hbm',id:'package/hbm-2'}]) {
      await go(sample.url,sample.mode);await pick(sample.part,sample.id);
      for(const stage of [0,100]) {
        await closeDossier();await controls();
        const main=await page.locator('#c').boundingBox();await page.mouse.move(main.x+main.width*.65,main.y+main.height*.4);await page.mouse.down();
        await page.mouse.move(main.x+main.width*.7,main.y+main.height*.45,{steps:8});await page.mouse.up();
        await page.evaluate(()=>{__ta29.controls.enableDamping=false;__ta29.controls.update();});await settle();const manual=await mainState();
        await page.locator('#explode').evaluate((input,value)=>{input.value=String(value);input.dispatchEvent(new Event('input',{bubbles:true}));},stage);await settle();
        assert.equal(await page.evaluate(()=>__ta29.readState().stage),stage);
        const afterStage=await mainState();for(const key of ['camera','target'])afterStage[key].forEach((number,index)=>assert.ok(Math.abs(number-manual[key][index])<1e-7,'Stage changed manually owned main camera'));
        await pick(sample.part,sample.id);await assertPhysical(sample.mode+' stage '+stage,sample.part,sample.id);
        const matrices=await page.evaluate(()=>{
          const v=__ta29,o=v.inspector.observeForTest(),id=document.querySelector('#dossier').dataset.partId;
          const source=v.currentPartMeshes(id);return source.map((mesh,index)=>{
            mesh.updateWorldMatrix(true,false);const clone=o.group.children[index];
            // Root centering is separate; each clone retains its own source matrix.
            return {source:mesh.matrixWorld.toArray(),clone:clone.matrix.toArray()};
          });
        });
        for(const pair of matrices)pair.clone.forEach((number,index)=>assert.ok(Math.abs(number-pair.source[index])<1e-7,'Reopen uses current source transform'));
        await save(sample.mode+'-stage-'+stage,true);
      }
      await closeDossier();
    }

    // Download the already adopted static artwork through its real dossier links.
    // Accepted receipt SHA and reviewed-source bytes must agree before public use.
    for(const item of [
      {figure:'TA-11',url:'/rack3d.html?view=server&x=55&node=part:server',mode:'server'},
      {figure:'TA-13',url:'/rack3d.html?view=rack&x=0&node=part:rack-frame',mode:'rack'}]) {
      const acceptance=JSON.parse(fs.readFileSync(path.join(root,'docs/design/technical-atlas',item.figure,'acceptance-v1.json')));
      await go(item.url,item.mode);const art=page.locator('#dossier .technical-atlas[data-figure="'+item.figure+'"]');
      await art.waitFor();await art.locator('img').evaluate(image=>image.decode());
      for(const name of ['下载标注图','下载无字底图']) {
        const link=art.getByRole('link',{name,exact:true}),href=await link.getAttribute('href');
        const target=new URL(href,base);assert.equal(target.origin,base);
        const artifact=acceptance.artifacts.find(record=>record.file==='web'+target.pathname);assert.ok(artifact);
        const local=fs.readFileSync(path.join(root,artifact.file));assert.equal(local.length,artifact.bytes);assert.equal(sha(local),artifact.sha256);
        const response=await publicGet(target.href),publicBytes=await response.body();assert.equal(publicBytes.length,artifact.bytes);assert.equal(sha(publicBytes),artifact.sha256);
        const pending=page.waitForEvent('download');await link.click();const download=await pending;assert.equal(await download.failure(),null);
        assert.equal(download.suggestedFilename(),path.basename(artifact.file));const destination=path.join(out,download.suggestedFilename());await download.saveAs(destination);
        const actual=fs.readFileSync(destination);assert.equal(actual.length,artifact.bytes);assert.equal(sha(actual),artifact.sha256);
        results.static_downloads.push({figure:item.figure,name,url:target.href,file:download.suggestedFilename(),bytes:actual.length,sha256:sha(actual),adopted_original_unchanged:true});
        await page.waitForTimeout(250);
      }
      await closeDossier();
    }

    // Disposal listeners observe real resources. No synthetic material/geometry
    // fixture replaces actual selected meshes or bypasses public source identity.
    async function beginResourceProbe() {
      await page.evaluate(()=>{
        const v=__ta29,o=v.inspector.observeForTest();
        const probe={renderer:o.renderer,canvas:o.canvas,owned:new Map(),borrowed:new Map(),rendererDisposes:0,renders:0,viewportDisposes:0};
        const add=(map,resource,kind)=>{if(!resource||map.has(resource))return;const record={kind,disposes:0};map.set(resource,record);resource.addEventListener('dispose',()=>record.disposes++);};
        for(const mesh of v.pickables) {
          add(probe.borrowed,mesh.geometry,'sourceGeometry');
          for(const material of new Set([].concat(mesh.material||[],v.baselineMaterialFor(mesh)||[]))) {
            add(probe.borrowed,material,'sourceMaterial');for(const value of Object.values(material))if(value?.isTexture)add(probe.borrowed,value,'sourceTexture');
          }
        }
        if(v.scene.environment?.isTexture)add(probe.borrowed,v.scene.environment,'sourceTexture');
        const dispose=o.renderer.dispose.bind(o.renderer);o.renderer.dispose=(...args)=>{probe.rendererDisposes++;return dispose(...args);};
        const render=o.renderer.render.bind(o.renderer);o.renderer.render=(...args)=>{probe.renders++;return render(...args);};
        const viewportDispose=o.viewport.dispose.bind(o.viewport);o.viewport.dispose=(...args)=>{probe.viewportDisposes++;return viewportDispose(...args);};
        probe.watch=()=>{
          const now=v.inspector.observeForTest();
          if(now.renderer!==probe.renderer)throw Error('Renderer recreated within one inspector lifetime');
          for(const mesh of now.group?.children||[])for(const material of [].concat(mesh.material||[]))add(probe.owned,material,'cloneMaterial');
          const owned=now.drawing?.ownedForTest();
          for(const geometry of owned?.geometries||[])add(probe.owned,geometry,'derivedEdgeGeometry');
          for(const material of owned?.materials||[])add(probe.owned,material,'drawingMaterial');
          for(const texture of owned?.textures||[])add(probe.owned,texture,'derivedLabelTexture');
          const stats={live:{},seen:{},disposed:{}};
          for(const record of probe.owned.values()){
            if(record.disposes>1)throw Error('Owned resource disposed more than once');
            stats.seen[record.kind]=(stats.seen[record.kind]||0)+1;
            stats.disposed[record.kind]=(stats.disposed[record.kind]||0)+record.disposes;
            if(!record.disposes)stats.live[record.kind]=(stats.live[record.kind]||0)+1;
          }
          if([...probe.borrowed.values()].some(record=>record.disposes))throw Error('Preview released borrowed resource');
          const cloneMaterials=new Set((now.group?.children||[]).flatMap(mesh=>[].concat(mesh.material||[]))).size;
          const edges=owned?.geometries.length||0;
          if((stats.live.cloneMaterial||0)!==cloneMaterials||(stats.live.derivedEdgeGeometry||0)!==edges)throw Error('Replaced preview resources retained');
          if((stats.live.drawingMaterial||0)!==(owned?.materials.length||0))throw Error('Drawing material retained after replacement');
          return stats;
        };
        globalThis.__ta29Resources=probe;probe.watch();
      });
    }
    async function resourceCheckpoint(label) {
      const stats=await page.evaluate(()=>__ta29Resources.watch());results.resources.push({label,...stats});
    }
    for(const sample of [
      {url:'/bom3d.html?d=control',mode:'campus',whole:'#campus-whole-dossier',part:'transformer',id:'campus/transformer-2',zero:true},
      {url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',whole:'#rack-overview-dossier',part:'network-switch',id:'rack/switch-2',zero:false}]) {
      await go(sample.url,sample.mode);await controls();await page.locator(sample.whole).click();await assertPhysical('resource start',sample.mode==='campus'?'shell':'rack-frame');
      await beginResourceProbe();
      for(let cycle=0;cycle<3;cycle++) {
        await pick(sample.part,sample.id);await assertPhysical('resource corpus part '+cycle,sample.part,sample.id);await resourceCheckpoint(sample.mode+' part '+cycle);
        await closeDossier();await controls();await page.locator(sample.whole).click();await assertPhysical('resource corpus whole '+cycle,sample.mode==='campus'?'shell':'rack-frame');await resourceCheckpoint(sample.mode+' whole '+cycle);
        if(sample.zero) {
          await closeDossier();await page.locator('#domainParts .pitem[data-part="dcim"]').click();await settle();
          assert.equal((await snapshotPreview()).preview_meshes,0);await resourceCheckpoint('no-mesh clear '+cycle);
        }
      }
      // End on a physical preview with its dialog created, so closure resources
      // include active clone materials, edges, controls, viewport and dialog.
      await pick(sample.part,sample.id);await assertPhysical('resource final part',sample.part,sample.id);
      await page.locator(WIRING.selectors.enlarge).click();await settle();await resourceCheckpoint('expanded before dispose');
      const released=await page.evaluate(async()=>{
        const v=__ta29,p=__ta29Resources,o=v.inspector.observeForTest();p.watch();
        let writes=0;const mutation=new MutationObserver(records=>writes+=records.length);mutation.observe(p.canvas,{attributes:true,childList:true,subtree:true});
        v.inspector.dispose();v.inspector.dispose();await Promise.resolve();mutation.takeRecords();writes=0;
        const renders=p.renders;v.inspector.tick();window.dispatchEvent(new Event('resize'));
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        const after=v.inspector.observeForTest(),owned=[...p.owned.values()],borrowed=[...p.borrowed.values()];
        const result={rendererDisposes:p.rendererDisposes,viewportDisposes:p.viewportDisposes,rendersAfter:p.renders-renders,canvasWritesAfter:writes,
          owned:owned.reduce((summary,record)=>{const item=summary[record.kind]||={count:0,disposes:0};item.count++;item.disposes+=record.disposes;return summary;},{}),
          borrowed:borrowed.reduce((summary,record)=>(summary[record.kind]=(summary[record.kind]||0)+record.disposes,summary),{}),
          ownedExactlyOnce:owned.every(record=>record.disposes===1),borrowedUntouched:borrowed.every(record=>record.disposes===0),
          connected:p.canvas.isConnected,remainingClones:after.group?.children.length||0,disposed:after.state.disposed,
          dialogCount:document.querySelectorAll('.part-inspector-dialog').length,controlsCount:document.querySelectorAll('.part-inspector-controls').length};
        mutation.disconnect();return result;
      });
      assert.equal(released.rendererDisposes,1);assert.equal(released.viewportDisposes,1);assert.equal(released.ownedExactlyOnce,true);assert.equal(released.borrowedUntouched,true);
      assert.equal(released.rendersAfter,0);assert.equal(released.canvasWritesAfter,0);assert.equal(released.connected,false);assert.equal(released.remainingClones,0);
      assert.equal(released.disposed,true);assert.equal(released.dialogCount,0);assert.equal(released.controlsCount,0);
      results.resources.push({label:sample.mode+' inspector dispose twice before page owner',...released});
      // A persisted pagehide must leave the listener available for the later real
      // exit. This tests the changed lifecycle branch; it is synthetic BFCache
      // event coverage, not a claim that a real browser history entry was cached.
      const lifecycle=await page.evaluate(async()=>{
        const v=__ta29,p=__ta29Resources;let renders=0;const render=v.composer.render.bind(v.composer);v.composer.render=(...args)=>{renders++;return render(...args);};
        const frames=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));await frames();
        const persisted={pageDisposed:v.readState().pageDisposed,renders};
        window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false}));v.disposePage();v.disposePage();const at=renders;await frames();
        const source=[...p.borrowed.values()];return {persisted,nonpersisted:{pageDisposed:v.readState().pageDisposed,rendersAfter:renders-at,
          inspectorRendererDisposes:p.rendererDisposes,sourceGeometry:source.filter(record=>record.kind==='sourceGeometry').map(record=>record.disposes),
          sourceMaterial:source.filter(record=>record.kind==='sourceMaterial').map(record=>record.disposes)}};
      });
      assert.equal(lifecycle.persisted.pageDisposed,false);assert.ok(lifecycle.persisted.renders>0);
      assert.equal(lifecycle.nonpersisted.pageDisposed,true);assert.equal(lifecycle.nonpersisted.rendersAfter,0);assert.equal(lifecycle.nonpersisted.inspectorRendererDisposes,1);
      assert.ok(lifecycle.nonpersisted.sourceGeometry.length>0 && lifecycle.nonpersisted.sourceGeometry.every(count=>count===1));
      assert.ok(lifecycle.nonpersisted.sourceMaterial.length>0 && lifecycle.nonpersisted.sourceMaterial.every(count=>count===1));
      results.resources.push({label:sample.mode+' synthetic persisted then nonpersisted pagehide, factory owner once',...lifecycle});
    }
    assert.equal(results.inventory.length,MODES.length);assert.equal(results.static_downloads.length,4);
    assert.ok(results.previews.some(preview=>preview.label.includes('TA29 whole152')));
    assert.deepEqual(results.errors,[]);assert.deepEqual(results.route_errors,[]);assert.deepEqual(results.resource_failures,[]);
    results.stage='PASS_AUTOMATED_PUBLIC_OBSERVATION';
    console.log('TA29 public preview matrix/independent controls/ownSVG/identity/material/resources PASS; visual review and restricted heatmap status recorded separately');
  } catch(error) {results.stage='FAIL';results.failure=error.stack||String(error);throw error;}
  finally {
    results.finished_at=new Date().toISOString();
    if(fs.existsSync(out))fs.writeFileSync(path.join(out,'ta29-shared-preview-results.json'),JSON.stringify(results,null,2)+'\n');
    if(browser)await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
