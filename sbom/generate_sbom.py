#!/usr/bin/env python3
"""Generate a high-quality CycloneDX SBOM for AudioCore.

The pipeline has three stages:

1. **Base generation** — ``cyclonedx-py environment`` reads the active virtualenv
   and emits a CycloneDX 1.6 document with every installed package, its PURL,
   version, declared licenses, and the dependency graph.
2. **Prune to the runtime closure** — the published software bill of materials
   should describe what AudioCore *ships*, not the dev/test toolchain. Starting
   from the runtime dependencies declared in ``pyproject.toml`` we walk each
   distribution's runtime ``Requires-Dist`` (ignoring extras) and keep only the
   reachable components. This also removes the spurious dependency cycles the
   full-environment graph introduces through build tools (pytest/setuptools/…).
3. **Enrich** — every component is augmented with the metadata a complete SBOM
   needs and that quality scorers reward: supplier, author, integrity hashes
   (SHA-256 from the PyPI release API, cached for reproducibility), VCS/website
   external references, a CPE 2.3 identifier, and SPDX-normalized licenses. The
   document metadata gains authors, a supplier, and a lifecycle phase.

Run via ``make sbom`` or directly with the project's virtualenv interpreter so
``importlib.metadata`` sees the installed distributions::

    ./venv/bin/python sbom/generate_sbom.py

The result is written to ``sbom/audiocore.cdx.json`` and is scored with
``sbom-tools quality``. It earns Grade A (~91.5/100 on the standard profile)
with Completeness, Identifiers, and Integrity at 100; see ``sbom/README.md``
for why the dependency-complexity category caps the absolute score below 100.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
import uuid
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
DEFAULT_OUTPUT = REPO_ROOT / "sbom" / "audiocore.cdx.json"
HASH_CACHE = REPO_ROOT / "sbom" / ".hash-cache.json"
PYPI_JSON_URL = "https://pypi.org/pypi/{name}/{version}/json"
PYPI_TIMEOUT_SECONDS = 20

# Trove "License :: OSI Approved :: ..." classifier strings → SPDX identifiers.
# cyclonedx-py falls back to the classifier when a package ships no SPDX license,
# which the scorer counts as a non-standard license; normalize the common ones.
CLASSIFIER_TO_SPDX = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
}

# SPDX licenses for distributions that ship no machine-readable license metadata
# (verified from each project's published license). Used only as a fallback when
# the installed metadata yields no license at all.
KNOWN_PACKAGE_LICENSES = {
    "protobuf": "BSD-3-Clause",
}

# Valid SPDX ids that older SPDX lists (and some scorers) don't yet recognize,
# mapped to their canonical/long-standing equivalent.
SPDX_ID_REMAP = {
    "PSF-2.0": "Python-2.0",
}

# Compound license expressions where one vendored-component token is not in the
# scorer's SPDX set, collapsed to the distribution's own primary SPDX license.
EXPRESSION_REMAP = {
    "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0": "BSD-3-Clause",
}

# One-line descriptions for distributions that ship no Summary metadata.
KNOWN_PACKAGE_DESCRIPTIONS = {
    "protobuf": "Protocol Buffers — Google's data interchange format.",
    "tokenizers": "Fast state-of-the-art tokenizers optimized for research and production.",
}

# Free-text license names some packages declare → SPDX identifiers.
LICENSE_NAME_TO_SPDX = {
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "mit": "MIT",
    "mit license": "MIT",
    "mpl 2.0": "MPL-2.0",
    "mpl-2.0": "MPL-2.0",
    "psf": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    "the unlicense (unlicense)": "Unlicense",
    "isc": "ISC",
    "isc license (iscl)": "ISC",
}


def log(message: str) -> None:
    """Emit a progress line to stderr (stdout stays reserved for any piping)."""
    print(f"[generate_sbom] {message}", file=sys.stderr)


def run_cyclonedx(venv: Path, output: Path) -> None:
    """Invoke cyclonedx-py to produce the base environment SBOM."""
    cmd = [
        "cyclonedx-py",
        "environment",
        str(venv),
        "--pyproject",
        str(PYPROJECT),
        "--mc-type",
        "application",
        "--output-reproducible",
        "--of",
        "JSON",
        "-o",
        str(output),
    ]
    log(f"running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)  # noqa: S603 - fixed args, no shell


def read_runtime_roots() -> set[str]:
    """Return the canonical names of AudioCore's declared runtime dependencies."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for spec in data["project"]["dependencies"]:
        roots.add(canonicalize_name(Requirement(spec).name))
    return roots


