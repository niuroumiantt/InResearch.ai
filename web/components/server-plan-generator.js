/* TA-12 formal native plan renderer. Same TA-11 generic geometry, not OEM CAD.
 * Front +z faces the bottom; rear -z faces the top. All layout units are arbitrary.
 * A true top view hides lower drive tiers, vertical fan faces and side apertures.
 * Lid is omitted as a virtual explanatory cutaway, not a removal instruction.
 */
import * as THREE from 'three';
import {buildServerAssembly} from './server-assembly.js';
import {configureAtlasRenderer,createAtlasDrawing} from './scene-atlas.js';
import {visibleBounds} from './scene-view.js';

export function renderNativeServerPlan(canvas,{width=1536,height=1024}={}) {
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1536||height<1024)throw new RangeError('Formal plan needs native dimensions at least1536x1024');
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
  renderer.setPixelRatio(1);renderer.setSize(width,height,false);
  const scene=new THREE.Scene();configureAtlasRenderer(THREE,renderer,scene);
  const pickables=[];
  // Neutral plan fills preserve the assembly geometry; outlines carry identity.
  const fills=new Map([[0xb4b6af,0xe1e2dc],[0x737970,0xa7aaa2],[0x292e2a,0x8d9189],[0x1e2520,0x83887f],[0x345340,0xe8eae3],[0xa9904e,0xbec1b6],[0xae8c42,0xadb2a7],[0x343c34,0x979d92]]);
  const assembly=buildServerAssembly({THREE,material:color=>new THREE.MeshBasicMaterial({color:fills.get(color)??color}),tag:mesh=>pickables.push(mesh)});
  assembly.groups.lid.visible=false;scene.add(assembly.root);
  const drawing=createAtlasDrawing({THREE,scene,normalize:false});drawing.sync();
  const bounds=visibleBounds([assembly.root]),center=bounds.getCenter(new THREE.Vector3());
  const size=bounds.getSize(new THREE.Vector3()),span=Math.max(size.z,size.x*height/width)*1.12;
  const camera=new THREE.OrthographicCamera(-span*width/height/2,span*width/height/2,span/2,-span/2,.01,100);
  camera.position.set(center.x,30,center.z);camera.up.set(0,0,-1);camera.lookAt(center.x,0,center.z);camera.updateMatrixWorld(true);
  scene.updateMatrixWorld(true);renderer.render(scene,camera);
  const point=(x,y,z)=>{const p=new THREE.Vector3(x,y,z).project(camera);return [(p.x+1)*width/2,(1-p.y)*height/2];};
  const evidence={projection:'OrthographicCamera',native_pixels:[canvas.width,canvas.height],up_axis:'-z',front:'+z at bottom',camera_position:camera.position.toArray(),camera_up:camera.up.toArray(),camera_direction:camera.getWorldDirection(new THREE.Vector3()).toArray(),camera_frustum:[camera.left,camera.right,camera.top,camera.bottom],counts:assembly.counts,mesh_count:pickables.length,lid:'hidden virtual omission; not exploded servicing',view:'assembled at source homes; no movement/rotation/reposition of subassemblies',outer_corners:[point(-2.985,1.35,-5),point(2.985,1.35,-5),point(-2.985,1.35,5),point(2.985,1.35,5)]};
  let disposed=false;
  return {scene,camera,assembly,renderer,evidence,point,png(){renderer.render(scene,camera);return canvas.toDataURL('image/png');},dispose(){if(disposed)return;disposed=true;drawing.dispose();assembly.dispose();renderer.dispose();}};
}
