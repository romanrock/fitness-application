# Next Steps (Efficiency + Quality)

This plan focuses on stabilizing dev UX, tightening data contracts, and adding quality gates without slowing iteration.

## Phase A — Dev UX (1–2 days)
- Consolidate run commands and lock ports (auto‑kill or auto‑rebind with printed URL).
- Always create a dev user if missing; no auth friction in dev.
- Add `run_status` script that reports API + Vite + pipeline status.

## Phase B — Data contracts (1–2 days)
- Freeze JSON contracts in `docs/contracts/`.
- Add API snapshot tests for critical endpoints (weekly, activities, activity detail, series, route).
- Validate route/series data on ingest; log when missing.

## Phase C — UI reliability (2–3 days)
- Remove all mock data remnants.
- Add loading/error states per panel to prevent “blank” regressions.
- Map fallback: polyline from summary when streams missing (already partially done).

## Phase D — Quality gates (1–2 days)
- Integration test: pipeline → API → UI smoke.
- Minimal CI gating: lint + unit + smoke tests.

