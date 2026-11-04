"""A run stopped with SIGTERM removes every container and volume it created.

SIGTERM is what a cancelled CI job, `docker stop` and Kubernetes send. Before
`runtime/shutdown.py`, Python's default handler exited immediately and leaked
every in-flight trial container.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import CHECKOUT_SUITE, REPO_ROOT, RUN_LABEL, requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


def _hanging_suite(tmp_path: Path) -> Path:
    """The reference suite with one task whose agent sleeps far past the test."""
    suite = tmp_path / "suite"
    shutil.copytree(CHECKOUT_SUITE, suite)
    tasks = suite / "tasks"
    keep = tasks / "happy-path.yaml"
    for task_file in tasks.glob("*.yaml"):
        if task_file != keep:
            task_file.unlink()
    text = keep.read_text()
    text = text.replace("limits:\n", 'adapter: "subprocess:probes:hang"\nlimits:\n', 1)
    keep.write_text(text)
    return suite


def _labelled(client: Any) -> tuple[list[Any], list[Any]]:
    filters = {"label": RUN_LABEL}
    return client.containers.list(all=True, filters=filters), client.volumes.list(filters=filters)


def test_sigterm_mid_trial_leaves_nothing_behind(docker_client: Any, tmp_path: Path) -> None:
    suite = _hanging_suite(tmp_path)
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from meridian.cli import app; app()",
            "run",
            "--suite",
            str(suite),
            "--sut",
            str(REPO_ROOT / "fixtures"),
            "--n",
            "2",
            "--k",
            "1",
            "--proxy-mode",
            "replay",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        # Wait until a trial container is actually running before pulling the plug.
        deadline = time.time() + 120
        while time.time() < deadline:
            running = [
                c
                for c in _labelled(docker_client)[0]
                if c.labels.get("meridian.role") != "proxy" and c.status == "running"
            ]
            if running:
                break
            time.sleep(1)
        else:
            pytest.fail("no trial container started")

        process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=120)
    finally:
        if process.poll() is None:
            process.kill()

    text = output.decode(errors="replace")
    assert process.returncode == 2, text
    assert "interrupted (SIGTERM)" in text, text
    containers, volumes = _labelled(docker_client)
    assert containers == [], f"leaked containers: {[c.name for c in containers]}"
    assert volumes == [], f"leaked volumes: {[v.name for v in volumes]}"
