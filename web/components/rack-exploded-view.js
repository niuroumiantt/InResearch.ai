/* TA14 fits actual mesh corners in the current authored orientation and keeps
 * the persistent controls clear. Shared sphere fitting and manual ownership
 * remain unchanged. Insets are CSS pixels relative to the measured canvas.
 */
import * as THREE from 'three';
export function fitRackExploded({camera,bounds,target,objects,insets={},width=innerWidth,height=innerHeight,padding=1.08}){
  if(bounds.isEmpty()||camera.aspect<=0||width<=0||height<=0)return false;
  const center=bounds.getCenter(new THREE.Vector3()),axis=camera.position.clone().sub(target);
  if(!axis.lengthSq())axis.set(22,15,30);axis.normalize();
  camera.position.copy(center).add(axis);camera.lookAt(center);camera.updateMatrixWorld(true);
  const right=new THREE.Vector3(1,0,0).applyQuaternion(camera.quaternion),up=new THREE.Vector3(0,1,0).applyQuaternion(camera.quaternion),points=[];
  for(const root of objects){let visible=true;for(let p=root;p;p=p.parent)visible&&=p.visible;if(!visible)continue;root.updateWorldMatrix(true,true);root.traverseVisible(o=>{if(!o.isMesh)return;if(!o.geometry.boundingBox)o.geometry.computeBoundingBox();const b=o.geometry.boundingBox;for(const x of[b.min.x,b.max.x])for(const y of[b.min.y,b.max.y])for(const z of[b.min.z,b.max.z])points.push(new THREE.Vector3(x,y,z).applyMatrix4(o.matrixWorld));});}
  if(!points.length)return false;
  const local=points.map(p=>p.clone().sub(center)),xs=local.map(p=>p.dot(right)),ys=local.map(p=>p.dot(up));center.addScaledVector(right,(Math.min(...xs)+Math.max(...xs))/2).addScaledVector(up,(Math.min(...ys)+Math.max(...ys))/2);
  const l=-1+2*(insets.left||0)/width,r=1-2*(insets.right||0)/width,b=-1+2*(insets.bottom||0)/height,t=1-2*(insets.top||0)/height;
  if(l>=r||b>=t)return false;
  const u=(l+r)/2,v=(b+t)/2,tanV=Math.tan(THREE.MathUtils.degToRad(camera.fov)/2),tanH=tanV*camera.aspect;
  // Solve each perspective inequality including its real depth, rather than
  // fitting a world AABB or treating all corners as if they were on one plane.
  let distance=0;for(const p of points){const q=p.clone().sub(center),x=q.dot(right)*padding/tanH,y=q.dot(up)*padding/tanV,z=q.dot(axis);distance=Math.max(distance,(x+r*z)/(r-u),(x+l*z)/(l-u),(y+t*z)/(t-v),(y+b*z)/(b-v));}
  if(!Number.isFinite(distance)||distance<=0)return false;
  const radius=bounds.getBoundingSphere(new THREE.Sphere()).radius;
  target.copy(center).addScaledVector(right,-u*distance*tanH).addScaledVector(up,-v*distance*tanV);
  camera.zoom=1;camera.position.copy(target).addScaledVector(axis,distance);camera.near=Math.max(radius/100,.000001);camera.far=distance+radius*4;camera.lookAt(target);camera.updateProjectionMatrix();camera.updateMatrixWorld(true);return true;
}
