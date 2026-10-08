/* Shared technical-atlas drawing recipe. Own edges and label textures, borrow meshes. */
import {visibleBounds} from './scene-view.js';
export const ATLAS = Object.freeze({paper:'#FAF9F2', graphite:'#454641', blue:'#09689B', exposure:1});

export function configureAtlasRenderer(THREE, renderer, scene) {
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.toneMappingExposure = ATLAS.exposure;
  scene.background = new THREE.Color(ATLAS.paper);
  scene.fog = null;
}

export function atlasMaterial(THREE, color, options = {}) {
  const material = new THREE.MeshStandardMaterial({color, roughness:0.65, metalness:0.25, ...options});
  finishAtlasMaterial(material);
  return material;
}
function finishAtlasMaterial(material) {
  if (!material.isMeshStandardMaterial) return;
  material.roughness = Math.max(0.48, material.roughness);
  material.envMapIntensity = 0.35;
  material.emissiveIntensity = Math.min(material.emissiveIntensity, 0.12);
  // Old decorative blue/purple hardware becomes charcoal; textured source panels remain intact.
  const hsl = material.color.getHSL({});
  if (hsl.h > 0.50 && hsl.h < 0.90 && hsl.s > 0.2) {
    material.color.setHSL(0.16, 0.025, Math.max(0.16, hsl.l));
  }
}

export function atlasStudio(THREE) {
  const studio = new THREE.Scene();
  studio.add(new THREE.Mesh(new THREE.BoxGeometry(60,60,60),
    new THREE.MeshBasicMaterial({color:0xdcdcd5, side:THREE.BackSide})));
  for (const [x,y,z,rx,ry,intensity] of [[0,28,0,Math.PI/2,0,3],[-28,12,0,0,Math.PI/2,2],[28,12,0,0,-Math.PI/2,2]]) {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(24,18),new THREE.MeshBasicMaterial({color:0xffffff}));
    panel.material.color.multiplyScalar(intensity); panel.position.set(x,y,z); panel.rotation.set(rx,ry,0); studio.add(panel);
  }
  return studio;
}

export function addAtlasLights(THREE, scene, keyPosition, shadowExtent) {
  scene.add(new THREE.HemisphereLight(0xffffff,0xd9d8cf,1.5));
  const key = new THREE.DirectionalLight(0xffffff,2);
  key.position.set(...keyPosition);
  if (shadowExtent) {
    key.castShadow = true; key.shadow.mapSize.set(2048,2048);
    Object.assign(key.shadow.camera, shadowExtent);
    key.shadow.bias = -0.0004; key.shadow.radius = 4;
  }
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff,0.65);
  fill.position.set(-keyPosition[0],keyPosition[1]/2,-keyPosition[2]); scene.add(fill);
}

