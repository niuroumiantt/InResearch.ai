import * as THREE from 'three';
import {GLTFLoader} from '/assets/vendor/GLTFLoader.js';

function ownedModel(gltf, entry) {
  let released = false;
  return {root:gltf.scene, entry, dispose() {
    if (released) return;
    released = true;
    const geometry = new Set(), materials = new Set(), textures = new Set(), images = new Set();
    for (const scene of gltf.scenes) {
      scene.removeFromParent();
      scene.traverse(object => {
        if (object.geometry) geometry.add(object.geometry);
        for (const material of [].concat(object.material || [])) materials.add(material);
        if (object.skeleton?.boneTexture) textures.add(object.skeleton.boneTexture);
      });
    }
    for (const material of materials) {
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      material.dispose();
    }
    for (const texture of textures) {
      for (const image of [].concat(texture.source?.data || [])) images.add(image);
      texture.dispose();
    }
    for (const item of geometry) item.dispose();
    for (const image of images) image.close?.();
  }};
}

export async function loadModel(entry, signal) {
  if (!/^[a-z0-9][a-z0-9_.-]{0,79}\.glb$/.test(entry.file)
      || entry.url !== '/assets/models/' + entry.file || !/^[a-f0-9]{64}$/.test(entry.sha256)) {
    throw Error('模型内容身份无效');
  }
  const response = await fetch(entry.url, {signal, cache:'no-cache'});
  if (!response.ok) throw Error('模型请求失败');
  const data = await response.arrayBuffer();
  if (data.byteLength > 10 * 1024 * 1024) throw Error('模型体积超过限制');
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', data))]
    .map(value => value.toString(16).padStart(2, '0')).join('');
  if (digest !== entry.sha256) throw Error('模型内容已变化，等待重新核对');
  signal.throwIfAborted();
  const manager = new THREE.LoadingManager(); let resourceFailed = false;
  manager.onError = () => {resourceFailed = true;};
  const model = ownedModel(await new GLTFLoader(manager).parseAsync(data, ''), entry);
  if (resourceFailed) {model.dispose(); throw Error('模型内嵌资源加载失败');}
  if (signal.aborted) {model.dispose(); signal.throwIfAborted();}
  return model;
}

// A slot owns only its loaded value. Replacement failure keeps the current value.
export function createModelLoad({host, label, load, commit, timeoutMs=15000}) {
  const element = document.createElement('div'), text = document.createElement('span');
  const retry = document.createElement('button');
  element.className = 'rg-model-status'; element.setAttribute('role', 'status');
  retry.type = 'button'; retry.textContent = '重试';
  element.append(text, retry); host.append(element);
  let generation = 0, active = null, current = null, disposed = false;
  async function run(force=false) {
    if (disposed || (active && !force)) return;
    const id = ++generation;
    active?.abort();
    const controller = new AbortController(); active = controller;
    const {signal} = controller;
    element.dataset.state = 'loading'; element.hidden = false;
    element.setAttribute('aria-busy', 'true'); retry.hidden = true;
    text.textContent = label + '加载中…';
    let timer, candidate;
    const pending = Promise.resolve().then(() => load(signal));
    // Parsers can finish after cancellation even when transport supports abort.
    pending.then(value => {if (signal.aborted || id !== generation) value.dispose();}, () => {});
    try {
      candidate = await Promise.race([pending, new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(Error('加载已取消')), {once:true});
        timer = setTimeout(() => {reject(Error('加载超时')); controller.abort();}, timeoutMs);
      })]);
      if (disposed || id !== generation || signal.aborted) {candidate.dispose(); return;}
      commit(candidate);
      current?.dispose(); current = candidate;
      element.dataset.state = 'ready'; element.hidden = true;
    } catch (error) {
      if (candidate && candidate !== current) candidate.dispose();
      if (disposed || id !== generation) return;
      element.dataset.state = 'error'; text.textContent = label + '暂不可用，请重试。';
      retry.hidden = false;
    } finally {
      clearTimeout(timer); controller.abort();
      if (id === generation) {active = null; element.setAttribute('aria-busy', 'false');}
    }
  }
  retry.addEventListener('click', () => run());
  const ready = run();
  return {element, ready, reload:() => run(true), dispose() {
    if (disposed) return;
    disposed = true; generation++; active?.abort(); current?.dispose(); element.remove();
  }};
}

function fit(model, defaultHeight) {
  const object = model.root, entry = model.entry;
  object.rotation.y = entry.rotationY || 0;
  object.traverse(mesh => {if (mesh.isMesh) mesh.castShadow = mesh.receiveShadow = true;});
  if (entry.scale == null || entry.scale === 'auto') {
    const bounds = new THREE.Box3().setFromObject(object), size = bounds.getSize(new THREE.Vector3());
    if (!Number.isFinite(size.y) || size.y < 1e-6) throw Error('模型没有可用高度');
    object.scale.setScalar((entry.fitHeight || defaultHeight) / size.y);
    bounds.setFromObject(object);
    const center = bounds.getCenter(new THREE.Vector3());
    object.position.set(-center.x, -bounds.min.y, -center.z);
    object.position.add(new THREE.Vector3(...(entry.position || [0, 0, 0])));
  } else {
    object.scale.setScalar(entry.scale); object.position.set(...(entry.position || [0, 0, 0]));
  }
}

export function mountSceneModels({scene, page, defaultHeight, replacement=null}) {
  const originalVisibility = replacement?.visible;
  const slot = createModelLoad({host:document.body, label:'可选模型',
    load:async signal => {
      const response = await fetch('/api/model-assets?page=' + page, {signal, cache:'no-store'});
      if (!response.ok) throw Error('模型登记不可用');
      const data = await response.json();
      if (data.schema_version !== 1 || !Array.isArray(data.models)
          || data.models.some(entry => entry.status !== 'adopted' || entry.page !== page)) throw Error('模型登记无效');
      const models = []; let failed = false;
      try {
        await Promise.all(data.models.map(async entry => {
          const model = await loadModel(entry, signal);
          if (failed) {model.dispose(); return;}
          models.push(model); fit(model, defaultHeight);
        }));
        return {models, dispose() {models.forEach(model => model.dispose());}};
      } catch (error) {
        failed = true; models.forEach(model => model.dispose()); throw error;
      }
    },
    commit:batch => {
      batch.models.forEach(model => scene.add(model.root));
      if (replacement) replacement.visible = originalVisibility && !batch.models.some(model => model.entry.hideRack);
    }});
  slot.element.classList.add('rg-scene-model-status');
  return {reload:slot.reload, ready:slot.ready, dispose() {
    slot.dispose(); if (replacement) replacement.visible = originalVisibility;
  }};
}
