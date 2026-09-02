# Industrial Authenticity Detector

A privacy-first, local writing review tool for LinkedIn, Facebook, blogs, product pages, and industrial B2B content. It combines explainable style analysis with a separately reported lightweight model benchmark.

> **Scope:** Results are risk indicators, not author identification. A probability is not proof that a person or an AI wrote the text. Conflicting signals require human review.

## What v0.2.0 includes

- two independent result tracks:
  - `writing_style_risk`: statistics, explainable rules, sentence highlighting, and the Industrial Authenticity Engine;
  - `model_detection`: a lightweight local model's AI-like benchmark probability, confidence, applicability, and exact model version;
- bilingual English/Chinese review and platform profiles for LinkedIn, Facebook, Blog, B2B, and general copy;
- prioritized revision suggestions that never invent technical facts;
- an offline local Web UI, CLI, and compatible JSON API;
- a private, gitignored industrial validation corpus that never leaves the machine;
- signed, versioned detector bundles with explicit user confirmation, health checks, and one-click rollback;
- weekly cloud benchmarks and at most one approved signed candidate per month.

The bundled model is intentionally small and transparent. It is a calibrated logistic scoring layer over inspectable writing signals, not a claim of state-of-the-art authorship detection. Candidate models remain research-only until every release gate passes.

## Quick start

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[updates]'
industrial-authenticity serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Paste an article, choose the channel, and select **Analyze locally**. The application does not upload the article.

Analyze a file from the command line:

```bash
industrial-authenticity analyze draft.txt --platform linkedin
```

Run directly from a source checkout:

```bash
PYTHONPATH=src python -m industrial_authenticity.cli serve
```

## Reading the result

`writing_style_risk` answers: *Which visible writing patterns deserve editorial review?* It considers rhythm, repetition, formulaic wording, unsupported claims, decision conditions, specificity, constraints, and trade-offs.

`model_detection` answers: *How AI-like is this text under the installed lightweight benchmark model?* It includes applicability and confidence because short, mixed-language, highly technical, or out-of-domain content can make the model less reliable.

The two tracks are not combined into an authorship score. If they disagree, the interface says so and asks for human review.

## API

`POST /api/analyze` remains compatible with v0.1 requests:

```json
{
  "text": "Choose the divider thickness after checking part weight.",
  "platform": "linkedin"
}
```

The response now includes:

```json
{
  "detector_version": "2026.09.0",
  "writing_style_risk": {},
  "model_detection": {
    "probability": 0.37,
    "confidence": "medium",
    "applicability": "applicable",
    "model_id": "iad-lightweight-logistic",
    "model_version": "2026.09.0"
  }
}
```

The legacy `classifier` field is retained. Supported platforms are `linkedin`, `facebook`, `blog`, `b2b`, and `general`; requests are limited to 50,000 characters.

Local-only maintenance endpoints:

- `GET /api/update/status` — current/available version, evaluation notes, signature state, and one-time confirmation tokens;
- `POST /api/update/apply` — download, verify, validate, switch, and health-check an approved release after confirmation;
- `POST /api/update/rollback` — return to the previous healthy version after confirmation;
- `GET /api/private-corpus/status` and `POST /api/private-corpus/import` — manage the local validation corpus.

These endpoints reject non-loopback requests. They do not accept a caller-provided URL or filesystem path.

## Safe update lifecycle

```text
Official RAID public benchmark
            ↓ weekly, fixed seed
current release ↔ rule baseline ↔ registered candidates
            ↓ accuracy + subgroup + license + size + speed + tests
monthly candidate (only when every gate passes)
            ↓ signed GitHub Release
local status page → user confirms → verify → private validation → switch
                                                    ↘ failure: keep/rollback
```

Cloud automation monitors and evaluates automatically. Installation never happens automatically. The local page checks releases no more than once per 24 hours and only shows an upgrade when an installable signed version is newer.

Release gates are encoded in [`benchmarks/gates.py`](benchmarks/gates.py): public FPR ≤ 5%, TPR@5% FPR regression ≤ 2 percentage points, Balanced Accuracy regression ≤ 1 point, critical human subgroup FPR regression ≤ 1 point, bundle/model limits, target-Mac latency and memory limits, license/redistribution approval, and complete regression tests.

Large two-model approaches such as Binoculars are cloud research comparisons only and are never included in the local package. A candidate registry records source, revision, license, redistribution status, training-data notes, and deployment scope in [`models/registry.json`](models/registry.json).

## Private industrial validation

Use the Web UI to paste **de-identified, human-written** samples. Separate samples with a blank line and choose their content category. The local store generates an anonymous ID from each sample:

```json
{"id":"generated-locally","category":"b2b","text":"..."}
```

Private originals are stored under the application state directory, excluded by `.gitignore`, never uploaded, and never written into update logs. Only aggregate metrics and anonymous IDs are used. An approved update is blocked if human industrial copy exceeds 5% false positives or worsens by more than 1 percentage point compared with the active version. If there are too few samples, the UI clearly marks the validation as insufficient.

## Cloud benchmark and release

The weekly workflow deterministically samples the official RAID dataset across human/AI labels, generators, genres, and attacks, then stores metrics and subgroup results as a GitHub Actions artifact. The monthly workflow repeats the benchmark with a larger sample, runs all tests, applies the release gates, and creates a signed release only on success.

Repository maintainers must configure the GitHub Actions secret `UPDATE_SIGNING_PRIVATE_KEY`. The matching Ed25519 public key is bundled with the application. Never commit the private key.

Run the benchmark locally only when needed:

```bash
python -m pip install -e '.[benchmark,updates]'
python -m benchmarks.fetch_raid_sample --output benchmark-results/raid.jsonl --count 600 --seed 20260902
python -m benchmarks.run_benchmark --dataset benchmark-results/raid.jsonl --model src/industrial_authenticity/models/bundled-model.json --output benchmark-results/current.json
```

Public benchmark content is downloaded only in GitHub Actions or by this explicit command; it is not bundled with or downloaded by the local application.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover bilingual/empty/long inputs, model failure fallback, dual-track contracts, deterministic metrics and gates, private-corpus acceptance, signature/hash/path/size rejection, one-time tokens, signed install, health checks, and rollback.

## Project structure

```text
src/industrial_authenticity/
├── analyzer.py          # style/rule/authenticity analysis and dual-track contract
├── model.py             # lightweight offline model and safe fallback
├── updates.py           # signed local-only install and rollback manager
├── private_corpus.py    # local industrial validation
├── server.py            # loopback Web/API server
└── web/                 # non-technical local UI
benchmarks/              # RAID sampler, metrics, reports, and release gates
models/                  # candidate registry and research candidate configuration
scripts/                 # deterministic bundle builder and signer
tests/                   # unit, API/UI, benchmark, security, and upgrade tests
```

## Privacy, security, and responsible use

The default server listens on `127.0.0.1`, has no telemetry, invokes no paid detector API, and stores no analyzed article. Network access is limited to checking and downloading approved GitHub Releases. Update bundles require an Ed25519 signature, SHA-256 match, repository/compatibility checks, size limits, safe extraction, local validation, and health checks.

Do not expose the server publicly without separate authentication and deployment hardening. Do not use a result as evidence of academic misconduct, employment wrongdoing, authorship, or deception. Reviewers remain responsible for verifying specifications, test data, certifications, customer claims, and publication authorization.

## License and notices

Project source is released under the [MIT License](LICENSE). Dataset, optional dependencies, and research references retain their own licenses and are not relicensed by this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
