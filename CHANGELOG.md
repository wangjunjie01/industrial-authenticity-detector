# Changelog

## 0.4.0 - 2026-09-02

- Renamed the primary workflow to **Research & Optimize / 研究并优化** and made it available before analysis.
- Added local AI-writing-pattern diagnosis, editable outbound query review, explicit network consent, manual HTTPS sources, and short-lived in-memory research sessions.
- Added Brave Search API support using only the server-side `BRAVE_SEARCH_API_KEY`; the draft and key never enter browser requests.
- Added traceable evidence cards with source metadata, applicability, credibility, timestamps, and content fingerprints. Only user-confirmed cards can enter the fact ledger.
- Added source-conflict handling, Blog body citation mode, evidence-panel citations for social platforms, and offline fallback when research is unavailable.
- Added SSRF, redirect, content type, response size, PDF page, expiry, consent, source confirmation, and API compatibility regression tests.
- Kept AI-like probability independent from optimization selection and retained manual apply as the only way to replace the original draft.

## 0.3.0 - 2026-09-02

- Added a fully offline, fact-preserving safe optimization engine.
- Added bilingual verified-fact intake, original/candidate comparison, score deltas, change reasons, unresolved fact gaps, copy, regenerate, discard, and manual apply actions.
- Added local-only `POST /api/optimize` while retaining `POST /api/analyze` compatibility.
- Separated optimizer version `iad-safe-optimizer-0.3.0` from detector bundle version `2026.09.0`.
- Added safety and regression tests for numbers, units, conditions, negation, unconfirmed facts, bilingual content, UI controls, and independent AI-like probability reporting.
- Clarified that optimization improves content quality and does not target detector evasion or identify authorship.

## 0.2.0 - 2026-09-02

- Added dual-track writing-style and lightweight-model reporting.
- Added signed detector updates, private local validation, cloud benchmarks, and bilingual local UI.
