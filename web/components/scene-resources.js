function disposeObject(root) {
  const geometries = new Set(), materials = new Set();
  root?.traverse?.(object => {
    if (object.geometry) geometries.add(object.geometry);
    const values = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
    values.forEach(material => materials.add(material));
  });
  geometries.forEach(geometry => geometry.dispose());
  materials.forEach(material => material.dispose());
}

/** Own one scene.environment across load, fallback, retry, replacement and exit. */
export function createSceneEnvironment({THREE, EXRLoader, renderer, scene, url, fallback,
                                        timeoutMs = 8000, onState = () => {},
                                        setTimer = setTimeout, clearTimer = clearTimeout,
                                        createPMREM = value => new THREE.PMREMGenerator(value)}) {
  if (!THREE || !EXRLoader || !renderer || !scene || !url || typeof fallback !== "function") {
    throw new TypeError("scene environment dependencies are required");
  }
  let generation = 0, current = null, timer = null, disposed = false, pending = null;

  const release = target => target?.dispose?.();
  const publish = (target, token) => {
    if (!target?.texture) throw new TypeError("PMREM target with texture required");
    if (disposed || token !== generation) { release(target); return false; }
    const previous = current;
    current = target;
    scene.environment = target.texture;
    if (previous !== target) release(previous);
    return true;
  };
  const fromScene = () => {
    const source = fallback();
    const pmrem = createPMREM(renderer);
    try { return pmrem.fromScene(source, 0.04); }
    finally { pmrem.dispose(); disposeObject(source); }
  };
  const fromTexture = texture => {
    texture.mapping = THREE.EquirectangularReflectionMapping;
    const pmrem = createPMREM(renderer);
    try { return pmrem.fromEquirectangular(texture); }
    finally { pmrem.dispose(); texture.dispose(); }
  };
  const begin = () => {
    if (disposed) return Promise.resolve({status: "disposed"});
    const token = ++generation;
    if (timer !== null) clearTimer(timer);
    let finished = false, resolveReady;
    const ready = new Promise(resolve => { resolveReady = resolve; });
    pending?.({status: "superseded"});
    pending = resolveReady;
    const finish = (status, targetFactory) => {
      if (finished || disposed || token !== generation) return false;
      finished = true;
      if (timer !== null) { clearTimer(timer); timer = null; }
      try {
        const committed = publish(targetFactory(), token);
        const result = {status: committed ? status : "superseded"};
        onState(result); resolveReady(result);
      } catch (error) {
        const result = {status: "error", error};
        onState(result); resolveReady(result);
      }
      if (pending === resolveReady) pending = null;
      return true;
    };
    timer = setTimer(() => finish("fallback", fromScene), timeoutMs);
    try {
      new EXRLoader().load(url,
        texture => {
          if (!finish("ready", () => fromTexture(texture))) texture.dispose();
        }, undefined,
        () => finish("fallback", fromScene));
    } catch (_error) {
      finish("fallback", fromScene);
    }
    return ready;
  };
  const api = {
    retry: begin,
    ready: begin(),
    current: () => current?.texture || null,
    dispose() {
      if (disposed) return;
      disposed = true; generation += 1;
      if (timer !== null) { clearTimer(timer); timer = null; }
      pending?.({status: "disposed"}); pending = null;
      if (scene.environment === current?.texture) scene.environment = null;
      release(current); current = null;
      onState({status: "disposed"});
    },
  };
  return api;
}

/** Own page-created CanvasTextures and image attempts without changing texture identity. */
export function createTexturePool({THREE, document: documentRef = document,
                                   createImage = () => new Image()}) {
  if (!THREE || !documentRef) throw new TypeError("texture pool dependencies are required");
  const textures = new Set(), images = new Set(), handles = new Set();
  let disposed = false;
  const canvas = (width, height, draw, repeatX = 1, repeatY = 1) => {
    if (disposed) throw new Error("texture pool disposed");
    const element = documentRef.createElement("canvas");
    element.width = width; element.height = height;
    draw(element.getContext("2d"), width, height);
    const texture = new THREE.CanvasTexture(element);
    texture.colorSpace = THREE.SRGBColorSpace;
    if (repeatX !== 1 || repeatY !== 1) {
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.repeat.set(repeatX, repeatY);
    }
    texture.anisotropy = 8;
    textures.add(texture);
    return texture;
  };
  const image = ({url, width = 256, height = 64, drawFallback}) => {
    const texture = canvas(width, height, drawFallback);
    let generation = 0, active = null, settle = null;
    let state = "fallback", ready = Promise.resolve({status: state});
    const retry = () => {
      if (disposed) return Promise.resolve({status: "disposed"});
      settle?.({status: "superseded"}); settle = null;
      const token = ++generation, request = createImage();
      images.add(request); state = "loading";
      ready = new Promise(resolve => {
        settle = resolve;
        request.onload = () => {
          images.delete(request); active = null;
          if (disposed || token !== generation) return resolve({status: "superseded"});
          const element = texture.image, context = element.getContext("2d");
          element.width = request.naturalWidth || request.width || width;
          element.height = request.naturalHeight || request.height || height;
          context.clearRect(0, 0, element.width, element.height);
          context.drawImage(request, 0, 0, element.width, element.height);
          texture.needsUpdate = true; state = "ready"; settle = null; resolve({status: state});
        };
        request.onerror = () => {
          images.delete(request); active = null;
          if (disposed || token !== generation) return resolve({status: "superseded"});
          state = "fallback"; settle = null; resolve({status: state});
        };
        request.src = url;
      });
      active = request;
      return ready;
    };
    const handle = {texture, retry, ready: () => ready, status: () => state,
      dispose() {
        generation += 1;
        if (active) { active.onload = active.onerror = null; images.delete(active); active = null; }
        settle?.({status: "disposed"}); settle = null;
        if (textures.delete(texture)) texture.dispose();
        handles.delete(handle); state = "disposed";
      }};
    handles.add(handle);
    retry();
    return handle;
  };
  return {canvas, image,
    dispose() {
      if (disposed) return;
      disposed = true;
      [...handles].forEach(handle => handle.dispose());
      images.forEach(request => { request.onload = request.onerror = null; }); images.clear();
      textures.forEach(texture => texture.dispose()); textures.clear();
    }};
}
