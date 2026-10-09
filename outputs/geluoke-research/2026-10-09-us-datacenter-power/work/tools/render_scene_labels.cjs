// Publish independently editable labels with an unchanged generated base image.
const {chromium}=require('playwright');
const path=require('path');
(async()=>{const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:640,height:587},deviceScaleFactor:2});
 const root=path.resolve(__dirname,'../..');
 await page.goto('file://'+path.join(root,'assets/scene-gas-labeled.svg'));
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:path.join(root,'assets/scene-gas-pipeline.jpg'),type:'jpeg',quality:85});
 await browser.close();
})();
