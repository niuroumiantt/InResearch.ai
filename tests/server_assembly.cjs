/* TA-11: actual server route, installation axes, gestures, picks and exports. */
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce'}),errors=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route(/\/rack3d\.html/,async route=>{
   const response=await route.fetch(),html=await response.text();
   const body=html.replace('</script>\n</body>','globalThis.__serverTest={scene,serverMode,serverAssembly,rack,pickables,animated,camera,controls,canvas,sceneView,sceneModels,atlasDrawing,disposePage,renderer,composer,spinners};\n</script>\n</body>');
   assert.notEqual(body,html,'observation must match current source');await route.fulfill({response,body});
  });
  async function openControls(){if(!await page.locator('details[data-responsive-panel]').evaluate(el=>el.open))await page.getByLabel('展开或收起场景控制').click();}
  async function screenshot(name){if(process.env.REVIEW_SCREENSHOTS)await page.screenshot({path:process.env.REVIEW_SCREENSHOTS+'/'+name+'.png'});}
  async function fitCheck(label){
   await openControls();await page.locator('#fit-view').click();
   const r=await page.evaluate(async()=>{
    const THREE=await import('three'),v=__serverTest;v.scene.updateMatrixWorld(true);v.camera.updateMatrixWorld();
    let maxX=0,maxY=0,count=0,minZ=1,maxZ=-1;
    for(const m of v.pickables){if(!m.geometry.boundingBox)m.geometry.computeBoundingBox();const b=m.geometry.boundingBox;
     for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z]){const p=new THREE.Vector3(x,y,z).applyMatrix4(m.matrixWorld).project(v.camera);count++;maxX=Math.max(maxX,Math.abs(p.x));maxY=Math.max(maxY,Math.abs(p.y));minZ=Math.min(minZ,p.z);maxZ=Math.max(maxZ,p.z);}}
    const box=v.canvas.getBoundingClientRect(),labels=[...document.querySelectorAll('.atlas-scene-labels text')].filter(e=>getComputedStyle(e).display!=='none').map(e=>{const b=e.getBoundingClientRect();return {text:e.textContent,x:b.x,y:b.y,width:b.width,height:b.height,font:parseFloat(getComputedStyle(e).fontSize)};});
    return {count,maxX,maxY,minZ,maxZ,aspect:v.camera.aspect,canvas:{width:box.width,height:box.height,top:box.top},header:Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom,document.querySelector('#ui-skinbar').getBoundingClientRect().bottom),labels};
   });
   assert.ok(r.count>0&&r.maxX<=1&&r.maxY<=1&&r.minZ>=-1&&r.maxZ<=1,label+' clipped '+JSON.stringify(r));
   assert.ok(Math.abs(r.aspect-r.canvas.width/r.canvas.height)<.005);assert.ok(r.canvas.top>=r.header-.5);
   assert.ok(r.labels.every(l=>l.font>=14&&l.x>=-1&&l.x+l.width<=r.canvas.width+1));
   for(let i=0;i<r.labels.length;i++)for(let j=i+1;j<r.labels.length;j++){const a=r.labels[i],b=r.labels[j];assert.ok(!(Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>1&&Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>1),label+' overlapping labels '+a.text+' / '+b.text);}
   results.push({label,...r});
  }
  await page.goto(process.env.UI_BASE_URL+'/rack3d.html?x=55',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!globalThis.__serverTest);
  assert.equal(await page.evaluate(()=>__serverTest.serverMode),true);assert.equal(await page.locator('#explode').inputValue(),'55');
  assert.deepEqual(await page.evaluate(()=>__serverTest.serverAssembly.counts),{server:1,cpu:2,dram:8,gpu:2,ssd:8,nic:1,psu:2,'server-fan':4});
  assert.equal(await page.evaluate(()=>__serverTest.rack.name),'generic-server-assembly');assert.equal(await page.evaluate(()=>__serverTest.sceneModels.objects().length),0);
  for(const stage of [0,55,100]){
   await page.locator('#explode').evaluate((el,stage)=>{el.value=stage;el.dispatchEvent(new Event('input',{bubbles:true}));},stage);await fitCheck('desktop stage '+stage);await screenshot('server-stage-'+stage+'-desktop');
  }
  const axes=await page.evaluate(()=>{const g=__serverTest.serverAssembly.groups;return {motions:__serverTest.animated.length,gpu:g.GPU.children.map(o=>o.userData.installationAxis),drive:g.drives.children.map(o=>o.userData.installationAxis),psu:g.PSU.children.map(o=>o.userData.installationAxis),fan:g.fan.children.map(o=>o.userData.installationAxis),slots:g.GPU.children.map(o=>({slot:o.userData.matingSlot,exists:!!__serverTest.rack.getObjectByName(o.userData.matingSlot)})),ports:(()=>{const a=[];__serverTest.rack.traverse(o=>{if(o.userData.facingAxis)a.push([o.name,o.userData.facingAxis]);});return a;})()};});
  assert.equal(axes.motions,17);assert.ok(axes.gpu.every(a=>JSON.stringify(a)==='[0,1,0]'));assert.ok(axes.drive.every(a=>JSON.stringify(a)==='[0,0,1]'));assert.ok(axes.psu.every(a=>JSON.stringify(a)==='[0,0,-1]'));assert.ok(axes.fan.every(a=>JSON.stringify(a)==='[0,1,0]'));assert.ok(axes.slots.every(s=>s.slot&&s.exists));
  assert.equal(axes.ports.filter(([n,a])=>n==='external-ac-recess'&&a==='-z').length,2);assert.equal(axes.ports.filter(([n,a])=>n==='internal-dc-interface'&&a==='+z').length,2);assert.equal(axes.ports.filter(([n,a])=>n==='rear-network-aperture'&&a==='-z').length,2);results.push({label:'installation and interface correspondence',...axes});
  // A real canvas drag takes ownership. Stage changes/resize/reload cannot steal it.
  const cb=await page.locator('canvas#c').boundingBox();await page.mouse.move(cb.x+cb.width*.55,cb.y+cb.height*.45);await page.mouse.down();await page.mouse.move(cb.x+cb.width*.62,cb.y+cb.height*.48,{steps:4});await page.mouse.up();await page.evaluate(()=>{__serverTest.controls.enableDamping=false;__serverTest.controls.update();});await page.waitForTimeout(50);
  const owned=await page.evaluate(()=>({position:__serverTest.camera.position.toArray(),target:__serverTest.controls.target.toArray()}));
  await page.locator('#explode').evaluate(el=>{el.value=55;el.dispatchEvent(new Event('input',{bubbles:true}));});await page.setViewportSize({width:1000,height:900});await page.evaluate(async()=>{await __serverTest.sceneModels.reload();__serverTest.sceneView.refresh();});await page.waitForTimeout(200);
  const current=await page.evaluate(()=>({position:__serverTest.camera.position.toArray(),target:__serverTest.controls.target.toArray()}));for(const k of ['position','target'])current[k].forEach((v,i)=>assert.ok(Math.abs(v-owned[k][i])<.005,'manual camera stolen '+JSON.stringify({owned,current})));
  await page.setViewportSize({width:1280,height:900});await fitCheck('explicit fit after manual gesture');
  // Find visible, unobscured actual meshes using ray casting, then use real pointer clicks.
  for(const part of ['gpu','ssd','psu']){
   const point=await page.evaluate(async part=>{const THREE=await import('three'),v=__serverTest,rect=v.canvas.getBoundingClientRect(),ray=new THREE.Raycaster();v.scene.updateMatrixWorld(true);v.camera.updateMatrixWorld();
    for(const m of v.pickables.filter(m=>m.userData.part===part)){if(!m.geometry.boundingBox)m.geometry.computeBoundingBox();const c=m.geometry.boundingBox.getCenter(new THREE.Vector3()).applyMatrix4(m.matrixWorld).project(v.camera);if(Math.abs(c.x)>.95||Math.abs(c.y)>.95)continue;const x=rect.left+(c.x+1)*rect.width/2,y=rect.top+(1-c.y)*rect.height/2;if(document.elementFromPoint(x,y)!==v.canvas)continue;ray.setFromCamera(new THREE.Vector2(c.x,c.y),v.camera);const hit=ray.intersectObjects(v.pickables,false)[0];if(hit?.object.userData.part===part)return {x,y};}return null;},part);
   assert.ok(point,'no visible pick target '+part);await page.mouse.click(point.x,point.y);await page.locator('#dossier h2').waitFor();assert.equal(await page.locator('#dossier').getAttribute('data-part-id'),part);await page.locator('#dossier canvas').waitFor();
   const pending=page.waitForEvent('download');await page.locator('#atlas-export').click();const d=await pending;assert.equal(await d.failure(),null);assert.equal(d.suggestedFilename(),'server-technical-atlas.svg');const raw=fs.readFileSync(await d.path(),'utf8');
   const exported=await page.evaluate(raw=>{const doc=new DOMParser().parseFromString(raw,'image/svg+xml');if(doc.querySelector('parsererror'))throw Error('invalid SVG');return {metadata:JSON.parse(doc.querySelector('metadata').textContent),labels:[...doc.querySelectorAll('#editable-labels text[stroke]')].map(e=>e.textContent),pixels:[__serverTest.canvas.width,__serverTest.canvas.height],leader:doc.querySelector('[data-object-id]')?.getAttribute('data-object-id')};},raw);
   assert.equal(exported.metadata.object_id,'part:'+part);assert.equal(exported.metadata.title,'通用服务器整机装配图册');assert.deepEqual(exported.metadata.pixels,exported.pixels);assert.ok(exported.labels.length>=2);if(exported.leader)assert.equal(exported.leader,'part:'+part);results.push({label:'actual pick and current-view export '+part,...exported});
   if(process.env.REVIEW_SCREENSHOTS)fs.writeFileSync(process.env.REVIEW_SCREENSHOTS+'/server-'+part+'-current.svg',raw);await page.getByRole('button',{name:'关闭部件档案'}).click();
  }
  for(const width of [1280,390])for(const theme of ['light','dark']){
   await page.setViewportSize({width,height:900});await page.locator('#ui-appearance').selectOption(theme);await page.locator('#explode').evaluate(el=>{el.value=100;el.dispatchEvent(new Event('input',{bubbles:true}));});await fitCheck(width+' '+theme+' fully exploded');
   if(width===390)await page.getByLabel('展开或收起场景控制').click();await screenshot('server-full-'+width+'-'+theme);
  }
  const released=await page.evaluate(async()=>{const v=__serverTest,geo=new Set(),mat=new Set();v.rack.traverse(o=>{if(o.isMesh){geo.add(o.geometry);[].concat(o.material||[]).forEach(m=>mat.add(m));}});let geometries=0,materials=0,renders=0;geo.forEach(g=>g.addEventListener('dispose',()=>geometries++));mat.forEach(m=>m.addEventListener('dispose',()=>materials++));const render=v.composer.render.bind(v.composer);v.composer.render=(...args)=>{renders++;return render(...args);};v.disposePage();v.disposePage();const at=renders;await new Promise(r=>setTimeout(r,80));return {sourceGeometry:geo.size,sourceMaterials:mat.size,geometries,materials,rendersAfter:renders-at,parent:!!v.rack.parent,animations:v.animated.length,picks:v.pickables.length,spinners:v.spinners.length,labels:document.querySelectorAll('.atlas-scene-labels').length};});
  assert.equal(released.geometries,released.sourceGeometry);assert.equal(released.materials,released.sourceMaterials);for(const k of ['rendersAfter','animations','picks','spinners','labels'])assert.equal(released[k],0,k+' survived disposal');assert.equal(released.parent,false);results.push({label:'page resources and registries released',...released});
  await page.setViewportSize({width:1280,height:900});for(const x of [0,35,90]){
   await page.goto(process.env.UI_BASE_URL+'/rack3d.html?x='+x,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!globalThis.__serverTest);assert.equal(await page.evaluate(()=>__serverTest.serverMode),false);assert.equal(await page.locator('#explode').inputValue(),String(x));assert.ok(await page.evaluate(()=>__serverTest.pickables.length>0));}
  await page.goto(process.env.UI_BASE_URL+'/rack3d.html?node=part:gpu',{waitUntil:'domcontentloaded'});await page.locator('#dossier canvas').waitFor();assert.equal(await page.evaluate(()=>__serverTest.serverMode),false);assert.equal(await page.locator('#dossier').getAttribute('data-part-id'),'gpu');assert.deepEqual(errors,[]);
  if(process.env.REVIEW_SCREENSHOTS)fs.writeFileSync(process.env.REVIEW_SCREENSHOTS+'/server-assembly-results.json',JSON.stringify({observed_at:new Date().toISOString(),results,page_errors:errors},null,2)+'\n');
  console.log('PASS TA11 independent server x55, counts/axes/interfaces, true picks/current SVG, stage0/100 fitting, user camera, both sizes/themes, cleanup and old rack routes');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
