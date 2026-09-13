/** Canvas-owned gestures and a disposable overlay; research meshes/materials stay intact. */
export function createScenePicking({THREE, canvas, camera, pickables, tip, describe, select}) {
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  const listeners = new AbortController();
  const material = new THREE.MeshBasicMaterial({color:0x93c5fd, transparent:true,
    opacity:0.25, depthWrite:false, polygonOffset:true, polygonOffsetFactor:-1, polygonOffsetUnits:-1});
  let overlay = null, hovered = null, gesture = null;
  function clear() {
    overlay?.removeFromParent(); overlay = null; hovered = null;
    tip.style.display = 'none'; canvas.style.cursor = 'grab';
  }
  function inside(event) {
    const rect = canvas.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && event.clientX >= rect.left && event.clientX < rect.right &&
      event.clientY >= rect.top && event.clientY < rect.bottom && document.elementFromPoint(event.clientX, event.clientY) === canvas;
  }
  function visible(object) {
    for (let parent = object; parent; parent = parent.parent) if (!parent.visible) return false;
    return true;
  }
  function pick(event) {
    if (!inside(event)) return null;
    const rect = canvas.getBoundingClientRect();
    mouse.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    camera.updateWorldMatrix(true, false);
    pickables.forEach(object => object.updateWorldMatrix(true, false));
    ray.setFromCamera(mouse, camera);
    return ray.intersectObjects(pickables, false).find(hit => visible(hit.object))?.object || null;
  }
  function move(event) {
    if (gesture) {
      gesture.dragged ||= Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > 5;
      clear(); return;
    }
    const object = pick(event), text = object && describe(object);
    if (!text) { clear(); return; }
    if (hovered !== object) {
      clear(); hovered = object;
      overlay = new THREE.Mesh(object.geometry, material);
      overlay.raycast = () => {}; object.add(overlay);
    }
    tip.textContent = text; tip.style.display = 'block';
    tip.style.left = Math.max(0, Math.min(event.clientX + 12, innerWidth - tip.offsetWidth - 8)) + 'px';
    tip.style.top = Math.max(0, Math.min(event.clientY + 12, innerHeight - tip.offsetHeight - 8)) + 'px';
    canvas.style.cursor = 'pointer';
  }
  function down(event) {
    clear();
    if (event.button !== 0 || event.isPrimary === false || gesture) { gesture = null; return; }
    if (inside(event)) gesture = {id:event.pointerId, x:event.clientX, y:event.clientY, dragged:false};
  }
  function up(event) {
    const previous = gesture; gesture = null;
    if (!previous || previous.id !== event.pointerId || previous.dragged ||
      Math.hypot(event.clientX - previous.x, event.clientY - previous.y) > 5) return;
    const object = pick(event); clear();
    if (object && describe(object)) select(object);
  }
  function cancel() { gesture = null; clear(); }
  const on = (target, type, listener) => target.addEventListener(type, listener, {signal:listeners.signal});
  on(canvas, 'pointermove', move); on(canvas, 'pointerdown', down); on(canvas, 'pointerup', up);
  on(canvas, 'pointerleave', clear); on(canvas, 'pointercancel', cancel); on(window, 'blur', cancel);
  return {clear, dispose() { cancel(); listeners.abort(); material.dispose(); }};
}
