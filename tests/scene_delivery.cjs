/* True customer frames, physical identity, delivered downloads and the private-resource boundary. */
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs'),{join}=require('node:path'),{createHash}=require('node:crypto');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const cases=[
 ['/bom3d.html?view=campus&p=transformer','transformer'],
 ['/bom3d.html?view=exploded&p=transformer','transformer'],
 ['/bom3d.html?node=site:water-rights','water'],
 ['/rack3d.html?view=server&x=55&node=part:server','server'],
 ['/rack3d.html?view=rack&x=0&node=part:rack-frame','rack-frame'],
 ['/rack3d.html?view=rack-exploded&x=35&node=part:power-shelf','power-shelf'],
 ['/rack3d.html?view=chip&x=90&node=part:hbm','hbm'],
];
(async()=>{
 const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true,args:['--enable-unsafe-swiftshader']});
 try{
  const expected=new Map();
  for(const [role,cookie] of [['admin',process.env.UI_ADMIN_COOKIE],['customer',process.env.UI_CUSTOMER_COOKIE]]){
   assert.ok(cookie,'use isolated real '+role+' account');
   const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:.5,reducedMotion:'reduce',acceptDownloads:true});
   const split=cookie.indexOf('=');await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:base}]);
   const page=await context.newPage(),errors=[],privateRequests=[],failedResources=[];
   page.on('pageerror',error=>errors.push(error.message));
   page.on('request',request=>{if(/research-graph|object-network|research-(summary|materials|adopted)|tco_targets|\/data\/products\.json|\/framework\/modules\.json/.test(new URL(request.url()).pathname))privateRequests.push(request.url());});
   page.on('response',response=>{if(response.status()>=400 && ['script','stylesheet','image','font'].includes(response.request().resourceType()))failedResources.push([response.status(),response.url()]);});
   await page.route(/\/(bom3d|rack3d)\.html/,async route=>{
    const response=await route.fetch();assert.equal(response.status(),200);
    const source=await response.text(),html=source.replace('</script>\n</body>','globalThis.__deliveryScene={scene,pickables,renderer,composer,resetFanPhase(){if(typeof spinners!=="undefined")spinners.forEach(rotor=>rotor.rotation.z=0);}};\n</script>\n</body>');
    assert.notEqual(html,source);await route.fulfill({response,body:html});
   });
   const navigation=await(await page.request.get(base+'/api/navigation')).json();
   assert.ok(navigation.delivery_pages.includes('/bom3d.html'));assert.ok(navigation.delivery_pages.includes('/rack3d.html'));
   for(const [path,part] of cases){
    await page.goto(base+path);await page.waitForFunction(()=>!!globalThis.__deliveryScene);
    await page.locator('#dossier h2').waitFor();
    assert.equal(await page.locator('#dossier').getAttribute('data-part-id'),part,'legacy/canonical scene identity remains stable');
    assert.equal(await page.locator('#dossier .rg-3d-panel,#dossier .dossier-targets,#dossier a[href*="supply.html"]').count(),0);
    if(part!=='water')assert.equal(await page.locator('#dossier .insp canvas').count(),1,'physical independent preview remains');
    else assert.equal(await page.locator('#dossier .insp canvas').count(),0,'nonphysical right is not fabricated into hardware');
    const physical=await page.evaluate(()=>{
     const s=__deliveryScene;s.resetFanPhase();s.scene.updateMatrixWorld(true);
     const objects=s.pickables.map(m=>({part:m.userData.part,node:m.userData.node_id,instance:m.userData.instanceId,vertices:m.geometry.attributes.position?.count,indices:m.geometry.index?.count,matrix:m.matrixWorld.elements.map(n=>Math.round(n*1e5)/1e5)}));
     s.composer.render();const gl=s.renderer.getContext(),bytes=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
     gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
     const colors=new Set();for(let i=0;i<bytes.length;i+=4*43)colors.add([bytes[i]>>3,bytes[i+1]>>3,bytes[i+2]>>3,bytes[i+3]].join(','));
     return {objects,colors:colors.size,width:gl.drawingBufferWidth,height:gl.drawingBufferHeight};
    });
    assert.ok(physical.objects.length>10);assert.ok(physical.colors>8,'real WebGL frame contains the scene, not a blank canvas');
    assert.ok((await page.locator('#c').screenshot()).byteLength>2000,'the actual framed canvas can be captured');
    const reading=await page.locator('#dossier').innerText();
    if(role==='admin')expected.set(path,{objects:physical.objects,reading});
    else{assert.deepEqual(physical.objects,expected.get(path).objects,'IT/customer physical meshes and identities match');assert.equal(reading,expected.get(path).reading,'IT/customer delivered dossier is identical');}
    for(const href of await page.locator('#dossier a[href]').evaluateAll(links=>links.map(link=>link.href))){const url=new URL(href);if(url.origin===new URL(base).origin && !url.pathname.startsWith('/assets/'))assert.ok(navigation.delivery_pages.includes(url.pathname),href);}
    if(role==='customer'){
     const download=page.waitForEvent('download');await page.locator('#atlas-export').click();const file=await download;
     assert.equal(await file.failure(),null);const svg=readFileSync(await file.path(),'utf8');
     assert.ok(svg.includes('<svg'));
     const metadata=await page.evaluate(raw=>{const doc=new DOMParser().parseFromString(raw,'image/svg+xml');return {meta:JSON.parse(doc.querySelector('metadata').textContent),leader:doc.querySelector('[data-object-id]')?.getAttribute('data-object-id')};},svg);
     assert.match(metadata.meta.object_id,/^(campus\/|server\/|rack\/|package\/|part:)/,'export metadata retains the selected evidence identity');
     assert.equal(metadata.meta.identity,'generic schematic; no model-specific dimensions');
     if(metadata.leader)assert.equal(metadata.leader,metadata.meta.object_id,'visible leader keeps the same physical identity');
     if(part==='water'){
      assert.equal(metadata.meta.object_id,'part:water','nonphysical source compatibility identity remains explicit');
      assert.equal(await page.locator('#dossier a[href*="node.html?id=site%3Awater-rights"]').count(),1,'the formal research identity remains the canonical site right');
     }else{
      const identity=await page.locator('.part-inspector-identity').innerText();
      if(part==='rack-frame'){
       assert.equal(metadata.meta.object_id,'part:rack-frame','retain the existing category export identity');
       assert.ok(identity.includes('rack/whole'),'retain the existing complete-cabinet preview identity');
      }else assert.ok(identity.includes(metadata.meta.object_id),path+' export '+metadata.meta.object_id+' vs inspector '+identity);
     }
     assert.doesNotMatch(svg,/research-summary|tco_targets|队 \/ 主机/);
     if(part==='server')for(const href of ['/assets/technical-atlas/server-v1.svg','/assets/technical-atlas/server-v1.png']){
      const response=await page.request.get(base+href);assert.equal(response.status(),200);assert.equal(digest(await response.body()),digest(readFileSync(join(__dirname,'../web',href))));
     }
     await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1280,height:900});
    }
   }
   assert.deepEqual(privateRequests,[]);assert.deepEqual(failedResources,[]);assert.deepEqual(errors,[]);
   await context.close();
  }
  console.log('PASS real admin/customer 3D: seven campus/layer/right/server/rack/chip frames, identical physical IDs and geometry, previews, exact source files, real SVG exports, mobile, zero private requests');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
