import * as THREE from 'three';

// Bounds belong to visible geometry, not lights, labels or a decorative background.
export function visibleBounds(objects) {
  const bounds = new THREE.Box3(), part = new THREE.Box3();
  for (const root of objects) {
    let visible = true;
    for (let parent = root; parent; parent = parent.parent) visible &&= parent.visible;
    if (!visible) continue;
    root.updateWorldMatrix(true, true);
    root.traverseVisible(object => {
      if (!object.isMesh) return;
      if (object.isSkinnedMesh || object.isInstancedMesh) object.computeBoundingBox();
      else if (!object.geometry.boundingBox) object.geometry.computeBoundingBox();
      part.copy(object.boundingBox || object.geometry.boundingBox).applyMatrix4(object.matrixWorld);
      bounds.union(part);
    });
  }
  return bounds;
}

// A sphere stays in frame during rotation. The narrower field of view owns distance.
export function fitPerspective({camera, bounds, target, direction, padding=1.12}) {
  if (bounds.isEmpty() || ![...bounds.min, ...bounds.max, camera.aspect, camera.fov, padding].every(Number.isFinite)
      || camera.aspect <= 0 || camera.fov <= 0 || camera.fov >= 180 || padding < 1) return false;
  const sphere = bounds.getBoundingSphere(new THREE.Sphere()), center = sphere.center;
  if (!Number.isFinite(sphere.radius) || ![...center].every(Number.isFinite)) return false;
  const axis = direction ? direction.clone() : camera.position.clone().sub(target || center);
  if (!axis.lengthSq() || ![...axis].every(Number.isFinite)) axis.set(0, 0, 1);
  const radius = Math.max(sphere.radius, 0.0001);
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
  const angle = Math.min(vertical, Math.atan(Math.tan(vertical) * camera.aspect));
  const distance = radius * padding / Math.sin(angle);
  if (!Number.isFinite(distance + radius * 4)) return false;
  camera.zoom = 1;
  camera.position.copy(center).addScaledVector(axis.normalize(), distance);
  camera.near = Math.max(radius / 100, 0.000001);
  camera.far = Math.max(distance + radius * 4, camera.near * 2);
  target?.copy(center);
  camera.lookAt(center); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  return true;
}

// Callers supply render-buffer ownership; only a measured size change resizes it.
export function createViewport({canvas, camera, resize, headers=[], onResize=()=>{}}) {
  let width = 0, height = 0, disposed = false;
  function sync() {
    if (disposed) return false;
    if (headers.length) {
      const top = Math.min(innerHeight, Math.max(0, ...headers.map(el => el.getBoundingClientRect().bottom)));
      Object.assign(canvas.style, {top:top+'px', width:innerWidth+'px', height:Math.max(0, innerHeight-top)+'px'});
    }
    const rect = canvas.getBoundingClientRect(), w = Math.round(rect.width), h = Math.round(rect.height);
    if (w <= 0 || h <= 0 || (width === w && height === h)) return false;
    width = w; height = h; camera.aspect = w / h;
    camera.updateProjectionMatrix(); resize(w, h); onResize();
    return true;
  }
  const observer = new ResizeObserver(sync);
  observer.observe(canvas); headers.forEach(el => observer.observe(el));
  window.addEventListener('resize', sync); sync();
  return {sync, dispose() {disposed = true; observer.disconnect(); window.removeEventListener('resize', sync);}};
}

// Initial/explicit fit may follow viewport changes; a user gesture or authored view takes ownership.
export function mountSceneView({canvas, camera, controls, objects, resize, headers, button, fog=null, beforeFit=()=>{}, fitView=fitPerspective}) {
  let automatic = true, disposed = false;
  function refresh() {
    if (disposed || !automatic) return false;
    const bounds = visibleBounds(objects());
    const fitted = fitView({camera, bounds, target:controls.target});
    if (fitted) {
      controls.maxDistance = Math.max(controls.maxDistance, camera.position.distanceTo(controls.target) * 3);
      if (fog) {
        const radius = bounds.getBoundingSphere(new THREE.Sphere()).radius;
        const distance = camera.position.distanceTo(controls.target);
        fog.near = Math.max(0, distance - radius); fog.far = distance + radius * 4;
      }
      controls.update();
    }
    return fitted;
  }
  const viewport = createViewport({canvas, camera, resize, headers, onResize:refresh});
  function takeControl() {automatic = false; controls.autoRotate = false;}
  function fit() {if (disposed) return; beforeFit(); automatic = true; viewport.sync(); refresh();}
  controls.addEventListener('start', takeControl);
  button.addEventListener('click', fit);
  return {fit, refresh, takeControl, dispose() {
    disposed = true; viewport.dispose(); controls.removeEventListener('start', takeControl); button.removeEventListener('click', fit);
  }};
}
