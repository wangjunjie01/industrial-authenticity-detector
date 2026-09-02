# Third-party notices

Industrial Authenticity Detector source code is MIT-licensed. The items below keep their original licenses; listing them does not relicense datasets, papers, or dependencies.

## Optional runtime dependency

- **cryptography** — used locally to verify Ed25519 release signatures. Distributed by its maintainers under Apache-2.0 OR BSD-3-Clause. This repository does not bundle its source.
- **pypdf** — optionally extracts text from user-selected public PDF sources for temporary local evidence cards. Distributed by its maintainers under BSD-3-Clause. This repository does not bundle its source.

## Optional research service

- **Brave Search API** — optional search provider used only after the user reviews the exact queries and explicitly permits network research. Authentication uses a server-side environment variable. Search results and source pages retain their publishers' rights and are not redistributed by this project. See the official [API documentation](https://api-dashboard.search.brave.com/api-reference/web/search/get) and [privacy notice](https://api-dashboard.search.brave.com/documentation/resources/privacy-notice).

## Cloud benchmark dependency and data

- **Hugging Face datasets** — optional benchmark loader, Apache-2.0. It is installed only for benchmark runs and is not required for normal local analysis.
- **RAID (Robust AI Detection)** — official public benchmark source: <https://github.com/liamdugan/raid>. Benchmark samples are fetched by GitHub Actions or an explicit maintainer command; the dataset and its text are not committed or redistributed in application releases. Users and maintainers must follow the dataset's own license and terms.

## Research-only comparison

- **Binoculars: Zero-Shot LLM-Generated Text Detection** — Hans et al., ICML 2024, <https://proceedings.mlr.press/v235/hans24a.html>. It is a research reference only. No paper code or model weights are bundled, and its large two-model approach is excluded from local releases.

## Bundled detector configuration

`src/industrial_authenticity/models/bundled-model.json` and `models/candidate-model.json` are original transparent configurations for this repository. They contain coefficients and calibration metadata, not third-party pretrained weights.

Every future candidate must be registered in `models/registry.json` with its source URL, exact version or commit, license, commercial-use and redistribution status, training-data notes, modifications, and intended cloud/local scope before it can pass the release gate.
