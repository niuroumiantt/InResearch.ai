/* TA29 narrow actual-public whole auto-spin supplement. Do not execute until owner review.
 * Headed Chromium only, exact permitted public origin, no local fallback/product substitute.
 * This source creation/static review does not prove any runtime or visual result.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const base='https://inresearch.ai',sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(process.env.UI_BASE_URL,base,'Strict actual public origin required');
const root=process.env.TA29_SOURCE_ROOT;assert.ok(root && path.isAbsolute(root),'Explicit reviewed TA29_SOURCE_ROOT required');
const out=process.env.REVIEW_SCREENSHOTS||'/private/tmp/ta29-whole-spin-public-'+Date.now();assert.ok(path.isAbsolute(out));
// Exact read-only observation wiring reused from owner-reviewed public-v2.
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
const cases=[
  {id:'campus0',url:'/bom3d.html',mode:'campus',whole:'#campus-whole-dossier',objectId:'campus/whole'},
  {id:'campus70',url:'/bom3d.html?view=exploded&x=70',mode:'campus-layered',whole:'#campus-whole-dossier',objectId:'campus/whole'},
  {id:'rack35',url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',whole:'#rack-overview-dossier',objectId:'rack/whole'}
];
const results={figure:'TA-29',kind:'whole_auto_spin_supplement',status:'NOT_EXECUTED',base,
  source_root:root,local_fallback:false,poll_interval_ms:500,minimum_yaw_delta:2*Math.PI,
  sources:[],cases:[],errors:[],route_errors:[],resource_failures:[],
  visual_review:'pending_actual_original_size_image_review',research_content:'not_verified'};
let browser;
(async()=>{
  try {
    fs.mkdirSync(out,{recursive:true});
    const {chromium}=require('playwright');
    browser=await chromium.launch({headless:false});
    const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce',serviceWorkers:'block'});
    await context.route('**/*',async route=>{
      try {assert.equal(new URL(route.request().url()).origin,base);await route.continue();}
      catch(error){results.route_errors.push(error.message);await route.abort('blockedbyclient');}
    });
    const page=await context.newPage();
    page.on('pageerror',error=>results.errors.push(error.message));
    page.on('response',response=>{if(new URL(response.url()).pathname.startsWith('/assets/') && response.status()>=400)
      results.resource_failures.push({url:response.url(),status:response.status()});});
    async function observe(route,relativeFile,hook) {
      try {
        const url=route.request().url();assert.equal(new URL(url).origin,base);
        const headers={...route.request().headers()};
        const removed=['if-none-match','if-modified-since'].filter(key=>key in headers);removed.forEach(key=>delete headers[key]);
        const response=await route.fetch({headers,maxRedirects:0}),bytes=await response.body();
        assert.equal(response.status(),200,url);assert.ok(bytes.length,'Nonempty actual public source');
        assert.equal(sha(bytes),sha(fs.readFileSync(path.join(root,relativeFile))),'Executed public source identity');
        const source=bytes.toString('utf8');assert.equal(source.split(hook.marker).length-1,1);
        results.sources.push({url,status:200,bytes:bytes.length,sha256:sha(bytes),removed_conditional_headers:removed,observation_only:true});
        await route.fulfill({response,body:source.replace(hook.marker,hook.replacement)});
      } catch(error){results.route_errors.push(error.stack||String(error));await route.abort('failed');}
    }
    await page.route(/\/assets\/part-inspector\.js(?:\?[^#]*)?$/,route=>observe(route,'web/components/part-inspector.js',WIRING.inspector));
    await page.route(/\/bom3d\.html(?:\?[^#]*)?$/,route=>observe(route,'web/pages/bom3d.html',WIRING.bom));
    await page.route(/\/rack3d\.html(?:\?[^#]*)?$/,route=>observe(route,'web/pages/rack3d.html',WIRING.rack));
    async function settle() {
      await page.evaluate(async()=>{await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));});
      assert.deepEqual(results.route_errors,[]);
    }
    async function sample() {return page.evaluate(()=>{
      const v=__ta29,o=v.inspector.observeForTest();
      if(!o.scene||!o.group||!o.camera)throw Error('Actual preview references unavailable');
      o.scene.updateMatrixWorld(true);o.camera.updateMatrixWorld(true);
      let count=0,maxX=0,maxY=0,minZ=Infinity,maxZ=-Infinity,finite=true;
      o.group.traverseVisible(mesh=>{
        if(!mesh.isMesh)return;mesh.geometry.computeBoundingBox();const box=mesh.geometry.boundingBox;
        for(const x of[box.min.x,box.max.x])for(const y of[box.min.y,box.max.y])for(const z of[box.min.z,box.max.z]){
          const point=new v.THREE.Vector3(x,y,z).applyMatrix4(mesh.matrixWorld).project(o.camera);
          finite&&=[point.x,point.y,point.z].every(Number.isFinite);count++;
          maxX=Math.max(maxX,Math.abs(point.x));maxY=Math.max(maxY,Math.abs(point.y));minZ=Math.min(minZ,point.z);maxZ=Math.max(maxZ,point.z);
        }
      });
      const rect=o.canvas.getBoundingClientRect(),live=v.readState();
      return {at_ms:performance.now(),objectId:o.state.objectId,spin:o.state.spin,expanded:o.state.enlarged,
        rotation:{...o.state.rotation},pivot_y:o.pivot.rotation.y,clones:o.group.children.length,
        bounds:{count,finite,maxX,maxY,minZ,maxZ,inside:finite&&count>0&&maxX<=1&&maxY<=1&&minZ>=-1&&maxZ<=1},
        preview:{position:o.camera.position.toArray(),aspect:o.camera.aspect,fov:o.camera.fov,viewport:[rect.width,rect.height],pixels:[o.canvas.width,o.canvas.height],connected:o.canvas.isConnected},
        main:{position:v.camera.position.toArray(),target:v.controls.target.toArray(),quaternion:v.camera.quaternion.toArray(),fov:v.camera.fov,zoom:v.camera.zoom,
          mode:live.mode,stage:live.stage,activeDomain:live.activeDomain,selectedInstance:live.selectedInstance}};
    });}
    function mainDifference(before,after) {
      let delta=0;for(const key of ['position','target','quaternion'])after[key].forEach((value,index)=>delta=Math.max(delta,Math.abs(value-before[key][index])));
      const sameState=['fov','zoom','mode','stage','activeDomain','selectedInstance'].every(key=>after[key]===before[key]);
      return {max_delta:delta,same_state:sameState,unchanged:delta<1e-7&&sameState};
    }
    function persist() {fs.writeFileSync(path.join(out,'ta29-whole-spin-results.json'),JSON.stringify(results,null,2)+'\n');}
    results.status='RUNNING';
    for(const entry of cases) {
      const record={id:entry.id,url:base+entry.url,objectId:entry.objectId,samples:[],clipped_samples:0,main_changed_samples:0,status:'RUNNING'};
      results.cases.push(record);persist();
      const response=await page.goto(record.url,{waitUntil:'domcontentloaded'});assert.ok(response);assert.equal(response.status(),200);
      await page.waitForFunction(()=>!!globalThis.__ta29);await page.locator('.drill').waitFor({state:'attached'});await settle();
      assert.equal(await page.evaluate(()=>__ta29.readState().mode),entry.mode);
      const panel=page.locator('details[data-responsive-panel]');if(!await panel.evaluate(element=>element.open))await panel.locator(':scope > summary').click();
      await page.locator(entry.whole).click();await page.locator('#inspSlot canvas').waitFor();await settle();
      const whole=await sample();assert.equal(whole.objectId,entry.objectId);assert.ok(whole.clones>0);
      assert.equal(whole.clones,await page.evaluate(()=>__ta29.pickables.length),'Actual whole preview includes all source pickables');
      assert.equal(whole.spin,false,'Reduced motion gives an explicit stopped starting state');
      await page.locator('[data-preview-action="expand"]').click();await page.locator('.part-inspector-dialog[open]').waitFor();
      await page.locator('[data-preview-action="fit"]').click();await settle();
      const fitted=await sample();assert.equal(fitted.objectId,entry.objectId);assert.equal(fitted.expanded,true);assert.equal(fitted.spin,false);
      assert.equal(mainDifference(whole.main,fitted.main).unchanged,true,'Enlarge/fit preserves actual main camera');
      record.initial=fitted;record.before_spin_image=entry.id+'-expanded-fitted.png';await page.screenshot({path:path.join(out,record.before_spin_image)});
      await page.locator('[data-preview-action="spin"]').click();assert.equal(await page.locator('[data-preview-action="spin"]').getAttribute('aria-pressed'),'true');
      const start=await sample();assert.equal(start.spin,true);record.start=start;
      const deadline=Date.now()+180000;let previousYaw=start.rotation.y,finished=false;
      while(Date.now()<deadline) {
        await page.waitForTimeout(500);const current=await sample();
        assert.equal(current.spin,true,'Actual UI-started auto-spin must continue');assert.equal(current.objectId,entry.objectId);assert.equal(current.expanded,true);
        assert.ok(current.rotation.y>=previousYaw,'Actual auto-spin yaw is monotonic');assert.ok(Math.abs(current.rotation.y-current.pivot_y)<1e-7,'Actual state yaw applied to preview pivot');
        previousYaw=current.rotation.y;current.yaw_delta=current.rotation.y-start.rotation.y;current.main_comparison=mainDifference(fitted.main,current.main);
        assert.ok(current.preview.connected && current.preview.viewport.every(value=>value>0));
        assert.ok(Math.abs(current.preview.aspect-current.preview.viewport[0]/current.preview.viewport[1])<.005);
        record.samples.push(current);if(!current.bounds.inside)record.clipped_samples++;if(!current.main_comparison.unchanged)record.main_changed_samples++;
        // Preserve the complete trace even if an earlier yaw clips; finish the
        // actual full turn before evaluating the bounded-yaw acceptance result.
        persist();
        if(current.yaw_delta>=2*Math.PI){finished=true;break;}
      }
      await page.locator('[data-preview-action="spin"]').click();await settle();const paused=await sample();assert.equal(paused.spin,false);
      record.paused=paused;record.actual_yaw_delta=paused.rotation.y-start.rotation.y;
      record.after_spin_image=entry.id+'-expanded-after-full-turn.png';await page.screenshot({path:path.join(out,record.after_spin_image)});
      record.finished_full_turn=finished&&record.actual_yaw_delta>=2*Math.PI;
      record.status=record.finished_full_turn && fitted.bounds.inside && paused.bounds.inside && record.clipped_samples===0 && record.main_changed_samples===0 && mainDifference(fitted.main,paused.main).unchanged?'PASS':'FAIL';
      persist();
      await page.getByRole('button',{name:'关闭放大预览',exact:true}).click();await settle();
    }
    assert.equal(results.cases.length,3);assert.ok(results.cases.every(record=>record.status==='PASS'),'Full-yaw bounds/main preservation failed; see recorded trace');
    assert.deepEqual(results.errors,[]);assert.deepEqual(results.route_errors,[]);assert.deepEqual(results.resource_failures,[]);
    results.status='PASS_AUTOMATED_FULL_YAW_SAMPLES';persist();
    console.log('TA29 whole auto-spin public supplement: campus0/campus70/rack35 actual >=2pi, 500ms bounds/main snapshots PASS; original-size images require review');
  } catch(error) {results.status='FAIL';results.failure=error.stack||String(error);throw error;}
  finally {results.finished_at=new Date().toISOString();if(fs.existsSync(out))fs.writeFileSync(path.join(out,'ta29-whole-spin-results.json'),JSON.stringify(results,null,2)+'\n');if(browser)await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
