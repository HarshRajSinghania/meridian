"""Runtime files resolve from a checkout and from an installed wheel alike."""

from __future__ import annotations

from pathlib import Path

import pytest

from meridian import assets

pytestmark = pytest.mark.unit


def test_the_proxy_dockerfile_is_found() -> None:
    assert assets.proxy_dockerfile().read_text().startswith("# The model proxy image.")


def test_the_terminal_agent_is_found() -> None:
    root = assets.bundled_agents_root()
    assert (root / "terminal_agent" / "agent.py").is_file()


def test_an_existing_sut_path_is_used_as_given(tmp_path: Path) -> None:
    assert assets.resolve_sut(tmp_path) == tmp_path.resolve()


def test_an_explicit_missing_path_is_not_silently_replaced(tmp_path: Path) -> None:
    """A typo in --sut must surface, not quietly run the bundled agent instead."""
    missing = tmp_path / "typo"
    assert assets.resolve_sut(missing) == missing.resolve()


def test_the_default_falls_back_to_the_bundled_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no ./fixtures here, as after a pip install
    assert assets.resolve_sut(assets.DEFAULT_SUT) == assets.bundled_agents_root()


def test_the_proxy_build_context_mirrors_the_repository_layout(tmp_path: Path) -> None:
    env_dir = assets.write_proxy_build_context(tmp_path)
    dockerfile = (env_dir / "Dockerfile").read_text()
    # every file the Dockerfile copies must exist in the context
    for line in dockerfile.splitlines():
        if line.startswith("COPY src/"):
            source = line.split()[1]
            assert (tmp_path / source).exists(), source
    assert not (tmp_path / "src" / "meridian" / "_assets").exists()
    assert not list((tmp_path / "src").rglob("__pycache__"))