export function createAtlasDrawing({THREE, scene, normalize = true}) {
  const edges = new Map(), geometries = new Map(), labels = new Set();
  const labelNodes = new Map();
  let overlay = null, overlayCanvas, overlayCamera;
  const lineMaterial = new THREE.LineBasicMaterial({color:ATLAS.graphite, transparent:true, opacity:0.65});
  let disposed = false;
  function sync() {
    if (disposed) return;
    const meshes = [];
    scene.traverse(object => {if (object.isMesh && !object.userData.atlasSkip) meshes.push(object);});
    const present = new Set(meshes);
    for (const [mesh,line] of edges) if (!present.has(mesh)) {mesh.remove(line); edges.delete(mesh);}
    for (const mesh of meshes) {
      if (edges.has(mesh) || mesh.isSkinnedMesh || mesh.isInstancedMesh) continue;
      if (normalize) [].concat(mesh.material || []).forEach(finishAtlasMaterial);
      if (!geometries.has(mesh.geometry)) geometries.set(mesh.geometry,new THREE.EdgesGeometry(mesh.geometry,35));
      const line = new THREE.LineSegments(geometries.get(mesh.geometry),lineMaterial);
      line.userData.atlasOutline = true; line.raycast = () => {}; // never steal a component selection
      mesh.add(line); edges.set(mesh,line);
    }
    const used = new Set(meshes.map(mesh=>mesh.geometry));
    for (const [source,geometry] of geometries) if (!used.has(source)) {geometry.dispose();geometries.delete(source);}
  }
  function update() {
    edges.forEach((line,mesh)=>{line.visible=[].concat(mesh.material || []).some(material=>material.visible && material.opacity>=0.5);});
    if (!overlay || disposed) return;
    const rect = overlayCanvas.getBoundingClientRect();
    Object.assign(overlay.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});
    overlay.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);
    scene.updateMatrixWorld(true); overlayCamera.updateMatrixWorld(true);
    const occupied = [];
    for (const sprite of labels) {
      if (!labelNodes.has(sprite)) {
        const text = document.createElementNS('http://www.w3.org/2000/svg','text');
        text.textContent = sprite.userData.atlasLabel.text; text.setAttribute('text-anchor','middle');
        text.setAttribute('fill',ATLAS.graphite); text.setAttribute('stroke',ATLAS.paper);
        text.setAttribute('stroke-width','6'); text.setAttribute('paint-order','stroke');
        overlay.append(text); labelNodes.set(sprite,text);
      }
      const text = labelNodes.get(sprite), point = sprite.getWorldPosition(new THREE.Vector3()).project(overlayCamera);
      const visible = sprite.visible && Math.abs(point.x)<=1 && Math.abs(point.y)<=1 && Math.abs(point.z)<=1;
      text.style.display = visible ? '' : 'none';
      if (!visible) continue;
      const font = rect.width<480 ? 14 : 16;
      text.setAttribute('font-size',font);
      const half = Math.min(rect.width/2-8, text.getComputedTextLength()/2);
      const x = Math.max(half+8,Math.min(rect.width-half-8,(point.x+1)*rect.width/2));
      let y = Math.max(22,Math.min(rect.height-12,(1-point.y)*rect.height/2));
      for (const used of occupied) if (Math.abs(used.y-y)<22 && Math.abs(used.x-x)<used.half+half) y=used.y+24;
      occupied.push({x,y,half}); text.setAttribute('x',x); text.setAttribute('y',y);
    }
  }
  function attachLabels(canvas,camera) {
    overlayCanvas=canvas; overlayCamera=camera;
    overlay=document.createElementNS('http://www.w3.org/2000/svg','svg');
    overlay.classList.add('atlas-scene-labels'); overlay.setAttribute('aria-label','结构图册标注');
    Object.assign(overlay.style,{position:'fixed',pointerEvents:'none',zIndex:'2',fontFamily:'Inter,"Noto Sans SC",sans-serif'});
    document.body.append(overlay);
    labels.forEach(sprite=>sprite.material.opacity=0); update();
  }
  function label(text,x,y,z,size,divisor,num,showAfter) {
    const S = 2, canvas = document.createElement('canvas'), measure = canvas.getContext('2d');
    measure.font = '600 52px Inter, "Noto Sans SC", sans-serif';
    canvas.width = Math.ceil(measure.measureText(text).width + 64 + (num ? 80 : 0)); canvas.height = 96;
    const g = canvas.getContext('2d'); g.fillStyle = ATLAS.paper; g.fillRect(0,0,canvas.width,canvas.height);
    g.strokeStyle = ATLAS.graphite; g.lineWidth = 1; g.strokeRect(1,1,canvas.width-2,canvas.height-2);
    g.font = '600 52px Inter, "Noto Sans SC", sans-serif'; g.textBaseline = 'middle';
    g.fillStyle = ATLAS.graphite; g.fillText((num ? num+' ' : '')+text,20,48);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthWrite:false}));
    sprite.scale.set(canvas.width/(divisor*S)*size,canvas.height/(divisor*S)*size,1); sprite.position.set(x,y,z);
    sprite.userData.atlasLabel = {text:(num ? num+' ' : '')+text};
    if (showAfter !== undefined) {sprite.userData.showAfter = showAfter; sprite.visible = false;}
    sprite.raycast = () => {}; scene.add(sprite); labels.add(sprite); return sprite;
  }
  return {sync,update,label,labels,attachLabels,dispose() {
    if (disposed) return; disposed = true;
    edges.forEach((line,mesh)=>mesh.remove(line)); edges.clear();
    geometries.forEach(geometry=>geometry.dispose()); geometries.clear(); lineMaterial.dispose();
    labels.forEach(sprite=>{sprite.removeFromParent();sprite.material.map.dispose();sprite.material.dispose();}); labels.clear();
    overlay?.remove(); labelNodes.clear();
  }};
}

