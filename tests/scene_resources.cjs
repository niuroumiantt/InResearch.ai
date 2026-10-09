const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.goto(process.env.UI_BASE_URL + '/rack3d.html', {waitUntil:'domcontentloaded'});
    const result = await page.evaluate(async () => {
      const {createSceneEnvironment, createTexturePool} = await import('/assets/scene-resources.js');
      const equal = (actual, expected, label) => {
        if (actual !== expected) throw new Error(`${label}: ${actual} !== ${expected}`);
      };
      const same = (actual, expected, label) => {
        if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(label);
      };
      const callbacks = [], timers = [], targets = [], states = [];
      class Loader { load(_url, success, _progress, failure) { callbacks.push({success, failure}); } }
      const target = name => {
        const value = {texture:{name}, disposed:0, dispose(){this.disposed += 1;}};
        targets.push(value); return value;
      };
      const createPMREM = () => ({
        fromScene(){return target('fallback');},
        fromEquirectangular(){return target('hdr');},
        dispose(){},
      });
      const THREE = {EquirectangularReflectionMapping:'equirect'};
      const source = name => ({name, disposed:0, dispose(){this.disposed += 1;}});
      const fallback = () => ({traverse(callback){callback({geometry:{dispose(){}},material:{dispose(){}}});}});
      const scene = {environment:null};
      const environment = createSceneEnvironment({THREE, EXRLoader:Loader, renderer:{}, scene,
        url:'/fixture.exr', fallback, createPMREM, onState:value=>states.push(value.status),
        setTimer:callback=>{timers.push(callback);return callback;}, clearTimer(){}});
      const first = source('first'); callbacks[0].success(first);
      equal((await environment.ready).status, 'ready', 'initial HDR status');
      equal(scene.environment.name, 'hdr', 'initial environment'); equal(first.disposed, 1, 'source disposal');

      const retryFallback = environment.retry(); callbacks[1].failure();
      equal((await retryFallback).status, 'fallback', 'failed retry status');
      equal(scene.environment.name, 'fallback', 'fallback environment'); equal(targets[0].disposed, 1, 'old target disposal');
      const old = environment.retry(), latest = environment.retry();
      equal((await old).status, 'superseded', 'superseded retry');
      const stale = source('stale'); callbacks[2].success(stale);
      equal(stale.disposed, 1, 'stale source disposal'); equal(scene.environment.name, 'fallback', 'stale attempt cannot publish');
      const final = source('final'); callbacks[3].success(final);
      equal((await latest).status, 'ready', 'latest retry'); equal(targets[1].disposed, 1, 'fallback target disposal');
      equal(final.disposed, 1, 'latest source disposal'); equal(scene.environment.name, 'hdr', 'latest target published');
      environment.dispose(); environment.dispose();
      equal(targets[2].disposed, 1, 'final target disposal'); equal(scene.environment, null, 'environment cleared');

      const timeoutCallbacks = [], timeoutTimers = [], timeoutScene = {environment:null};
      class TimeoutLoader { load(_url, success, _progress, failure){timeoutCallbacks.push({success,failure});} }
      const timed = createSceneEnvironment({THREE, EXRLoader:TimeoutLoader, renderer:{}, scene:timeoutScene,
        url:'/slow.exr', fallback, createPMREM, setTimer:callback=>{timeoutTimers.push(callback);return callback;}, clearTimer(){}});
      timeoutTimers[0](); equal((await timed.ready).status, 'fallback', 'timeout fallback');
      const late = source('late'); timeoutCallbacks[0].success(late);
      equal(late.disposed, 1, 'late timeout source disposal'); equal(timeoutScene.environment.name, 'fallback', 'late timeout cannot publish'); timed.dispose();

      const pool = createTexturePool({THREE:await import('three')});
      const fallbackDraw = (context,width,height) => {context.fillStyle='#e11d48';context.fillRect(0,0,width,height);};
      const failed = pool.image({url:'/assets/panels/missing-fixture.png',width:8,height:8,drawFallback:fallbackDraw});
      equal((await failed.ready()).status, 'fallback', 'image failure status');
      const failedIdentity = failed.texture;
      same([...failed.texture.image.getContext('2d').getImageData(0,0,1,1).data].slice(0,3),[225,29,72], 'fallback pixels');
      equal((await failed.retry()).status, 'fallback', 'image retry fallback'); equal(failed.texture, failedIdentity, 'failed texture identity');
      const loaded = pool.image({url:'/assets/panels/server_nvme.png',width:8,height:8,drawFallback:fallbackDraw});
      equal((await loaded.ready()).status, 'ready', 'image success status');
      equal(loaded.texture.image.width > 8, true, 'image pixels loaded'); const identity = loaded.texture;
      let disposed = 0; identity.addEventListener('dispose',()=>disposed++);
      loaded.dispose(); loaded.dispose(); equal(disposed,1,'handle dispose once');
      pool.dispose(); pool.dispose(); equal(failed.status(),'disposed','pool disposes handle');
      return {states, targets:targets.map(item=>({name:item.texture.name,disposed:item.disposed})),
              stableFailureTexture:failedIdentity===failed.texture, stableSuccessTexture:identity===loaded.texture};
    });
    assert.deepEqual(result.states,['ready','fallback','ready','disposed']);
    console.log('PASS scene resource generation, timeout, retry, replacement, fallback and disposal', JSON.stringify(result));
    await page.close();

    for (const name of ['bom3d', 'rack3d']) {
      const actual = await browser.newPage({viewport:{width:900,height:700}});
      const errors = []; actual.on('pageerror', error => errors.push(error.message));
      await actual.route('**/*.exr', route => route.fulfill({status:503,body:'environment unavailable'}));
      await actual.route('**/assets/panels/*.png', route => route.fulfill({status:503,body:'panel unavailable'}));
      await actual.route(new RegExp(`/${name}\\.html(?:\\?|$)`), async route => {
        const response = await route.fetch(), source = await response.text();
        const expose = `globalThis.__resourcePage={sceneEnvironment,texturePool,renderer,composer,disposePage${name==='rack3d'?',PANEL':''}};\n</script>\n</body>`;
        const body = source.replace('</script>\n</body>', expose);
        assert.notEqual(body, source, 'resource page fixture injection failed');
        await route.fulfill({response, body});
      });
      // Retained OEM panel fallback lives in the explicit legacy rack scene.
      await actual.goto(`${process.env.UI_BASE_URL}/${name}.html${name==='rack3d'?'?view=legacy&x=35':''}`, {waitUntil:'domcontentloaded'});
      try { await actual.waitForFunction(() => !!globalThis.__resourcePage, null, {timeout:20000}); }
      catch (error) { throw new Error(name+' resource fixture unavailable: '+JSON.stringify(errors)); }
      const pageResult = await actual.evaluate(async name => {
        const view = globalThis.__resourcePage;
        const environment = await view.sceneEnvironment.ready;
        const panels = name === 'rack3d'
          ? await Promise.all(Object.values(view.PANEL).map(async handle => ({status:(await handle.ready()).status,texture:handle.texture.uuid})))
          : [];
        let rendererDisposals = 0, composerDisposals = 0, renders = 0;
        const rendererDispose = view.renderer.dispose.bind(view.renderer);
        const composerDispose = view.composer.dispose.bind(view.composer);
        const composerRender = view.composer.render.bind(view.composer);
        view.renderer.dispose = () => {rendererDisposals += 1; rendererDispose();};
        view.composer.dispose = () => {composerDisposals += 1; composerDispose();};
        view.composer.render = (...args) => {renders += 1; return composerRender(...args);};
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        view.disposePage(); view.disposePage();
        const rendersAtDispose = renders;
        await new Promise(resolve => setTimeout(resolve, 60));
        return {environment:environment.status,environmentCleared:view.sceneEnvironment.current()===null,
                panels,rendererDisposals,composerDisposals,rendersAtDispose,rendersAfterWait:renders};
      }, name);
      assert.equal(pageResult.environment,'procedural',name+' must use the neutral atlas environment');
      assert.equal(pageResult.environmentCleared,true,name+' environment must release on exit');
      assert.equal(pageResult.rendererDisposals,1,name+' renderer must dispose once');
      assert.equal(pageResult.composerDisposals,1,name+' composer must dispose once');
      assert.equal(pageResult.rendersAfterWait,pageResult.rendersAtDispose,name+' render loop survived disposal');
      if (name === 'rack3d') {
        assert.equal(pageResult.panels.length,5);
        assert.ok(pageResult.panels.every(panel => panel.status === 'fallback'));
        assert.equal(new Set(pageResult.panels.map(panel => panel.texture)).size,5);
      }
      assert.deepEqual(errors,[]);
      await actual.close();
      console.log('PASS actual '+name+' environment/panel failure and idempotent page disposal');
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
