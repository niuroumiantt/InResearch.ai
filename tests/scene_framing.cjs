/* Actual geometry must fit the measured viewport; user intent owns the camera. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {writeFileSync}=require('node:fs');
function sameCamera(actual,expected){for(const key of ['position','target'])actual[key].forEach((v,i)=>assert.ok(Math.abs(v-expected[key][i])<1e-8,'camera ownership changed '+key));}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:process.env.CI?.5:1,reducedMotion:'reduce'});
  const errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route(/\/assets\/part-inspector\.js(?:\?[^#]*)?$/,async r=>{
   const res=await r.fetch(),source=await res.text();
   const body=source.replace('return {canvas: iCv,','return {viewForTest:()=>({camera:iCam,canvas:iCv,objects:[iGroup]}), canvas: iCv,');
   assert.notEqual(body,source,'inspector observation fixture must match the current implementation');
   await r.fulfill({response:res,body});
  });
  await page.route(/\/(bom3d|rack3d)\.html/,async r=>{
   const res=await r.fetch(),source=await res.text();
   const body=source.replace('</script>\n</body>','globalThis.__framing={scene,camera,controls,canvas,sceneView,framingObjects,pickables,sceneModels,inspector,showDossier,PART};\n</script>\n</body>');
   assert.notEqual(body,source);await r.fulfill({response:res,body});
  });
  await page.route('**/compare.html',async r=>{
   const res=await r.fetch(),source=await res.text();
   const body=source.replace('  previews.push(', '  globalThis.__compareView={camera:cam,canvas:cv,objects:[pivot],pivot};\n  previews.push(');
   assert.notEqual(body,source);await r.fulfill({response:res,body});
  });
  async function check(view,label,headers=false) {
   const result=await page.evaluate(async({view,headers})=>{
    const THREE=await import('three');
    const data=view==='main'?{...__framing,objects:__framing.framingObjects()}:view==='inspector'?__framing.inspector.viewForTest():__compareView;
    const {camera,canvas,objects}=data;camera.updateMatrixWorld();
    let count=0,maxX=0,maxY=0,minZ=1,maxZ=-1,farthest=0;
    for(const root of objects){
     let visible=true;for(let p=root;p;p=p.parent)visible&&=p.visible;if(!visible)continue;
     root.updateWorldMatrix(true,true);
     root.traverseVisible(o=>{
      if(!o.isMesh)return;if(!o.geometry.boundingBox)o.geometry.computeBoundingBox();
      const {min,max}=o.geometry.boundingBox;
      for(const x of [min.x,max.x])for(const y of [min.y,max.y])for(const z of [min.z,max.z]){
       const v=new THREE.Vector3(x,y,z).applyMatrix4(o.matrixWorld);farthest=Math.max(farthest,v.distanceTo(camera.position));v.project(camera);
       count++;maxX=Math.max(maxX,Math.abs(v.x));maxY=Math.max(maxY,Math.abs(v.y));minZ=Math.min(minZ,v.z);maxZ=Math.max(maxZ,v.z);
      }
     });
    }
    const rect=canvas.getBoundingClientRect(),headerBottom=headers?Math.max(...[document.querySelector('.topbar'),document.querySelector('#ui-skinbar')].map(e=>e.getBoundingClientRect().bottom)):0;
    const fog = view==='main'?__framing.scene.fog:null;
    return {farthest,fog: fog?{near:fog.near,far:fog.far,distance:camera.position.distanceTo(__framing.controls.target)}:null,count,maxX,maxY,minZ,maxZ,aspect:camera.aspect,width:rect.width,height:rect.height,top:rect.top,headerBottom};
   },{view,headers});
   assert.ok(result.count>0 && result.maxX<=1 && result.maxY<=1 && result.minZ>=-1 && result.maxZ<=1,label+' clipped '+JSON.stringify(result));
   assert.ok(Math.abs(result.aspect-result.width/result.height)<.005,label+' camera aspect mismatch');
   if(headers)assert.ok(result.top>=result.headerBottom-.5,label+' canvas covered by header');
   if(result.fog)assert.ok(result.fog.far>result.farthest,'model geometry fully hidden by fog');
   results.push({label,...result});
  }
  async function screenshot(name){if(process.env.REVIEW_SCREENSHOTS)await page.screenshot({path:process.env.REVIEW_SCREENSHOTS+'/'+name+'.png'});}
  for(const scene of ['bom3d','rack3d']){
   console.log('Framing: '+scene+' default, resize, explicit fit and inspector');
   await page.setViewportSize({width:1280,height:900});
   // The optional model contract belongs to the retained legacy rack scene;
   // TA13's default procedural overview deliberately rejects replacement.
   await page.goto(process.env.UI_BASE_URL+'/'+scene+'.html'+(scene==='rack3d'?'?view=legacy&x=35':''),{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!globalThis.__framing);
   await page.locator('.rg-scene-model-status[data-state=ready]').waitFor({state:'attached'});
   assert.ok((await page.locator('#fit-view').boundingBox()).height>=36,'fit button needs a usable touch target');
   if(scene==='bom3d')assert.ok(await page.evaluate(()=>__framing.pickables.some(m=>m.userData.part==='land') && __framing.framingObjects().every(m=>m.userData.part!=='land')),'site remains selectable while buildings/devices own framing');
   await check('main',scene+' default',true);await screenshot(scene+'-desktop');
   // Changing layout while initial automatic fit owns the view must still fit.
   await page.setViewportSize({width:360,height:800});
   await page.waitForFunction(()=>__framing.canvas.getBoundingClientRect().width===360 && __framing.camera.aspect<1);
   await check('main',scene+' phone',true);await screenshot(scene+'-phone');
   await page.setViewportSize({width:1280,height:900});
   await page.locator('#play').click();await page.locator('#fit-view').click();
   await check('main',scene+' expanded',true);
   // User pan survives resizing and a late optional-model completion.
   await page.evaluate(()=>{const v=__framing;v.controls.autoRotate=false;v.sceneView.takeControl();v.camera.position.x+=3;v.controls.target.x+=3;globalThis.__ownedCamera={position:v.camera.position.toArray(),target:v.controls.target.toArray()};});
   await page.setViewportSize({width:900,height:800});
   await page.route('**/api/model-assets*',r=>r.fulfill({status:503,json:{error:'framing failure fixture'}}));
   await page.evaluate(async()=>{await __framing.sceneModels.reload();__framing.sceneView.refresh();});
   sameCamera(await page.evaluate(()=>({position:__framing.camera.position.toArray(),target:__framing.controls.target.toArray()})),await page.evaluate(()=>__ownedCamera));
   await page.unroute('**/api/model-assets*');
   const snapshot=await (await page.request.get(process.env.UI_BASE_URL+'/api/model-assets')).json();
   const adopted={...snapshot.models[0],status:'adopted',page:scene,decision:'isolated browser fixture'};
   await page.route('**/api/model-assets*',r=>r.fulfill({json:{...snapshot,models:[adopted]}}));
   await page.evaluate(async()=>{await __framing.sceneModels.reload();__framing.sceneView.refresh();});
   assert.ok(await page.evaluate(()=>{const roots=__framing.sceneModels.objects();const length=roots.length;roots.pop();return length===1 && __framing.sceneModels.objects().length===1;}),'current model query must return a defensive list');
   sameCamera(await page.evaluate(()=>({position:__framing.camera.position.toArray(),target:__framing.controls.target.toArray()})),await page.evaluate(()=>__ownedCamera));
   await page.locator('#fit-view').click();await check('main',scene+' restored',true);
   await page.unroute('**/api/model-assets*');
   await page.evaluate(()=>__framing.sceneModels.reload());
   for(const part of ['server','gpu']){
    await page.setViewportSize({width:part==='gpu'?360:1280,height:900});
    await page.evaluate(part=>__framing.showDossier(__framing.PART[part]),part);
    await page.locator('#dossier .insp canvas').waitFor();
    await page.waitForFunction(()=>{const v=__framing.inspector.viewForTest();return Math.abs(v.camera.aspect-v.canvas.clientWidth/v.canvas.clientHeight)<.005;});
    await check('inspector',scene+' '+part+' reopened');
    const cv=page.locator('#dossier .insp canvas'),rect=await cv.boundingBox();
    await page.mouse.move(rect.x+30,rect.y+30);await page.mouse.down();await page.mouse.move(rect.x+rect.width-30,rect.y+rect.height-25,{steps:3});await page.mouse.up();
    await check('inspector',scene+' '+part+' rotated');
    await page.getByRole('button',{name:'关闭部件档案'}).click();
   }
   if(scene==='bom3d'){
    await page.setViewportSize({width:1280,height:900});
    await page.locator('#dchip-power').click();
    const owned=await page.evaluate(()=>({position:__framing.camera.position.toArray(),target:__framing.controls.target.toArray()}));
    await page.setViewportSize({width:1000,height:900});await page.evaluate(()=>__framing.sceneView.refresh());
    sameCamera(await page.evaluate(()=>({position:__framing.camera.position.toArray(),target:__framing.controls.target.toArray()})),owned);
   }
  }
  console.log('Framing: real registered GLB comparison and narrow viewport');
  await page.goto(process.env.UI_BASE_URL+'/compare.html',{waitUntil:'domcontentloaded'});
  await page.locator('.card .rg-model-status[data-state=ready]').waitFor({state:'attached'});
  await check('compare','comparison desktop');await screenshot('compare-desktop');
  for(const width of [360,1280]){
   await page.setViewportSize({width,height:900});
   await page.waitForFunction(()=>Math.abs(__compareView.camera.aspect-__compareView.canvas.clientWidth/__compareView.canvas.clientHeight)<.005);
   const cv=page.locator('.card canvas'),rect=await cv.boundingBox();
   await page.mouse.move(rect.x+30,rect.y+30);await page.mouse.down();await page.mouse.move(rect.x+rect.width-30,rect.y+rect.height-30,{steps:3});await page.mouse.up();
   await check('compare','comparison rotated '+width);
  }
  // Edge cases exercise the shared implementation with real Three geometry and measured DOM.
  await page.evaluate(async()=>{
   const THREE=await import('three'),{visibleBounds,fitPerspective,createViewport,mountSceneView}=await import('/assets/scene-view.js');
   const check=(v,m)=>{if(!v)throw Error(m)};
   const camera=new THREE.PerspectiveCamera(40,1,.1,100),before=camera.position.toArray();
   check(!fitPerspective({camera,bounds:new THREE.Box3()}),'empty geometry cannot fit');
   check(JSON.stringify(camera.position.toArray())===JSON.stringify(before),'empty fit moved camera');
   check(!fitPerspective({camera,bounds:new THREE.Box3(new THREE.Vector3(-1e200,-1e200,-1e200),new THREE.Vector3(1e200,1e200,1e200))}),'overflowing bounds poisoned camera');
   const mesh=new THREE.Mesh(new THREE.BoxGeometry(2,6,4),new THREE.MeshBasicMaterial()),parent=new THREE.Group();parent.add(mesh);parent.visible=false;
   check(visibleBounds([mesh]).isEmpty(),'invisible parent changed bounds');parent.visible=true;parent.position.set(70,20,-40);
   const bounds=visibleBounds([mesh]);check(bounds.getCenter(new THREE.Vector3()).x===70,'world transform ignored');
   camera.aspect=0;check(!fitPerspective({camera,bounds}),'zero aspect accepted');camera.aspect=.2;
   check(fitPerspective({camera,bounds}),'valid portrait fit rejected');
   const canvas=document.createElement('canvas');canvas.style.cssText='position:fixed;width:180px;height:240px';document.body.append(canvas);
   let sizes=0;const viewport=createViewport({canvas,camera,resize:()=>sizes++});viewport.sync();viewport.sync();check(sizes===1,'same size repeatedly resized buffer');
   viewport.dispose();canvas.style.width='200px';viewport.sync();check(sizes===1,'disposed viewport still wrote');canvas.remove();
   const controls=new THREE.EventDispatcher();controls.target=new THREE.Vector3();controls.maxDistance=1;controls.update=()=>{};
   const button=document.createElement('button');document.body.append(button);
   const view=mountSceneView({canvas,camera,controls,objects:()=>[mesh],resize:()=>{},headers:[],button});
   view.fit();controls.dispatchEvent({type:'start'});camera.position.x+=4;const owned=camera.position.clone();view.refresh();check(camera.position.equals(owned),'gesture lost view ownership');
   view.fit();check(!camera.position.equals(owned),'explicit fit did not reacquire');view.dispose();camera.position.x+=4;const disposed=camera.position.clone();button.click();view.refresh();check(camera.position.equals(disposed),'disposed view still moved camera');
   button.remove();mesh.geometry.dispose();mesh.material.dispose();
  });
  assert.deepEqual(errors,[]);
  if(process.env.REVIEW_SCREENSHOTS)writeFileSync(process.env.REVIEW_SCREENSHOTS+'/framing-results.json',JSON.stringify(results,null,2)+'\n');
  console.log('PASS geometry inside viewport, headers, rotation/reopen, current model roots, user/author camera ownership, empty/hidden geometry and resize disposal');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
