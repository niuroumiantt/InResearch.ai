const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.UI_BASE_URL;
(async()=>{
 const browser=await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL||undefined,headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/supply.html');
  await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  assert.match(page.url(),/#targets$/,'the target table is the first screen');
  assert.equal(await page.locator('#team-cards .team-card').count(),6,'six teams');
  assert.equal(await page.locator('table.heat tbody tr').count(),7,'five systems, site rights and the root by five classes');
  await page.goto(base+'/supply.html?node=part:transformer&col=4#targets');
  await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  assert.equal(await page.locator('table.targets tbody tr').count(),1,'node + column prefilter from the node page');
  assert.match(await page.locator('table.targets tbody').innerText(),/P\.transformer\.lead_time/);
  await page.getByRole('button',{name:'派工',exact:true}).first().click();await page.locator('#target-dialog[open]').waitFor();
  await page.locator('#td-cancel').click();
  await page.goto(base+'/supply.html');await page.locator('#targets-panel table.targets tbody tr').first().waitFor();
  await page.getByRole('button',{name:'作战总览',exact:true}).click();
  await page.getByRole('heading',{name:'目的与当前进展',exact:true}).waitFor();
  assert.match(page.url(),/#overview$/);
  assert.match(await page.locator('#counts').innerText(),/7 个供应入口/);
  await page.getByRole('button',{name:'广度与深度',exact:true}).click();
  assert.match(page.url(),/#coverage$/);assert.match(await page.locator('#list').innerText(),/第 0 批：验证闭环/);
  await page.goto(base+'/supply.html#resources');await page.getByRole('heading',{name:'资源分工',exact:true}).waitFor();
  assert.match(await page.locator('#list').innerText(),/Spark/);
  await page.getByRole('button',{name:'供应方与任务',exact:true}).click();
  await page.getByRole('button',{name:/fetchspec/}).waitFor();
  for(const team of ['fetchstat','fetchfilings','fetchreports','fetchquotes','inews.today'])await page.getByRole('button',{name:new RegExp(team)}).waitFor();
  await page.getByRole('button',{name:'研究需求',exact:true}).click();
  await page.locator('#create-panel').waitFor();
  assert.ok(await page.locator('#question option').count()>1);
  await page.locator('#execution-mode').selectOption('assisted');
  assert.equal(await page.locator('#execution-mode').inputValue(),'assisted');
  await page.getByRole('button',{name:'交付与验收',exact:true}).click();
  assert.match(await page.locator('#list').innerText(),/等待第一份交付包/);
  await page.getByRole('heading',{name:'跨产品资料检索',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'检索已接收资料',exact:true}).count());
  for(const width of [390,1280]){
   await page.setViewportSize({width,height:950});
   for(const theme of ['light','dark']){
    await page.locator('#ui-appearance').selectOption(theme);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   }
  }
  await page.goto(base+'/supply-demo.html');
  await page.getByRole('button',{name:'交付与验收',exact:true}).click();
  await page.getByRole('button',{name:'验收合格 2 份',exact:true}).click();
  assert.match(await page.locator('#sd-message').innerText(),/需求保持部分交付/);
  await page.getByRole('button',{name:'研究需求与分配',exact:true}).click();
  await page.getByRole('button',{name:'分配示例任务',exact:true}).click();
  assert.match(await page.locator('#sd-message').innerText(),/接通后才可执行/);
  await page.setViewportSize({width:390,height:950});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  if(process.env.UI_QA_DIR){await page.goto(base+'/supply.html');await page.getByRole('button',{name:/fetchspec/}).waitFor();await page.setViewportSize({width:1280,height:1000});await page.screenshot({path:process.env.UI_QA_DIR+'/supply.png',fullPage:true});}
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
