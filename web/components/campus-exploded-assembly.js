import {buildCampusAssembly,CAMPUS_COUNTS} from './campus-assembly.js';

/* TA19 virtual layers reuse TA18's exact equipment/steel geometry and homes.
 * Translation lengths are drawing choices, not site dimensions or removal
 * clearances. Grey guides/empty footprints are nonphysical, non-pickable lines.
 * No installation procedure, complete topology, new hardware or OEM identity.
 */
export const CAMPUS_EXPLODED_STAGES=Object.freeze([
 [0,'① 原位装配 · 通用八柜示例，前墙/部分屋面虚拟省略'],
 [.02,'② 保留屋面向上分离 · 同实例灰虚线对应原位'],
 [.10,'③ 围护墙组侧移 · 完整钢架与基础保持原位'],
 [.18,'④ 室内设备层抬升 · 八柜/五冷却/三CDU/一组UPS'],
 [.35,'⑤ 桥架层抬升 · 局部服务线不代表完整拓扑'],
 [.68,'⑥ 分层示意完整 · 非施工、维护或拆装程序'],
].map(Object.freeze));
export const CAMPUS_EXPLODED_MARKS=Object.freeze([
 ['01','保留屋面','retained-roof-sections',[0,.06,-8.5]],
 ['02','围护墙组','retained-wall-sections',[14,6,-10.79]],
 ['03','桥架分组','overhead-service-trays',[-2.5,.035,0]],
 ['04','机柜×8','rack-r2-c2',[.83,2.3,1.37]],
 ['05','室内冷却×5','room-cooling-3',[1.05,2.2,.70]],
 ['06','CDU×3','CDU-2',[0,2.6,.93]],
 ['07','UPS四柜门','UPS-bank',[-.28,2.304,1.095]],
 ['08','基础与原位','building-base',[0,.54,7]],
 ['09','冷水机×3','air-chiller-2',[.05,1.8,1.675]],
 ['10','变压器×2','transformer-1',[0,3.50,0]],
 ['11','备用发电×3','standby-generator-2',[0,1.0,1.45]],
 ['12','储能柜×2','battery-cabinet-2',[.9,2.0,1.05]],
].map(row=>Object.freeze([row[0],row[1],row[2],Object.freeze(row[3])])));

export function buildCampusExplodedAssembly({THREE,material,tag,label}){
 const assembly=buildCampusAssembly({THREE,material,tag});
 assembly.root.name='generic-campus-exploded';
 const guides=[],footprints=[],decorations=[],guideGeometries=new Set();
 const guideMaterial=new THREE.LineDashedMaterial({color:0x9d9f96,transparent:true,
  opacity:.65,dashSize:.24,gapSize:.16,depthTest:true});
 let disposed=false;
 for(const i of assembly.instances){
  let axis=[0,0,0],range=[0,1];
  if(i.id.endsWith('/retained-roof-sections')){axis=[0,14,0];range=[.02,.20];}
  else if(i.id.endsWith('/retained-wall-sections')){axis=[-4,0,-10];range=[.10,.30];}
  else if(i.id.endsWith('/overhead-service-trays')){axis=[0,11,0];range=[.35,.68];}
  else if(['rack-frame','room-cooling','cdu','ups'].includes(i.part)){axis=[0,8,0];range=[.18,.52];}
  i.axis.set(...axis);i.range=range;
 }
 function line(points,name,instance){
  const geometry=new THREE.BufferGeometry().setFromPoints(points);guideGeometries.add(geometry);
  const o=new THREE.Line(geometry,guideMaterial);o.name=name;o.userData.atlasSkip=true;
  o.userData.homeInstance=instance.id;o.computeLineDistances();o.visible=false;
  assembly.root.add(o);return o;
 }
 function guide(i,local){
  const p=new THREE.Vector3(...local),home=p.clone().add(i.home);
  const object=line([home,home.clone()],'same-instance-home-guide',i);
  guides.push({instance:i,local:p,home,object});
 }
 function footprint(i,w,d){
  // home.y=.55 is .01 above the actual floor top=.54. The old -.04
  // rack candidate was buried at .51 and remains rejected in the audit.
  const points=[[-w/2,0,-d/2],[w/2,0,-d/2],[w/2,0,d/2],[-w/2,0,d/2],[-w/2,0,-d/2]];
  const object=line(points.map(p=>new THREE.Vector3(...p).add(i.home)),'empty-home-outline',i);
  footprints.push({instance:i,object});
  guide(i,points[0]);guide(i,points[2]);
 }
 for(const i of assembly.instances){
  if(i.part==='rack-frame')footprint(i,2.2,2.4);
  else if(i.part==='room-cooling')footprint(i,2.4,1.4);
  else if(i.part==='cdu')footprint(i,1.8,1.7);
  else if(i.part==='ups')footprint(i,5.6,2);
  else if(i.id.endsWith('/retained-roof-sections'))for(const p of [[-15.8,.06,-10.8],[15.8,.06,-10.8],[-15.8,.06,10.8]])guide(i,p);
  else if(i.id.endsWith('/retained-wall-sections'))for(const p of [[-15.9,.55,-10.9],[15.9,.55,-10.9],[-15.9,.55,10.9]])guide(i,p);
  else if(i.id.endsWith('/overhead-service-trays'))for(const p of [[-2.5,-.09,-8],[6.5,-.09,8]])guide(i,p);
 }
 if(label)for(const[num,text,id,anchor]of CAMPUS_EXPLODED_MARKS){
  const i=assembly.instances.find(i=>i.id==='campus/'+id),o=label(num,0,0,0,.8,null,null);
  if(o){o.position.set(anchor[0],anchor[1]+.65,anchor[2]);
   o.userData.atlasLabel.anchorPosition=[...anchor];o.userData.atlasLabel.anchorInstance=i.id;
   i.object.add(o);decorations.push(o);}
 }
 function explode(t){
  if(disposed)return;
  assembly.explode(t);
  for(const g of guides){
   const moved=g.local.clone().add(g.instance.object.position),a=g.object.geometry.attributes.position;
   a.setXYZ(0,...g.home);a.setXYZ(1,...moved);a.needsUpdate=true;
   g.object.geometry.computeBoundingSphere();
   const distances=g.object.geometry.attributes.lineDistance;
   distances.setX(0,0);distances.setX(1,moved.distanceTo(g.home));distances.needsUpdate=true;
   g.object.visible=moved.distanceToSquared(g.home)>1e-12;
  }
  for(const f of footprints)f.object.visible=f.instance.object.position.distanceToSquared(f.instance.home)>1e-12;
  assembly.root.updateMatrixWorld(true);
 }
 explode(0);
 return {...assembly,counts:CAMPUS_COUNTS,stages:CAMPUS_EXPLODED_STAGES,guides,footprints,explode,
  dispose(){if(disposed)return;disposed=true;decorations.forEach(o=>o.removeFromParent());
   guides.forEach(g=>g.object.removeFromParent());footprints.forEach(f=>f.object.removeFromParent());
   guideGeometries.forEach(g=>g.dispose());guideMaterial.dispose();assembly.dispose();}};
}
