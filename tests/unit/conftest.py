"""Shared fixtures for the unit test suite.

Unit tests must be hermetic: they must not depend on ambient credentials that
happen to be present on a developer's machine. In particular, a locally
exported ``OPENAI_API_KEY`` would let key-dependent code paths pass locally
while failing in CI (which has no key). This autouse fixture removes the
OpenAI key environment variables for every unit test; tests that exercise a
configured backend must supply their own key explicitly (e.g. via
``OpenAIConfig(api_key=...)`` or ``monkeypatch.setenv``).

Integration tests (under ``tests/integration``) are intentionally not covered
by this conftest, so they can still run against a real key when invoked.
"""

from __future__ import annotations

import pytest

_OPENAI_KEY_ENV_VARS = ("OPENAI_API_KEY", "AUDIOCORE_OPENAI_API_KEY")


@pytest.fixture(autouse=True)
def _scrub_ambient_openai_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ambient OpenAI API keys so unit tests match CI's keyless env."""
    for env_var in _OPENAI_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
