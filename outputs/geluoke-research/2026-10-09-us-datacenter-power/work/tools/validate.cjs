const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'../..');const base=process.env.ARTICLE_CHECK_URL||'http://127.0.0.1:18769';
(async()=>{
 const browser=await chromium.launch({headless:true});let results=[];
 const context=await browser.newContext({permissions:['clipboard-read','clipboard-write'],deviceScaleFactor:1});
 const page=await context.newPage();
 for(const mode of ['wechat','full','lite']) for(const width of [1000,390]){
  await page.setViewportSize({width,height:1100});await page.goto(base+'/'+mode+'.html');
  await page.evaluate(()=>document.fonts.ready);await page.waitForFunction(()=>[...document.images].every(x=>x.complete));
  const r=await page.evaluate(()=>{
   const a=document.querySelector('article'),rect=a.getBoundingClientRect();const p=document.querySelector('p');
   return {viewport:innerWidth,scroll_width:document.documentElement.scrollWidth,article_width:rect.width,left:rect.left,right:innerWidth-rect.right,body_font:getComputedStyle(p).fontSize,images:[...document.images].map(x=>({alt:x.alt,width:x.naturalWidth,loaded:x.complete&&x.naturalWidth>0,rendered:x.getBoundingClientRect().width})),h2:[...document.querySelectorAll('h2')].map(x=>({text:x.textContent,width:x.scrollWidth,client:x.clientWidth})),height:document.body.scrollHeight};
  });r.mode=mode;r.pass=r.scroll_width<=width&&r.images.length===7&&r.images.every(x=>x.loaded)&&r.h2.every(x=>x.width<=x.client+1);
  if(mode!=='wechat')r.pass=r.pass&&r.article_width===(width===390?374:720)&&r.left===(width===390?8:140);
  results.push(r);
  if(mode==='lite'){
   await page.screenshot({path:path.join(root,'checks',`article-${width}-full.jpg`),fullPage:true,type:'jpeg',quality:65});
   await page.screenshot({path:path.join(root,'checks',`article-${width}-top.png`)});
   if(width===390){
    const heads=page.locator('h2');
    for(let i=0;i<6;i++){await heads.nth(i).evaluate(el=>el.scrollIntoView({block:'start'}));await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await page.screenshot({path:path.join(root,'checks',`mobile-chapter-${i+1}.png`)});}
   }
  }
 }
 await page.goto(base+'/wechat.html');
 await page.evaluate(()=>{let r=document.createRange();r.selectNodeContents(document.querySelector('article'));getSelection().removeAllRanges();getSelection().addRange(r);});
 const copied=await page.evaluate(()=>document.execCommand('copy'));
 let copy={method:'browser selection / copy / Clipboard API read / contenteditable insertHTML',copied,images_before:7,images_after:0,pass:false};
 try{
  const pasted=await page.evaluate(async()=>{
   let data=await navigator.clipboard.read();let item=data.find(x=>x.types.includes('text/html'));if(!item)return {error:'no HTML clipboard format'};
   let html=await (await item.getType('text/html')).text();let ed=document.createElement('div');ed.contentEditable='true';document.body.appendChild(ed);ed.focus();let inserted=document.execCommand('insertHTML',false,html);
   return {html_bytes:new TextEncoder().encode(html).length,inserted,images:ed.querySelectorAll('img').length,preserved_data_images:[...ed.querySelectorAll('img')].every(x=>x.src.startsWith('data:image/'))};
  });Object.assign(copy,pasted);copy.images_after=pasted.images||0;copy.pass=copied&&pasted.inserted&&pasted.images===7&&pasted.preserved_data_images;
 }catch(e){copy.error=String(e);}
 const result={checked_at:'2026-10-09',render:results,clipboard_roundtrip:copy,wechat_platform:'未进入实际微信编辑器；浏览器往返不等于公众号实粘',pass:results.every(x=>x.pass)&&copy.pass};
 fs.writeFileSync(path.join(root,'checks','browser.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({pass:result.pass,render:results.map(x=>({mode:x.mode,width:x.viewport,pass:x.pass,height:x.height})),copy}));
 await browser.close();if(!result.pass)process.exitCode=1;
})();
