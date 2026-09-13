import {describe,it,expect} from 'vitest';
import {validateGhost,contractCompatible,cabinetSelection} from './domain';
import type {Placement,Rack} from './types';
const racks=[{id:'r1',height_u:42}] as Rack[];
const placements=[{asset_id:'a',rack_id:'r1',u:1,height_u:2},{asset_id:'b',rack_id:'r1',u:5,height_u:4}] as Placement[];
describe('placement preview',()=>{
 it('rejects occupied slots without changing the scene',()=>{expect(validateGhost({asset_id:'a',rack_id:'r1',u:6,face:'front'},racks,placements)).toMatch(/occupied/);expect(placements[0].u).toBe(1)});
 it('allows the last fitting U range',()=>expect(validateGhost({asset_id:'a',rack_id:'r1',u:41,face:'front'},racks,placements)).toBeNull());
 it('rejects an overflowing or fractional range',()=>{for(const u of [42,0,1.5])expect(validateGhost({asset_id:'a',rack_id:'r1',u,face:'front'},racks,placements)).not.toBeNull()});
 it('rejects unknown contract majors',()=>expect(contractCompatible('unum.scene/2','unum.scene/1')).toBe(false));
});

describe('cabinet multi-selection',()=>{
 const ordered=['a','b','c','d'];
 it('replaces selection on ordinary click',()=>expect(cabinetSelection(['a','b'],'c',ordered,'replace','a')).toEqual(['c']));
 it('adds and removes cabinets with modifier/toggle mode',()=>{expect(cabinetSelection(['a'],'c',ordered,'toggle','a')).toEqual(['a','c']);expect(cabinetSelection(['a','c'],'a',ordered,'toggle','a')).toEqual(['c'])});
 it('selects a contiguous range without duplicates',()=>expect(cabinetSelection(['a'],'d',ordered,'range','a')).toEqual(ordered));
 it('keeps selection in the visible room',()=>expect(cabinetSelection(['other'],'a',ordered,'toggle','other')).toEqual(['a']));
 it('can clear the last selected cabinet',()=>expect(cabinetSelection(['a'],'a',ordered,'toggle','a')).toEqual([]));
});
