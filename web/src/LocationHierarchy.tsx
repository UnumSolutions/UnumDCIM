import {ArrowRight, ChevronRight, Building2, Globe2, Layers} from 'lucide-react';
import type {Room, Rack} from './types';
export const roomTypeLabel=(room:Room)=>({data_hall:'Data hall',mdf:'MDF',idf:'IDF',room:'Room'}[room.room_type||'room']);
export const REGIONS=['AMER','EMEA','APAC'] as const;
const levels=['region','country','state','city','site'] as const;
const labels=['Region','Country','State / province','City','Site'];
export function matchesLocation(room:Room, query:string){
 return [room.region,room.country,room.state,room.city,room.site_name,room.name,roomTypeLabel(room)].some(value=>value?.toLowerCase().includes(query.trim().toLowerCase()));
}
export default function LocationHierarchy({rooms,racks,onOpen,showEmptyRegions=true}:{rooms:Room[];racks:Rack[];showEmptyRegions?:boolean;onOpen:(id:string)=>void}){
 function branch(items:Room[],depth:number){
  if(depth===levels.length) return <ul className="hierarchy-rooms">{items.map(room=><li key={room.id}><button aria-label={`Open ${room.site_name} / ${room.name} floor plan`} onClick={()=>onOpen(room.id)}><Layers size={16}/><span className="hierarchy-name"><strong>{room.name}</strong><small>{roomTypeLabel(room)} · Open floor plan</small></span><span className="hierarchy-count">{racks.filter(r=>r.room_id===room.id).length}</span><ArrowRight size={15}/></button></li>)}</ul>;
  const field=levels[depth];
  const groups=new Map<string,Room[]>(depth===0&&showEmptyRegions?REGIONS.map(region=>[region,[]]):[]);
  for(const room of items){const key=room[field]||'';groups.set(key,[...(groups.get(key)||[]),room]);}
  return [...groups].map(([key,children])=><details className="geo-branch" key={key} open={children.length>0}><summary><ChevronRight size={15} className="geo-chevron"/>{depth===4?<Building2 size={16}/>:<Globe2 size={16}/>}<span className="hierarchy-name"><strong>{(depth===4?children[0].site_name:key)||`Unspecified ${labels[depth].toLowerCase()}`}</strong><small>{labels[depth]}</small></span><span className="hierarchy-count">{racks.filter(r=>children.some(room=>room.id===r.room_id)).length}</span></summary><div className="geo-children">{children.length?branch(children,depth+1):<p className="empty-region">No sites available in this region.</p>}</div></details>);
 }
 return <nav className="location-hierarchy geography-hierarchy" aria-label="Location hierarchy"><div className="hierarchy-heading"><span>Region / country / state / city / site / room</span><span>Cabinets</span></div>{branch(rooms,0)}</nav>;
}
