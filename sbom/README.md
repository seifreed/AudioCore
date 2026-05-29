# AudioCore SBOM

This directory holds AudioCore's Software Bill of Materials (SBOM) and the
tooling that produces and grades it.

| File | Purpose |
|------|---------|
| `audiocore.cdx.json` | The committed CycloneDX 1.6 SBOM (runtime dependency closure). |
| `generate_sbom.py` | Reproducible generate → prune → enrich pipeline. |
| `REPORT.md` | Latest `sbom-tools quality` report (standard profile). |
| `.hash-cache.json` | Cached PyPI SHA-256 digests for reproducible/offline runs. |

## Rating

Scored with [`sbom-tools`](https://github.com/sbom-tool/sbom-tools)
(`sbom-tools quality`):

| Profile | Score | Grade |
|---------|-------|-------|
| minimal | **92.2 / 100** | **A** |
| standard (default) | **91.5 / 100** | **A** |
| security | **90.5 / 100** | **A** |

Category breakdown (standard profile):

| Category | Score |
|----------|-------|
| Completeness | 100.0 |
| Identifiers | 100.0 |
| Integrity (hashes) | 100.0 |
| Licenses | 92.2 |
| Provenance | 82.7 |
| Dependencies (graph complexity) | 54.7 |

The SBOM is also **NTIA-minimum-elements compliant** (`sbom-tools validate`).

### Why the absolute score is ~92 and not 100

The grade is **A — the highest letter grade**. The numeric score is held below
100 by a single category: **dependency-graph complexity**. `sbom-tools` rewards
shallow, low-fan-out, chain-like graphs (a contrived three-package chain scores
100 there) and penalizes broad, realistic ones. AudioCore genuinely depends on
17 runtime packages, and one of them (`torch`) alone pulls in 13 more, so the
real graph is inherently "bushy" and scores ~55 in that category.

Reaching a perfect 100 would require reshaping the dependency graph into an
artificial chain — i.e. **misrepresenting AudioCore's actual dependencies**.
An SBOM's entire value is being a *truthful* inventory, so we keep the graph
accurate and accept the honest Grade A rather than gaming the metric. Every
category that reflects SBOM *quality we control* — completeness, identifiers,
integrity, NTIA compliance — is at 100.

## Regenerating

```bash
# from the repo root, with the project virtualenv populated (pip install -e ".[dev]")
make sbom            # generate + prune to runtime closure + enrich
make sbom-validate   # NTIA minimum-elements check
make sbom-score      # quality score, gated at Grade A (min 90)
make sbom-report     # refresh REPORT.md
```

`sbom-tools` install (one of):

```bash
brew install sbom-tool/tap/sbom-tools
cargo install sbom-tools
# or a prebuilt binary from the GitHub releases page
```

## How the SBOM is built

1. **Generate** — `cyclonedx-py environment ./venv` emits a CycloneDX 1.6
   document for the installed distributions (PURLs, versions, licenses, graph).
2. **Prune to the runtime closure** — starting from the runtime dependencies in
   `pyproject.toml`, walk each distribution's runtime `Requires-Dist` and keep
   only reachable components. This drops the dev/test toolchain (pytest, mypy,
   ruff, …) — which does not belong in a shipped-software BOM — and removes the
   spurious dependency cycles the full-environment graph introduces.
3. **Enrich** — add supplier, author, SHA-256 integrity hashes (from the PyPI
   release API), VCS/website external references, CPE 2.3 identifiers,
   SPDX-normalized licenses, a `compositions` completeness declaration, document
   authors/supplier/lifecycle, and a deterministic serial number.

## CI

`.github/workflows/sbom.yml` validates the SBOM (NTIA) and fails if the standard
profile drops below Grade A (`--min-score 90`), uploading the Markdown report and
a SARIF result to the Security tab.
