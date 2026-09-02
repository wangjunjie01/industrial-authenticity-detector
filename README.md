# Industrial Authenticity Detector

An explainable local quality gate for LinkedIn, Facebook, blog, and industrial B2B writing. It highlights formulaic language, weak decision logic, unsupported marketing terms, low specificity, and missing engineering trade-offs.

> **Scope:** This project diagnoses writing patterns. It does not determine whether a human or AI authored a text, does not output an AI-authorship probability, and is not designed to evade third-party detectors.

## What v0.1.0 includes

- statistical layer: sentence-length variation, lexical diversity, repetition, burstiness score, and a documented predictability proxy;
- explainable style classifier: low / medium / high AI-like writing risk with visible signals;
- multilingual rule layer for common English and Chinese formulaic patterns;
- Industrial Authenticity Engine with six quality dimensions;
- sentence-level risk highlighting and rule evidence;
- prioritized revision suggestions that do not invent technical facts;
- channel profiles for LinkedIn, Facebook, Blog, and B2B copy;
- dependency-free local Web UI and JSON API;
- CLI and automated tests.

## Quick start

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
industrial-authenticity serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Text is processed locally and is not uploaded by this application.

Analyze a text file from the command line:

```bash
industrial-authenticity analyze draft.txt --platform linkedin
```

Or run directly from the source checkout without installing:

```bash
PYTHONPATH=src python -m industrial_authenticity.cli serve
```

## API

`POST /api/analyze`

```json
{
  "text": "Choose the divider thickness after checking part weight.",
  "platform": "linkedin"
}
```

Supported platform values are `linkedin`, `facebook`, `blog`, `b2b`, and `general`. The local server accepts up to 50,000 characters per analysis.

## How scoring works

The tool combines three inspectable layers:

1. **Statistical signals** measure the text's rhythm and repetition. `predictability_proxy` is explicitly a lexical/rhythm heuristic, not model perplexity.
2. **Rules** point to exact sentences containing generic verbs, unsupported marketing vocabulary, formulaic transitions, repeated openings, or overloaded sentences.
3. **Industrial authenticity** rewards decision conditions, engineering variables, constraints, and trade-offs when they are actually present.

Scores are editorial prioritization aids, not scientific measurements. Short copy, technical terminology, or polished grammar is never treated as proof of AI authorship. Reviewers remain responsible for verifying specifications, test data, certifications, customer claims, and publication authorization.

## Tests

No test dependency is required:

```bash
python -m unittest discover -s tests -v
```

If `pytest` is installed, `pytest` also works.

## Project structure

```text
src/industrial_authenticity/
├── analyzer.py       # statistics, rules, classifier, authenticity scores
├── cli.py            # analyze and serve commands
├── server.py         # local HTTP server and JSON endpoint
└── web/              # responsive local Web UI
tests/                # core contract and bilingual behavior tests
```

## Roadmap

- optional locally hosted transformer adapter with model-card and calibration reporting;
- editable organization rule packs;
- exportable audit reports;
- regression corpus for industrial packaging content;
- reviewer-approved rewrite workflow with fact-check queue.

## Privacy and security

The default server listens on `127.0.0.1`, has no telemetry, uses no external APIs, and stores no analyzed text. Do not bind it to a public interface without adding authentication, request controls, and deployment hardening.

## License and third-party code

The project is released under the [MIT License](LICENSE). Version 0.1.0 was implemented without copying code or model weights from the GitHub projects considered during research, so there are no bundled third-party runtime components. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the boundary and future contribution requirements.

## Responsible use

Use the detector to improve clarity, evidence, and professional credibility. Do not use it as evidence of academic misconduct, employment wrongdoing, authorship, or deception. Do not fabricate anecdotes, specifications, test results, or random stylistic noise to change a score.