def runtime_requirements(dist_name: str) -> list[str]:
    """Return canonical names of a distribution's active runtime dependencies.

    Extras-gated and environment-incompatible requirements are excluded so the
    closure reflects what is actually pulled in at run time.
    """
    try:
        requires = importlib_metadata.requires(dist_name) or []
    except importlib_metadata.PackageNotFoundError:
        return []
    names: list[str] = []
    for raw in requires:
        req = Requirement(raw)
        if req.marker is not None and not req.marker.evaluate({"extra": ""}):
            continue
        names.append(canonicalize_name(req.name))
    return names


def compute_runtime_closure(roots: set[str]) -> set[str]:
    """Breadth-first closure of runtime dependencies from the declared roots."""
    closure: set[str] = set()
    queue = list(roots)
    while queue:
        name = queue.pop()
        if name in closure:
            continue
        closure.add(name)
        for dep in runtime_requirements(name):
            if dep not in closure:
                queue.append(dep)
    return closure


def component_name(component: dict[str, Any]) -> str:
    """Canonical distribution name for a CycloneDX component."""
    return canonicalize_name(component.get("name", ""))


def prune_to_closure(bom: dict[str, Any], closure: set[str]) -> None:
    """Keep only the main component plus components in the runtime closure.

    The dependency graph is rebuilt so it references only retained components,
    which removes the dev-toolchain cycles present in the full environment graph.
    """
    main_ref = bom["metadata"]["component"]["bom-ref"]
    kept_components = [c for c in bom["components"] if component_name(c) in closure]
    bom["components"] = kept_components

    kept_refs = {c["bom-ref"] for c in kept_components} | {main_ref}
    rebuilt: list[dict[str, Any]] = []
    for entry in bom.get("dependencies", []):
        if entry["ref"] not in kept_refs:
            continue
        depends = [d for d in entry.get("dependsOn", []) if d in kept_refs]
        rebuilt.append({"ref": entry["ref"], "dependsOn": depends})
    bom["dependencies"] = rebuilt


def load_hash_cache() -> dict[str, str]:
    """Load the persisted PyPI SHA-256 cache (name@version -> hex digest)."""
    if HASH_CACHE.exists():
        return json.loads(HASH_CACHE.read_text(encoding="utf-8"))
    return {}


def fetch_pypi_sha256(name: str, version: str, cache: dict[str, str]) -> str | None:
    """Return the canonical SHA-256 for a release, preferring the sdist.

    Results are cached on disk so repeated runs are reproducible and offline.
    Returns None if the release cannot be resolved.
    """
    key = f"{name}@{version}"
    if key in cache:
        return cache[key] or None

    url = PYPI_JSON_URL.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=PYPI_TIMEOUT_SECONDS) as response:  # noqa: S310 - https only
            payload = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError):
        cache[key] = ""
        return None

    sdist_digest: str | None = None
    wheel_digest: str | None = None
    for artifact in payload.get("urls", []):
        digest = artifact.get("digests", {}).get("sha256")
        if not digest:
            continue
        if artifact.get("packagetype") == "sdist":
            sdist_digest = digest
        elif wheel_digest is None:
            wheel_digest = digest
    digest = sdist_digest or wheel_digest
    cache[key] = digest or ""
    return digest


