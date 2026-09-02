# Changelog

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
