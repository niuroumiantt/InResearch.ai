const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const manifest = require('../framework/site_navigation.json');
const {setAppearance,navigationProjection:projection} = require('./ui_helpers.cjs');
const base = process.env.UI_BASE_URL;
const qaDir = process.env.UI_QA_DIR;
if(qaDir) require('node:fs').mkdirSync(qaDir,{recursive:true});
(async () => {
  const browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || undefined,headless:true});
  try {
    for (const role of ['reader','customer','admin','member','intern']) {
      const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
      const page = await context.newPage(), errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      const active = role==='intern'?{area:'backstage',section:'production',view:'tasks'}:{area:'delivery',section:'campuses',view:'directory'};
      const data = projection(role, active);
      const navigationRequests=[];
      await page.route('**/api/navigation?*',route=>{navigationRequests.push(new URL(route.request().url()).searchParams.get('page'));return route.fulfill({json:data});});
      await page.goto(base+'/'); await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
      assert.equal(await page.locator('#ui-skinbar').getAttribute('data-identity'),data.identity.kind);
      assert.equal(await page.locator('#ui-site-footer').count(),1,'one shared footer');
      assert.equal(await page.locator('.ui-home img').getAttribute('src'),'/assets/marketing/wordmark-light.png');
      assert.equal(await page.locator('.ui-home .ui-brand-watermark').count(),0,'logo never receives a second watermark');
      await setAppearance(page,'dark');
      assert.equal(await page.locator('.ui-home img').getAttribute('src'),'/assets/marketing/brand/wordmark-dark.png','dark mode uses the marketing reverse wordmark');
      await setAppearance(page,'light');
      if(qaDir) await page.screenshot({path:qaDir+'/navigation-'+role+'-desktop.png'});
      if(role==='reader') {
        assert.deepEqual(await page.locator('.ui-navigation-public a').allTextContents(),manifest.public_navigation.map(item=>item.label));
        assert.equal(await page.locator('.ui-navigation-backstage,.ui-navigation-delivery,.ui-search-form').count(),0);
        assert.deepEqual(await page.locator('#ui-site-footer a').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href'))),['/','/tasks.html','/login']);
      } else {
        for(const area of ['delivery','backstage']) assert.equal(await page.locator('.ui-navigation-'+area+' [data-nav-section]').count(),data.navigation[area].length);
        assert.equal(await page.locator('.ui-account-panel .ui-management-link,.ui-account-panel .ui-admin-link').count(),0);
        await page.locator('.ui-account-menu > summary').click();
        assert.deepEqual(await page.locator('.ui-account-panel a').allTextContents(),['个人信息','修改密码','退出登录']);
        await page.keyboard.press('Escape');
        const group = data.navigation.delivery[0] || data.navigation.backstage[0];
        const navArea = data.navigation.delivery.length?'delivery':'backstage';
        const summary = page.locator('.ui-navigation-'+navArea+' [data-nav-section="'+group.id+'"] > summary');
        await summary.click();
        assert.deepEqual(await page.locator('.ui-navigation-'+navArea+' [data-nav-section="'+group.id+'"] .ui-section-panel a').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href'))),group.children.map(child=>child.href));
        await page.keyboard.press('Escape'); assert.equal(await summary.evaluate(node=>node===document.activeElement),true);
        if(role==='customer') assert.equal(await page.locator('[data-nav-area=backstage],.ui-footer-runtime').count(),0);
        else {
          await page.locator('.ui-footer-runtime > summary').click();
          assert.deepEqual(await page.locator('.ui-footer-runtime p').allTextContents(),['运行版本：未取得','运行环境：未取得','部署时间：未取得','状态时间：未取得','运行状态：未取得']);
          const operations=data.navigation.backstage.find(item=>item.id==='operations');
          assert.deepEqual(await page.locator('.ui-runtime-links a').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href'))),['deployment','health'].flatMap(id=>{const item=operations?.children.find(child=>child.id===id);return item?[item.href]:[];}));
          await page.locator('.ui-footer-runtime > summary').click();await page.evaluate(()=>scrollTo(0,0));
        }
        if(['customer','intern'].includes(role)) {
          assert.equal(await page.locator('.ui-search-form select').count(),0,'fixed role cannot choose a broader scope');
          assert.equal(await page.locator('.ui-search-scope-fixed').innerText(),role==='customer'?'交付内容':'后台工作');
          assert.equal(await page.locator('.ui-search-form [name=scope]').inputValue(),role==='customer'?'delivery':'backstage');
        } else {
          assert.deepEqual(await page.locator('.ui-search-scope option').evaluateAll(nodes=>nodes.map(node=>node.value)),['delivery','backstage','all']);
          await page.locator('.ui-search-scope').selectOption('all');assert.equal(await page.locator('.ui-search-form [name=q]').getAttribute('placeholder'),'搜索全部授权内容');await page.locator('.ui-search-scope').selectOption('delivery');
        }
      }
      for (const width of [320,390,700]) {
        await page.setViewportSize({width,height:844});
        for(const mode of ['light','dark','system']) await setAppearance(page,mode);
        if(qaDir&&width===390) await page.screenshot({path:qaDir+'/navigation-'+role+'-mobile.png'});
        const bounds=await page.locator('#ui-skinbar').boundingBox();
        assert.ok(bounds.height<=86,role+' compact two-row header at '+width+': '+bounds.height);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),role+' no horizontal overflow at '+width);
        const offset=await page.evaluate(()=>Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui-bar-height')));
        assert.equal(offset,Math.ceil(bounds.height),'shared layout follows measured header height');
        if(role!=='reader') {
          const area = role==='intern'?'backstage':'delivery';
          await page.locator('.ui-mobile-areas button[data-area="'+area+'"]').click();
          const panel=page.locator('.ui-mobile-panel'); await panel.waitFor({state:'visible'});
          const box=await panel.boundingBox(); assert.ok(box.x>=0&&box.x+box.width<=width,'mobile menu fits');
          const sections=panel.locator('.ui-mobile-section'); assert.ok(await sections.count()>0);
          const second=sections.nth((await sections.count())>1?1:0); await second.locator(':scope > summary').click();
          await second.locator('a').first().waitFor({state:'visible'});
          assert.ok((await second.locator('a').first().getAttribute('href')).startsWith('/'));
          await page.keyboard.press('Escape');
          await page.locator('.ui-account-menu > summary').click();
          const account=await page.locator('.ui-account-panel').boundingBox(); assert.ok(account.x>=0&&account.x+account.width<=width+1);
          await page.keyboard.press('Escape');
        }
      }
      await page.setViewportSize({width:1440,height:1000});
      if(['customer','admin','member'].includes(role)) {
        data.active={area:'delivery',section:'economics',view:'cost'};
        await page.evaluate(()=>{history.pushState({},'', '/ledger.html?view=cost#cost');window.dispatchEvent(new Event('inresearch:page-navigation'));});
        await page.locator('.ui-navigation-delivery [data-nav-section=economics] > summary[aria-current=page]').waitFor();
        assert.equal(navigationRequests.at(-1),'/ledger.html?view=cost#cost','in-page query navigation refreshes registered location');
        data.active=active;
        await page.evaluate(()=>history.back()); await page.waitForURL(base+'/');
        await page.locator('.ui-navigation-delivery [data-nav-section=campuses] > summary[aria-current=page]').waitFor();
        assert.equal(navigationRequests.at(-1),'/','browser history refreshes active navigation');
      }
      if(['admin','member'].includes(role)) {
        await page.locator('.ui-search-scope').selectOption('all');await page.locator('.ui-search-form [name=q]').fill('Microsoft');
        await Promise.all([page.waitForURL(url=>url.pathname==='/search.html'&&url.searchParams.get('scope')==='all'&&url.searchParams.get('q')==='Microsoft'),page.locator('.ui-search-form button').click()]);
        await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();assert.equal(await page.locator('.ui-search-scope').inputValue(),'all','native header search submits and retains authorized scope');
      }
      if(role==='customer') {
        await page.setViewportSize({width:390,height:844});
        await page.locator('.ui-mobile-areas button[data-area=delivery]').click();
        const section=page.locator('.ui-mobile-section').filter({has:page.locator('summary',{hasText:'数据中心研究'})});
        await section.locator(':scope > summary').click();
        const target=section.locator('a').first(); const href=await target.getAttribute('href');
        data.active={area:'delivery',section:'datacenter',view:'build'};
        await Promise.all([page.waitForURL(base+href),target.click()]);
        await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
        assert.equal(await page.locator('.ui-mobile-menu').evaluate(node=>node.open),false,'secondary click follows the registered page and closes menu');
        await page.setViewportSize({width:1440,height:1000});
      }
      await page.evaluate(()=>{const image=document.createElement('img');image.id='navigation-brand-fixture';image.src='/assets/marketing/wordmark-light.png';image.width=300;image.height=60;document.querySelector('main').append(image);});
      await page.locator('#navigation-brand-fixture[data-brand-watermarked=true]').waitFor({state:'attached'});
      assert.equal(await page.locator('#navigation-brand-fixture').getAttribute('src'),'/assets/marketing/wordmark-light.png','presentation branding never rewrites image source');
      assert.equal(await page.locator('.ui-branded-image:has(#navigation-brand-fixture) .ui-brand-watermark').count(),1);
      assert.deepEqual(errors,[]); await context.close();
      console.log('PASS shared navigation '+role+' desktop/mobile/footer/theme/brand');
    }
    const context=await browser.newContext(),page=await context.newPage(); let succeed=false;
    await page.route('**/api/navigation?*',route=>succeed?route.fulfill({json:projection('customer',{area:'delivery',section:'campuses',view:'directory'})}):route.fulfill({status:503,body:'unavailable'}));
    await page.goto(base+'/');await page.locator('#ui-navigation-error').waitFor();
    assert.equal(await page.locator('.ui-navigation-backstage').count(),0,'failed identity never displays internal navigation');
    succeed=true;await page.locator('#ui-navigation-error').click();await page.locator('#ui-skinbar[data-navigation-ready=true]').waitFor();
    assert.equal(await page.locator('#ui-navigation-error').count(),0);await context.close();
    console.log('PASS navigation failure keeps anonymous boundary and recovers by retry');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
