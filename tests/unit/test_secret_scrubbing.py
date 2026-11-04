"""No credential reaches a file a run writes: archives, cassettes, reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meridian.runtime import secrets
from meridian.runtime.secrets import REDACTION, redact

pytestmark = pytest.mark.unit

ODD_KEY = "zq9-Plain-Looking-Key-1234567890"  # no known prefix: only value-scrubbing catches it


def test_a_key_with_no_known_prefix_is_scrubbed_by_value() -> None:
    env = {"OPENAI_API_KEY": ODD_KEY}
    assert ODD_KEY not in redact(f"provider said: invalid key {ODD_KEY}", env=env)
    assert REDACTION in redact(f"key={ODD_KEY}", env=env)


def test_prefixed_keys_are_still_scrubbed() -> None:
    assert "sk-ant-abcdefghijklmnop" not in redact("got sk-ant-abcdefghijklmnop back", env={})


def test_short_values_are_not_scrubbed_by_value() -> None:
    """A tiny credential value would otherwise mangle ordinary text."""
    assert redact("abc appears here", env={"GROQ_API_KEY": "abc"}) == "abc appears here"


def test_scrubbing_keeps_json_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", ODD_KEY)
    text = json.dumps({"error": {"message": f"bad key {ODD_KEY}"}})
    assert json.loads(redact(text))["error"]["message"] == f"bad key {REDACTION}"


def test_run_archives_are_scrubbed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from meridian.manifest import store
    from meridian.models.run import (
        ErrorCause,
        Outcome,
        RunResult,
        RunStatus,
        TaskResult,
        TrialResult,
    )

    monkeypatch.setenv("GROQ_API_KEY", ODD_KEY)
    trial = TrialResult(
        run_id="r",
        task_slug="happy-path",
        trial_index=0,
        seed=0,
        outcome=Outcome.HARNESS_ERROR,
        detail=f"upstream rejected {ODD_KEY}",
        error_cause=ErrorCause.MODEL_PROVIDER,
    )
    result = RunResult(
        run_id="r",
        suite_slug="s",
        suite_version=1,
        status=RunStatus.COMPLETE,
        k=1,
        n_requested=1,
        tasks=(TaskResult(task_slug="happy-path", trials=(trial,)),),
    )

    class _Manifest:
        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps({"note": f"{ODD_KEY}"})

    directory = store.save(_Manifest(), result, root=tmp_path)  # type: ignore[arg-type]
    for path in directory.iterdir():
        assert ODD_KEY not in path.read_text(), path.name


def test_cassettes_are_scrubbed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from meridian.runtime.proxy.cassette import CassetteStore

    monkeypatch.setenv("ANTHROPIC_API_KEY", ODD_KEY)
    cassettes = CassetteStore(tmp_path)
    cassette = cassettes.get("happy-path")
    cassette.record(
        0,
        key="k",
        response={"content": [{"type": "text", "text": f"echo {ODD_KEY}"}]},
        input_tokens=1,
        output_tokens=1,
    )
    path = cassettes.save(cassette)
    assert ODD_KEY not in path.read_text()
    json.loads(path.read_text())  # still valid JSON


def test_the_throttling_line_never_prints_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from meridian.runtime.orchestrator import summarize_throttling

    monkeypatch.setenv("GROQ_API_KEY", ODD_KEY)
    usage = {
        "trials": {
            "a:0": {
                "upstream_retries": 1,
                "upstream_wait_ms": 1000,
                "last_retry_reason": f"401: invalid key {ODD_KEY}",
            }
        }
    }
    assert ODD_KEY not in summarize_throttling(usage)


def test_write_redacted_writes_utf8(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    secrets.write_redacted(target, "café sk-abcdefghijklmnop")
    assert target.read_text(encoding="utf-8") == f"café {REDACTION}"
