# Local verification engine v4

Inputs: original image bytes, local browser OCR and reviewed fields. Original bytes are encrypted without enhancement.
Fields are explicitly operator-supplied observations, not trusted issuer data.

Quality measurements and low OCR confidence request recapture. Missing checks are tracked independently of inconsistencies.
TD3 MRZ validity is represented as VALID / INVALID / NOT_DETECTED. Other supported ID types show NOT_APPLICABLE;
visa MRZ shows NOT_SUPPORTED. Format/checksum success does not establish authenticity.

Coverage is the fraction of applicable checks performed. It is not a learned confidence, fraud probability or authenticity score.
The engine never consults synthetic issuer/watchlist records for operational recommendations.
Cross-document visa linking uses an explicit passport reference, never the visa number itself.

System recommendations and recorded officer decisions are separate. Every decision needs a reason and authenticated actor.
Acceptance of recapture/review cases requires a supervisor. New screenings are not labelled as officer-accepted automatically.

Face inference uses locally bundled YuNet and SFace models. Similarity is retained as a raw cosine value with model hashes.
No binary identity verdict is generated because checkpoint thresholds have not been validated. Liveness remains NOT_IMPLEMENTED.
JPEG residual visualization is strictly an inspection aid and never affects risk.
