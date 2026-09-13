import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import RackElevations from './RackElevations';
import type {Asset, Placement, Rack} from './types';

const racks = [
  {id:'r1', label:'A01', height_u:42},
  {id:'r2', label:'A02', height_u:24},
  {id:'r3', label:'A03', height_u:42},
] as Rack[];
const placements = [
  {asset_id:'a1',rack_id:'r1',u:3,height_u:2},
  {asset_id:'a2',rack_id:'r2',u:8,height_u:2},
] as Placement[];
const assets = [{id:'a1',name:'server-one'}, {id:'a2',name:'server-two'}] as Asset[];
function render(ids:string[], face:'front'|'rear'='front') {
  return renderToStaticMarkup(<RackElevations racks={racks} selectedRackIds={ids}
    assets={assets} placements={placements} selectedAsset="a1" onSelectAsset={()=>{}}
    face={face} ghost={null}/>);
}

describe('selected cabinet elevations',()=>{
  it('shows every selected cabinet and its own installed equipment',()=>{
    const html=render(['r1','r2']);
    expect(html).toContain('A01 front rack elevation');
    expect(html).toContain('A02 front rack elevation');
    expect(html).not.toContain('A03 front rack elevation');
    expect(html).toContain('A01: server-one, U3 to U4');
    expect(html).toContain('A02: server-two, U8 to U9');
  });
  it('applies the shared rear control to every selected cabinet',()=>{
    const html=render(['r1','r2'],'rear');
    expect(html).toContain('A01 rear rack elevation');
    expect(html).toContain('A02 rear rack elevation');
    expect(html).not.toContain('front rack elevation');
  });
  it('handles no selection and removed cabinets without falling into 3D',()=>{
    expect(render([])).toContain('Select one or more cabinets');
    expect(render(['removed'])).toContain('Select one or more cabinets');
  });
});
