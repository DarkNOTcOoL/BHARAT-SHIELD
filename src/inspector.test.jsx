import React from 'react';
import {describe,it,expect,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import DocumentInspector from './DocumentInspector';
import {fieldGeometry,safeBoxes,serializeNotes,savedNotes} from './fieldGeometry';
afterEach(cleanup);
const word=(text,x0,x1,confidence=90)=>({text,confidence,bbox:{x0,x1,y0:10,y1:30}});
const data=words=>({blocks:[{paragraphs:[{lines:[{words}]}]}]});
describe('visual evidence geometry',()=>{
 it('uses actual value word coordinates, excluding adjacent QR noise',()=>{
  const result=fieldGeometry(data([word('Number:',0,80),word('ZX729381',90,190),word('PLFAK',700,780)]),{documentNumber:'ZX729381'},[1000,500]);
  expect(result).toEqual([{field:'documentNumber',text:'ZX729381',confidence:90,box:[.09,.02,.1,.04]}]);
 });
 it('unions multi-word names and averages word confidence',()=>{
  const result=fieldGeometry(data([word('KAVYA',20,90,80),word('RAO',100,150,60)]),{name:'KAVYA RAO'},[1000,500]);
  expect(result[0].box).toEqual([.02,.02,.13,.04]);expect(result[0].confidence).toBe(70);
 });
 it('does not guess missing, repeated or out-of-range geometry',()=>{
  expect(fieldGeometry(data([word('IND',20,90),word('IND',100,150)]),{nationality:'IND'},[1000,500])).toEqual([]);
  expect(fieldGeometry(data([word('ABC',20,90)]),{name:'XYZ'},[1000,500])).toEqual([]);
  expect(fieldGeometry(data([word('ABC',20,90)]),{name:'ABC'},null)).toEqual([]);
  expect(fieldGeometry(data([word('ABC',-5,90)]),{name:'ABC'},[1000,500])).toEqual([]);
 });
 it('retains unknown confidence and rejects invalid stored rectangles',()=>{
  expect(safeBoxes([null,{field:'x',box:[.9,0,.2,.2]}])).toEqual([]);
  expect(safeBoxes([{field:'x',box:[0,0,.2,.2],confidence:'99',text:{}}])[0].confidence).toBeNull();
 });
 it('serializes oversized notes as valid JSON without losing bounded field boxes',()=>{
  const notes={method:'test',layout_text:'x'.repeat(40000),source_values:{name:'a'.repeat(30000)},field_boxes:[{field:'name',text:'Kavya',box:[0,0,.2,.2],confidence:90}]};
  const serialized=serializeNotes(notes);expect(serialized.length).toBeLessThanOrEqual(20000);expect(JSON.parse(serialized).field_boxes).toHaveLength(1);expect(savedNotes({intake_notes_browser_supplied:'{bad'})).toEqual({});
 });
 it('clicks a field and keeps OCR, corrections, QR and registry comparisons separate',()=>{
  render(<DocumentInspector src="/test.png" boxes={[{field:'documentNumber',text:'ZX729381',box:[.1,.2,.3,.1],confidence:85}]} rawFields={{document_number:'ZX729381'}} fields={{document_number:'ZX729382'}} analysis={{registry:{fields:[{field:'document_number',registry:'ZX729382',status:'EXACT_MATCH'}]},signed_qr:{comparisons:[{field:'document_number',signed:'ZX729381',printed_vs_signed:'CONFLICT',registry_vs_signed:'CONFLICT'}]}}}/>);
  const button=screen.getByRole('button',{name:'Inspect documentNumber'});expect(button.className).toContain('uncertain');expect(button.style.left).toBe('10%');fireEvent.click(button);
  expect(screen.getByText('Officer-reviewed value')).toBeTruthy();expect(screen.getByText(/reviewed\/registry: EXACT_MATCH/)).toBeTruthy();expect(screen.getByText(/printed\/signed: CONFLICT/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText('Show boxes'));expect(screen.queryByRole('button',{name:'Inspect documentNumber'})).toBeNull();
 });
 it('old records have no invented boxes or mismatch verdict',()=>{
  render(<DocumentInspector src="/old.png"/>);expect(screen.getByText(/No unambiguous field geometry/)).toBeTruthy();expect(screen.queryByText('CONFLICT')).toBeNull();
 });
});
