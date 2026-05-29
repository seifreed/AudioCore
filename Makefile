# AudioCore developer tasks.
#
# SBOM targets generate a high-quality CycloneDX SBOM and score it with
# sbom-tools (https://github.com/sbom-tool/sbom-tools). See sbom/README.md.

PYTHON ?= ./venv/bin/python
SBOM_FILE ?= sbom/audiocore.cdx.json
SBOM_PROFILE ?= standard
SBOM_MIN_SCORE ?= 90

.PHONY: help sbom sbom-score sbom-score-ntia sbom-validate sbom-report test lint

help:
	@echo "AudioCore make targets:"
	@echo "  sbom            Generate + enrich the CycloneDX SBOM ($(SBOM_FILE))"
	@echo "  sbom-score      sbom-tools quality, gated at Grade A (min $(SBOM_MIN_SCORE))"
	@echo "  sbom-score-ntia sbomqs NTIA Minimum Elements score (target 10.0/A = 100%)"
	@echo "  sbom-validate   Validate the SBOM against NTIA minimum elements"
	@echo "  sbom-report     Write a Markdown quality report to sbom/REPORT.md"
	@echo "  test            Run the unit test suite"
	@echo "  lint            Run ruff/black/mypy/bandit gates on src/audiocore"

sbom:
	$(PYTHON) sbom/generate_sbom.py --output $(SBOM_FILE)

sbom-score:
	sbom-tools quality $(SBOM_FILE) --profile $(SBOM_PROFILE) \
		--min-score $(SBOM_MIN_SCORE) --recommendations

sbom-score-ntia:
	sbomqs score $(SBOM_FILE) --profile ntia,ntia-2025 --detailed

sbom-validate:
	sbom-tools validate $(SBOM_FILE)

sbom-report:
	sbom-tools quality $(SBOM_FILE) --profile $(SBOM_PROFILE) --recommendations \
		--no-color -o markdown -O sbom/REPORT.md
	@echo "Wrote sbom/REPORT.md"

test:
	$(PYTHON) -m pytest tests/unit -q

lint:
	ruff check src/audiocore
	ruff format --check src/audiocore
	black --check src/audiocore
	mypy src/audiocore --ignore-missing-imports
	bandit -r src/audiocore -c pyproject.toml
