# BHARATSHIELD v7.1.1 — direct decision workflow

This maintenance release keeps the v7.1 SIH26188 screening engine and UI theme, but simplifies the officer decision flow.

- Clean `REVIEW_COMPLETE_CHECKS` cases remain directly decidable with ACCEPT / FLAG / ESCALATE.
- Supervisors can directly ACCEPT a non-critical `MANUAL_REVIEW` case when the queue was created only by an evidence gap and there is no explicit conflict/review signal. The pending review is resolved atomically and the supervisor override is audit logged.
- Explicit tamper/identity/travel/registry review signals, recapture-required cases and critical escalation conditions still use the protected review workflow.
- Blocked, revoked and Registry 2.2 escalation conditions cannot be accepted.
