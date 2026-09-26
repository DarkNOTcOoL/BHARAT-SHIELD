# BHARATSHIELD v7.1 release notes

## SIH26188 native-console visual refinement

v7.1 keeps the v7.0 integrated React architecture and the same BHARATSHIELD navy/white/tricolour visual identity. This release is a UI/UX refinement only; screening, AI/ML, registry, risk, biometric, travel, audit and officer-decision logic are unchanged.

### Improvements
- Removed remaining dark-theme fragments from white dashboard tables and status cells.
- Refined Command Center KPI cards and risk/status colour hierarchy.
- Polished navigation, top bar, panels, buttons, forms and focus states without changing the theme.
- Improved New Screening upload area, pipeline spacing and document rows.
- Made the officer recommendation card sticky on desktop during evidence review.
- Improved risk score readability and evidence-image presentation.
- Styled the native v7 Decision Center, Demo Readiness, evidence lanes and scenario cards to match the main BHARATSHIELD UI.
- Improved responsive behaviour and accessibility focus indicators.

### Architecture
No v5.8-v6.9 post-build enhancement scripts were reintroduced. All v7 native React components remain the source of truth.
## Decision workflow maintenance

- Clean cases remain directly decidable.
- Supervisors may directly accept a non-critical manual-review case when the queue exists only because of an evidence gap and there is no explicit conflict/review signal. The override is audit logged and automatically resolves the pending review case.
- Explicit review signals, recapture-required cases and critical escalation conditions still use the protected review workflow.

