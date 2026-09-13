import {Canvas,useFrame} from '@react-three/fiber';
import {OrbitControls,Html,Grid,PointerLockControls} from '@react-three/drei';
import {useEffect,useRef} from 'react';
import {Vector3} from 'three';
import type {Rack,Overlay} from './types';

function Walking(){
 const keys=useRef(new Set<string>());
 useEffect(()=>{const down=(e:KeyboardEvent)=>keys.current.add(e.code);const up=(e:KeyboardEvent)=>keys.current.delete(e.code);window.addEventListener('keydown',down);window.addEventListener('keyup',up);return()=>{window.removeEventListener('keydown',down);window.removeEventListener('keyup',up)}},[]);
 useFrame(({camera},delta)=>{if(!document.pointerLockElement)return;const direction=new Vector3();camera.getWorldDirection(direction);direction.y=0;direction.normalize();const right=new Vector3().crossVectors(direction,new Vector3(0,1,0));const step=Math.min(delta,.05)*5;if(keys.current.has('KeyW'))camera.position.addScaledVector(direction,step);if(keys.current.has('KeyS'))camera.position.addScaledVector(direction,-step);if(keys.current.has('KeyD'))camera.position.addScaledVector(right,step);if(keys.current.has('KeyA'))camera.position.addScaledVector(right,-step);camera.position.y=1.65});
 return <PointerLockControls/>;
}
export default function Twin3D({racks,selected,onSelect,overlay,reduced,walk}:{racks:Rack[];selected:string[];onSelect:(id:string,toggle?:boolean,range?:boolean)=>void;overlay:Overlay;reduced:boolean;walk:boolean}){
 return <Canvas shadows={!reduced} frameloop={walk?'always':'demand'} camera={{position:walk?[0,1.65,8]:[9,12,14],fov:42}}>
  <color attach="background" args={['#e6eceb']}/><ambientLight intensity={1.5}/><directionalLight position={[4,10,5]} intensity={2} castShadow={!reduced}/>
  <Grid args={[30,18]} cellSize={1} cellThickness={.5} cellColor="#bccbc8" sectionSize={4} sectionColor="#aebfba" fadeDistance={40}/>
  {racks.map((r,i)=><group key={r.id} position={[(r.x-3.5)*1.5,0,(r.y-.5)*4]}>
   <mesh position={[0,1.2,0]} onClick={e=>{e.stopPropagation();onSelect(r.id,e.ctrlKey||e.metaKey,e.shiftKey)}} castShadow={!reduced}>
    <boxGeometry args={[1,2.4,1.35]}/><meshStandardMaterial color={selected.includes(r.id)?'#1ea38b':overlay==='heat'?['#6eafa4','#7fba94','#d1ad68'][i%3]:'#35494e'} roughness={.65}/>
   </mesh>
   {[.4,.8,1.2,1.6,2].map(y=><mesh key={y} position={[0,y,.681]}><boxGeometry args={[.78,.27,.025]}/><meshStandardMaterial color="#14282d"/></mesh>)}
   <Html position={[0,2.7,.1]} center style={{fontSize:11,color:"#263f45",pointerEvents:"none",fontWeight:600}}>{r.label}</Html>
  </group>)}
  {walk?<Walking/>:<OrbitControls makeDefault target={[0,0,0]} minDistance={4} maxDistance={32} maxPolarAngle={Math.PI/2.1} enableDamping={!reduced}/>}
 </Canvas>;
}
