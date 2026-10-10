/* TA30–34 actual-public panel runner. Test source only, NOT EXECUTED.
 * Exact https://inresearch.ai only. Local source is read for byte/SHA checks,
 * never imported, executed, served, or used as a network fallback.
 * Owner reviews/deploys the final source before serial headed public execution.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const BASE='https://inresearch.ai';
assert.equal(process.env.UI_BASE_URL,BASE,'Exact actual-public origin required');
const ROOT=process.env.TA30_34_SOURCE_ROOT;
assert.ok(ROOT&&path.isAbsolute(ROOT),'Explicit reviewed source root required');
const OUT=process.env.REVIEW_SCREENSHOTS||'/private/tmp/ta30-34-panel-public-'+Date.now();
assert.ok(path.isAbsolute(OUT));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const ITEMS=[
 {id:'TA-30',key:'server',file:'server_nvme',title:'NVMe服务器来源面板',model:'Supermicro AS-1114S-WN10RT',width:966,height:88,count:6,aspect:2.3/.735,sha:'935cda787dbdd9db2e09e655e8ec1ee6f858a31d069f0762c7c07273993b1fb2'},
 {id:'TA-31',key:'hero',file:'server_gpu',title:'计算机箱来源面板',model:'Supermicro SYS-620BT-CHASSIS',width:400,height:70,count:1,aspect:2.3/.735,sha:'56386f5d0e9988f13d0b3cf3b2fa2cff99018f92d8045253bc5c9e7faccdd04f'},
 {id:'TA-32',key:'storage',file:'server_storage',title:'存储服务器来源面板',model:'Supermicro SSG-610P-ACR12N4H',width:814,height:72,count:1,aspect:2.3/.735,sha:'81c396ef73aa46505cbc91fd9f5c9a63b21eaa0fc6479f7ffe224ff03e987851'},
 {id:'TA-33',key:'tor',file:'switch_tor',title:'交换机来源面板',model:'Supermicro SSE-G3648B',width:1820,height:180,count:1,aspect:2.3/.399,sha:'47a53a7338b8815efe4302a0a1f9fc9e5e4d67c3c4f871cfaf6ed64c5ef97c2e'},
 {id:'TA-34',key:'ib',file:'switch_ib',title:'高速交换机来源面板',model:'Mellanox SN2100',width:999,height:211,count:1,aspect:2.3/.399,sha:'0354d636bbf6317cdb3eeaaa903a70383036f726f75b37532242cdc377ea5026'},
];
const ASSEMBLIES={
 'rack-assembly':'e8a59af66489308d7daef67c053bcbb7621bb719b4115d3d324f7edc6857793e',
 'rack-exploded-view':'43d6c292bc5d764d874de8d7e183f79c64e5454132417f1dbf9bc020fe9b41e3',
 'server-assembly':'6d3abd5554afeb621798b91a9fb35f78c05ea439b7012b75b4ae79cd0fb9d676',
 'chip-package-assembly':'196e3ea3ac81a73108147aa438be0c41a3266169483acd12c272543f8a6a7241'
};
const END='</script>\n</body>';
const HOOKS={
 page:{file:'web/pages/rack3d.html',marker:END,replacement:`globalThis.__taPanels={THREE,PANEL,scene,rack,camera,controls,canvas,slider,renderer,composer,pickables,texturePool,panelSources,sceneModels,disposePage,
 readState:()=>({mode:chipMode?'chip':serverMode?'server':rackExplodedMode?'rack-exploded':rackOverviewMode?'rack':'legacy-rack',stage:+slider.value,pageDisposed})};\n`+END},
 pool:{file:'web/components/scene-resources.js',marker:'return {canvas, image,',replacement:'return {observeForTest:()=>({disposed,textures:[...textures],images:[...images],handles:[...handles]}),canvas, image,'}
};
const receipt={task:'TA30-34 retained panel sources',stage:'NOT_EXECUTED',origin:BASE,source_root:ROOT,local_fallback:false,
 sources:[],assets:[],displays:[],downloads:[],panels:[],dialogs:[],views:[],modern:[],faults:[],resources:[],errors:[],route_errors:[],network_failures:[],
 scope:{headed:true,product_camera_assignments:false,local_product_access:false,product_source_writes:false,authentication:'not_verified'},
 limits:['Original-size screenshot review remains pending after machine checks. Counts, nonblank pixels and ready status are not visual acceptance.',
 'Source/model names are provenance; switch_ib does not certify InfiniBand and server_gpu does not identify an accelerator board or GPU configuration.',
 'Generic front dimensions are drawing coordinates, not OEM fit/CAD/installed equipment proof.',
 'Historical implicit legacy routes are retained; modern isolation covers the four adopted modern modes plus default only.',
 'GPU texture resize invalidations are counted separately from terminal resource release.']};
let browser;
const contexts=new Set(),releases=new Set();
function flush(){fs.mkdirSync(OUT,{recursive:true});fs.writeFileSync(path.join(OUT,'receipt.json'),JSON.stringify(receipt,null,2)+'\n');}
function near(a,b,label,tolerance=1e-7){assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tolerance,`${label}: ${a} vs ${b}`);}
function sameMain(a,b,label){for(const k of ['camera','target','quaternion'])a[k].forEach((x,i)=>near(x,b[k][i],label+' '+k));assert.equal(b.mode,a.mode,label+' mode');assert.equal(b.stage,a.stage,label+' stage');}
(async()=>{
 try{
  fs.mkdirSync(OUT,{recursive:true});flush();
  for(const item of ITEMS)assert.equal(sha(fs.readFileSync(path.join(ROOT,'web/assets/panels',item.file+'.png'))),item.sha,'Unchanged reviewed original '+item.id);
  for(const[name,digest]of Object.entries(ASSEMBLIES))assert.equal(sha(fs.readFileSync(path.join(ROOT,'web/components',name+'.js'))),digest,'Unchanged TA29 modern assembly source '+name);
  const {chromium}=require('playwright');browser=await chromium.launch({headless:false});
  async function makePage(label,fault={fail:false,hold:false,waiters:[]}){
   const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce',acceptDownloads:true,serviceWorkers:'block'});contexts.add(context);
   context.setDefaultTimeout(30000);
   const stats={label,requests:[],responses:[],failures:[],expected503:new Set()};
   await context.route('**/*',async route=>{
    try{assert.equal(new URL(route.request().url()).origin,BASE,'Blocked off-origin '+route.request().url());await route.continue();}
    catch(e){receipt.route_errors.push({label,error:String(e)});await route.abort('blockedbyclient');}
   });
   const page=await context.newPage();page.on('pageerror',e=>receipt.errors.push({label,error:e.stack||e.message}));
   page.on('request',r=>stats.requests.push({url:r.url(),type:r.resourceType()}));
   page.on('response',r=>stats.responses.push({url:r.url(),status:r.status()}));
   page.on('requestfailed',r=>stats.failures.push({url:r.url(),error:r.failure()?.errorText,expected_fault:/\/assets\/panels\/[^/]+\.png(?:\?|$)/.test(r.url())&&!!(fault.fail||fault.hold||fault.lifecycle)}));
   async function observe(route,hook){
    try{
     const url=route.request().url();assert.equal(new URL(url).origin,BASE);
     const headers={...route.request().headers()};for(const h of ['if-none-match','if-modified-since'])delete headers[h];
     const response=await route.fetch({headers,maxRedirects:0});const bytes=await response.body();
     assert.equal(response.status(),200,url);assert.equal(new URL(response.url()).origin,BASE);assert.ok(bytes.length);
     assert.equal(sha(bytes),sha(fs.readFileSync(path.join(ROOT,hook.file))),url+' actual source SHA');
     const source=bytes.toString('utf8');assert.equal(source.split(hook.marker).length-1,1,'Unique observation anchor '+hook.file);
     const patched=source.replace(hook.marker,hook.replacement);
     receipt.sources.push({label,url,status:200,bytes:bytes.length,sha256:sha(bytes),observer_sha256:sha(Buffer.from(patched)),observation_only:true});
     await route.fulfill({response,body:patched});
    }catch(e){receipt.route_errors.push({label,error:e.stack||String(e)});await route.abort('failed');}
   }
   await page.route(/\/rack3d\.html(?:\?[^#]*)?$/,r=>observe(r,HOOKS.page));
   await page.route(/\/assets\/scene-resources\.js(?:\?[^#]*)?$/,r=>observe(r,HOOKS.pool));
   const imageRoute=async route=>{
    try{
     assert.equal(new URL(route.request().url()).origin,BASE);
     if(fault.fail){stats.expected503.add(route.request().url());receipt.faults.push({label,url:route.request().url(),injected_status:503});await route.fulfill({status:503,contentType:'text/plain',body:'Intentional public panel failure fixture'});return;}
     if(fault.hold){
      const response=await route.fetch({maxRedirects:0});assert.equal(response.status(),200);const body=await response.body();
      const item=ITEMS.find(i=>new URL(route.request().url()).pathname==='/assets/panels/'+i.file+'.png');assert.ok(item);assert.equal(sha(body),item.sha);
      if(!fault.releaseAll)await new Promise(resolve=>{fault.waiters.push(resolve);releases.add(resolve);});
      await route.fulfill({response,body});return;
     }
     await route.fallback();
    }catch(e){receipt.route_errors.push({label,error:e.stack||String(e)});try{await route.abort('failed');}catch{}}
   };
   await page.route(/\/assets\/panels\/[^/]+\.png(?:\?[^#]*)?$/,imageRoute);
   return {page,context,stats,fault,imageRoute};
  }
  async function publicBytes(context,relative,file,kind){
   const url=new URL(relative,BASE);assert.equal(url.origin,BASE);
   const response=await context.request.get(url.href,{maxRedirects:0});assert.equal(response.status(),200,url.href);assert.equal(new URL(response.url()).origin,BASE);
   const bytes=await response.body();assert.ok(bytes.length);if(file)assert.equal(sha(bytes),sha(fs.readFileSync(path.join(ROOT,file))),url.href+' bytes/SHA');
   receipt[kind||'sources'].push({url:url.href,status:200,bytes:bytes.length,sha256:sha(bytes),observation_only:false});return bytes;
  }
  async function settle(page){await page.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(r))));});assert.deepEqual(receipt.route_errors,[]);}
  async function go(v,url,mode){const target=new URL(url,BASE);assert.equal(target.origin,BASE);const response=await v.page.goto(target.href,{waitUntil:'domcontentloaded'});assert.ok(response);assert.equal(response.status(),200);assert.equal(v.page.url(),target.href);await v.page.waitForFunction(()=>!!globalThis.__taPanels);await v.page.evaluate(()=>__taPanels.sceneModels.ready);await settle(v.page);if(mode)assert.equal(await v.page.evaluate(()=>__taPanels.readState().mode),mode);}
  async function controls(page){const d=page.locator('details[data-responsive-panel]');if(await d.count()&&!await d.evaluate(e=>e.open))await d.locator(':scope > summary').click();}
  async function main(page){return page.evaluate(()=>({camera:__taPanels.camera.position.toArray(),quaternion:__taPanels.camera.quaternion.toArray(),target:__taPanels.controls.target.toArray(),...__taPanels.readState()}));}
  async function panelReady(page,status='ready'){await page.waitForFunction(s=>Object.keys(__taPanels.PANEL).length===5&&Object.values(__taPanels.PANEL).every(h=>h.status()===s),status);const ready=await page.evaluate(()=>Promise.all(Object.values(__taPanels.PANEL).map(h=>h.ready())));assert.ok(ready.every(r=>r.status===status));}
  async function open(page){await controls(page);await page.locator('#panel-sources').click();await page.locator('.panel-source-dialog[open]').waitFor();await settle(page);}
  async function choose(page,item,status='ready'){await page.locator('.panel-source-dialog nav button[data-figure-id="'+item.id+'"]').click();await page.waitForFunction(({id,status})=>{const d=document.querySelector('.panel-source-dialog[open]');return d?.dataset.figureId===id&&d.dataset.sourceStatus===status;},{id:item.id,status});await settle(page);}
  async function close(page){await page.keyboard.press('Escape');await page.locator('.panel-source-dialog[open]').waitFor({state:'hidden'});await settle(page);}
  async function stage(page,n){await controls(page);const slider=page.locator('#explode');await slider.focus();await slider.press('Home');for(let k=0;k<n;k++)await slider.press('ArrowRight');await page.waitForFunction(n=>+document.getElementById('explode').value===n,n);await settle(page);}
  async function capture(page,name){const file=name+'.png';await page.screenshot({path:path.join(OUT,file),fullPage:true});receipt.views.push({file,review:'pending_original_size_human_review'});flush();}
  async function fullDialog(page,name){
   const d=page.locator('.panel-source-dialog[open]');await d.locator('h2').scrollIntoViewIfNeeded();await d.hover();await page.mouse.wheel(0,-100000);await settle(page);assert.ok(await d.evaluate(e=>e.scrollTop<=1),'Dialog screenshot coverage starts at top');let end=-1;
   for(let k=0;k<20;k++){
    const s=await d.evaluate(e=>({top:e.scrollTop,height:e.clientHeight,total:e.scrollHeight}));await capture(page,name+'-scroll-'+k);
    if(s.top+s.height>=s.total-2)return;
    assert.notEqual(s.top,end,'Actual dialog wheel must advance');end=s.top;await page.mouse.wheel(0,Math.max(100,Math.floor(s.height*.75)));await settle(page);
   }throw Error('Dialog content not fully covered '+name);
  }
  async function download(page,selector,name,expected){
   const before=await main(page);const pending=page.waitForEvent('download');await page.locator(selector).click();const d=await pending;assert.equal(await d.failure(),null);assert.equal(d.suggestedFilename(),name);
   const dest=path.join(OUT,name);await d.saveAs(dest);const b=fs.readFileSync(dest);assert.equal(sha(b),sha(expected));assert.equal(b.length,expected.length);sameMain(before,await main(page),'download '+name);
   receipt.downloads.push({file:name,bytes:b.length,sha256:sha(b),actual_UI_click:true});await page.waitForTimeout(300);
  }
  const normal=await makePage('normal');const page=normal.page;
  for(const name of ['panel-source-viewer','scene-atlas','scene-view',...Object.keys(ASSEMBLIES)])await publicBytes(normal.context,'/assets/'+name+'.js','web/components/'+name+'.js');
  const pngs={},svgs={};
  for(const item of ITEMS){
   pngs[item.key]=await publicBytes(normal.context,'/assets/panels/'+item.file+'.png','web/assets/panels/'+item.file+'.png','assets');assert.equal(sha(pngs[item.key]),item.sha);
   svgs[item.key]=await publicBytes(normal.context,'/assets/panels/display/'+item.file+'-contain.svg','web/assets/panels/display/'+item.file+'-contain.svg','displays');
  }
  await go(normal,'/rack3d.html?view=legacy&x=35','legacy-rack');await panelReady(page);
  for(const item of ITEMS){
   const data=await page.evaluate(({source,item})=>{
    const d=new DOMParser().parseFromString(source,'image/svg+xml');if(d.querySelector('parsererror'))throw Error('Invalid display SVG');
    const m=JSON.parse(d.querySelector('metadata').textContent),image=d.querySelector('image'),href=image?.getAttribute('href');
    return {metadata:m,title:d.querySelector('title')?.textContent,desc:d.querySelector('desc')?.textContent,viewBox:d.documentElement.getAttribute('viewBox'),imageFit:image?.getAttribute('preserveAspectRatio'),embedded:href?.split(',')[1],fill:d.querySelector('rect')?.getAttribute('fill')};
   },{source:svgs[item.key].toString('utf8'),item});
   assert.equal(data.metadata.figure_id,item.id);assert.equal(data.metadata.source_sha256,item.sha);assert.deepEqual(data.metadata.source_pixels,[item.width,item.height]);assert.equal(data.metadata.source,'web/assets/panels/'+item.file+'.png');
   assert.equal(data.metadata.fit,'contain');assert.equal(data.metadata.original_bytes_unchanged,true);assert.equal(data.metadata.not_static_master_or_cad,true);assert.equal(data.imageFit,'xMidYMid meet');assert.equal(data.fill,'#faf8f2');
   assert.ok(data.title.includes(item.id)&&data.desc.includes('不'));assert.equal(sha(Buffer.from(data.embedded,'base64')),item.sha);const vb=data.viewBox.split(/\s+/).map(Number);near(vb[2]/vb[3],item.aspect,item.id+' SVG face ratio');near(data.metadata.generic_surface_ratio[0]/data.metadata.generic_surface_ratio[1],item.aspect,item.id+' SVG metadata ratio');delete data.embedded;receipt.displays.push({item:item.id,...data});
  }
  async function inspect(item){
   const data=await page.evaluate(async({item,publicPNG})=>{
    const v=__taPanels,h=v.PANEL[item.key],t=h.texture,c=t.image,meta=t.userData.sourceDisplay;v.scene.updateMatrixWorld(true);
    const bindings=[];
    v.scene.traverse(mesh=>{if(!mesh.isMesh)return;[].concat(mesh.material||[]).forEach((m,mi)=>{
     if(m.map!==t)return;const g=mesh.geometry,group=g.groups.find(q=>q.materialIndex===mi);if(!group)throw Error('No material geometry group');
     const pos=g.getAttribute('position'),uv=g.getAttribute('uv'),corners=new Map();
     for(let n=group.start;n<group.start+group.count;n++){const i=g.index?g.index.getX(n):n;corners.set(uv.getX(i)+','+uv.getY(i),new v.THREE.Vector3().fromBufferAttribute(pos,i).applyMatrix4(mesh.matrixWorld));}
     const a=corners.get('0,0'),b=corners.get('1,0'),d=corners.get('0,1');if(!a||!b||!d)throw Error('Front UV unit quad unavailable');
     bindings.push({mesh:mesh.uuid,coordinateType:pos.array.constructor.name,materialIndex:mi,worldWidth:a.distanceTo(b),worldHeight:a.distanceTo(d),emissiveSame:m.emissiveMap===t,materialColor:m.color.getHex(),roughness:m.roughness,metalness:m.metalness,emissiveIntensity:m.emissiveIntensity});
    });});
    const ref=new Image();ref.src='data:image/png;base64,'+publicPNG;await ref.decode();
    if(!meta||!bindings.length)throw Error('No actual contained panel/front');
    const face=bindings[0].worldWidth/bindings[0].worldHeight,source=ref.naturalWidth/ref.naturalHeight;
    const target=document.createElement('canvas');target.width=c.width;target.height=c.height;const cx=target.getContext('2d');cx.fillStyle='#faf8f2';cx.fillRect(0,0,c.width,c.height);
    const nw=Math.min(1,source/face),nh=Math.min(1,face/source);cx.drawImage(ref,c.width*(1-nw)/2,c.height*(1-nh)/2,c.width*nw,c.height*nh);
    const actual=c.getContext('2d').getImageData(0,0,c.width,c.height).data,expected=cx.getImageData(0,0,c.width,c.height).data;
    let maxDiff=0,bad=0;for(let k=0;k<actual.length;k++){const diff=Math.abs(actual[k]-expected[k]);maxDiff=Math.max(maxDiff,diff);if(diff>2)bad++;}
    const hex=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
    return {status:h.status(),uuid:t.uuid,meta,bindings,pixels:[c.width,c.height],pixelDifference:{max:maxDiff,componentsOver2:bad,total:actual.length},pixel_sha256:await hex(actual),reference_sha256:await hex(expected),png:c.toDataURL('image/png'),repeat:t.repeat.toArray(),offset:t.offset.toArray(),rotation:t.rotation};
   },{item,publicPNG:pngs[item.key].toString('base64')});
   assert.equal(data.status,'ready');assert.equal(data.bindings.length,item.count);assert.equal(new URL(data.meta.url,BASE+'/rack3d.html').href,BASE+'/assets/panels/'+item.file+'.png');assert.equal(data.meta.fit,'contain');assert.equal(data.meta.background,'#faf8f2');
   assert.equal(data.meta.sourceWidth,item.width);assert.equal(data.meta.sourceHeight,item.height);assert.deepEqual(data.pixels,[data.meta.canvasWidth,data.meta.canvasHeight]);near(data.meta.surfaceAspect,item.aspect,item.id+' configured face');
   assert.deepEqual(data.repeat,[1,1]);assert.deepEqual(data.offset,[0,0]);assert.equal(data.rotation,0);
   const r=data.meta.rect;assert.ok(r.left>=-1e-8&&r.top>=-1e-8&&r.left+r.width<=data.pixels[0]+1e-8&&r.top+r.height<=data.pixels[1]+1e-8);near(r.left,(data.pixels[0]-r.width)/2,item.id+' center x');near(r.top,(data.pixels[1]-r.height)/2,item.id+' center y');
   for(const b of data.bindings){assert.equal(b.materialIndex,4);assert.equal(b.emissiveSame,true);assert.equal(b.coordinateType,'Float32Array');near(b.worldWidth/b.worldHeight,data.meta.surfaceAspect,item.id+' actual world face',data.meta.surfaceAspect*8*2**-23);near((r.width/data.pixels[0]*b.worldWidth)/(r.height/data.pixels[1]*b.worldHeight),item.width/item.height,item.id+' displayed source ratio',item.width/item.height*8*2**-23);}
   assert.ok(data.pixelDifference.max<=4&&data.pixelDifference.componentsOver2<=data.pixelDifference.total*.0001,item.id+' actual canvas differs from decoded public original contain');
   const filename=item.id+'-actual-texture.png';fs.writeFileSync(path.join(OUT,filename),Buffer.from(data.png.split(',')[1],'base64'));delete data.png;receipt.panels.push({item:item.id,file:filename,...data});return data;
  }
  const initial={};for(const item of ITEMS)initial[item.key]=await inspect(item);assert.equal(new Set(Object.values(initial).map(d=>d.uuid)).size,5);
  for(const width of [1280,390])for(const theme of ['light','dark']){
   await page.setViewportSize({width,height:width===390?844:900});await page.locator('#ui-appearance').selectOption(theme);await settle(page);
   await stage(page,0);await capture(page,'legacy0-'+width+'-'+theme);await stage(page,35);await capture(page,'legacy35-'+width+'-'+theme);
   const before=await main(page);await open(page);
   assert.equal(await page.locator('.panel-source-dialog nav button[data-figure-id]').count(),5);
   for(const item of ITEMS){
    await choose(page,item);const ui=await page.locator('.panel-source-dialog[open]').evaluate(e=>{const c=e.querySelector('canvas'),r=c.getBoundingClientRect(),s=getComputedStyle(c);return {figure:e.dataset.figureId,status:e.dataset.sourceStatus,text:e.innerText,pressed:[...e.querySelectorAll('nav button[aria-pressed="true"]')].map(b=>b.dataset.figureId),boxSizing:s.boxSizing,transform:s.transform,padding:[s.paddingLeft,s.paddingRight,s.paddingTop,s.paddingBottom].map(parseFloat),pixels:[c.width,c.height],content:[r.width-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth),r.height-parseFloat(s.borderTopWidth)-parseFloat(s.borderBottomWidth)],png:c.toDataURL('image/png')};});
    assert.equal(ui.figure,item.id);assert.equal(ui.status,'ready');assert.deepEqual(ui.pressed,[item.id]);for(const text of [item.title,item.model,item.file+'.png','原始PNG不裁切','不表示三维机箱相符','现场配置、数量和安装规格未知','来源已载入'])assert.ok(ui.text.includes(text),item.id+' visible caption '+text);
    if(item.key==='hero')assert.ok(ui.text.includes('文件名不证明GPU配置'));if(item.key==='ib')assert.ok(ui.text.includes('文件名ib不认证InfiniBand'));
    assert.deepEqual(ui.pixels,initial[item.key].pixels);assert.equal(ui.boxSizing,'content-box');assert.equal(ui.transform,'none');assert.deepEqual(ui.padding,[0,0,0,0]);near(ui.content[1],ui.content[0]/item.aspect,item.id+' actual dialog CSS content height',1/64+1e-7);
    const actualTexture=fs.readFileSync(path.join(OUT,item.id+'-actual-texture.png'));assert.equal(sha(Buffer.from(ui.png.split(',')[1],'base64')),sha(actualTexture),'Actual dialog copies actual CanvasTexture');
    delete ui.png;receipt.dialogs.push({item:item.id,width,theme,...ui});await fullDialog(page,item.id+'-'+width+'-'+theme);
    if(width===1280&&theme==='light'){
     const raw='.panel-source-actions a[download][href$="/'+item.file+'.png"]',svg='.panel-source-actions a[download][href$="/'+item.file+'-contain.svg"]';
     assert.equal(await page.locator(raw).getAttribute('href'),'/assets/panels/'+item.file+'.png');assert.equal(await page.locator(svg).getAttribute('href'),'/assets/panels/display/'+item.file+'-contain.svg');
     await download(page,raw,item.file+'.png',pngs[item.key]);await download(page,svg,item.file+'-contain.svg',svgs[item.key]);
     const uuid=await page.evaluate(key=>__taPanels.PANEL[key].texture.uuid,item.key);await page.locator('.panel-source-actions button').click();await page.waitForFunction(key=>__taPanels.PANEL[key].status()==='ready'&&document.querySelector('.panel-source-dialog').dataset.sourceStatus==='ready',item.key);await settle(page);assert.equal(await page.evaluate(key=>__taPanels.PANEL[key].texture.uuid,item.key),uuid);await inspect(item);
    }
    sameMain(before,await main(page),'dialog '+item.id);
   }
   await close(page);sameMain(before,await main(page),'Escape closes panel only');assert.equal(await page.evaluate(()=>document.activeElement?.id),'panel-sources');
  }
  function cleanNetwork(v){
   for(const x of v.stats.responses){const u=new URL(x.url);assert.equal(u.origin,BASE);if(u.pathname.startsWith('/assets/')){if(v.stats.expected503.has(x.url)&&x.status===503)continue;assert.equal(x.status,200,'Declared public resource '+x.url);}}
   assert.ok(v.stats.failures.every(x=>x.expected_fault),'Unexpected public request failure '+v.stats.label);
   receipt.network_failures.push(...v.stats.failures);assert.deepEqual(receipt.route_errors,[]);assert.deepEqual(receipt.errors,[]);
  }
  cleanNetwork(normal);
  await normal.context.close();contexts.delete(normal.context);
  for(const m of [
   {url:'/rack3d.html',mode:'rack',pickables:598},
   {url:'/rack3d.html?view=rack&x=0',mode:'rack',pickables:598},
   {url:'/rack3d.html?view=rack-exploded&x=35',mode:'rack-exploded',pickables:611},
   {url:'/rack3d.html?view=server&x=55',mode:'server',pickables:1129},
   {url:'/rack3d.html?view=chip&x=90',mode:'chip',pickables:1049}
  ]){
   const v=await makePage('modern '+m.mode);await go(v,m.url,m.mode);await settle(v.page);
   const actual=await v.page.evaluate(()=>({keys:Object.keys(__taPanels.PANEL),pickables:__taPanels.pickables.length,buttonHidden:document.getElementById('panel-sources').hidden,dialogs:document.querySelectorAll('.panel-source-dialog').length,mode:__taPanels.readState().mode}));
   assert.deepEqual(actual.keys,[]);assert.equal(actual.pickables,m.pickables);assert.equal(actual.buttonHidden,true);assert.equal(actual.dialogs,0);
   assert.equal(v.stats.requests.filter(r=>/\/assets\/panels\/[^/]+\.png(?:\?|$)/.test(r.url)).length,0,'Modern must not request original panel images');cleanNetwork(v);receipt.modern.push({url:m.url,...actual,source_assembly_SHA_preserved:true});await v.context.close();contexts.delete(v.context);flush();
  }
  const failed=await makePage('intentional panel failure',{fail:true,hold:false,waiters:[]});await go(failed,'/rack3d.html?view=legacy&x=35','legacy-rack');await panelReady(failed.page,'fallback');await open(failed.page);
  const fallbackIds={};
  for(const item of ITEMS){await choose(failed.page,item,'fallback');const d=await failed.page.evaluate(key=>{const h=__taPanels.PANEL[key],c=h.texture.image;return {uuid:h.texture.uuid,status:h.status(),pixels:[c.width,c.height],corner:[...c.getContext('2d').getImageData(0,0,1,1).data],meta:h.texture.userData.sourceDisplay||null,nonBackgroundPixels:[...c.getContext('2d').getImageData(0,0,c.width,c.height).data].filter((x,i)=>i%4!==3&&x!==[17,24,39][i%4]).length,caption:document.querySelector('.panel-source-dialog').innerText};},item.key);assert.equal(d.status,'fallback');assert.deepEqual(d.pixels,[256,64]);assert.deepEqual(d.corner,[17,24,39,255]);assert.equal(d.meta,null);assert.ok(d.nonBackgroundPixels>0);assert.ok(d.caption.includes('程序化占位前脸')&&d.caption.includes('不作为真实面板'));fallbackIds[item.key]=d.uuid;receipt.faults.push({item:item.id,...d});}
  failed.fault.fail=false;await failed.page.unroute(/\/assets\/panels\/[^/]+\.png(?:\?[^#]*)?$/,failed.imageRoute);
  for(const item of ITEMS){await choose(failed.page,item,'fallback');await failed.page.locator('.panel-source-actions button').click();await failed.page.waitForFunction(key=>__taPanels.PANEL[key].status()==='ready'&&document.querySelector('.panel-source-dialog').dataset.sourceStatus==='ready',item.key);await settle(failed.page);const d=await failed.page.evaluate(key=>({uuid:__taPanels.PANEL[key].texture.uuid,meta:__taPanels.PANEL[key].texture.userData.sourceDisplay,png:__taPanels.PANEL[key].texture.image.toDataURL('image/png')}),item.key);assert.equal(d.uuid,fallbackIds[item.key]);assert.equal(d.meta.fit,'contain');assert.equal(sha(Buffer.from(d.png.split(',')[1],'base64')),sha(fs.readFileSync(path.join(OUT,item.id+'-actual-texture.png'))),'Recovered actual texture pixels');delete d.png;receipt.faults.push({item:item.id,recovery:'real_UI_retry_after_unroute',...d});}
  await close(failed.page);cleanNetwork(failed);await failed.context.close();contexts.delete(failed.context);
  const life=await makePage('resource boundaries',{fail:false,hold:false,waiters:[]});await go(life,'/rack3d.html?view=legacy&x=35','legacy-rack');await panelReady(life.page);await open(life.page);
  await life.page.evaluate(()=>{const v=__taPanels;globalThis.__panelProbe={events:Object.fromEntries(Object.keys(v.PANEL).map(k=>[k,0])),images:[],renderer:0,composer:0,renders:0};for(const[k,h]of Object.entries(v.PANEL))h.texture.addEventListener('dispose',()=>__panelProbe.events[k]++);const rd=v.renderer.dispose.bind(v.renderer),cd=v.composer.dispose.bind(v.composer),render=v.composer.render.bind(v.composer);v.renderer.dispose=(...a)=>{__panelProbe.renderer++;return rd(...a);};v.composer.dispose=(...a)=>{__panelProbe.composer++;return cd(...a);};v.composer.render=(...a)=>{__panelProbe.renders++;return render(...a);};});
  life.fault.hold=true;life.fault.lifecycle=true;
  await life.page.evaluate(()=>{__panelProbe.p1=__taPanels.PANEL.server.retry();__panelProbe.images=[...__taPanels.texturePool.observeForTest().images];});
  await life.page.waitForFunction(()=>__taPanels.texturePool.observeForTest().images.length>0);for(let k=0;life.fault.waiters.length===0;k++){assert.ok(k<300,'Actual held public response deadline');await life.page.waitForTimeout(100);}
  await life.page.evaluate(()=>{__panelProbe.p2=__taPanels.PANEL.server.retry();__panelProbe.allImages=[...new Set([...__panelProbe.images,...__taPanels.texturePool.observeForTest().images])];});
  const superseded=await life.page.evaluate(async()=>({first:await __panelProbe.p1,obsolete:__panelProbe.images.map(i=>({retained:__taPanels.texturePool.observeForTest().images.includes(i),load:i.onload!==null,error:i.onerror!==null}))}));
  assert.equal(superseded.first.status,'superseded');assert.ok(superseded.obsolete.every(i=>!i.retained&&!i.load&&!i.error),'Superseded real Image attempts must detach callbacks immediately');receipt.resources.push({kind:'overlapping_real_retry',...superseded});
  const terminal=await life.page.evaluate(async()=>{const v=__taPanels,p=__panelProbe,h=v.PANEL.server,t=h.texture,before={version:t.version,events:p.events.server};h.dispose();h.dispose();const r=await h.retry(),pool=v.texturePool.observeForTest();return {retry:r,second:await p.p2,status:h.status(),version:t.version,before,events:p.events.server,pool:{images:pool.images.length,handles:pool.handles.length,textures:pool.textures.includes(t)},obsolete:p.images.map(i=>({load:i.onload!==null,error:i.onerror!==null}))};});
  assert.equal(terminal.retry.status,'disposed');assert.equal(terminal.second.status,'disposed');assert.equal(terminal.status,'disposed');assert.equal(terminal.version,terminal.before.version);assert.equal(terminal.events,terminal.before.events+1);assert.equal(terminal.pool.images,0);assert.equal(terminal.pool.handles,4);assert.equal(terminal.pool.textures,false);assert.ok(terminal.obsolete.every(i=>!i.load&&!i.error));receipt.resources.push({kind:'handle_terminal_retry',...terminal});
  const poolPending=await life.page.evaluate(()=>{const p=__panelProbe,v=__taPanels,h=v.PANEL.hero;p.p3=h.retry();p.poolImages=[...v.texturePool.observeForTest().images];p.allImages=[...new Set([...p.allImages,...p.poolImages])];return {status:h.status(),images:p.poolImages.length,complete:p.poolImages.map(i=>i.complete),version:h.texture.version};});
  assert.equal(poolPending.status,'loading');assert.equal(poolPending.images,1);assert.ok(poolPending.complete.every(v=>!v));
  const poolCancelled=await life.page.evaluate(async()=>{const p=__panelProbe,v=__taPanels;v.texturePool.dispose();v.texturePool.dispose();v.panelSources.dispose();v.panelSources.dispose();return {result:await p.p3,status:v.PANEL.hero.status(),version:v.PANEL.hero.texture.version,images:v.texturePool.observeForTest().images.length,callbacks:p.poolImages.map(i=>({load:i.onload!==null,error:i.onerror!==null}))};});
  assert.equal(poolCancelled.result.status,'disposed');assert.equal(poolCancelled.status,'disposed');assert.equal(poolCancelled.images,0);assert.equal(poolCancelled.version,poolPending.version);assert.ok(poolCancelled.callbacks.every(i=>!i.load&&!i.error));receipt.resources.push({kind:'pool_dispose_with_actual_pending_image',before:poolPending,...poolCancelled});
  life.fault.releaseAll=true;life.fault.hold=false;for(const resolve of life.fault.waiters.splice(0)){resolve();releases.delete(resolve);}await life.page.waitForFunction(()=>__panelProbe.allImages.every(i=>i.complete));await settle(life.page);
  const final=await life.page.evaluate(async()=>{const v=__taPanels,p=__panelProbe,before=p.renders;v.disposePage();v.disposePage();const at=p.renders;await new Promise(r=>setTimeout(r,100));const pool=v.texturePool.observeForTest();return {before,rendersAfter:p.renders-at,renderer:p.renderer,composer:p.composer,events:p.events,pool:{disposed:pool.disposed,textures:pool.textures.length,images:pool.images.length,handles:pool.handles.length},buttonHidden:document.getElementById('panel-sources').hidden,dialogs:document.querySelectorAll('.panel-source-dialog').length,viewerStyles:[...document.head.querySelectorAll('style')].filter(e=>e.textContent.includes('.panel-source-dialog')).length,pageDisposed:v.readState().pageDisposed,version:v.PANEL.server.texture.version,heroVersion:v.PANEL.hero.texture.version,obsolete:p.images.map(i=>({load:i.onload!==null,error:i.onerror!==null}))};});
  assert.equal(final.rendersAfter,0);assert.equal(final.renderer,1);assert.equal(final.composer,1);assert.equal(final.pool.disposed,true);for(const k of ['textures','images','handles'])assert.equal(final.pool[k],0);assert.ok(Object.values(final.events).every(n=>n===1));assert.equal(final.dialogs,0);assert.equal(final.viewerStyles,0);assert.equal(final.buttonHidden,true);assert.equal(final.pageDisposed,true);assert.equal(final.version,terminal.version);assert.equal(final.heroVersion,poolPending.version);assert.ok(final.obsolete.every(i=>!i.load&&!i.error));receipt.resources.push({kind:'pool_viewer_page_dispose_twice',...final});cleanNetwork(life);await life.context.close();contexts.delete(life.context);
  assert.equal(receipt.downloads.length,10);assert.equal(receipt.modern.length,5);assert.deepEqual(receipt.errors,[]);assert.deepEqual(receipt.route_errors,[]);
  receipt.stage='MACHINE_CHECKS_PASSED_VISUAL_REVIEW_PENDING';receipt.visual_review='pending actual original-size owner review';flush();console.log(JSON.stringify({stage:receipt.stage,output:OUT,downloads:receipt.downloads.length,panels:receipt.panels.length,views:receipt.views.length}));
 }catch(e){receipt.stage='FAILED';receipt.failure=e.stack||String(e);flush();console.error(receipt.failure);process.exitCode=1;}
 finally{for(const resolve of releases)resolve();for(const c of contexts){try{await c.close();}catch{}}if(browser)await browser.close();flush();}
})();