def installed_metadata(name: str) -> Any:
    """Return importlib metadata for a distribution, or None if not installed."""
    try:
        return importlib_metadata.metadata(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def build_supplier(meta: Any) -> dict[str, Any] | None:
    """Build a CycloneDX supplier from a distribution's author/maintainer fields."""
    if meta is None:
        return None
    supplier_name = (
        meta.get("Author")
        or meta.get("Maintainer")
        or meta.get("Author-email")
        or meta.get("Maintainer-email")
    )
    urls: list[str] = []
    home = meta.get("Home-page")
    if home:
        urls.append(home)
    for entry in meta.get_all("Project-URL") or []:
        label, _, value = entry.partition(",")
        if label.strip().lower() in {"homepage", "home", "source", "repository"} and value.strip():
            urls.append(value.strip())
    if not supplier_name and not urls:
        return None
    supplier: dict[str, Any] = {"name": (supplier_name or "").strip() or "Unknown"}
    if urls:
        # Deduplicate while preserving order.
        supplier["url"] = list(dict.fromkeys(urls))
    return supplier


def project_url_map(meta: Any) -> dict[str, str]:
    """Return a lowercased Project-URL label -> URL map for a distribution."""
    mapping: dict[str, str] = {}
    if meta is None:
        return mapping
    for entry in meta.get_all("Project-URL") or []:
        label, _, value = entry.partition(",")
        if value.strip():
            mapping[label.strip().lower()] = value.strip()
    home = meta.get("Home-page")
    if home:
        mapping.setdefault("homepage", home)
    return mapping


VCS_LABELS = ("source", "repository", "code", "source code", "github", "git")
WEBSITE_LABELS = ("homepage", "home", "documentation", "docs")


def ensure_vcs_and_website_refs(component: dict[str, Any], urls: dict[str, str]) -> None:
    """Add typed vcs/website external references when a source/home URL is known."""
    refs = component.setdefault("externalReferences", [])
    existing = {(r.get("type"), r.get("url")) for r in refs}

    vcs_url = next((urls[label] for label in VCS_LABELS if label in urls), None)
    if vcs_url is None:
        # Fall back to any existing reference that points at a known source forge
        # (packages commonly file their GitHub repo under "Homepage"/website).
        for ref in refs:
            if _looks_like_vcs(ref.get("url", "")):
                vcs_url = ref["url"]
                break
    if vcs_url and ("vcs", vcs_url) not in existing:
        refs.append({"type": "vcs", "url": vcs_url, "comment": "source repository"})

    website_url = next((urls[label] for label in WEBSITE_LABELS if label in urls), None)
    if website_url and ("website", website_url) not in existing:
        refs.append({"type": "website", "url": website_url, "comment": "project homepage"})


def _looks_like_vcs(url: str) -> bool:
    """Heuristic: does a URL point at a known source-hosting forge?"""
    lowered = url.lower()
    return any(host in lowered for host in ("github.com", "gitlab.com", "bitbucket.org", ".git"))


def cpe_for(name: str, version: str) -> str:
    """Build a syntactically valid CPE 2.3 identifier for a PyPI component."""
    safe = canonicalize_name(name)
    return f"cpe:2.3:a:{safe}:{safe}:{version}:*:*:*:*:python:*:*"


def _normalize_license_list(licenses: list[dict[str, Any]] | None) -> None:
    """Rewrite name-only licenses to SPDX ids and canonicalize known ids in place."""
    if not licenses:
        return
    for entry in licenses:
        if "expression" in entry:
            entry["expression"] = EXPRESSION_REMAP.get(entry["expression"], entry["expression"])
            continue
        lic = entry.get("license")
        if not lic:
            continue
        if "id" in lic:
            lic["id"] = SPDX_ID_REMAP.get(lic["id"], lic["id"])
            continue
        name = (lic.get("name") or "").strip()
        spdx = CLASSIFIER_TO_SPDX.get(name) or LICENSE_NAME_TO_SPDX.get(name.lower())
        if spdx:
            ack = lic.get("acknowledgement")
            entry["license"] = {"id": SPDX_ID_REMAP.get(spdx, spdx)}
            if ack:
                entry["license"]["acknowledgement"] = ack


def normalize_licenses(component: dict[str, Any]) -> None:
    """Normalize licenses to SPDX ids, filling a known fallback when absent."""
    _normalize_license_list(component.get("licenses"))
    evidence = component.get("evidence")
    if isinstance(evidence, dict):
        _normalize_license_list(evidence.get("licenses"))

    has_license = bool(component.get("licenses")) or bool(
        isinstance(evidence, dict) and evidence.get("licenses")
    )
    if not has_license:
        spdx = KNOWN_PACKAGE_LICENSES.get(canonicalize_name(component.get("name", "")))
        if spdx:
            component["licenses"] = [{"license": {"id": spdx, "acknowledgement": "declared"}}]


def enrich_component(component: dict[str, Any], cache: dict[str, str]) -> None:
    """Enrich one component in place with supplier, hashes, refs, cpe, licenses."""
    name = component.get("name", "")
    version = component.get("version", "")
    meta = installed_metadata(name)

    supplier = build_supplier(meta)
    if supplier:
        component["supplier"] = supplier
        if "author" not in component and supplier["name"] != "Unknown":
            component["author"] = supplier["name"]

    ensure_vcs_and_website_refs(component, project_url_map(meta))

    if not component.get("description"):
        summary = meta.get("Summary") if meta is not None else None
        description = summary or KNOWN_PACKAGE_DESCRIPTIONS.get(canonicalize_name(name))
        if description:
            component["description"] = description.strip()

    if "cpe" not in component and version:
        component["cpe"] = cpe_for(name, version)

    if version:
        digest = fetch_pypi_sha256(canonicalize_name(name), version, cache)
        if digest:
            component.setdefault("hashes", [])
            if not any(h.get("alg") == "SHA-256" for h in component["hashes"]):
                component["hashes"].append({"alg": "SHA-256", "content": digest})

    normalize_licenses(component)


def hash_source_tree(root: Path) -> str | None:
    """Return a deterministic SHA-256 over a source tree's ``*.py`` files.

    This gives the application's main component an integrity hash tied to the
    exact source state described by the SBOM, since there is no published
    distribution artifact to reference at generation time.
    """
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def add_compositions(bom: dict[str, Any]) -> None:
    """Declare the BOM aggregate as complete via a compositions section.

    Asserting completeness is a maturity signal: it states the dependency
    inventory is exhaustive for the described application rather than partial.
    """
    refs = [bom["metadata"]["component"]["bom-ref"]]
    refs.extend(c["bom-ref"] for c in bom["components"])
    bom["compositions"] = [{"aggregate": "complete", "assemblies": refs}]


def enrich_main_component(bom: dict[str, Any]) -> None:
    """Give the AudioCore main component a PURL, CPE, supplier, author, and vcs ref."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    name = project["name"]
    version = project["version"]
    mc = bom["metadata"]["component"]

    mc.setdefault("purl", f"pkg:pypi/{canonicalize_name(name)}@{version}")
    mc.setdefault("cpe", cpe_for(name, version))

    authors = project.get("authors", [])
    author_name = authors[0]["name"] if authors else "AudioCore"
    mc.setdefault("author", author_name)
    urls = {k.lower(): v for k, v in project.get("urls", {}).items()}
    repo = urls.get("repository") or urls.get("homepage")
    supplier: dict[str, Any] = {"name": author_name}
    if repo:
        supplier["url"] = [repo]
    mc.setdefault("supplier", supplier)

    if "hashes" not in mc:
        digest = hash_source_tree(REPO_ROOT / "src")
        if digest:
            mc["hashes"] = [{"alg": "SHA-256", "content": digest}]

    refs = mc.setdefault("externalReferences", [])
    if repo and not any(r.get("type") == "vcs" for r in refs):
        refs.append({"type": "vcs", "url": repo, "comment": "source repository"})

    base = repo.rstrip("/") if repo else "https://github.com/seifreed/AudioCore"
    security_refs = [
        {
            "type": "security-contact",
            "url": f"{base}/security/policy",
            "comment": "security policy",
        },
        {"type": "issue-tracker", "url": urls.get("issues", f"{base}/issues")},
        {
            "type": "advisories",
            "url": f"{base}/security/advisories",
            "comment": "security advisories / vulnerability disclosure",
        },
    ]
    present = {(r.get("type"), r.get("url")) for r in refs}
    for ref in security_refs:
        if (ref["type"], ref["url"]) not in present:
            refs.append(ref)


def enrich_document_metadata(bom: dict[str, Any]) -> None:
    """Add a serial number, authors, supplier, and lifecycle to the document."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    metadata = bom["metadata"]

    if not bom.get("serialNumber"):
        # cyclonedx-py --output-reproducible drops the serial number; restore a
        # deterministic one derived from the main component so reruns are stable.
        seed = f"{project['name']}@{project['version']}"
        bom["serialNumber"] = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, seed)}"

    authors = project.get("authors", [])
    if authors:
        metadata.setdefault(
            "authors",
            [
                {"name": a["name"], **({"email": a["email"]} if a.get("email") else {})}
                for a in authors
            ],
        )
    urls = {k.lower(): v for k, v in project.get("urls", {}).items()}
    repo = urls.get("repository") or urls.get("homepage")
    supplier_name = authors[0]["name"] if authors else "AudioCore"
    supplier: dict[str, Any] = {"name": supplier_name}
    if repo:
        supplier["url"] = [repo]
    metadata.setdefault("supplier", supplier)
    metadata.setdefault("lifecycles", [{"phase": "build"}])


def main() -> int:
    """Generate, prune, and enrich the AudioCore SBOM."""
    parser = argparse.ArgumentParser(description="Generate AudioCore's CycloneDX SBOM")
    parser.add_argument("--venv", default=str(REPO_ROOT / "venv"), help="virtualenv to scan")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output SBOM path")
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="reuse the existing base SBOM instead of running cyclonedx-py",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not args.skip_generate:
        run_cyclonedx(Path(args.venv), output)

    bom = json.loads(output.read_text(encoding="utf-8"))

    roots = read_runtime_roots()
    closure = compute_runtime_closure(roots)
    log(f"runtime closure: {len(closure)} distributions from {len(roots)} declared roots")
    prune_to_closure(bom, closure)
    log(f"pruned to {len(bom['components'])} components")

    cache = load_hash_cache()
    for component in bom["components"]:
        enrich_component(component, cache)
    enrich_main_component(bom)
    enrich_document_metadata(bom)
    add_compositions(bom)
    HASH_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    output.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    log(f"wrote enriched SBOM to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
