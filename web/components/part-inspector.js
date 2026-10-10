/* Own the preview renderer, clones, controls and dialog; borrow source geometry/textures. */
import {createViewport, visibleBounds, fitPerspective} from './scene-view.js';
import {configureAtlasRenderer, addAtlasLights, createAtlasDrawing, atlasSnapshot} from './scene-atlas.js?v=20261008.14';

export function createPartInspector({THREE, environment, meshesFor,
  materialFor = mesh => mesh.material, initialRotation = () => null,
  identityFor = pid => 'part:' + pid, titleFor = pid => pid}) {
  const iCv = document.createElement('canvas');
  const controls = document.createElement('div');
  controls.className = 'part-inspector-controls'; controls.hidden = true;
  controls.setAttribute('aria-label', '独立三维预览操作');
  const identityLabel = document.createElement('div');
  identityLabel.className = 'part-inspector-identity';
  const actions = document.createElement('div'); actions.className = 'part-inspector-actions';
  const status = document.createElement('div'); status.className = 'part-inspector-status';
  status.setAttribute('role', 'status'); controls.append(identityLabel, actions, status);
  const listeners = [], downloads = new Map();
  let drawing, viewport, bounds, disposed = false, style, dialog, dialogTitle, dialogIdentity, dialogView;
  let expanded = false, origin = null, drag = null, currentId = '', currentTitle = '';
  let iRen = null, iScene, iCam, iPivot, iGroup, iSpin = true, iRotX = -0.35, iRotY = 0.7, iVisible = false;

  function listen(node, type, handler, options) {
    node.addEventListener(type, handler, options);
    listeners.push(() => node.removeEventListener(type, handler, options));
  }
  function button(action, title, handler) {
    const node = document.createElement('button'); node.type = 'button';
    node.dataset.previewAction = action; node.textContent = title;
    listen(node, 'click', event => { event.stopPropagation(); handler(); });
    actions.append(node); return node;
  }
  button('fit', '适配预览', () => { fit(); renderPreview(); });
  const spinButton = button('spin', '暂停旋转', () => { iSpin = !iSpin; updateControls(); });
  const expandButton = button('expand', '放大三维预览', () => expanded ? closeExpanded() : expand());
  const downloadButton = button('download', '下载当前预览 SVG', download);
  function updateControls() {
    spinButton.textContent = iSpin ? '暂停旋转' : '开始旋转';
    spinButton.setAttribute('aria-pressed', String(iSpin));
    expandButton.textContent = expanded ? '返回档案内预览' : '放大三维预览';
    expandButton.setAttribute('aria-expanded', String(expanded));
    identityLabel.textContent = currentTitle ? currentTitle + ' · ' + currentId + ' · 通用示意' : '';
    controls.dataset.objectId = currentId;
    if (dialog) {
      dialogTitle.textContent = currentTitle + ' · 独立三维预览';
      dialogIdentity.textContent = currentId + ' · 通用结构示意，非现场配置或工程图';
      dialog.dataset.objectId = currentId;
    }
  }
  function ensureStyle() {
    if (style) return;
    style = document.createElement('style');
    style.textContent = [
      '.part-inspector-controls { padding:8px; color:var(--text,#454641); }',
      '.part-inspector-controls[hidden] { display:none; }',
      '.part-inspector-identity { font-size:12px; overflow-wrap:anywhere; margin-bottom:6px; }',
      '.part-inspector-actions { display:flex; flex-wrap:wrap; gap:6px; }',
      '.part-inspector-actions button,.part-inspector-dialog-close { min-height:36px; padding:6px 9px; font:inherit; font-size:12px; color:var(--text,#454641); background:var(--ui-surface,#faf9f2); border:1px solid var(--line,#b8b8b0); border-radius:var(--ui-radius,6px); cursor:pointer; }',
      '.part-inspector-status { font-size:12px; overflow-wrap:anywhere; }',
      '.part-inspector-dialog { box-sizing:border-box; width:min(1100px,calc(100vw - 24px)); height:min(780px,calc(100dvh - 24px)); max-width:none; max-height:none; padding:0; color:var(--text,#454641); background:var(--ui-surface,#faf9f2); border:1px solid var(--line,#b8b8b0); border-radius:var(--ui-radius,10px); }',
      '.part-inspector-dialog[open] { display:flex; flex-direction:column; }',
      '.part-inspector-dialog::backdrop { background:rgba(0,0,0,.5); }',
      '.part-inspector-dialog-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding:12px; }',
      '.part-inspector-dialog-header h2 { margin:0; font-size:16px; overflow-wrap:anywhere; }',
      '.part-inspector-dialog-header p { margin:5px 0 0; font-size:12px; overflow-wrap:anywhere; }',
      '.part-inspector-dialog-view { flex:1; min-height:0; background:#faf9f2; }',
      '.part-inspector-dialog-view canvas { display:block; width:100%; height:100%; touch-action:none; cursor:grab; }'
    ].join('\n');
    document.head.append(style);
  }
  function applyRotation() { iPivot?.rotation.set(iRotX, iRotY, 0); }
  function fit() {
    if (disposed || !iGroup?.children.length) return false;
    applyRotation(); bounds = visibleBounds([iGroup]);
    return fitPerspective({camera:iCam, bounds, direction:new THREE.Vector3(0, 0.45, 2.9)});
  }
  function releaseDrag() {
    if (!drag) return;
    const pointer = drag.pointer; drag = null;
    if (iCv.hasPointerCapture(pointer)) iCv.releasePointerCapture(pointer);
  }
  function initInspector() {
    ensureStyle();
    iRen = new THREE.WebGLRenderer({canvas:iCv, antialias:true, alpha:true});
    iRen.setPixelRatio(1);
    iScene = new THREE.Scene(); configureAtlasRenderer(THREE, iRen, iScene);
    drawing = createAtlasDrawing({THREE, scene:iScene, normalize:false});
    iScene.environment = environment(); iCam = new THREE.PerspectiveCamera(36, 1, 0.01, 200);
    iPivot = new THREE.Group(); iScene.add(iPivot); iGroup = new THREE.Group(); iPivot.add(iGroup);
    viewport = createViewport({canvas:iCv, camera:iCam, resize:(w,h)=>iRen.setSize(w,h,false), onResize:fit});
    addAtlasLights(THREE, iScene, [3,5,4]);
    listen(iCv, 'pointerdown', event => {
      if (disposed || !iVisible || !event.isPrimary || event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      drag = {pointer:event.pointerId, x:event.clientX, y:event.clientY};
      iSpin = false; updateControls(); iCv.setPointerCapture(event.pointerId);
    });
    listen(iCv, 'pointermove', event => {
      if (!drag || event.pointerId !== drag.pointer) return;
      event.preventDefault(); event.stopPropagation();
      iRotY += (event.clientX - drag.x) * 0.012;
      iRotX = Math.max(-1.3, Math.min(1.3, iRotX + (event.clientY - drag.y) * 0.012));
      drag.x = event.clientX; drag.y = event.clientY;
    });
    for (const type of ['pointerup','pointercancel','lostpointercapture']) listen(iCv, type, event => {
      if (!drag || event.pointerId !== drag.pointer) return;
      event.stopPropagation(); releaseDrag();
    });
  }
  function clearClones(rebuildDrawing = true) {
    drawing?.dispose(); drawing = null;
    const materials = new Set();
    iGroup?.children.forEach(mesh => [].concat(mesh.material || []).forEach(material => materials.add(material)));
    materials.forEach(material => material.dispose()); iGroup?.clear(); bounds = null;
    if (rebuildDrawing && iScene) drawing = createAtlasDrawing({THREE, scene:iScene, normalize:false});
  }
  function cloneMatForInspect(material) {
    const clone = material.clone(); clone.userData = {}; return clone;
  }
  function buildInspector(pid) {
    if (disposed) return false;
    hide(); clearClones(); currentId = ''; currentTitle = ''; status.textContent = ''; updateControls();
    const meshes = meshesFor(pid);
    if (!meshes?.length) return false;
    if (!iRen) initInspector();
    iPivot.rotation.set(0, 0, 0); iGroup.position.set(0, 0, 0);
    meshes.forEach(source => {
      source.updateWorldMatrix(true, false);
      const material = materialFor(source);
      const clone = new THREE.Mesh(source.geometry, Array.isArray(material) ? material.map(cloneMatForInspect) : cloneMatForInspect(material));
      clone.applyMatrix4(source.matrixWorld); iGroup.add(clone);
    });
    bounds = visibleBounds([iGroup]);
    if (bounds.isEmpty()) { clearClones(); return false; }
    const center = bounds.getCenter(new THREE.Vector3()); iGroup.position.sub(center);
    const initial = initialRotation(pid);
    iRotX = Number.isFinite(initial?.x) ? Math.max(-1.3, Math.min(1.3, initial.x)) : -0.35;
    iRotY = Number.isFinite(initial?.y) ? initial.y : 0.7;
    currentId = String(identityFor(pid) || 'part:' + pid); currentTitle = String(titleFor(pid) || pid);
    iSpin = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    iVisible = true; controls.hidden = false; updateControls(); applyRotation();
    drawing.sync(); viewport.sync(); fit(); return true;
  }
  function renderPreview() {
    if (disposed || !iRen || !iVisible || !iCv.isConnected) return false;
    applyRotation(); viewport.sync(); iScene.environment = environment();
    drawing.update(); iRen.render(iScene, iCam); return true;
  }
  function inspectTick() {
    if (disposed || !iRen || !iVisible || !iCv.isConnected) return;
    if (iSpin) iRotY += 0.006;
    renderPreview();
  }
  function dialogKeydown(event) {
    if (!expanded) return;
    // Main-scene Escape/domain shortcuts must not receive this dialog's keystrokes.
    event.stopPropagation();
    if (event.key === 'Escape') { event.preventDefault(); closeExpanded(); }
  }
  function ensureDialog() {
    if (dialog) return;
    dialog = document.createElement('dialog'); dialog.className = 'part-inspector-dialog';
    dialog.setAttribute('aria-label', '放大独立三维预览');
    const header = document.createElement('header'); header.className = 'part-inspector-dialog-header';
    const heading = document.createElement('div');
    dialogTitle = document.createElement('h2'); dialogIdentity = document.createElement('p');
    heading.append(dialogTitle, dialogIdentity);
    const close = document.createElement('button'); close.type = 'button';
    close.className = 'part-inspector-dialog-close'; close.textContent = '关闭放大预览';
    listen(close, 'click', () => closeExpanded()); header.append(heading, close);
    dialogView = document.createElement('div'); dialogView.className = 'part-inspector-dialog-view';
    dialog.append(header, dialogView); document.body.append(dialog);
    listen(dialog, 'cancel', event => { event.preventDefault(); closeExpanded(); });
    // A queued close event from an earlier opening must not close a newly reopened dialog.
    listen(dialog, 'close', () => { if (expanded && !dialog.open) closeExpanded(); });
    listen(dialog, 'click', event => {
      event.stopPropagation();
      const rect = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) closeExpanded();
    });
    for (const type of ['pointerdown','pointerup','pointermove']) listen(dialog, type, event => event.stopPropagation());
  }
  function placeholder(node) {
    if (!node.parentNode) return null;
    const mark = document.createComment('independent preview position'); node.before(mark); return mark;
  }
  function expand() {
    if (disposed || !iVisible || !iCv.isConnected || expanded) return false;
    releaseDrag(); ensureDialog();
    origin = {canvas:placeholder(iCv), controls:placeholder(controls), focus:document.activeElement};
    expanded = true; dialogView.append(iCv); dialog.append(controls); updateControls();
    document.addEventListener('keydown', dialogKeydown, true);
    try { dialog.showModal(); }
    catch (error) { closeExpanded({restoreFocus:false}); status.textContent = '放大预览未能打开，请重试'; return false; }
    viewport.sync(); fit(); renderPreview(); return true;
  }
  function closeExpanded({restoreFocus = true} = {}) {
    if (!expanded) return;
    releaseDrag(); expanded = false; document.removeEventListener('keydown', dialogKeydown, true);
    if (dialog.open) dialog.close();
    for (const [node, mark] of [[iCv, origin?.canvas],[controls, origin?.controls]]) {
      if (mark?.parentNode) mark.replaceWith(node); else node.remove();
    }
    const focus = origin?.focus; origin = null; updateControls();
    if (iVisible && !disposed) { viewport.sync(); fit(); renderPreview(); }
    if (restoreFocus && focus?.isConnected) focus.focus({preventScroll:true});
  }
  function hide() {
    iVisible = false; controls.hidden = true; releaseDrag(); closeExpanded({restoreFocus:false});
  }
  function download() {
    if (!renderPreview()) return;
    downloadButton.disabled = true; status.textContent = '';
    try {
      const svg = atlasSnapshot({THREE, scene:iScene, camera:iCam, canvas:iCv, drawing,
        render:renderPreview, title:currentTitle + ' · 独立三维预览',
        caption:'当前独立预览视角；对象 ' + currentTitle + '；标识 ' + currentId + '；通用示意，数量和比例不代表现场事实',
        selected:{id:currentId, name:currentTitle, meshes:[...iGroup.children]}});
      const url = URL.createObjectURL(new Blob([svg], {type:'image/svg+xml'}));
      downloads.set(url, setTimeout(() => { URL.revokeObjectURL(url); downloads.delete(url); }, 1000));
      const anchor = document.createElement('a'); anchor.href = url;
      anchor.download = 'preview-' + currentId.replace(/[^a-zA-Z0-9._-]/g, '-').slice(0,120) + '.svg';
      document.body.append(anchor); anchor.click(); anchor.remove(); status.textContent = '已导出当前独立预览视角';
    } catch (error) { status.textContent = '预览导出失败，请重试'; }
    finally { downloadButton.disabled = false; }
  }
  return {canvas: iCv, controls, show: buildInspector, tick: inspectTick, hide, fit, expand, closeExpanded, download, dispose() {
    if (disposed) return;
    hide(); disposed = true; viewport?.dispose(); clearClones(false);
    listeners.splice(0).forEach(remove => remove()); document.removeEventListener('keydown', dialogKeydown, true);
    downloads.forEach((timer,url) => { clearTimeout(timer); URL.revokeObjectURL(url); }); downloads.clear();
    dialog?.remove(); style?.remove(); controls.remove(); iCv.remove();
    iRen?.dispose(); iRen = null; iScene = null; bounds = null;
  }};
}
