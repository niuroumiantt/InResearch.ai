/* TA-13: one generic illustrated cabinet, front +z. Arbitrary drawing units.
 * 2 shelves / 8 compute chassis / 2 switches are composition choices, not an
 * OEM configuration. Front/left skins are virtually cut away in position.
 * This overview does not claim the legacy exploded stages or servicing steps.
 */
export function buildRackAssembly({THREE, material, tag, label}) {
  const root = new THREE.Group(); root.name = 'generic-rack-overview';
  const geometries = new Set(), materials = new Set();
  const groups = {}, labels = [];
  const dimensions = {width:4.2, depth:5.6, height:12.1, front:2.8};
  const counts = {framePosts:4, mountingRails:4, computeChassis:8,
    driveCarriersPerChassis:8, powerShelves:2, psuModulesPerShelf:6, switches:2,
    adjustableFeet:4, optionalPipes:2, optionalCopperBars:1};
  const mat = (color, options={}) => {const m=material(color,options); materials.add(m); return m;};
  const steel=mat(0xb7b9b5), bright=mat(0xd4d5d0), dark=mat(0x363a38),
    cavity=mat(0x151a18,{roughness:.9}), amber=mat(0xba8d39), copper=mat(0xa77848);
  const group = (name, parent=root) => {const g=new THREE.Group();g.name=name;parent.add(g);return g;};
  const mesh = (parent, geometry, m, x=0,y=0,z=0, name='') => {
    geometries.add(geometry); const o=new THREE.Mesh(geometry,m);
    o.name=name;o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;
  };
  const box = (parent,w,h,d,m,x,y,z,name='') => mesh(parent,new THREE.BoxGeometry(w,h,d),m,x,y,z,name);
  const boltGeo = new THREE.CylinderGeometry(.035,.035,.025,8);
  function bolt(parent,x,y,z) {const b=mesh(parent,boltGeo,dark,x,y,z,'fastener');b.rotation.x=Math.PI/2;return b;}
  // Actual holes in a thin sheet, rather than opaque painted dots.
  function plate(w,h,holes,depth=.035) {
    const s=new THREE.Shape();s.moveTo(-w/2,-h/2);s.lineTo(w/2,-h/2);s.lineTo(w/2,h/2);s.lineTo(-w/2,h/2);s.closePath();
    for(const [x,y,hw,hh] of holes){const p=new THREE.Path();p.moveTo(x-hw/2,y-hh/2);p.lineTo(x-hw/2,y+hh/2);p.lineTo(x+hw/2,y+hh/2);p.lineTo(x+hw/2,y-hh/2);p.closePath();s.holes.push(p);}
    const g=new THREE.ExtrudeGeometry(s,{depth,bevelEnabled:false});g.translate(0,0,-depth/2);return g;
  }
  const gridHoles=(cols,rows,dx,dy,hw,hh)=>Array.from({length:cols*rows},(_,i)=>[
    (i%cols-(cols-1)/2)*dx,(Math.floor(i/cols)-(rows-1)/2)*dy,hw,hh]);
  const frame=groups.frame=group('cabinet-frame');
  for(const x of [-1.97,1.97])for(const z of [-2.67,2.67]){
    const p=group('frame-post',frame);p.position.set(x,6.23,z);
    box(p,.16,11.75,.055,steel,0,0,0);box(p,.055,11.75,.18,steel,-.06,0,-.06);
    for(const y of [-5.65,-3.25,0,3.25,5.65])bolt(p,0,y,.045);
    mesh(frame,new THREE.CylinderGeometry(.055,.055,.22,12),steel,x,.24,z,'foot-thread');
    mesh(frame,new THREE.CylinderGeometry(.13,.16,.07,16),dark,x,.095,z,'adjustable-foot');
  }
  for(const y of [.45,12.05]){
    for(const z of [-2.67,2.67])box(frame,4.02,.22,.16,steel,0,y,z,'crossmember');
    for(const x of [-1.97,1.97])box(frame,.16,.22,5.3,steel,x,y,0,'side-crossmember');
  }
  for(const x of [-1.97,1.97])for(const y of [2.6,5.7,8.8]){
    box(frame,.07,.14,5.1,steel,x,y,0,'side-brace');
  }
  const holes=Array.from({length:84},(_,i)=>[0,(i-41.5)*.128,.07,.075]);
  const railGeo=plate(.15,11.05,holes,.065);
  for(const x of [-1.15,1.75])for(const z of [-2.26,2.10]){
    mesh(frame,railGeo,bright,x,6.12,z,'mounting-rail');
    box(frame,.17,11.05,.04,steel,x+(x<0?.08:-.08),6.12,z-.09,'mounting-rail-fold');
  }
  // Omitted front door / left skin are a virtual section, not displaced panels.
  box(frame,.055,11.4,5.15,steel,2.01,6.22,0,'right-side-skin');
  box(frame,3.78,11.35,.055,dark,0,6.22,-2.7,'rear-skin');
  box(frame,3.98,.065,5.34,bright,0,12.18,0,'roof');
  box(frame,3.98,.065,5.34,steel,0,.4,0,'base-tray');
  for(const z of [-2.67,2.67])for(const y of [1.0,5.8,10.9]){
    mesh(frame,new THREE.CylinderGeometry(.055,.055,.19,12),dark,-1.91,y,z,'door-hinge');
  }
  box(frame,.1,.3,.12,dark,1.97,6.2,2.72,'door-latch');
  for(const y of [1,3.6,6.2,8.8,11.4])for(const z of [-2.4,0,2.4]){
    const b=bolt(frame,2.05,y,z);b.rotation.z=Math.PI/2;b.rotation.x=0;
  }
  tag(frame,'rack-frame');

  function chassis(parent,name,y,h) {
    const g=group(name,parent);g.position.set(.3,y,.15);
    g.userData.installationAxis=[0,0,1];g.userData.front='+z';
    // Folded metal envelope; installed equipment stays on the original plane.
    box(g,2.69,.045,3.8,bright,0,h/2,0,'chassis-cover');
    box(g,2.69,.045,3.8,steel,0,-h/2,0,'chassis-bottom');
    for(const x of [-1.32,1.32])box(g,.045,h,3.8,steel,x,0,0,'chassis-side');
    box(g,2.69,h,.045,dark,0,0,-1.88,'chassis-rear');
    for(const x of [-1.38,1.38]){
      box(g,.14,h,.065,bright,x,0,2.015,'rack-ear');
      for(const dy of [-h*.32,h*.32])bolt(g,x,dy,2.06);
      // Paired outer rail fastens at both front and rear mounting columns.
      box(g,.10,.06,4.36,steel,x,-h/2-.06,-.23,'outer-slide-rail');
      box(g,.045,.08,3.8,dark,x*.955,-h/2-.025,0,'inner-slide-rail');
      for(const z of [-2.41,1.95])box(g,.14,.19,.06,steel,x,-h/2-.02,z,'rail-end-bracket');
    }
    return g;
  }
  const driveGeo=plate(.287,.57,gridHoles(3,6,.070,.073,.038,.043));
  const handleGeo=new THREE.BoxGeometry(.045,.43,.075);
  const servers=groups.servers=group('compute-bank');
  for(let i=0;i<8;i++){
    const g=chassis(servers,'compute-'+(i+1),3.05+i*.91,.73);
    box(g,2.60,.65,.07,cavity,0,0,1.88,'front-drive-recess');
    for(let k=0;k<8;k++){
      const d=group('drive-carrier-'+(k+1),g);d.position.set((k-3.5)*.321,0,1.975);
      mesh(d,driveGeo,dark,0,0,0,'perforated-drive-front');
      box(d,.022,.15,.04,amber,.119,0,.04,'drive-release-latch');
      box(d,.24,.026,.04,steel,0,.24,.04,'carrier-retainer');
    }
    for(const x of [-1.42,1.42])mesh(g,handleGeo,dark,x,0,2.04,'chassis-handle');
  }
  tag(servers,'server');
  const shelves=groups.power=group('power-bank');
  const psuGeo=plate(.405,.66,gridHoles(4,7,.073,.073,.038,.038));
  for(let i=0;i<2;i++){
    const g=chassis(shelves,'power-shelf-'+(i+1),1.04+i*.98,.83);
    box(g,2.60,.73,.07,cavity,0,0,1.88,'power-module-recess');
    for(let k=0;k<6;k++){
      const p=group('psu-module-'+(k+1),g);p.position.set((k-2.5)*.437,0,1.975);
      mesh(p,psuGeo,dark,0,0,0,'perforated-psu-front');
      box(p,.028,.27,.05,amber,-.178,0,.05,'psu-latch');
      box(p,.23,.035,.07,steel,0,-.23,.06,'psu-handle');
    }
  }
  tag(shelves,'power-shelf');
  const network=groups.network=group('network-bank');
  const portHoles=gridHoles(16,2,.145,.16,.106,.102);
  const switchGeo=plate(2.65,.45,portHoles);
  for(let i=0;i<2;i++){
    const g=chassis(network,'switch-'+(i+1),10.64+i*.60,.48);
    mesh(g,switchGeo,bright,0,0,1.975,'network-port-face');
    box(g,2.60,.40,.05,cavity,0,0,1.89,'network-port-recess');
    for(const x of [-1.42,1.42])box(g,.06,.29,.09,dark,x,0,2.02,'switch-handle');
  }
  tag(network,'network-switch');

  // Optional unconnected accessories: not a verified power/coolant topology.
  const service=groups.service=group('optional-service-bay');
  const bus=group('optional-busbar',service);
  box(bus,.10,10.1,.055,copper,-1.70,6.12,.15,'unconnected-copper-bar');
  for(const y of [1.45,3.2,5.0,6.8,8.6,10.5]){
    box(bus,.24,.08,.10,dark,-1.70,y,.10,'busbar-support');
    bolt(bus,-1.70,y,.20);
  }
  tag(bus,'rack-frame');
  const pipes=group('optional-pipe-accessories',service);
  for(const [x,z] of [[-1.56,-.25],[-1.78,-.52]]){
    mesh(pipes,new THREE.CylinderGeometry(.052,.052,9.7,12),steel,x,5.95,z,'unconnected-pipe-accessory');
    for(const y of [1.12,10.8])mesh(pipes,new THREE.CylinderGeometry(.075,.075,.11,12),bright,x,y,z,'pipe-end-cap');
  }
  tag(pipes,'rack-frame');
  const guide=group('cable-guide',frame);
  for(const z of [-1.8,-.9,0,.9,1.8])box(guide,.035,10.6,.045,dark,-1.88,6.15,z,'cable-guide-rib');
  tag(guide,'rack-frame');
  function note(text,x,y,z,category) {const l=label(text,x,y,z,.9,null,null);l.userData.rackCategory=category;labels.push(l);}
  note('前门 / 左侧虚拟剖口',-2.7,12.2,2.8,'all');
  note('示例交换机 ×2',2.6,11.2,2.6,'network');
  note('示例计算托盘 ×8',2.7,6.8,2.6,'servers');
  note('示例电源架 ×2',2.7,1.6,2.6,'power');
  note('可选附件 · 未接线',-2.7,3.7,.3,'service');
  const stages=[[0,'整柜概览 · 通用数量与比例示意'],[.2,'电源分区观察 · 设备保持安装位置'],
    [.4,'计算分区观察 · 八托盘仅为图示'],[.65,'网络分区观察 · 端口形状数量示意'],[.85,'可选服务附件 · 未核实连接拓扑']];
  function focus(t) {
    const selected=t<.2?'all':t<.4?'power':t<.65?'servers':t<.85?'network':'service';
    for(const key of ['servers','power','network','service'])groups[key].visible=selected==='all'||selected===key;
    labels.forEach(l=>l.visible=l.userData.rackCategory==='all'||selected==='all'||l.userData.rackCategory===selected);
    return selected;
  }
  let disposed=false;
  function dispose(){if(disposed)return;disposed=true;root.removeFromParent();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());}
  focus(0);
  return {root,groups,dimensions,counts,stages,focus,dispose};
}