const escape = text => String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
function wrappedText(text,width,font=14) {
  const context=document.createElement('canvas').getContext('2d'); context.font=`${font}px Inter,"Noto Sans SC",sans-serif`;
  const lines=[];let line='';
  for(const character of text) {
    if(line && context.measureText(line+character).width>width){lines.push(line);line='';}
    line+=character;
  }
  if(line)lines.push(line);return lines;
}
// Snapshot the CURRENT view. Text is editable SVG; geometry stays a raster, not a CAD export.
export function atlasSnapshot({THREE, scene, camera, canvas, render, drawing, title, caption, selected}) {
  caption = typeof caption === 'function' ? caption() : caption;
  selected = typeof selected === 'function' ? selected() : selected;
  scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
  const visibleLabels = [...drawing.labels].filter(label=>label.visible);
  const coordinates = visibleLabels.map(label=>({text:label.userData.atlasLabel.text,
    point:label.getWorldPosition(new THREE.Vector3()).project(camera)}));
  let pixels;
  try {
    visibleLabels.forEach(label=>label.visible=false); render(); pixels = canvas.toDataURL('image/png');
  } finally {visibleLabels.forEach(label=>label.visible=true); render();}
  const width = canvas.width, height = canvas.height, margin = 48;
  const footnote = wrappedText(`${caption} · 通用结构示意，非工程图；当前视角，像素 ${width}×${height}`,width-48);
  const footer = 66+footnote.length*20;
  const font = Math.max(16,Math.round(width/96));
  const texts = coordinates.filter(({point})=>Math.abs(point.x)<=1 && Math.abs(point.y)<=1 && Math.abs(point.z)<=1)
    .map(({text,point})=>`<text x="${(point.x+1)*width/2}" y="${(1-point.y)*height/2+margin}" text-anchor="middle">${escape(text)}</text>`);
  let leader = '';
  if (selected?.meshes?.length) {
    const bounds = visibleBounds(selected.meshes);
    if (!bounds.isEmpty()) {
      const point = bounds.getCenter(new THREE.Vector3()).project(camera);
      if (Math.abs(point.x)<=1 && Math.abs(point.y)<=1 && Math.abs(point.z)<=1) {
        const x=(point.x+1)*width/2,y=(1-point.y)*height/2+margin;
        leader=`<g data-object-id="${escape(selected.id)}"><path d="M 24 ${height+margin+32} H 100 L ${x} ${y}" fill="none" stroke="${ATLAS.blue}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="4" fill="${ATLAS.blue}"/><text x="112" y="${height+margin+38}">${escape(selected.name)} · ${escape(selected.id)}</text></g>`;
      }
    }
  }
  const footTexts=footnote.map((line,index)=>`<text x="24" y="${height+margin+66+index*20}" font-size="14">${escape(line)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height+margin+footer}" viewBox="0 0 ${width} ${height+margin+footer}"><metadata>${escape(JSON.stringify({style:'white-technical-atlas-v1',recipe:'scene-atlas-v1',title,caption,pixels:[width,height],object_id:selected?.id || null,projection:'current interactive perspective',identity:'generic schematic; no model-specific dimensions'}))}</metadata><rect width="100%" height="100%" fill="${ATLAS.paper}"/><image x="0" y="${margin}" width="${width}" height="${height}" href="${pixels}"/><g id="editable-labels" fill="${ATLAS.graphite}" font-family="Inter,Noto Sans SC,sans-serif" font-size="${font}"><text x="24" y="32">${escape(title)}</text>${texts.join('')}${leader}${footTexts}</g></svg>`;
}

export function mountAtlasExport(options) {
  const {button} = options;
  function download() {
    button.disabled = true;
    try {
      const svg = atlasSnapshot(options);
      const url = URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = options.filename;
      anchor.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
      button.textContent = '导出图册';
    } catch (error) {button.textContent = '导出失败，请重试'; console.error(error);}
    finally {button.disabled = false;}
  }
  button.addEventListener('click',download);
  return {dispose:()=>button.removeEventListener('click',download)};
}
