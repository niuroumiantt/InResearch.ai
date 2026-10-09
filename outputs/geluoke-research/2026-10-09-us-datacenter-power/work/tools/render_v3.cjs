const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'../..');
(async()=>{const browser=await chromium.launch({headless:true});const page=await browser.newPage({deviceScaleFactor:2});let checks=[];
 const plan=JSON.parse(fs.readFileSync(path.join(root,'work/v3/figure-plan.json'),'utf8'));
 for(const f of plan.figures){
  await page.setViewportSize({width:f.design_width,height:f.design_height});
  const svg=fs.readFileSync(path.join(root,f.editable),'utf8');
  await page.setContent('<html><body style="margin:0">'+svg+'</body></html>');
  await page.evaluate(()=>document.fonts.ready);
  const overflow=await page.evaluate(()=>[...document.querySelectorAll('text')].map(e=>({text:e.textContent,x:e.getBBox().x,y:e.getBBox().y,w:e.getBBox().width,h:e.getBBox().height})).filter(e=>e.x<4||e.x+e.w>636||e.y<0||e.y+e.h>Number(document.querySelector('svg').getAttribute('height'))));
  await page.screenshot({path:path.join(root,f.asset),type:f.asset.endsWith('.jpg')?'jpeg':'png',...(f.asset.endsWith('.jpg')?{quality:85}:{})});
  checks.push({number:f.number,file:f.editable,overflow});
 }
 fs.writeFileSync(path.join(root,'checks/v3-svg-layout.json'),JSON.stringify(checks,null,2));
 console.log(JSON.stringify(checks.filter(x=>x.overflow.length)));await browser.close();if(checks.some(x=>x.overflow.length))process.exitCode=1;
})();
