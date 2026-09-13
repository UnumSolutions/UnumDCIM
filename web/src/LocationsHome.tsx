import LocationHierarchy, {matchesLocation,roomTypeLabel} from './LocationHierarchy';
import {useMemo,useState} from 'react';
import {ArrowRight,Building2,Globe2,MapPin,Search,Server,Layers,ArrowDownUp,List,LayoutGrid} from 'lucide-react';
import type {Asset,Scene} from './types';

export default function LocationsHome({scene,assets,error,onOpen}:{scene:Scene|null;assets:Asset[];error:string;onOpen:(room:string)=>void}){
 const [query,setQuery]=useState('');
 const [directoryView,setDirectoryView]=useState<'list'|'cards'>('list');
 const sites=useMemo(()=>[...new Set(scene?.rooms.map(r=>r.site)||[])].map(site=>{
  const rooms=scene!.rooms.filter(r=>r.site===site);
  const racks=scene!.racks.filter(r=>rooms.some(room=>room.id===r.room_id));
  return {id:site,name:rooms[0].site_name,rooms,racks,assets:assets.filter(a=>a.site===site)};
 }),[scene,assets]);
 const search=query.trim().toLowerCase();
 const filteredSites=sites.map(site=>({...site,rooms:site.rooms.filter(room=>matchesLocation(room,search))})).filter(site=>site.rooms.length>0);
 return <main className="locations-home"><div className="home-intro"><div><span className="eyebrow">ENTERPRISE OVERVIEW</span><h1>Your locations</h1><p>Choose a location to explore its floor plans, cabinets and equipment.</p></div><span className="home-context"><Globe2 size={18}/> One connected workspace</span></div>
  {error&&<div className="alert error" role="alert">{error} · Retaining the last available location data.</div>}
  <div className="home-metrics"><div><Building2 size={19}/><strong>{sites.length}</strong><span>locations</span></div><div><Layers size={19}/><strong>{scene?.rooms.length||0}</strong><span>rooms</span></div><div><Server size={19}/><strong>{scene?.racks.length||0}</strong><span>cabinets</span></div><div><ArrowDownUp size={19}/><strong>{assets.length}</strong><span>assets</span></div></div>
  <div className="home-section-title"><div><h2>Location directory</h2><p>Browse regions to rooms, including data halls and office MDFs / IDFs.</p></div><div className="directory-controls"><div className="view-tabs" role="group" aria-label="Location directory view"><button className={directoryView==='list'?'active':''} aria-pressed={directoryView==='list'} onClick={()=>setDirectoryView('list')}><List size={15}/>List</button><button className={directoryView==='cards'?'active':''} aria-pressed={directoryView==='cards'} onClick={()=>setDirectoryView('cards')}><LayoutGrid size={15}/>Cards</button></div><label className="search"><Search size={16}/><input aria-label="Search hierarchy" placeholder="Search hierarchy…" value={query} onChange={e=>setQuery(e.target.value)}/></label></div></div>
  {!scene?<div className="empty">Loading your locations…</div>:directoryView==='list'?<LocationHierarchy showEmptyRegions={!search} key={search} rooms={filteredSites.flatMap(site=>site.rooms)} racks={scene.racks} onOpen={onOpen}/>:<div className="location-grid">{filteredSites.map((site,i)=><article className="location-card" key={site.id}>
   <button className={`location-art location-art-${i%2}`} onClick={()=>onOpen(site.rooms[0].id)} aria-label={`Open ${site.name} floor plan`}>
    <svg viewBox="0 0 500 180" aria-hidden="true"><defs><pattern id={`home-grid-${i}`} width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="currentColor" strokeWidth=".5" opacity=".25"/></pattern></defs><rect width="500" height="180" fill={`url(#home-grid-${i})`}/><g transform="translate(120,28) skewY(-8)">{Array.from({length:Math.min(site.racks.length,16)},(_,n)=><g key={n} transform={`translate(${n%8*33},${Math.floor(n/8)*75})`}><rect width="23" height="42" rx="2" fill="currentColor" opacity=".45"/><path d="M4 6h15M4 11h15M4 16h15M4 21h15M4 26h15M4 31h15" stroke="var(--panel)" strokeWidth=".6" opacity=".75"/><circle cx="5" cy="37" r="1.2" fill="#a0efd0"/></g>)}</g></svg>
    <span className="location-art-label"><MapPin size={13}/>{site.id.toUpperCase()}</span><span className="location-open-icon"><ArrowRight size={19}/></span>
   </button><div className="location-card-body"><div className="location-title"><div><span className="eyebrow">ENTERPRISE LOCATION</span><h2>{site.name}</h2></div><span className="status-tag"><i/> Local data</span></div><div className="location-counts"><span><strong>{site.rooms.length}</strong> rooms</span><span><strong>{site.racks.length}</strong> cabinets</span><span><strong>{site.assets.length}</strong> assets</span></div><div className="location-rooms">{site.rooms.map(r=><button key={r.id} onClick={()=>onOpen(r.id)}><Layers size={13}/>{r.name} · {roomTypeLabel(r)}<ArrowRight size={12}/></button>)}</div><button className="button primary open-location" onClick={()=>onOpen(site.rooms[0].id)}>Open location <ArrowRight size={15}/></button></div>
  </article>)}</div>}
  {scene&&filteredSites.length===0&&<div className="empty">No locations match your search.</div>}
  <div className="home-help"><Server size={19}/><div><strong>Work with multiple cabinets</strong><p>Open a floor plan, then use Multi-select, Ctrl/Cmd-click or Shift-click. Review combined equipment and space without changing any placement.</p></div></div>
 </main>;
}
