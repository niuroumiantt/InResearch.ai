const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'../..');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:800,height:1200},deviceScaleFactor:2});
 let records=[];
 for(const file of fs.readdirSync(path.join(root,'assets')).filter(x=>x.endsWith('.svg')&&(x.startsWith('fig')||x.startsWith('cover')))){
  const cover=file.startsWith('cover');const svg=fs.readFileSync(path.join(root,'assets',file),'utf8');
  const width=cover?800:640;const height=Number(svg.match(/height="(\d+)"/)[1]);
  await page.setViewportSize({width,height});
  await page.setContent('<html><head><meta charset="utf-8"></head><body style="margin:0">'+svg+'</body></html>');
  await page.evaluate(()=>document.fonts.ready);
  const overflow=await page.evaluate(()=>Array.from(document.querySelectorAll('text')).map(x=>({s:x.textContent,b:x.getBBox()})).filter(x=>x.b.x+x.b.width>Number(document.querySelector('svg').getAttribute('width'))-8||x.b.x<0).map(x=>x.s));
  const out=path.join(root,'assets',file.replace('.svg','-render.png'));
  if(cover){await page.screenshot({path:out,scale:'css'});
   const p3=await browser.newPage({viewport:{width,height},deviceScaleFactor:3});await p3.setContent('<body style="margin:0">'+svg+'</body>');await p3.screenshot({path:path.join(root,'assets','cover-master.png')});await p3.close();
  }else{await page.screenshot({path:out});}
  records.push({file,design_width:width,design_height:height,overflow_text:overflow});
 }
 fs.writeFileSync(path.join(root,'checks','svg-layout.json'),JSON.stringify(records,null,2));
 console.log(JSON.stringify(records));await browser.close();
})();
