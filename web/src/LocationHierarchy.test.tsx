import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import LocationHierarchy,{matchesLocation} from './LocationHierarchy';
import type {Room} from './types';
const room:Room={id:'idf',site:'office',site_name:'Office campus',name:'Floor 2',region:'AMER',country:'United States',state:'Texas',city:'Dallas',room_type:'idf'};
describe('Location hierarchy',()=>{
 it('renders geographic ancestors and office room types',()=>{
  const html=renderToStaticMarkup(<LocationHierarchy rooms={[room]} racks={[]} onOpen={()=>{}}/>);
  const names=['AMER','United States','Texas','Dallas','Office campus','Floor 2'];
  expect(names.map(name=>html.indexOf(`<strong>${name}</strong>`))).toEqual(names.map(name=>html.indexOf(`<strong>${name}</strong>`)).sort((a,b)=>a-b));
  for(const name of names) expect(html).toContain(`<strong>${name}</strong>`);
  expect(html).toContain('IDF');
  expect(html).toContain('<strong>EMEA</strong>');
  expect(html).toContain('<strong>APAC</strong>');
 });
 it('searches ancestors and room type without inventing missing geography',()=>{
  for(const query of ['texas','amer','IDF','floor 2']) expect(matchesLocation(room,query)).toBe(true);
  expect(matchesLocation(room,'Virginia')).toBe(false);
  const html=renderToStaticMarkup(<LocationHierarchy rooms={[{id:'r',site:'s',site_name:'Legacy site',name:'Room'}]} racks={[]} onOpen={()=>{}}/>);
  expect(html).toContain('Unspecified region');
 });
});
