/* TA35 actual-public-only candidate. Never executed by its author.
 * UI_BASE_URL=https://inresearch.ai TA_CROSS_SCALE_SOURCE_ROOT=/absolute/reviewed/tree
 * REVIEW_SCREENSHOTS=/absolute/output UI_HEADED=1 node /private/tmp/ta35-public-fixture-child.cjs
 * Local files supply byte identities only. All product execution is the actual HTTPS site.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');
const BASE = 'https://inresearch.ai';
const ROOT = process.env.TA_CROSS_SCALE_SOURCE_ROOT;
const OUT = process.env.REVIEW_SCREENSHOTS || '/private/tmp/ta35-public-' + Date.now();
assert.ok(path.isAbsolute(OUT), 'Output must be absolute');
fs.mkdirSync(OUT, {recursive:true});
const receiptPath = path.join(OUT, 'ta35-results.json');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const result = {
  figure:'TA-35', status:'RUNNING', observed_at:new Date().toISOString(), finished_at:null,
  scope_proof:{required_origin:BASE, source_root:ROOT || null, local_fallback:false,
    local_product_server:false, source_execution:false, observation_injection:false,
    service_workers:'block', anonymous_fresh_context:true, browser_requests:[]},
  stages:[], sources:[], declared_resources:[], documents:[], views:[], readable_lists:[], downloads:[],
  full_svgs:[], font_checks:[], related:[], errors:[], route_errors:[], resource_failures:[],
  request_failures:[], request_failure_snapshots:{}, not_verified:['Navigation smoke does not reaccept old geometry, lifecycle or visual quality.',
    'ERR_ABORTED remains in raw records; it is only expected at real navigation/page-destruction boundaries, never as an HTTP/resource-error exemption.',
    'Screenshots require a separate actual-original human review before publication.']
};
let browser, context, page, currentStage;
const writeReceipt = () => fs.writeFileSync(receiptPath, JSON.stringify(result,null,2)+'\n');
writeReceipt();
async function stage(name, action) {
  currentStage=name;
  const row={name,status:'RUNNING',started_at:new Date().toISOString()}; result.stages.push(row); writeReceipt();
  try {await action(); row.status='PASS';}
  catch(error) {row.status='FAIL'; row.error={name:error.name,message:error.message,stack:error.stack}; throw error;}
  finally {row.finished_at=new Date().toISOString(); writeReceipt();}
}
const related = [
  {id:'TA-15',href:'/rack3d.html?x=90',type:'3D',title:'芯片封装独立近景'},
  {id:'TA-11',href:'/rack3d.html?x=55',type:'3D',title:'服务器整机拆解台'},
  {id:'TA-13',href:'/rack3d.html?x=0',type:'3D',title:'机柜整柜结构图'},
  {id:'TA-18',href:'/bom3d.html',type:'3D',title:'园区装配全景'},
  {id:'TA-22',href:'/power-atlas.html',type:'static'},
  {id:'TA-23',href:'/thermal-atlas.html',type:'static'}
];
const expectedStages=['preflight','public_source_and_declared_resources','visible_bom_entry',
  'new_atlas_and_four_views','mobile360_header','two_real_downloads',
  'full_svg_native_and_own_fonts','preview_svg_own_fonts',...related.map(r=>'related_'+r.id),'final_gates'];

(async()=>{
  let passed=false;
  try {
    let routes, manifest, labels, fontProof, requireSource, PNG;
    await stage('preflight',async()=>{
      assert.equal(process.env.UI_BASE_URL,BASE,'Only the actual public HTTPS origin is authorized');
      assert.ok(ROOT && path.isAbsolute(ROOT),'TA_CROSS_SCALE_SOURCE_ROOT must be explicit and absolute');
      assert.ok(fs.statSync(ROOT).isDirectory());
      routes=JSON.parse(fs.readFileSync(path.join(ROOT,'web/routes.json'),'utf8'));
      const doc='docs/design/technical-atlas/TA-35/';
      manifest=JSON.parse(fs.readFileSync(path.join(ROOT,doc+'asset-manifest-v1.json'),'utf8'));
      labels=JSON.parse(fs.readFileSync(path.join(ROOT,doc+'labels-v1.json'),'utf8')).labels;
      fontProof=JSON.parse(fs.readFileSync(path.join(ROOT,doc+'font-subset-proof-v1.json'),'utf8'));
      assert.equal(manifest.figure_id,'TA-35'); assert.equal(labels.length,7);
      assert.deepEqual(labels.map(l=>l.number).sort(),['01','02','03','04','05','06','07']);
      for(const asset of manifest.assets){const b=fs.readFileSync(path.join(ROOT,asset.file));assert.equal(b.length,asset.bytes);assert.equal(hash(b),asset.sha256);}
      result.source_manifest={file:path.join(ROOT,doc+'asset-manifest-v1.json'),sha256:hash(fs.readFileSync(path.join(ROOT,doc+'asset-manifest-v1.json')))};
      requireSource=createRequire(path.join(ROOT,'package.json'));
      ({PNG}=requireSource('pngjs'));
      const {chromium}=requireSource('playwright');
      browser=await chromium.launch({headless:process.env.UI_HEADED!=='1'});
      context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,
        reducedMotion:'reduce',acceptDownloads:true,serviceWorkers:'block'});
      context.setDefaultTimeout(30000); context.setDefaultNavigationTimeout(45000);
      await context.route('**/*',async route=>{
        const url=route.request().url();
        try {assert.equal(new URL(url).origin,BASE,'Off-origin browser request blocked');result.scope_proof.browser_requests.push(url);await route.continue();}
        catch(error){result.route_errors.push({url,message:error.message});await route.abort('blockedbyclient');}
      });
      context.on('page',p=>p.on('pageerror',error=>result.errors.push({url:p.url(),message:error.message})));
      context.on('response',response=>{
        const url=response.url(),request=response.request();
        if(request.isNavigationRequest() && request.resourceType()==='document')result.documents.push({url,status:response.status()});
        if(new URL(url).pathname.startsWith('/assets/') && response.status()>=400)result.resource_failures.push({url,status:response.status()});
      });
      context.on('requestfailed',request=>result.request_failures.push({url:request.url(),resource_type:request.resourceType(),stage:currentStage,navigation_request:request.isNavigationRequest(),failure:request.failure()?.errorText}));
      page=await context.newPage();
    });

    const publicURL = value => {const u=new URL(value,BASE);assert.equal(u.origin,BASE);assert.equal(u.protocol,'https:');return u.href;};
    const publicBytes=new Map();
    async function strictGet(value) {
      const url=publicURL(value);if(publicBytes.has(url))return publicBytes.get(url);
      const response=await context.request.get(url,{maxRedirects:0,timeout:45000});
      assert.equal(response.status(),200,'Strict public GET '+url);assert.equal(response.url(),url);
      const bytes=await response.body();assert.ok(bytes.length,'Nonempty public resource '+url);
      const rel=routes[new URL(url).pathname];assert.ok(rel,'Declared resource must map to reviewed source '+url);
      const local=path.resolve(ROOT,rel);assert.ok(local.startsWith(path.resolve(ROOT)+path.sep));
      assert.equal(hash(bytes),hash(fs.readFileSync(local)),'Actual public/source byte identity '+url);
      const entry={url,bytes};publicBytes.set(url,entry);
      result.sources.push({url,status:200,bytes:bytes.length,sha256:hash(bytes),local_source:local});return entry;
    }
    const scanned=new Set();
    async function declaredTree(value,importMap={}) {
      const resource=await strictGet(value);if(scanned.has(resource.url))return;scanned.add(resource.url);
      result.declared_resources.push({url:resource.url,status:200,sha256:hash(resource.bytes)});
      const pathname=new URL(resource.url).pathname;
      if(!/\.(?:html|js|css)$/.test(pathname))return;
      const text=resource.bytes.toString('utf8'),deps=[];
      let imports={...importMap};
      if(pathname.endsWith('.html')){
        for(const m of text.matchAll(/<script\b[^>]*type=["']importmap["'][^>]*>([\s\S]*?)<\/script>/g)){
          for(const [key,val] of Object.entries(JSON.parse(m[1]).imports||{}))imports[key]=new URL(val,resource.url).href;
        }
        for(const m of text.matchAll(/<(?:script|link)\b[^>]+(?:src|href)=["']([^"']+)["']/g))deps.push({value:m[1],kind:'resource'});
      }
      if(pathname.endsWith('.css'))for(const m of text.matchAll(/url\(\s*["']?([^\s"')]+)["']?\s*\)/g))deps.push({value:m[1],kind:'resource'});
      const scripts=pathname.endsWith('.html')?[...text.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]):pathname.endsWith('.js')?[text]:[];
      for(const script of scripts){
        const code=script.replace(/\/\*[\s\S]*?\*\//g,'').replace(/^\s*\/\/.*$/gm,'');
        for(const m of code.matchAll(/^\s*(?:import\b\s*(?!\()|export\s+(?:\*|\{))[^;]*?\bfrom\s*["']([^"']+)["']/gm))deps.push({value:m[1],kind:'module'});
        for(const m of code.matchAll(/(?:^\s*import\s*|\bimport\s*\(\s*)["']([^"']+)["']/gm))deps.push({value:m[1],kind:'module'});
      }
      for(const {value:dep,kind} of deps){
        if(dep.startsWith('data:')||dep.startsWith('#'))continue;
        const mapped=imports[dep];
        if(kind==='module'&&!mapped&&!/^(?:\.?\.?\/|https?:)/.test(dep))throw Error('Unresolved declared module '+dep+' in '+resource.url);
        await declaredTree(mapped||new URL(dep,resource.url).href,imports);
      }
    }
    async function settle(p) {await p.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(r))));});}
    function noErrors(){assert.deepEqual(result.errors,[]);assert.deepEqual(result.route_errors,[]);assert.deepEqual(result.resource_failures,[]);}
    async function readyAtlas(p,id) {
      const atlas=p.locator('.technical-atlas[data-figure="'+id+'"]');await atlas.waitFor({state:'visible'});
      await atlas.locator('img').evaluate(async image=>{await image.decode();if(!image.complete||image.naturalWidth!==1536||image.naturalHeight!==1024)throw Error('Actual atlas image must decode at native1536x1024');});
      await p.waitForFunction(()=>{const a=document.querySelector('.technical-atlas figure>a');return a&&getComputedStyle(a).backgroundColor==='rgb(250, 249, 242)';});
      await settle(p);noErrors();return atlas;
    }
    async function gotoDocument(p,value){const url=publicURL(value),response=await p.goto(url,{waitUntil:'domcontentloaded'});assert.ok(response,'New-document navigation must return its response');assert.equal(response.status(),200,url);assert.equal(p.url(),url);return response;}
    async function linkDocument(p,link,expected,popup) {
      const url=publicURL(expected);assert.equal(await link.getAttribute('href'),expected);
      await link.scrollIntoViewIfNeeded();assert.equal(await link.isVisible(),true);
      let target=p;
      if(popup){const pending=p.waitForEvent('popup');await link.click();target=await pending;await target.waitForLoadState('domcontentloaded');}
      else {const pending=p.waitForURL(url,{waitUntil:'domcontentloaded'});await link.click();await pending;}
      assert.equal(target.url(),url);
      assert.ok(result.documents.some(d=>d.url===url&&d.status===200),'Actual link document must have HTTP200 '+url);
      return target;
    }
    async function save(p,name,details={},fullPage=true){const target=path.join(OUT,name);await p.screenshot({path:target,fullPage});result.views.push({file:target,...details});return target;}

    await stage('public_source_and_declared_resources',async()=>{
      for(const route of ['/cross-scale-atlas.html','/bom.html',...related.map(r=>r.href)])await declaredTree(route);
      for(const a of manifest.assets){const route=Object.keys(routes).find(key=>routes[key]===a.file);assert.ok(route);const got=await strictGet(route);assert.equal(got.bytes.length,a.bytes);assert.equal(hash(got.bytes),a.sha256);}
      for(const original of JSON.parse(fs.readFileSync(path.join(ROOT,'docs/design/technical-atlas/TA-35/component-manifest-v1.json'),'utf8')).components){
        const got=await strictGet('/assets/technical-atlas/'+original.file);assert.equal(got.bytes.length,original.bytes);assert.equal(hash(got.bytes),original.sha256);
      }
      for(const font of fontProof.fonts)await strictGet(Object.keys(routes).find(key=>routes[key]===font.original_file));
    });
    await stage('visible_bom_entry',async()=>{
      await gotoDocument(page,'/bom.html');await page.locator('[data-atlas-cross-scale]').waitFor({state:'visible'});
      await linkDocument(page,page.locator('[data-atlas-cross-scale]'),'/cross-scale-atlas.html',false);
    });
    let atlas;
    await stage('new_atlas_and_four_views',async()=>{
      atlas=await readyAtlas(page,'TA-35');assert.equal(await page.locator('.technical-atlas').count(),1);
      assert.equal(await atlas.locator('img').getAttribute('src'),'/assets/technical-atlas/cross-scale-v1-preview.svg');
      assert.equal(await atlas.locator('details li').count(),7);
      const details=atlas.locator('details');if(!await details.evaluate(element=>element.open))await details.locator(':scope>summary').click();
      const rows=await atlas.locator('details li').allTextContents();rows.forEach((t,i)=>assert.ok(t.startsWith(String(i+1).padStart(2,'0'))));
      const caption=await atlas.locator('figcaption').textContent();assert.match(caption,/不同通用例型/);assert.match(caption,/非同一套设备或共同实物比例/);assert.match(caption,/另一选定方案/);assert.match(caption,/风冷机箱/);
      assert.equal(await atlas.locator('a[data-related-figure]').count(),6);
      for(const width of [1280,390])for(const theme of ['light','dark']){
        await page.setViewportSize({width,height:width===390?844:900});await page.locator('#ui-appearance').selectOption(theme);await settle(page);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
        const visibleList=await atlas.locator('details li').evaluateAll(elements=>elements.map(element=>{const box=element.getBoundingClientRect(),style=getComputedStyle(element),range=document.createRange();range.selectNodeContents(element);return{text:element.textContent,fontSize:parseFloat(style.fontSize),visible:element.closest('details').open&&style.display!=='none'&&style.visibility!=='hidden'&&box.width>0&&box.height>0,left:box.left,right:box.right,text_rects:[...range.getClientRects()].map(r=>({left:r.left,right:r.right})),viewport:innerWidth};}));
        assert.equal(visibleList.length,7);for(const li of visibleList){assert.ok(li.visible&&li.fontSize>=14);assert.ok(li.left>=0&&li.right<=width);assert.ok(li.text_rects.every(r=>r.left>=0&&r.right<=width));}
        result.readable_lists.push({width,theme,labels:visibleList});
        assert.equal(await atlas.locator('figure>a').evaluate(a=>getComputedStyle(a).backgroundColor),'rgb(250, 249, 242)');
        await page.evaluate(()=>scrollTo(0,0));await save(page,'cross-scale-'+width+'-'+theme+'.png',{kind:'static',width,theme});
      }
    });
    await stage('mobile360_header',async()=>{
      await page.setViewportSize({width:360,height:844});await settle(page);
      const bounds=await page.locator('#ui-skinbar').boundingBox();assert.ok(bounds&&bounds.height<=86,'360px header <=86px');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));result.header360=bounds;
      await page.evaluate(()=>scrollTo(0,0));await save(page,'cross-scale-360-header.png',{kind:'mobile_header',width:360});
    });
    await stage('two_real_downloads',async()=>{
      for(const [name,suffix] of [['下载标注图','.svg'],['下载无字底图','.png']]){
        const link=atlas.getByRole('link',{name,exact:true}),href=await link.getAttribute('href');assert.equal(new URL(href,BASE).origin,BASE);
        const pending=page.waitForEvent('download');await link.click();const download=await pending;assert.equal(await download.failure(),null);
        assert.equal(download.suggestedFilename(),'cross-scale-v1'+suffix);
        const target=path.join(OUT,download.suggestedFilename());await download.saveAs(target);const bytes=fs.readFileSync(target);
        const expected=manifest.assets.find(a=>path.basename(a.file)===download.suggestedFilename());assert.ok(expected);assert.equal(bytes.length,expected.bytes);assert.equal(hash(bytes),expected.sha256);
        result.downloads.push({name,file:target,bytes:bytes.length,sha256:hash(bytes)});
        await page.waitForTimeout(250); // Retain established real-browser continuous-download spacing.
      }
    });

    async function inspectSVG(p,route,kind) {
      const response=await gotoDocument(p,route);const bytes=await response.body(),expected=manifest.assets.find(a=>routes[route]===a.file);
      assert.ok(expected);assert.equal(bytes.length,expected.bytes);assert.equal(hash(bytes),expected.sha256);
      await p.setViewportSize({width:1536,height:1024});
      const root=p.locator('svg').first();assert.equal(await root.getAttribute('viewBox'),'0 0 1536 1024');assert.equal(await root.getAttribute('width'),'1536');assert.equal(await root.getAttribute('height'),'1024');
      const fontURIs=await p.locator('style').allTextContents();const embeddedFonts=[];
      for(const css of fontURIs)for(const match of css.matchAll(/url\(["']?(data:font\/woff2;base64,[A-Za-z0-9+/=]+)/g)){
        const b=Buffer.from(match[1].split(',')[1],'base64'),digest=hash(b),font=fontProof.fonts.find(f=>f.subset_sha256===digest);assert.ok(font,'Embedded font belongs to proof');assert.equal(b.length,font.bytes);embeddedFonts.push({family:font.family,bytes:b.length,sha256:digest});
      }
      assert.equal(embeddedFonts.length,3);
      const licenses=JSON.parse(await p.locator('metadata#embedded-font-licenses').textContent());
      for(const license of ['web/assets/fonts/LICENSE-Inter.txt','web/assets/fonts/LICENSE-NotoSansSC.txt'])assert.equal(licenses.licenses[license],fs.readFileSync(path.join(ROOT,license),'utf8'));
      const observed=await p.evaluate(async()=>{
        const texts=[...document.querySelectorAll('text')],sample=texts.map(e=>e.textContent).join('');
        await document.fonts.load('400 16px "Inter"',sample);await document.fonts.load('700 22px "Inter"',sample);
        await document.fonts.load('400 16px "Noto Sans SC"',sample);await document.fonts.load('700 22px "Noto Sans SC"',sample);await document.fonts.ready;
        const faces=[...document.fonts].map(f=>({family:f.family,status:f.status,weight:f.weight}));
        const images=await Promise.all([...document.querySelectorAll('image')].map(async element=>{const href=element.getAttribute('href')||element.getAttributeNS('http://www.w3.org/1999/xlink','href');const image=new Image();image.src=href;await image.decode();return{href,width:image.naturalWidth,height:image.naturalHeight};}));
        const boxes=texts.map(e=>{const b=e.getBBox();return{text:e.textContent,x:b.x,y:b.y,w:b.width,h:b.height,fontSize:+e.getAttribute('font-size')};});
        const overlaps=[];for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){const a=boxes[i],b=boxes[j];if(Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)&&Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y))overlaps.push({a:a.text,b:b.text});}
        function intersects(a,b,rect){let low=0,high=1;const dx=b[0]-a[0],dy=b[1]-a[1],q=[a[0]-rect.x,rect.x+rect.w-a[0],a[1]-rect.y,rect.y+rect.h-a[1]],v=[-dx,dx,-dy,dy];for(let i=0;i<4;i++){if(v[i]===0){if(q[i]<0)return false;}else{const t=q[i]/v[i];if(v[i]<0)low=Math.max(low,t);else high=Math.min(high,t);if(low>high)return false;}}return true;}
        const hits=[],paths=[];
        for(const element of document.querySelectorAll('path')){
          const d=element.getAttribute('d')||'';if(/[A-KN-Za-kn-z]/.test(d))throw Error('Unreviewed non-M/L path syntax in static fixture');
          const segments=[];let previous=null;
          for(const m of d.matchAll(/([ML])([^ML]+)/g)){const values=m[2].trim().split(/[\s,]+/).map(Number);if(values.length%2)throw Error('Odd path coordinate list');for(let i=0;i<values.length;i+=2){const point=[values[i],values[i+1]];if(m[1]==='L'||i>0){if(!previous)throw Error('Path starts without M');segments.push([previous,point]);}previous=point;}}
          const name=element.getAttribute('data-flow')||element.closest('.callout')?.getAttribute('data-label')||'arrow/wall';paths.push({name,d});
          for(const segment of segments)for(const box of boxes)if(intersects(segment[0],segment[1],box))hits.push({path:name,text:box.text});
        }
        return{faces,fontsReady:document.fonts.status,images,boxes,overlaps,hits,paths,
          labels:[...document.querySelectorAll('.callout')].map(g=>({number:g.getAttribute('data-label'),part:g.getAttribute('data-object'),x:+g.querySelector('circle').getAttribute('cx'),y:+g.querySelector('circle').getAttribute('cy')})),
          fontChecks:{Inter:document.fonts.check('700 22px "Inter"','GPU/HBM'),Noto:document.fonts.check('400 16px "Noto Sans SC"',sample)}};
      });
      assert.equal(observed.fontsReady,'loaded');assert.equal(observed.faces.length,3);assert.ok(observed.faces.every(f=>f.status==='loaded'));assert.ok(observed.fontChecks.Inter&&observed.fontChecks.Noto);
      assert.equal(observed.boxes.length,44);assert.ok(observed.boxes.every(b=>b.fontSize>=14&&b.x>=0&&b.y>=0&&b.x+b.w<=1536&&b.y+b.h<=1024));assert.deepEqual(observed.overlaps,[]);assert.deepEqual(observed.hits,[]);
      assert.equal(observed.labels.length,7);for(const l of labels){const found=observed.labels.find(x=>x.number===l.number);assert.ok(found);assert.equal(found.part,l.part_id);assert.ok(Math.abs(found.x-l.display_anchor[0])<1e-4&&Math.abs(found.y-l.display_anchor[1])<1e-4);}
      assert.equal(observed.images.length,1);assert.equal(observed.images[0].width,1536);assert.equal(observed.images[0].height,1024);
      const embedded=Buffer.from(observed.images[0].href.split(',')[1],'base64');const imageExpected=manifest.assets.find(a=>a.file.endsWith(kind==='full'?'/cross-scale-v1.png':'/cross-scale-v1-preview.jpg'));assert.equal(hash(embedded),imageExpected.sha256);
      delete observed.images[0].href;observed.images[0].sha256=hash(embedded);
      await settle(p);noErrors();const target=path.join(OUT,'cross-scale-'+kind+'-svg-1536.png');await root.screenshot({path:target});
      result.views.push({kind:kind+'SVG',file:target,width:1536,height:1024});result.font_checks.push({kind,embeddedFonts,faces:observed.faces,license_files:Object.keys(licenses.licenses)});
      result.full_svgs.push({kind,url:p.url(),status:200,sha256:hash(bytes),...observed});
    }
    await stage('full_svg_native_and_own_fonts',async()=>{
      const link=atlas.getByRole('link',{name:'放大查看',exact:true});const popup=await linkDocument(page,link,'/assets/technical-atlas/cross-scale-v1.svg',true);
      try{await inspectSVG(popup,'/assets/technical-atlas/cross-scale-v1.svg','full');}finally{await popup.close();}
    });
    await stage('preview_svg_own_fonts',async()=>{const previewPage=await context.newPage();try{await inspectSVG(previewPage,'/assets/technical-atlas/cross-scale-v1-preview.svg','preview');}finally{await previewPage.close();}});
    await page.setViewportSize({width:1280,height:900});await page.locator('#ui-appearance').selectOption('light');await settle(page);
    for(const target of related)await stage('related_'+target.id,async()=>{
      const link=atlas.locator('a[data-related-figure="'+target.id+'"]');assert.equal(await link.count(),1);
      const popup=await linkDocument(page,link,target.href,true);
      try{
        await popup.setViewportSize({width:1280,height:900});await popup.locator('#ui-appearance').selectOption('light');await settle(popup);
        let observed;
        if(target.type==='3D'){
          await popup.waitForFunction(title=>document.querySelector('.hud h1')?.textContent===title,target.title);
          const canvas=popup.locator('#c');await canvas.waitFor({state:'visible'});const box=await canvas.boundingBox();assert.ok(box&&box.width>0&&box.height>0);
          await popup.waitForFunction(()=>{const c=document.querySelector('#c');return c.width>0&&c.height>0;});await settle(popup);
          const shot=path.join(OUT,'related-'+target.id+'-canvas.png');const bytes=await canvas.screenshot({path:shot}),png=PNG.sync.read(bytes),colors=new Set();for(let i=0;i<png.data.length;i+=16)colors.add(png.data[i]+','+png.data[i+1]+','+png.data[i+2]);assert.ok(colors.size>20,'Actual canvas smoke must contain drawn content');
          result.views.push({kind:'related_3D_canvas_smoke',file:shot,id:target.id});observed={title:await popup.locator('.hud h1').textContent(),stage:await popup.locator('#stage').textContent(),canvas:box,colors:colors.size};
        }else{const old=await readyAtlas(popup,target.id);assert.equal(await popup.locator('.technical-atlas').count(),1);observed={figure:await old.getAttribute('data-figure')};}
        const shot=await save(popup,'related-'+target.id+'-page.png',{kind:'related_navigation_smoke',id:target.id},target.type!=='3D');
        result.related.push({id:target.id,href:target.href,actual_url:popup.url(),type:target.type,status:200,observed,screenshot:shot});
      }finally{await popup.close();}
    });
    await stage('final_gates',async()=>{
      noErrors();assert.equal(result.downloads.length,2);assert.equal(result.related.length,6);assert.equal(result.full_svgs.length,2);
      result.request_failure_snapshots.before_close=result.request_failures.map(r=>({...r}));
      assert.deepEqual(result.request_failures.filter(r=>!String(r.failure).includes('ERR_ABORTED')),[],'Non-abort request failures must be empty');
      assert.deepEqual(result.stages.map(s=>s.name),expectedStages);assert.ok(result.stages.slice(0,-1).every(s=>s.status==='PASS'));
      assert.ok(result.views.every(v=>path.isAbsolute(v.file)));
      result.scope_proof.browser_request_count=result.scope_proof.browser_requests.length;
      assert.ok(result.scope_proof.browser_requests.every(url=>new URL(url).origin===BASE));
    });
    passed=true;
  }catch(error){
    result.status='FAIL';result.failure={stage:currentStage,name:error.name,message:error.message,stack:error.stack};
    if(page&&!page.isClosed())try{const target=path.join(OUT,'failure.png');await page.screenshot({path:target,fullPage:true});result.failure.screenshot=target;result.failure.actual_url=page.url();}catch(captureError){result.failure.capture_error=captureError.message;}
    process.exitCode=1;
  }finally{
    if(browser)try{await browser.close();}catch(error){result.close_error=error.message;passed=false;process.exitCode=1;}
    result.request_failure_snapshots.after_close=result.request_failures.map(r=>({...r}));
    if(passed)try{assert.deepEqual(result.errors,[]);assert.deepEqual(result.route_errors,[]);assert.deepEqual(result.resource_failures,[]);assert.deepEqual(result.request_failures.filter(r=>!String(r.failure).includes('ERR_ABORTED')),[]);assert.ok(result.stages.every(s=>s.status==='PASS'));}
    catch(error){passed=false;result.failure={stage:'after_browser_close',message:error.message,stack:error.stack};process.exitCode=1;}
    result.finished_at=new Date().toISOString();result.status=passed?'PASS':'FAIL';writeReceipt();
    if(passed)console.log('PASS TA35 actual public static atlas, own-font SVG, downloads and six navigation smokes; '+receiptPath);
    else console.error('FAIL TA35 '+(result.failure?.message||result.close_error)+'; '+receiptPath);
  }
})().catch(error=>{result.status='FAIL';result.failure={stage:currentStage||'outer',message:error.message,stack:error.stack};result.finished_at=new Date().toISOString();writeReceipt();console.error(error.message);process.exitCode=1;});
