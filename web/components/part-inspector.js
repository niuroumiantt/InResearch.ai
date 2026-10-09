/* A component owns its renderer and cloned materials, never the source geometry. */
import {createViewport, visibleBounds, fitPerspective} from './scene-view.js';
import {configureAtlasRenderer, addAtlasLights, createAtlasDrawing} from './scene-atlas.js?v=20261008.14';
export function createPartInspector({THREE, environment, meshesFor, materialFor = mesh => mesh.material, initialRotation = () => null}) {
  const iCv = document.createElement("canvas");
  let drawing, viewport, bounds, disposed = false;
  const fit = () => {if (bounds) fitPerspective({camera:iCam, bounds, direction:new THREE.Vector3(0, 0.45, 2.9)});};
  let iRen = null, iScene, iCam, iPivot, iGroup, iSpin = true, iRotX = -0.35, iRotY = 0.7, iVisible = false;
  function initInspector() {
    iRen = new THREE.WebGLRenderer({ canvas: iCv, antialias: true, alpha: true });
    iRen.setPixelRatio(1);
    iRen.outputColorSpace = THREE.SRGBColorSpace;
    iRen.toneMapping = THREE.ACESFilmicToneMapping;
    iRen.toneMappingExposure = 1.25;
    iScene = new THREE.Scene();
    configureAtlasRenderer(THREE, iRen, iScene);
    drawing = createAtlasDrawing({THREE, scene:iScene, normalize:false});
    iScene.environment = environment();
    iCam = new THREE.PerspectiveCamera(36, 1, 0.01, 200);
    viewport = createViewport({canvas:iCv, camera:iCam, resize:(w,h)=>iRen.setSize(w,h,false), onResize:fit});
    addAtlasLights(THREE,iScene,[3,5,4]);
    iPivot = new THREE.Group(); iScene.add(iPivot);
    iGroup = new THREE.Group(); iPivot.add(iGroup);
    let drag = null;
    iCv.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; iSpin = false; iCv.setPointerCapture(e.pointerId); });
    iCv.addEventListener("pointermove", e => {
      if (!drag) return;
      iRotY += (e.clientX - drag[0]) * 0.012;
      iRotX = Math.max(-1.3, Math.min(1.3, iRotX + (e.clientY - drag[1]) * 0.012));
      drag = [e.clientX, e.clientY];
    });
    iCv.addEventListener("pointerup", () => drag = null);
    iCv.addEventListener("pointercancel", () => drag = null);
  }
  function cloneMatForInspect(m) {
    const c = m.clone();
    c.userData = {};
    return c;
  }
  function buildInspector(pid) {
    if (disposed) return false;
    const meshes = meshesFor(pid);
    iVisible = false;
    if (!meshes?.length) return false;
    if (!iRen) initInspector();
    while (iGroup.children.length) {
      const old = iGroup.children[0];
      (Array.isArray(old.material) ? old.material : [old.material]).filter(Boolean).forEach(m => m.dispose());
      iGroup.remove(old);
    }
    iPivot.rotation.set(0, 0, 0);
    iGroup.position.set(0, 0, 0);
    meshes.forEach(src => {
      src.updateWorldMatrix(true, false);
      const source = materialFor(src);
      const mat = Array.isArray(source) ? source.map(cloneMatForInspect) : cloneMatForInspect(source);
      const m = new THREE.Mesh(src.geometry, mat);
      m.applyMatrix4(src.matrixWorld);
      iGroup.add(m);
    });
    drawing.sync();
    bounds = visibleBounds([iGroup]);
    if (bounds.isEmpty()) return false;
    const center = bounds.getCenter(new THREE.Vector3());
    iGroup.position.sub(center); bounds.translate(center.negate());
    viewport.sync(); fit();
    const initial = initialRotation(pid);
    iSpin = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    iRotX = Number.isFinite(initial?.x) ? Math.max(-1.3, Math.min(1.3, initial.x)) : -0.35;
    iRotY = Number.isFinite(initial?.y) ? initial.y : 0.7;
    iVisible = true;
    return true;
  }
  function inspectTick() {
    if (!iRen || !iVisible || !iCv.isConnected) return;
    viewport.sync();
    if (iSpin) iRotY += 0.006;
    iPivot.rotation.set(iRotX, iRotY, 0);
    iScene.environment = environment();
    drawing.update();
    iRen.render(iScene, iCam);
  }

  return {canvas: iCv, show: buildInspector, tick: inspectTick, hide: () => { iVisible = false; }, dispose() {
    if (disposed) return;
    disposed = true; iVisible = false; viewport?.dispose(); drawing?.dispose();
    iGroup?.children.forEach(mesh => [].concat(mesh.material || []).forEach(material => material.dispose()));
    iGroup?.clear(); iRen?.dispose(); iRen = null; bounds = null;
  }};
}
