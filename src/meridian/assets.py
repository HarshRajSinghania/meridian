"""Files Meridian needs at run time that are not Python modules.

A repository checkout has them in place (`envs/proxy/Dockerfile`,
`fixtures/terminal_agent/`). An installed wheel carries copies under
`meridian/_assets/`, added at build time from those same files, so there is one
source of truth either way. These helpers find whichever is present.
"""

from __future__ import annotations

import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
_BUNDLED = PACKAGE_DIR / "_assets"
_REPO_ROOT = PACKAGE_DIR.parents[1]

DEFAULT_SUT = Path("fixtures")


class MissingAssetError(FileNotFoundError):
    """A runtime file is in neither the installed package nor a repository checkout."""


def proxy_dockerfile() -> Path:
    for candidate in (_BUNDLED / "proxy.Dockerfile", _REPO_ROOT / "envs" / "proxy" / "Dockerfile"):
        if candidate.is_file():
            return candidate
    raise MissingAssetError("the proxy Dockerfile is missing from this installation")


def bundled_agents_root() -> Path:
    """The directory holding the bundled agents (currently `terminal_agent`)."""
    for candidate in (_BUNDLED / "agents", _REPO_ROOT / "fixtures"):
        if (candidate / "terminal_agent" / "agent.py").is_file():
            return candidate
    raise MissingAssetError("the bundled terminal agent is missing from this installation")


def resolve_sut(sut: Path) -> Path:
    """The system-under-test root to ship into trials.

    An explicit or existing path wins. Only when the default `fixtures` directory
    does not exist (a pip install, run outside the repository) does it fall back
    to the agents bundled with the package, so `meridian run` works out of the box.
    """
    if sut.exists() or sut != DEFAULT_SUT:
        return sut.resolve()
    return bundled_agents_root()


def write_proxy_build_context(destination: Path) -> Path:
    """Lay out a Docker build context for the proxy image; return its Dockerfile dir.

    Mirrors the repository layout the Dockerfile's COPY lines expect
    (`src/meridian/...` beside `envs/proxy/Dockerfile`), filled from whichever copy of
    the package is running, so an installed wheel builds the same image as a checkout.
    """
    source_tree = destination / "src" / "meridian"
    shutil.copytree(
        PACKAGE_DIR,
        source_tree,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_assets"),
        dirs_exist_ok=True,
    )
    env_dir = destination / "envs" / "proxy"
    env_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(proxy_dockerfile(), env_dir / "Dockerfile")
    return env_dir
