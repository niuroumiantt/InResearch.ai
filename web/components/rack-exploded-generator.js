/* TA14 independent native illustration. Arbitrary units, never CAD/OEM dimensions.
 * Same generic assembly as TA13, with three representative devices and virtual
 * skins translated. Native1536x1024 rendering is separate from user snapshots.
 */
import * as THREE from 'three';
import {buildRackAssembly} from './rack-assembly.js';
import {atlasMaterial,configureAtlasRenderer,addAtlasLights,createAtlasDrawing,atlasStudio} from './scene-atlas.js';
export function renderNativeRackExploded(canvas,{width=1536,height=1024}={}) {
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1536||height<1024)throw new RangeError('Formal master requires native1536x1024 or more');
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(1);renderer.setSize(width,height,false);
  const scene=new THREE.Scene();configureAtlasRenderer(THREE,renderer,scene);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;addAtlasLights(THREE,scene,[14,22,12],{left:-25,right:25,top:25,bottom:-25,near:.1,far:80});
  const pmrem=new THREE.PMREMGenerator(renderer),studio=atlasStudio(THREE),environment=pmrem.fromScene(studio,.06);scene.environment=environment.texture;
  const assembly=buildRackAssembly({THREE,material:(c,o)=>atlasMaterial(THREE,c,o),tag:(o,id)=>o.traverse(m=>m.userData.part=id),label:()=>new THREE.Group(),exploded:true});assembly.explode(1);scene.add(assembly.root);
  const drawing=createAtlasDrawing({THREE,scene});drawing.sync();
  const bbox=new THREE.Box3().setFromObject(assembly.root),center=bbox.getCenter(new THREE.Vector3()),camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,300);camera.position.copy(center).add(new THREE.Vector3(24,10,36));camera.lookAt(center);camera.updateMatrixWorld(true);
  const points=[];assembly.root.updateMatrixWorld(true);let meshes=0;
  assembly.root.traverse(o=>{if(!o.isMesh)return;meshes++;o.geometry.computeBoundingBox();const b=o.geometry.boundingBox;for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])points.push(new THREE.Vector3(x,y,z).applyMatrix4(o.matrixWorld).applyMatrix4(camera.matrixWorldInverse));});
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y),midX=(Math.min(...xs)+Math.max(...xs))/2,midY=(Math.min(...ys)+Math.max(...ys))/2;
  const shift=new THREE.Vector3(midX,midY,0).applyQuaternion(camera.quaternion);camera.position.add(shift);center.add(shift);camera.lookAt(center);
  const ratio=width/height,halfH=Math.max((Math.max(...ys)-Math.min(...ys))/2,(Math.max(...xs)-Math.min(...xs))/(2*ratio))*1.08;Object.assign(camera,{left:-halfH*ratio,right:halfH*ratio,top:halfH,bottom:-halfH});camera.updateProjectionMatrix();camera.updateMatrixWorld(true);renderer.render(scene,camera);
  const point=(x,y,z)=>{const p=new THREE.Vector3(x,y,z).project(camera);return[(p.x+1)*width/2,(1-p.y)*height/2];};
  const instances=assembly.explosionInstances.map(i=>({id:i.id,category:i.part,home:i.home.toArray(),axis:i.axis.toArray(),actual:i.object.position.toArray()}));
  const evidence={method:'Independent native WebGL render, no interpolation or interactive snapshot',native_pixels:[canvas.width,canvas.height],projection:'OrthographicCamera, oblique exploded assembly view',identity:'Generic correspondence diagram; not OEM/CAD/maintenance procedure',mesh_count:meshes,counts:assembly.counts,instances,camera:{position:camera.position.toArray(),target:center.toArray(),frustum:[camera.left,camera.right,camera.top,camera.bottom]}};
  function composition(){
    png();const sheet=document.createElement('canvas');sheet.width=width;sheet.height=height;
    const ctx=sheet.getContext('2d');ctx.drawImage(canvas,0,0);
    const states=[];assembly.root.traverse(o=>{if(o.isMesh)states.push([o,o.visible]);});
    const detailEvidence=[];
    for(const [id,x,y,w,h,offset,stage] of [
      ['compute-front',32,106,320,145,[0,0,30],1],
      ['power-front',32,330,320,145,[0,0,30],1],
      ['rail-pair',1184,630,320,210,[-6,3,8],0]]){
      assembly.explode(stage);assembly.root.updateMatrixWorld(true);
      const compute=assembly.root.getObjectByName('compute-4'),power=assembly.root.getObjectByName('power-shelf-1'),fixed=assembly.root.getObjectByName('compute-4-fixed-outer-rails');
      const chosen=new Set();
      if(id!=='rail-pair')(id==='compute-front'?compute:power).traverse(o=>{if(o.isMesh)chosen.add(o);});
      else for(const parent of [compute,fixed])parent.traverse(o=>{if(o.isMesh&&['outer-slide-rail','inner-slide-rail','rail-end-bracket'].includes(o.name)&&o.position.x<0)chosen.add(o);});
      states.forEach(([o])=>o.visible=chosen.has(o));
      const b=new THREE.Box3();chosen.forEach(o=>b.expandByObject(o));const c=b.getCenter(new THREE.Vector3()),cam=new THREE.OrthographicCamera(-1,1,1,-1,.01,200);cam.position.copy(c).add(new THREE.Vector3(...offset));cam.lookAt(c);cam.updateMatrixWorld(true);
      const pts=[];chosen.forEach(o=>{o.geometry.computeBoundingBox();const q=o.geometry.boundingBox;for(const ax of [q.min.x,q.max.x])for(const ay of [q.min.y,q.max.y])for(const az of [q.min.z,q.max.z])pts.push(new THREE.Vector3(ax,ay,az).applyMatrix4(o.matrixWorld).applyMatrix4(cam.matrixWorldInverse));});
      const dx=pts.map(p=>p.x),dy=pts.map(p=>p.y),shift=new THREE.Vector3((Math.min(...dx)+Math.max(...dx))/2,(Math.min(...dy)+Math.max(...dy))/2,0).applyQuaternion(cam.quaternion);cam.position.add(shift);c.add(shift);cam.lookAt(c);
      const span=Math.max((Math.max(...dy)-Math.min(...dy))/2,(Math.max(...dx)-Math.min(...dx))*h/w/2)*1.10;Object.assign(cam,{left:-span*w/h,right:span*w/h,top:span,bottom:-span});cam.updateProjectionMatrix();cam.updateMatrixWorld(true);
      renderer.setSize(w,h,false);renderer.render(scene,cam);ctx.drawImage(canvas,x,y);
      const project=(name)=>{const o=[...chosen].find(o=>o.name===name),v=o.getWorldPosition(new THREE.Vector3()).project(cam);return[x+(v.x+1)*w/2,y+(1-v.y)*h/2];};
      detailEvidence.push({id,rect:[x,y,w,h],native_pixels:[canvas.width,canvas.height],same_geometry:true,stage,instance:id==='power-front'?'rack/power-shelf-1':'rack/compute-4',visible_meshes:chosen.size,part_count:id==='compute-front'?8:id==='power-front'?6:null,anchors:id==='rail-pair'?{outer:project('outer-slide-rail'),inner:project('inner-slide-rail'),bracket:project('rail-end-bracket')}:null});
    }
    states.forEach(([o,v])=>o.visible=v);assembly.explode(1);renderer.setSize(width,height,false);renderer.render(scene,camera);
    evidence.details=detailEvidence;evidence.composition='Independent native main and same-geometry native detail renders copied1:1; no resampling; detail insets repeat existing instances';
    return sheet.toDataURL('image/png');
  }
  function png(){renderer.render(scene,camera);return canvas.toDataURL('image/png');}
  let disposed=false;return {scene,camera,assembly,renderer,evidence,point,png,composition,dispose(){if(disposed)return;disposed=true;drawing.dispose();assembly.dispose();environment.dispose();pmrem.dispose();studio.traverse(o=>{if(o.isMesh){o.geometry.dispose();[].concat(o.material).forEach(m=>m.dispose());}});renderer.dispose();}};
}
