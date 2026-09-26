import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import ForensicAssist from './ForensicAssist';

describe('v5.8 photo substitution evidence',()=>{
 it('shows YuNet portrait integrity result and exposes the photo map',()=>{
  const analysis={
   authenticity:'NOT_DETERMINED',processing_ms:123,copy_move_candidates:[],limitations:[],
   tamper_ai:{status:'NO_STRONG_ANOMALY',max_anomaly_score:32,strong_region_count:0,patch_count:88,affected_fields:[]},
   photo_substitution:{status:'REVIEW_REQUIRED',photo_integrity_index:81.2,face_count:1,frame_detected:true,cues:['JPEG_RESIDUAL_MISMATCH','NOISE_PATTERN_MISMATCH'],reason:'Review portrait.'}
  };
  const {container}=render(<ForensicAssist analysis={analysis} screeningId="SCR-DEMO"/>);
  expect(screen.getByText('Portrait / replaced-photo inspection')).toBeTruthy();
  expect(screen.getAllByText('REVIEW_REQUIRED').length).toBeGreaterThan(0);
  expect(screen.getByText(/JPEG_RESIDUAL_MISMATCH/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Photo integrity'}));
  expect(container.querySelector('img').getAttribute('src')).toContain('view=photo-integrity');
 });
});
