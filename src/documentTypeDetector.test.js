import {describe,it,expect} from 'vitest';
import {detectDocumentType,recommendedPageSegMode} from './documentTypeDetector';

describe('local document type router',()=>{
  it('detects passport from TD3 MRZ even when passport is otherwise sparse',()=>{
    const r=detectDocumentType('REPUBLIC OF INDIA\nPASSPORT\nP<INDDOE<<JANE<<<<<<<<<<<<<<<<<<<<<<<<\nA1234567<8IND9001011F3001012<<<<<<<<<<<<<<04');
    expect(r.status).toBe('DETECTED'); expect(r.detectedType).toBe('Passport');
  });
  it('does not confuse a visa passport-reference field with a passport',()=>{
    const r=detectDocumentType('INDIA E-VISA\nVisa Type: TOURIST\nEntries: MULTIPLE\nPassport No: P1234567\nValid From: 01/01/2026\nDuration of Stay: 90 DAYS');
    expect(r.detectedType).toBe('Visa'); expect(r.status).toBe('DETECTED');
  });
  it('detects common Indian IDs from strong independent cues',()=>{
    expect(detectDocumentType('UNIQUE IDENTIFICATION AUTHORITY OF INDIA\nAADHAAR\n1234 5678 9012').detectedType).toBe('Aadhaar Card');
    expect(detectDocumentType('INCOME TAX DEPARTMENT\nPermanent Account Number\nABCDE1234F').detectedType).toBe('PAN Card');
    expect(detectDocumentType('ELECTION COMMISSION OF INDIA\nELECTOR PHOTO IDENTITY CARD\nABC1234567').detectedType).toBe('Voter ID (EPIC)');
  });
  it('keeps weak unknown text undetermined',()=>expect(detectDocumentType('SAMPLE PERSON\nDATE 2026').status).toBe('UNDETERMINED'));
  it('routes sparse Indian cards to sparse OCR mode',()=>expect(recommendedPageSegMode('PAN Card')).toBe('11'));
});
