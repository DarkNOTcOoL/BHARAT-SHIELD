# v6.9 runtime migration map

The twelve standalone enhancement scripts are retired from the served frontend. v7.0 renders components from source instead of observing and rewriting React's DOM. The base colour/theme stylesheet is retained.

| Previous runtime script | v7.0 source owner |
|---|---|
| v58 photo integrity | `src/ForensicAssist.jsx` |
| v59 liveness | `src/OptionalPersonCheck.jsx`, `src/LivenessCameraCapture.jsx` |
| v60 visa intelligence | `src/ocrParser.js`, `src/Registry.jsx`, `src/ForensicAssist.jsx`, `src/console/EvidencePanels.jsx` |
| v61 identity history | `src/OptionalPersonCheck.jsx` |
| v62 auto document routing | `src/documentTypeDetector.js`, `src/main.jsx` |
| v63 advanced OCR | `src/adaptiveOCR.js`, `src/main.jsx`, `src/console/EvidencePanels.jsx` |
| v64 layout security | `src/ForensicAssist.jsx`, `src/console/EvidencePanels.jsx` |
| v65 relational registry | `src/console/RegistryGraph.jsx`, `src/console/EvidencePanels.jsx` |
| v66 visual references | `src/ForensicAssist.jsx`, `src/console/RegistryGraph.jsx`, `src/console/EvidencePanels.jsx` |
| v67 travel intelligence | `src/console/RegistryGraph.jsx`, `src/console/EvidencePanels.jsx` |
| v68 Decision Center | `src/console/EvidencePanels.jsx`, shared saved screening state in `src/main.jsx` |
| v69 demo hardening | `src/console/DemoReadiness.jsx` |

## Behaviour retained

OCR fallback/type routing, QR source comparison, field review, local forensic views, optional face/liveness/history, registry mutations, individual and all-demo seeding, reports, review queue and acceptance remain available. Backend authorization remains authoritative. Backend detection algorithms, reference records and scoring weights are unchanged by this release.

## Data flow

Screening upload produces the saved result. The result view passes that evidence to its child components. Those children do not each refetch the same screening. Explicit refresh and completed person checks reload the saved screening once. Request cancellation prevents a late response from replacing a different case. Registry search and readiness use their own scoped requests.

Detailed evidence sections mount on expansion and unmount on closing. This avoids loading hidden forensic images and releases optional camera components. Render errors within a section show a recovery message instead of crashing the entire screen.

No claim of a measured end-to-end speedup is made. The structural reduction is from thirteen entry scripts (base plus twelve enhancements) to one compiled entry script, with no application MutationObserver enhancement loops.

The console keeps synthetic reference scope, rule points, missing evidence and human decisions separate. The original v6.9 backend schemas remain compatible with the copied private folder.
