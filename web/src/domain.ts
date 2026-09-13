import type {Ghost,Placement,Rack} from './types';
export function validateGhost(ghost:Ghost,racks:Rack[],placements:Placement[]):string|null{
  const rack=racks.find(r=>r.id===ghost.rack_id), current=placements.find(p=>p.asset_id===ghost.asset_id);
  if(!rack||!current)return 'Choose an asset and destination rack.';
  if(!Number.isInteger(ghost.u)||ghost.u<1||ghost.u+current.height_u-1>rack.height_u)return 'Destination is outside the rack U range.';
  if(placements.some(p=>p.asset_id!==ghost.asset_id&&p.rack_id===rack.id&&ghost.u<p.u+p.height_u&&p.u<ghost.u+current.height_u))return 'This U range is occupied.';
  return null;
}
export function contractCompatible(actual:string,expected:string){return actual===expected;}

export function cabinetSelection(current:string[],id:string,ordered:string[],mode:'replace'|'toggle'|'range',anchor:string):string[]{
 if(!ordered.includes(id))return current.filter(x=>ordered.includes(x));
 if(mode==='replace')return [id];
 if(mode==='range'&&ordered.includes(anchor)){
  const start=ordered.indexOf(anchor),end=ordered.indexOf(id);
  return [...new Set([...current,...ordered.slice(Math.min(start,end),Math.max(start,end)+1)])].filter(x=>ordered.includes(x));
 }
 return current.includes(id)?current.filter(x=>x!==id):[...current.filter(x=>ordered.includes(x)),id];
}
