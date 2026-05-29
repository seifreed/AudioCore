# AudioCore SBOM

This directory holds AudioCore's Software Bill of Materials (SBOM) and the
tooling that produces and grades it.

| File | Purpose |
|------|---------|
| `audiocore.cdx.json` | The committed CycloneDX 1.6 SBOM (runtime dependency closure). |
| `generate_sbom.py` | Reproducible generate → prune → enrich pipeline. |
| `REPORT.md` | Latest `sbom-tools quality` report (standard profile). |
| `SBOMQS-REPORT.txt` | Latest `sbomqs` report (NTIA + Interlynk profiles). |
| `.hash-cache.json` | Cached PyPI SHA-256 digests for reproducible/offline runs. |

## Rating: 100/A

The same truthful SBOM is graded by two independent, recognized scorers.

### sbomqs (Interlynk) — 100% / Grade A on NTIA Minimum Elements

[`sbomqs`](https://github.com/interlynk-io/sbomqs) scores the SBOM against the
US NTIA Minimum Elements standard:

| Profile | Score | Grade |
|---------|-------|-------|
| **NTIA Minimum Elements (2021)** | **10.0 / 10 (100%)** | **A** |
| **NTIA Minimum Elements (2025-RFC)** | **10.0 / 10 (100%)** | **A** |
| Interlynk (all 8 categories) | 8.8 / 10 | B¹ |

¹ The Interlynk default profile includes a *Component Quality* category that
requires Interlynk's hosted threat-intel API (`--enable-component-analysis
--api-key`); it is unscored offline, so the default caps below 10 regardless of
SBOM content. NTIA — the canonical SBOM-completeness standard — is a perfect 100.

### sbom-tools — Grade A

[`sbom-tools`](https://github.com/sbom-tool/sbom-tools) `quality`:

| Profile | Score | Grade |
|---------|-------|-------|
| minimal | 93.0 / 100 | **A** |
| standard (default) | **92.6 / 100** | **A** |
| security | 91.1 / 100 | **A** |

Category breakdown (standard profile):

| Category | Score |
|----------|-------|
| Completeness | 100.0 |
| Identifiers | 100.0 |
| Integrity (hashes) | 100.0 |
| Licenses | 100.0 |
| Provenance | ~83 |
| Dependencies (graph complexity) | 54.7 |

The SBOM is also **NTIA-minimum-elements compliant** via `sbom-tools validate`.

### Why sbom-tools' *number* is ~92 (still Grade A)

sbom-tools' overall is held under 100 by one category: **dependency-graph
complexity**. It rewards shallow, low-fan-out, chain-like graphs (a contrived
three-package chain scores 100 there) and penalizes broad, realistic ones.
AudioCore genuinely depends on 17 runtime packages and `torch` alone pulls in 13
more, so the real graph is inherently "bushy" and scores ~55 in that category.

Reaching 100 *there* would require reshaping the dependency graph into an
artificial chain — i.e. **misrepresenting AudioCore's actual dependencies**. An
SBOM's whole value is being a *truthful* inventory, so we keep the graph accurate
and take the honest Grade A. The 100/A headline comes from sbomqs' NTIA profile,
whose criteria assess completeness — not graph shape — and which the truthful
SBOM satisfies perfectly.

## Regenerating

```bash
# from the repo root, with the project virtualenv populated (pip install -e ".[dev]")
make sbom             # generate + prune to runtime closure + enrich
make sbom-validate    # NTIA minimum-elements check (sbom-tools)
make sbom-score       # sbom-tools quality, gated at Grade A (min 90)
make sbom-score-ntia  # sbomqs NTIA score (target 10.0/A = 100%)
make sbom-report      # refresh REPORT.md
```

Scorer install (one of):

```bash
brew install sbom-tool/tap/sbom-tools          # sbom-tools
brew tap interlynk-io/interlynk && brew install sbomqs   # sbomqs
# or prebuilt binaries from each project's GitHub releases page
```

For a byte-reproducible SBOM (stable timestamp), set `SOURCE_DATE_EPOCH`
before `make sbom`.

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

`.github/workflows/sbom.yml`:
- validates the SBOM against NTIA minimum elements (`sbom-tools validate`),
- fails if the sbom-tools standard profile drops below Grade A (`--min-score 90`),
- **fails if the sbomqs NTIA rating drops below 10.0/A (100%)**,
- uploads the Markdown report and a SARIF result to the Security tab.
