/* Published adoption, real GLTF parsing and owned replacement across all consumers. */
const assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const {chromium}=require('playwright');
function fixture(name, brokenTexture=false) {
 const binary=Buffer.from(new Float32Array([0,0,0,1,0,0,0,2,0]).buffer);
 const data={asset:{version:'2.0'},scene:0,scenes:[{nodes:[0,1]}],nodes:[{name,mesh:0},{name:'shared_mesh',mesh:0,translation:[2,0,0]}],
  meshes:[{primitives:[{attributes:{POSITION:0},material:0}]}],materials:[{pbrMetallicRoughness:{baseColorTexture:{index:0}}}],
  textures:[{source:0}],images:[{uri:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=='}],
  buffers:[{byteLength:binary.length}],bufferViews:[{buffer:0,byteOffset:0,byteLength:binary.length}],
  accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[0,0,0],max:[1,2,0]}]};
 if(brokenTexture)data.images[0].uri='data:image/png;base64,bm90IGEgcG5n';
 let json=Buffer.from(JSON.stringify(data));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);
 const header=Buffer.alloc(20);header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+binary.length,8);header.writeUInt32LE(json.length,12);header.write('JSON',16);
 const chunk=Buffer.alloc(8);chunk.writeUInt32LE(binary.length);chunk.write('BIN\0',4);
 return Buffer.concat([header,json,chunk,binary]);
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:.5,reducedMotion:'reduce'});
  const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().endsWith('.glb'))requests.push(new URL(r.url()).pathname)});
  const binaries={'a.glb':fixture('server_a'),'b.glb':fixture('server_b'),'bad.glb':Buffer.from('not a GLB'),'texture.glb':fixture('server_texture',true)};
  const entry=(file,scene='rack3d',hideRack=false)=>({file,page:scene,hideRack,status:'adopted',decision:'isolated fixture',source:'https://example.test/source',license:'CC0',fitHeight:6,url:'/assets/models/'+file,sha256:createHash('sha256').update(binaries[file]).digest('hex')});
  let response=null,failFile=null,wrongHash=false,schemaVersion=1;
  await page.route('**/api/model-assets*',r=>response===null?r.continue():response==='fail'?r.fulfill({status:503,json:{error:'injected'}}):r.fulfill({json:{schema_version:schemaVersion,revision:'fixture',models:response}}));
  await page.route('**/assets/models/*.glb',r=>{
   const name=new URL(r.request().url()).pathname.split('/').pop();
   if(!binaries[name])return r.continue();
   return r.fulfill({status:failFile===name?503:200,body:wrongHash?Buffer.from('changed bytes'):binaries[name],contentType:'model/gltf-binary'});
  });
  await page.route(/\/(bom3d|rack3d)\.html/,async r=>{
   const res=await r.fetch(),html=await res.text();
   const tail='globalThis.__assetsTest={scene,sceneModels'+(new URL(r.request().url()).pathname.includes('rack')?',rack':'')+'};\n</script>\n</body>';
   await r.fulfill({response:res,body:html.replace('</script>\n</body>',tail)});
  });
  for(const scene of ['bom3d','rack3d']) {
   console.log('Model assets: '+scene+' default selection, retry and replacement');
   response=null;failFile=null;requests.length=0;
   await page.goto(process.env.UI_BASE_URL+'/'+scene+'.html?node=part:gpu',{waitUntil:'domcontentloaded'});
   await page.locator('.rg-scene-model-status[data-state=ready]').waitFor({state:'attached'});
   assert.deepEqual(requests,[],'rejected sample must not load in the scene');
   await page.waitForFunction(()=>!!globalThis.__assetsTest);
   response='fail';await page.evaluate(()=>__assetsTest.sceneModels.reload());
   const status=page.locator('.rg-scene-model-status[data-state=error]');await status.waitFor();
   for(const width of [360,1280]) {
    await page.setViewportSize({width,height:900});
    for(const skin of ['Attio','folk'])for(const mode of ['light','dark']) {
     await page.getByRole('button',{name:skin,exact:true}).click();await page.locator('#ui-appearance').selectOption(mode);
     const b=await status.boundingBox();assert.ok(b.x>=0 && b.x+b.width<=width);
     const retry=status.getByRole('button',{name:'重试',exact:true});assert.ok(await retry.isVisible());
     assert.ok(await retry.evaluate(e=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2))}),'retry is covered by another panel');
     const contrast=await retry.evaluate(e=>{
      const style=getComputedStyle(e),luminance=color=>color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
      const a=luminance(style.color),b=luminance(style.backgroundColor);
      return {ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),height:e.getBoundingClientRect().height};
     });
     assert.ok(contrast.ratio>=4.5 && contrast.height>=36,'retry needs readable contrast and a usable touch target');
     assert.notEqual(await status.evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
    }
   }
   await page.locator('#play').click();assert.equal(await page.locator('#explode').inputValue(),'100');
   response=[entry('a.glb',scene,scene==='rack3d')];failFile='a.glb';
   await status.getByRole('button',{name:'重试',exact:true}).click();await status.waitFor();
   assert.ok(await page.evaluate(()=>!__assetsTest.rack || __assetsTest.rack.visible));
   failFile=null;await status.getByRole('button',{name:'重试',exact:true}).click();
   await page.locator('.rg-scene-model-status[data-state=ready]').waitFor({state:'attached'});
   const ready=await page.evaluate(async()=>{
    const THREE=await import('three'),root=__assetsTest.scene.getObjectByName('server_a');
    const group=root.parent;globalThis.__oldModel=group;globalThis.__oldDisposed=0;
    root.geometry.addEventListener('dispose',()=>__oldDisposed++);
    return {height:new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3()).y,rack:__assetsTest.rack?.visible};
   });
   assert.ok(Math.abs(ready.height-6)<1e-6);if(scene==='rack3d')assert.equal(ready.rack,false);
   // One bad member cannot partially replace the currently displayed successful group.
   response=[entry('b.glb',scene),entry('bad.glb',scene)];await page.evaluate(()=>__assetsTest.sceneModels.reload());
   await status.waitFor();assert.equal(await page.evaluate(()=>__oldDisposed),0);
   assert.ok(await page.evaluate(()=>__oldModel.parent===__assetsTest.scene));
   response=[entry('texture.glb',scene)];await page.evaluate(()=>__assetsTest.sceneModels.reload());
   await status.waitFor();assert.equal(await page.evaluate(()=>__oldDisposed),0);
   response=[entry('b.glb',scene)];await page.evaluate(()=>__assetsTest.sceneModels.reload());
   assert.equal(await page.evaluate(()=>__oldDisposed),1);
   assert.ok(await page.evaluate(()=>!!__assetsTest.scene.getObjectByName('server_b')));
   if(scene==='rack3d')assert.ok(await page.evaluate(()=>__assetsTest.rack.visible));
   response=[];await page.evaluate(()=>__assetsTest.sceneModels.reload());
   assert.ok(await page.evaluate(()=>!__assetsTest.scene.getObjectByName('server_b')));
   if(scene==='rack3d')assert.ok(await page.evaluate(()=>__assetsTest.rack.visible));
  }
  console.log('Model assets: comparison status, empty state and content integrity');
  response='fail';await page.goto(process.env.UI_BASE_URL+'/compare.html',{waitUntil:'domcontentloaded'});
  const startup=page.locator('.rg-scene-startup[data-state=error]');await startup.waitFor();
  response=[];schemaVersion=2;
  await Promise.all([page.waitForResponse(r=>r.url().includes('/api/model-assets')),startup.getByRole('button',{name:'重试',exact:true}).click()]);
  await startup.waitFor();
  response=null;schemaVersion=1;await startup.getByRole('button',{name:'重试',exact:true}).click();
  await page.locator('.card .rg-model-status[data-state=ready]').waitFor({state:'attached'});
  assert.match(await page.locator('.meta').textContent(),/未采用/);
  response=[entry('a.glb')];wrongHash=true;await page.goto(process.env.UI_BASE_URL+'/compare.html',{waitUntil:'domcontentloaded'});
  const failure=page.locator('.card .rg-model-status[data-state=error]');await failure.waitFor();
  wrongHash=false;await failure.getByRole('button',{name:'重试',exact:true}).click();
  await page.locator('.card .rg-model-status[data-state=ready]').waitFor({state:'attached'});
  assert.match(await page.locator('.rows').textContent(),/网格与名称仅作线索/);
  response=[];await page.goto(process.env.UI_BASE_URL+'/compare.html',{waitUntil:'domcontentloaded'});
  await page.getByText('尚无已登记模型。候选通过审阅后才会进入研究场景。',{exact:true}).waitFor();
  const payload='<img src=x onerror="window.__modelExecuted=true">';
  response=[entry('a.glb')];await page.goto(process.env.UI_BASE_URL+'/compare.html?f='+encodeURIComponent(payload),{waitUntil:'domcontentloaded'});
  await page.locator('.meta b').waitFor();assert.equal(await page.locator('.meta b').textContent(),payload);
  assert.equal(await page.locator('.card canvas,.meta img').count(),0);
  console.log('Model assets: cancellation, version takeover and private resource disposal');
  await page.evaluate(async entry=>{
   const {createModelLoad,loadModel}=await import('/assets/model-assets.js');
   const check=(v,m)=>{if(!v)throw Error(m)},settle=async()=>{for(let n=0;n<20;n++)await Promise.resolve()};
   let requests=[],committed=[],disposed=[];
   const slot=createModelLoad({host:document.body,label:'fixture',timeoutMs:40,
    load:signal=>new Promise(resolve=>requests.push({signal,resolve})),commit:value=>committed.push(value.id)});
   const value=id=>({id,dispose(){disposed.push(id)}});
   await settle();await new Promise(r=>setTimeout(r,60));
   check(slot.element.dataset.state==='error' && requests[0].signal.aborted,'deadline must release request and show failure');
   slot.element.querySelector('button').click();slot.element.querySelector('button').click();await settle();
   check(requests.length===2,'double retry duplicated load');
   requests[1].resolve(value('A'));await settle();requests[0].resolve(value('late'));await settle();
   check(committed.join()==='A' && disposed.includes('late'),'late value replaced current');
   const old=slot.reload();await settle();const newer=slot.reload();await settle();
   requests[3].resolve(value('A2'));await newer;requests[2].resolve(value('B'));await old;await settle();
   check(committed.join()==='A,A2' && disposed.includes('B') && disposed.includes('A'),'A→B→A takeover leaked or published old state');
   const cancelled=slot.reload();await settle();slot.dispose();requests[4].resolve(value('after-dispose'));await cancelled;await settle();
   check(disposed.includes('A2') && disposed.includes('after-dispose'),'dispose leaked current or pending value');
   const model=await loadModel(entry,new AbortController().signal);
   const meshes=[];model.root.traverse(o=>{if(o.isMesh)meshes.push(o)});
   check(meshes.length===2 && meshes[0].geometry===meshes[1].geometry,'fixture must actually share parsed geometry');
   let geometry=0,material=0,texture=0,image=0;
   meshes[0].geometry.addEventListener('dispose',()=>geometry++);meshes[0].material.addEventListener('dispose',()=>material++);
   const map=meshes[0].material.map;check(map,'real embedded texture did not parse');map.addEventListener('dispose',()=>texture++);
   const bitmap=map.source.data,close=bitmap.close.bind(bitmap);bitmap.close=()=>{image++;close()};
   model.dispose();model.dispose();check(geometry===1 && material===1 && texture===1 && image===1,'owned shared resources must release exactly once');
  },entry('a.glb'));
  assert.deepEqual(errors,[]);
  console.log('PASS adopted-only scenes, real GLTF/SHA, complete-group replacement, rejected comparison, retry, timeout, double retry, A→B→A, late disposal and shared resource ownership');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
