/* TA15 generic silicon-interposer package. All dimensions, pitch and counts
 * below are illustration choices; not OEM/CAD or a fabrication recipe.
 * One logic die and four HBM stacks share a common installed contact plane.
 * Eight DRAM layers and six internal TSVs are deliberately enlarged examples.
 */
export const CHIP_STAGES=Object.freeze([
  [0,'① 同一通用封装 · 层次保持结合位置'],
  [.12,'② 硅中介层与顶部器件整体虚拟上移'],
  [.45,'③ 一块逻辑裸片与四组HBM沿同一竖轴展开'],
  [.9,'④ 展示连接层次 · 非可拆维护或制造步骤'],
].map(Object.freeze));
export function buildChipPackage({THREE,material,tag,label}){
 const root=new THREE.Group();root.name='generic-chip-package';root.userData.genericIllustration=true;
 const geometries=new Set(),materials=new Set(),cache=new Map(),decorations=[],instances=[];let disposed=false;
 const geo=(key,make)=>{if(!cache.has(key)){const g=make();cache.set(key,g);geometries.add(g)}return cache.get(key)};
 const box=(w,h,d)=>geo('b'+[w,h,d],()=>new THREE.BoxGeometry(w,h,d));
 const ball=r=>geo('s'+r,()=>new THREE.SphereGeometry(r,12,8));
 const cylinder=(r,h)=>geo('c'+[r,h],()=>new THREE.CylinderGeometry(r,r,h,10));
 const mat=(c,o={})=>{const m=material?material(c,o):new THREE.MeshStandardMaterial({color:c,roughness:.72,metalness:.25,...o});materials.add(m);return m};
 const p={substrate:mat(0x385742,{roughness:.83,metalness:.12}),silicon:mat(0x3e443f,{roughness:.70,metalness:.26}),die:mat(0xabb0a5,{roughness:.50,metalness:.55}),dram:mat(0x414641,{roughness:.72,metalness:.25}),edge:mat(0x73796f,{roughness:.74,metalness:.32}),gold:mat(0xb59d59,{roughness:.73,metalness:.35}),copper:mat(0xaf8051,{roughness:.72,metalness:.4}),solder:mat(0xa6aaa0,{roughness:.60,metalness:.55})};
 function group(parent,id,part,x=0,y=0,z=0){const g=new THREE.Group();g.name=id;g.position.set(x,y,z);g.userData.instanceId='package/'+id;g.userData.part=part;parent.add(g);return g}
 function mesh(parent,name,g,m,x,y,z,part){const o=new THREE.Mesh(g,m);o.name=name;o.position.set(x,y,z);o.castShadow=o.receiveShadow=true;o.userData.part=part;o.userData.packageInstance=parent.userData.instanceId;parent.add(o);tag?.(o,part);return o}
 const block=(parent,name,w,h,d,m,x,y,z,part)=>mesh(parent,name,box(w,h,d),m,x,y,z,part);
 const substrate=group(root,'substrate','gpu',0,.34,0),interposer=group(root,'interposer','gpu',0,.635,0);
 block(substrate,'organic-package-substrate',8,.3,6,p.substrate,0,0,0,'gpu');
 // Edge laminations are schematic, not an actual layer stack specification.
 for(const y of[-.11,-.04,.035,.11])for(const side of[-1,1]){block(substrate,'substrate-laminate-edge',8,.009,.012,p.edge,0,y,side*3.006,'gpu');block(substrate,'substrate-laminate-edge',.012,.009,6,p.edge,side*4.006,y,0,'gpu')}
 const balls=group(substrate,'solder-balls','gpu');
 for(let x=0;x<20;x++)for(let z=0;z<14;z++)mesh(balls,'attached-BGA-ball',ball(.095),p.solder,(x-9.5)*.38,-.24,(z-6.5)*.40,'gpu');
 for(const side of[-1,1])for(let n=0;n<16;n++){block(substrate,'illustrative-top-pad',.10,.009,.16,p.gold,(n-7.5)*.42,.155,side*2.75,'gpu');block(substrate,'illustrative-top-pad',.12,.009,.12,p.gold,side*3.75,.155,(n-7.5)*.32,'gpu')}
 block(interposer,'silicon-interposer',7.2,.10,5.3,p.silicon,0,0,0,'gpu');
 const c4=group(interposer,'interposer-underside-contacts','gpu');
 for(let x=0;x<12;x++)for(let z=0;z<9;z++)mesh(c4,'illustrative-C4',ball(.0475),p.solder,(x-5.5)*.53,-.0975,(z-4)*.55,'gpu');
 const positions=[[-2.6,-1.85],[-2.6,1.85],[2.6,-1.85],[2.6,1.85]];
 const logic=group(interposer,'logic-die','gpu',0,.091,0);
 block(logic,'logic-silicon',3.4,.12,3.0,p.die,0,.06,0,'gpu');
 // Fine die boundaries provide restrained surface detail.
 for(const side of[-1,1]){block(logic,'die-edge',3.4,.012,.014,p.edge,0,.12,side*1.5,'gpu');block(logic,'die-edge',.014,.012,3,p.edge,side*1.7,.12,0,'gpu')}
 // Bare silicon surface intentionally has no invented logical floorplan.
 for(const side of[-1,1]){block(logic,'die-passivation-boundary',3.18,.001,.003,p.edge,0,.121,side*1.38,'gpu');block(logic,'die-passivation-boundary',.003,.001,2.76,p.edge,side*1.59,.121,0,'gpu');}
 const hbms=[];
 function cutLayer(w,h,d){return geo('cut'+[w,h,d],()=>{const s=new THREE.Shape();s.moveTo(-w/2,-d/2);s.lineTo(.08,-d/2);s.lineTo(.08,-.08);s.lineTo(w/2,-.08);s.lineTo(w/2,d/2);s.lineTo(-w/2,d/2);s.closePath();const g=new THREE.ExtrudeGeometry(s,{depth:h,bevelEnabled:false});g.rotateX(-Math.PI/2);return g})}
 for(const [i,[x,z]]of positions.entries()){
  const h=group(interposer,'hbm-'+(i+1),'hbm',x,.091,z);h.userData.stackIndex=i+1;h.userData.cutaway=i===1;hbms.push(h);
  block(h,'HBM-base-layer',1.18,.065,1.08,p.edge,0,.0325,0,'hbm');
  for(let l=0;l<8;l++){
   const y=.085+l*.061;mesh(h,'DRAM-layer-'+(l+1),i===1?cutLayer(1.18,.046,1.08):box(1.18,.046,1.08),l===7?p.die:p.dram,0,i===1?y-.023:y,0,'hbm');
   // Thin front layer edge only, not exterior TSV posts.
   block(h,'layer-edge',1.18,.008,.012,p.edge,0,y+.022,-.546,'hbm');
  }
  // Six TSVs remain inside silicon footprint, exposed only in the virtual cut.
  if(i===1)for(const [tx,tz]of[[.18,.18],[.34,.18],[.50,.18],[.18,.34],[.34,.34],[.50,.34]])mesh(h,'internal-TSV',cylinder(.018,.47),p.copper,tx,.285,tz,'hbm');
 }
 const devices=[logic,...hbms];
 for(const [idx,g]of devices.entries()){
  const [w,d]=idx===0?[3.4,3]:[1.18,1.08],nx=idx===0?12:5,nz=idx===0?10:4;
  // A real paired contact grid, same x/z and orientation at home and separation.
  for(let x=0;x<nx;x++)for(let z=0;z<nz;z++){
   const xx=(x-(nx-1)/2)*w/(nx+1),zz=(z-(nz-1)/2)*d/(nz+1);
   mesh(g,'die-underside-contact',ball(.019),p.gold,xx,-.018,zz,idx===0?'gpu':'hbm');
   block(interposer,'corresponding-contact-pad',.047,.004,.047,p.gold,g.position.x+xx,.052,g.position.z+zz,'gpu');
  }
  instances.push({id:g.userData.instanceId,object:g,home:g.position.clone(),axis:new THREE.Vector3(0,1.7,0),contactHome:[g.position.x,.091,g.position.z]});
 }
 // Symbolic etched routes, same endpoint zones, not verified routing topology.
 for(const [x,z]of positions)for(let n=0;n<12;n++){
  const y=.053,xx=Math.sign(x)*(1.72+n*.025),zz=Math.sign(z)*(.8+n*.10);
  block(interposer,'illustrative-route-x',Math.abs(x-xx)-.08,.003,.009,p.gold,(x+xx)/2,y,zz,'gpu');
  block(interposer,'illustrative-route-z',.009,.003,Math.abs(z-zz)-.10,p.gold,x,y,(z+zz)/2,'gpu');
 }
 const layerInstance={id:interposer.userData.instanceId,object:interposer,home:interposer.position.clone(),axis:new THREE.Vector3(0,1.05,0)};
 const marks=[['逻辑裸片',0,.25,0,'1'],['四组HBM · 一处虚拟剖口',0,.7,0,'2'],['硅中介层 · 示例布线',3.45,.06,2.3,'3'],['封装基板',3.8,.49,2.8,'4'],['基板底部焊球',3.6,.1,2.6,'5']];
 if(label)for(const [text,x,y,z,num]of marks){const o=label(['①','②','③','④','⑤'][+num-1],x,y,z,.8,null,null);if(o){(num==='1'?logic:num==='2'?hbms[1]:num==='3'?interposer:root).add(o);decorations.push(o)}}
 const ease=t=>t*t*(3-2*t),fraction=(t,a,b)=>ease(Math.max(0,Math.min(1,(t-a)/(b-a))));
 function explode(t){const k=Math.max(0,Math.min(1,Number(t)||0));interposer.position.copy(layerInstance.home).addScaledVector(layerInstance.axis,fraction(k,.12,.45));for(const i of instances)i.object.position.copy(i.home).addScaledVector(i.axis,fraction(k,.45,1));root.updateMatrixWorld(true)}
 const counts=Object.freeze({logicDies:1,HBMStacks:4,DRAMLayersPerStack:8,internalTSVsInCutaway:6,substrates:1,interposers:1,BGABalls:280});
 return {root,substrate,interposer,logic,hbms,balls,instances,layerInstance,counts,stages:CHIP_STAGES,explode,dispose(){if(disposed)return;disposed=true;decorations.forEach(o=>o.removeFromParent());root.removeFromParent();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())}};
}
