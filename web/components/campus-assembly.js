import {mergeGeometries} from "./vendor/BufferGeometryUtils.js";
/* TA18 generic assembled campus. Drawing units, eight rack cabinets and all
 * selected counts are explanatory choices, not project quantities/OEM/CAD.
 * Front wall and most roof are virtually omitted in place. Local service
 * stubs/trays do not certify electrical or fluid topology. DCIM/site rights
 * are independent nonphysical research entries and own no hardware meshes.
 */
export const CAMPUS_COUNTS=Object.freeze({rackRows:2,racksPerRow:4,rackCabinets:8,
 indoorCooling:5,CDUs:3,UPSBank:1,UPSVisibleDoors:4,chillers:3,fansPerChiller:2,
 transformers:2,standbyGenerators:3,batteryCabinets:2});
export const CAMPUS_STAGES=Object.freeze([
 [0,'① 园区装配全景 · 通用八柜示例，前墙/部分屋面虚拟省略'],
 [.05,'② 建筑围护分组预览 · 位移示意，非拆装程序'],
 [.30,'③ 机电设备分组预览 · 非完整电力/流体连接图'],
 [.55,'④ 机柜分组预览 · 原计划TA19分层图仍待逐项验收'],
 [.84,'⑤ 独立芯片/服务器结构请进入对应图册'],
].map(Object.freeze));
export function buildCampusAssembly({THREE,material,tag,label}){
 const root=new THREE.Group();root.name='generic-campus-overview';root.userData.genericIllustration=true;
 const geometries=new Set(),materials=new Set(),geoCache=new Map(),instances=[],decorations=[];let disposed=false;
 const geo=(key,make)=>{if(!geoCache.has(key)){const g=make();geoCache.set(key,g);geometries.add(g)}return geoCache.get(key)};
 const bg=(w,h,d)=>geo('b'+[w,h,d],()=>new THREE.BoxGeometry(w,h,d));
 const cg=(r,h,n=16)=>geo('c'+[r,h,n],()=>new THREE.CylinderGeometry(r,r,h,n));
 const sg=r=>geo('s'+r,()=>new THREE.SphereGeometry(r,10,8));
 const mat=(c,o={})=>{const m=material?material(c,o):new THREE.MeshStandardMaterial({color:c,roughness:.8,metalness:.2,...o});materials.add(m);return m};
 const p={concrete:mat(0xe0dfd5,{roughness:.98,metalness:0}),slab:mat(0xc7c8bf,{roughness:.95,metalness:0}),steel:mat(0xa7aca6),light:mat(0xd0d3ca),dark:mat(0x353c39),cavity:mat(0x181e1b,{roughness:.95,metalness:.05}),metal:mat(0x7e8780,{roughness:.65,metalness:.55}),copper:mat(0x9d7955),insulation:mat(0xd9d0ac,{roughness:1,metalness:0}),blue:mat(0x527c91),black:mat(0x303831),bushing:mat(0x7c624d)};
 function mesh(parent,name,g,m,x=0,y=0,z=0){const o=new THREE.Mesh(g,m);o.name=name;o.position.set(x,y,z);o.castShadow=o.receiveShadow=true;parent.add(o);return o}
 const box=(g,n,w,h,d,m,x,y,z)=>mesh(g,n,bg(w,h,d),m,x,y,z);
 function cyl(g,n,r,h,m,x,y,z,axis='y'){const o=mesh(g,n,cg(r,h),m,x,y,z);if(axis==='x')o.rotation.z=Math.PI/2;if(axis==='z')o.rotation.x=Math.PI/2;return o}
 function group(parent,name,x=0,y=0,z=0){const g=new THREE.Group();g.name=name;g.position.set(x,y,z);parent.add(g);return g}
 function instance(id,part,x,y,z,axis=[0,0,0],range=[0,1]){const o=group(root,id,x,y,z);o.userData.instanceId='campus/'+id;o.userData.part=part;const i={id:o.userData.instanceId,part,object:o,home:o.position.clone(),axis:new THREE.Vector3(...axis),range};instances.push(i);return o}
 function finish(g){
  // Bake only static shapes inside ONE instance. Materials and surface detail
  // remain intact; local IDs/picking never merge different equipment instances.
  g.updateWorldMatrix(true,true);const inverse=g.matrixWorld.clone().invert(),buckets=new Map(),features={},old=[];let inputVertices=0;
  g.traverse(o=>{if(!o.isMesh)return;old.push(o);features[o.name]=(features[o.name]||0)+1;const geometry=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();geometry.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse,o.matrixWorld));inputVertices+=geometry.attributes.position.count;if(!buckets.has(o.material))buckets.set(o.material,[]);buckets.get(o.material).push(geometry)});
  old.forEach(o=>o.removeFromParent());let packedVertices=0;
  for(const [m,pieces]of buckets){const geometry=mergeGeometries(pieces,false);if(!geometry)throw Error('incompatible campus geometry attributes');geometries.add(geometry);packedVertices+=geometry.attributes.position.count;pieces.forEach(p=>p.dispose());const o=mesh(g,'packed-static-detail',geometry,m);o.userData.campusInstance=g.userData.instanceId;tag?.(o,g.userData.part)}
  g.userData.featureCounts=features;g.userData.geometryPacking={sourceMeshes:old.length,inputVertices,packedVertices,drawMeshes:buckets.size};return g;
 }
 function bolt(g,x,y,z){return cyl(g,'visible-fastener',.035,.04,p.dark,x,y,z,'z')}
 function linePipe(g,name,points,r,m){for(let i=1;i<points.length;i++){const a=new THREE.Vector3(...points[i-1]),b=new THREE.Vector3(...points[i]),v=b.clone().sub(a),o=mesh(g,name,cg(r,v.length()),m,...a.clone().add(b).multiplyScalar(.5));o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize())}for(const a of points.slice(1,-1))mesh(g,name+'-bend',sg(r),m,...a)}
 function plate(w,h,holes,depth=.035){return geo('plate'+JSON.stringify([w,h,holes,depth]),()=>{const s=new THREE.Shape();s.moveTo(-w/2,-h/2);s.lineTo(w/2,-h/2);s.lineTo(w/2,h/2);s.lineTo(-w/2,h/2);s.closePath();for(const[x,y,hw,hh]of holes){const q=new THREE.Path();q.moveTo(x-hw/2,y-hh/2);q.lineTo(x-hw/2,y+hh/2);q.lineTo(x+hw/2,y+hh/2);q.lineTo(x+hw/2,y-hh/2);q.closePath();s.holes.push(q)}const g=new THREE.ExtrudeGeometry(s,{depth,bevelEnabled:false});g.translate(0,0,-depth/2);return g})}
 function louvers(g,w,h,z,x=0,y=0,n=14){box(g,'louver-recess',w,h,.04,p.cavity,x,y,z);for(let i=0;i<n;i++)box(g,'louver-blade',w,.035,.065,p.metal,x,y-h/2+(i+.5)*h/n,z+.045)}
 function cabinet(g,w,h,d,doors=1){box(g,'cabinet-envelope',w,h,d,p.light,0,h/2+.2,0);for(let i=0;i<doors;i++){const x=(i-(doors-1)/2)*w/doors;box(g,'door-seam',.018,h-.12,.025,p.dark,x+w/doors/2-.015,h/2+.2,d/2+.02);box(g,'door-handle',.045,.38,.07,p.dark,x+w/doors*.30,h*.48,d/2+.06);louvers(g,w/doors*.68,h*.25,d/2+.04,x,h*.75,10)}for(const x of[-w/2+.12,w/2-.12])for(const z of[-d/2+.12,d/2-.12])box(g,'cabinet-foot',.15,.22,.15,p.dark,x,.11,z)}
 const site=group(root,'context-ground');box(site,'pale-context-ground',65,.06,39,p.concrete,3,-.08,3);site.userData.atlasSkip=true;site.traverse(o=>o.userData.atlasSkip=true);
 const base=instance('building-base','shell',0,0,0);box(base,'shallow-building-foundation',32,.48,22,p.slab,0,.24,0);box(base,'interior-floor',31.7,.06,21.7,p.concrete,0,.51,0);
 for(let x=-15;x<=15;x+=2)box(base,'floor-joint',.012,.004,21.6,p.slab,x,.544,0);for(let z=-10;z<=10;z+=2)box(base,'floor-joint',31.6,.004,.012,p.slab,0,.544,z);
 const frame=instance('building-frame','shell',0,0,0);
 for(const x of[-15.6,-8,0,8,15.6])for(const z of[-10.6,10.6]){box(frame,'column-web',.16,7.6,.42,p.steel,x,4.35,z);for(const sx of[-.22,.22])box(frame,'column-flange',.08,7.6,.55,p.metal,x+sx,4.35,z);box(frame,'column-baseplate',.78,.09,.84,p.metal,x,.59,z);for(const dx of[-.28,.28])for(const dz of[-.3,.3])cyl(frame,'baseplate-bolt',.045,.12,p.dark,x+dx,.69,z+dz)}
 for(const z of[-10.6,10.6]){box(frame,'beam-web',31.6,.54,.10,p.steel,0,8.05,z);for(const y of[7.77,8.33])box(frame,'beam-flange',31.8,.07,.46,p.metal,0,y,z)}
 for(const x of[-15.6,-8,0,8,15.6]){box(frame,'cross-beam-web',.10,.5,21.2,p.steel,x,8.05,0);for(const y of[7.8,8.3])box(frame,'cross-beam-flange',.42,.06,21.2,p.metal,x,y,0)}
 const walls=instance('retained-wall-sections','shell',0,0,0,[0,0,-6],[.05,.3]);box(walls,'back-insulated-wall',32,7.5,.22,p.light,0,4.30,-10.9);box(walls,'left-insulated-wall',.22,7.5,22,p.light,-15.9,4.30,0);
 for(let x=-15;x<=15;x+=1.2)box(walls,'wall-panel-seam',.018,7.4,.035,p.metal,x,4.3,-10.76);for(let z=-10;z<=10;z+=1.2)box(walls,'wall-panel-seam',.035,7.4,.018,p.metal,-15.76,4.3,z);
 // The right wall is a rear strip, the front wall is virtually omitted in place.
 box(walls,'right-retained-wall-strip',.22,7.5,3.5,p.light,15.9,4.3,-9.15);
 box(walls,'UPS-partition',.16,5.9,9.0,p.light,-8.8,3.5,5.7);box(walls,'UPS-partition-return',7.0,5.9,.16,p.light,-12.4,3.5,1.3);
 const roof=instance('retained-roof-sections','shell',0,8.55,0,[0,10,0],[.05,.3]);box(roof,'roof-rear-skin',32,.12,5,p.steel,0,0,-8.5);box(roof,'roof-rear-insulation',32,.22,5,p.insulation,0,-.16,-8.5);box(roof,'roof-left-skin',7,.12,17,p.steel,-12.5,0,2.5);box(roof,'roof-left-insulation',7,.22,17,p.insulation,-12.5,-.16,2.5);
 for(let x=-15.6;x<16;x+=.7)box(roof,'roof-seam',.035,.05,5,p.metal,x,.08,-8.5);for(let z=-5.6;z<11;z+=.7)box(roof,'roof-seam',7,.05,.035,p.metal,-12.5,.08,z);
 const UPS=instance('UPS-bank','ups',-12.1,.55,6.3,[-6,0,0],[.3,.55]);cabinet(UPS,5.6,4.8,2.0,4);
 const rackDoorHoles=Array.from({length:160},(_,i)=>[(i%8-3.5)*.20,(Math.floor(i/8)-9.5)*.20,.085,.09]);
 const rackDoor=plate(2.02,4.4,rackDoorHoles,.04);
 for(let row=0;row<2;row++)for(let col=0;col<4;col++){
  const g=instance('rack-r'+(row+1)+'-c'+(col+1),'rack-frame',-5.8+col*4.6,.55,-3+row*7.3,[0,0,row?4:-4],[.3,.55]);
  box(g,'rack-back',2.18,4.8,.07,p.dark,0,2.5,-1.2);for(const x of[-1.08,1.08])box(g,'rack-side',.055,4.8,2.4,p.dark,x,2.5,0);box(g,'rack-top',2.2,.07,2.4,p.metal,0,4.94,0);box(g,'rack-bottom',2.2,.07,2.4,p.metal,0,.08,0);
  for(const x of[-.99,.99])box(g,'front-mounting-post',.10,4.6,.12,p.metal,x,2.5,1.10);
  for(let i=0;i<12;i++){const y=.32+i*.37;box(g,'closed-server-front',1.82,.28,.07,p.black,0,y,1.04);for(const x of[-.82,.82])box(g,'tray-ear',.055,.20,.10,p.steel,x,y,1.095);for(let k=0;k<4;k++)box(g,'carrier-front-detail',.34,.22,.04,p.dark,(k-1.5)*.43,y,1.10)}
  mesh(g,'perforated-closed-rack-door',rackDoor,p.dark,0,2.50,1.24);box(g,'door-handle',.06,.60,.12,p.metal,.83,2.3,1.31);
  for(const x of[-.9,.9])for(const z of[-1,1])cyl(g,'rack-foot',.10,.16,p.dark,x,.04,z);
 }
 for(let i=0;i<5;i++){const g=instance('room-cooling-'+(i+1),'room-cooling',-6.5+i*4,.55,-9.2,[0,0,-5],[.3,.55]);cabinet(g,2.4,4.0,1.4);louvers(g,1.85,2.5,.76,0,2.2,22);box(g,'top-duct-stub',1.0,.6,.85,p.steel,0,4.5,-.1)}
 for(let i=0;i<3;i++){const g=instance('CDU-'+(i+1),'cdu',14,.55,-4+i*4,[6,0,0],[.3,.55]);cabinet(g,1.8,3.6,1.7);box(g,'unlit-control-panel',.65,.55,.06,p.cavity,0,2.6,.90);for(const x of[-.48,.48])linePipe(g,'local-service-stub-not-loop',[[x,3.8,-.2],[x,4.35,-.2],[x,4.35,-.65],[x,4.05,-.65]],.07,p.blue)}
 const trays=instance('overhead-service-trays','cabling',0,6.65,0,[0,3,0],[.3,.55]);
 function tray(w,d,x,z){box(trays,'tray-bottom',w,.07,d,p.metal,x,0,z);for(const dx of[-w/2,w/2])box(trays,'tray-edge',.04,.22,d,p.steel,x+dx,.08,z);for(let dz=-d/2;dz<d/2;dz+=.45)box(trays,'tray-crossmember',w,.035,.06,p.dark,x,-.07,z+dz);for(const dx of[-w*.22,w*.22])box(trays,'illustrative-closed-cable',.055,.06,d,p.black,x+dx,.10,z)}
 tray(.75,18,-2.5,0);tray(.75,18,6.5,0);for(const z of[-6,4]){const g=group(trays,'cross-tray',0,0,z);box(g,'cross-tray-bottom',22,.07,.75,p.metal,2,0,0);for(const zz of[-.375,.375])box(g,'cross-tray-edge',22,.22,.04,p.steel,2,.08,zz)}for(const x of[-2.5,6.5])for(const z of[-8,0,8]){box(trays,'tray-suspension',.045,1.2,.045,p.steel,x,.65,z);box(trays,'tray-support-foot',.9,.06,.15,p.metal,x,-.09,z)}
 function pad(g,w,d){box(g,'independent-concrete-pad',w,.22,d,p.concrete,0,.11,0)}
 function fan(g,x,y,z){cyl(g,'fan-well',.66,.15,p.cavity,x,y,z);const ring=geo('fan-ring',()=>new THREE.TorusGeometry(.66,.025,6,30));const o=mesh(g,'fan-guard-ring',ring,p.steel,x,y+.10,z);o.rotation.x=Math.PI/2;for(let k=0;k<8;k++){const a=k*Math.PI/4,b=box(g,'fan-guard-spoke',1.3,.025,.025,p.steel,x,y+.10,z);b.rotation.y=a}cyl(g,'fan-hub',.14,.17,p.dark,x,y+.02,z);for(let k=0;k<6;k++){const a=k*Math.PI/3,b=box(g,'fan-blade',.45,.04,.16,p.metal,x+Math.cos(a)*.32,y,z+Math.sin(a)*.32);b.rotation.y=-a}}
 for(let i=0;i<3;i++){const g=instance('air-chiller-'+(i+1),'chiller',-24,0,-8+i*8,[-4,0,0],[.12,.4]);pad(g,5.1,4.4);box(g,'chiller-frame',4.2,.15,3.4,p.steel,0,.5,0);box(g,'chiller-upper-frame',4.2,.15,3.4,p.steel,0,3.1,0);for(const x of[-1.95,1.95])for(const z of[-1.55,1.55])box(g,'chiller-leg',.12,2.6,.12,p.steel,x,1.8,z);for(const z of[-1.55,1.55]){box(g,'coil-recess',3.9,2.2,.12,p.dark,0,1.8,z);for(let k=0;k<38;k++)box(g,'individual-coil-fin',.035,2.15,.17,p.metal,(k-18.5)*.1,1.8,z+.04*Math.sign(z))}for(const x of[-1,1])fan(g,x,3.2,0);for(const z of[-.5,.5])linePipe(g,'unconnected-service-pipe',[[2.15,.7,z],[2.35,.7,z],[2.35,2.1,z]],.055,p.blue)}
 for(let i=0;i<2;i++){const g=instance('transformer-'+(i+1),'transformer',22+i*7,0,-7,[4,0,-2],[.12,.4]);pad(g,5.5,5);box(g,'transformer-tank',3.6,2.8,2.5,p.steel,0,1.95,0);box(g,'tank-top-flange',3.85,.14,2.75,p.metal,0,3.43,0);for(const z of[-1.6,1.6]){for(let k=0;k<22;k++)box(g,'individual-radiator-fin',.055,2.6,.66,p.metal,(k-10.5)*.16,1.9,z);for(const y of[.7,3.1])cyl(g,'radiator-header',.07,3.65,p.steel,0,y,z,'x')}
  for(const x of[-1.1,0,1.1]){cyl(g,'generic-bushing',.11,.9,p.bushing,x,3.96,.4);for(let k=0;k<5;k++)cyl(g,'bushing-shed',.19,.06,p.bushing,x,3.58+k*.16,.4);cyl(g,'bushing-terminal',.075,.17,p.copper,x,4.50,.4)}cyl(g,'closed-conservator',.34,1.5,p.steel,-.7,3.9,-.55,'x');for(const x of[-1.1,-.3])box(g,'conservator-support',.12,.4,.14,p.metal,x,3.57,-.55);box(g,'tank-cabinet',.7,1.1,.32,p.light,1.05,1.65,1.43);box(g,'cabinet-handle',.04,.2,.06,p.dark,1.28,1.65,1.62)}
 for(let i=0;i<3;i++){const g=instance('standby-generator-'+(i+1),'backup-power',20+i*6.0,0,14,[3,0,3],[.12,.4]);pad(g,5.8,4.2);cabinet(g,4.8,2.8,2.9,3);box(g,'generator-base',5.0,.28,3.1,p.metal,0,.39,0);louvers(g,1.35,1.95,1.51,1.52,1.75,18);
  cyl(g,'external-horizontal-muffler',.24,2.4,p.steel,0,3.43,0,'x');linePipe(g,'continuous-inlet-duct',[[-1.2,3.43,0],[-1.45,3.43,0],[-1.45,3.03,0]],.11,p.metal);linePipe(g,'continuous-outlet-duct',[[1.2,3.43,0],[1.5,3.43,0],[1.5,4.15,0],[1.72,4.15,0]],.11,p.metal);for(const x of[-.75,.75]){box(g,'muffler-bracket',.09,.25,.1,p.metal,x,3.10,0);const r=mesh(g,'muffler-band',geo('muffler-band',()=>new THREE.TorusGeometry(.245,.018,6,18)),p.dark,x,3.43,0);r.rotation.y=Math.PI/2}}
 for(let i=0;i<2;i++){const g=instance('battery-cabinet-'+(i+1),'bess',24+i*4,0,7,[3,0,1],[.12,.4]);pad(g,3.3,3);cabinet(g,2.4,3.5,2.1,1);box(g,'closed-battery-lower-panel',2.1,.8,.035,p.steel,0,.8,1.09)}
 // Tag once after every instance is complete; every Mesh has one stable local instance.
 instances.forEach(i=>finish(i.object));
 const markSpecs=[['01','建筑围护与剖口','retained-roof-sections',[0,.15,-8.5]],['02','八柜示例','rack-r2-c2',[0,5,1.2]],['03','室内冷却×5','room-cooling-3',[0,4.9,0]],['04','CDU×3','CDU-2',[0,4.8,0]],['05','UPS一组4柜门','UPS-bank',[0,5.3,0]],['06','冷水机×3','air-chiller-2',[0,3.8,0]],['07','变压器×2','transformer-1',[0,5.1,0]],['08','备用发电×3','standby-generator-2',[0,4.7,0]],['09','储能×2','battery-cabinet-2',[0,4.2,0]]];
 if(label)for(const[num,text,id,pos]of markSpecs){const i=instances.find(i=>i.id==='campus/'+id),o=label(num,0,0,0,.8,null,null);if(o){o.position.set(...pos);i.object.add(o);decorations.push(o)}}
 const clamp=t=>Math.max(0,Math.min(1,Number(t)||0)),ease=t=>t*t*(3-2*t);
 function explode(t){const k=clamp(t);for(const i of instances){const f=ease(clamp((k-i.range[0])/(i.range[1]-i.range[0])));i.object.position.copy(i.home).addScaledVector(i.axis,f)}root.updateMatrixWorld(true)}
 const instanceFor=o=>instances.find(i=>i.id===o?.userData?.campusInstance)||null;
 return {root,instances,counts:CAMPUS_COUNTS,stages:CAMPUS_STAGES,instanceFor,explode,
  objectsFor(part){return instances.filter(i=>i.part===part).map(i=>i.object)},
  dispose(){if(disposed)return;disposed=true;decorations.forEach(o=>o.removeFromParent());root.removeFromParent();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())}};
}
