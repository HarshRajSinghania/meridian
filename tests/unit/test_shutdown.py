"""Signals stop a run in an orderly way and leave nothing behind."""

from __future__ import annotations

import os
import signal
from typing import Any

import pytest

from meridian.runtime import shutdown

pytestmark = pytest.mark.unit


def test_sigterm_becomes_an_interrupt_inside_the_block() -> None:
    with pytest.raises(KeyboardInterrupt, match="SIGTERM"), shutdown.terminate_as_interrupt():
        os.kill(os.getpid(), signal.SIGTERM)
        for _ in range(1000):  # the handler runs at the next bytecode boundary
            pass


def test_previous_handlers_are_restored_afterwards() -> None:
    before = signal.getsignal(signal.SIGTERM)
    with shutdown.terminate_as_interrupt():
        assert signal.getsignal(signal.SIGTERM) is not before
    assert signal.getsignal(signal.SIGTERM) is before


def test_signals_are_ignored_while_cleaning_up() -> None:
    with shutdown.signals_ignored():
        assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_IGN
        os.kill(os.getpid(), signal.SIGTERM)  # must not raise
    assert signal.getsignal(signal.SIGINT) is not signal.SIG_IGN


class _Request:
    run_id = "run-interrupted-1"


def test_an_interrupted_run_sweeps_exactly_its_own_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    swept: list[str | None] = []

    async def interrupted(client: Any, request: Any) -> Any:
        raise KeyboardInterrupt("SIGTERM")

    def fake_sweep(client: Any, *, run_id: str | None = None) -> list[str]:
        swept.append(run_id)
        return ["container:meridian-trial-x", "volume:meridian-work-x"]

    monkeypatch.setattr(shutdown, "execute", interrupted)
    monkeypatch.setattr(shutdown, "sweep_orphans", fake_sweep)
    with pytest.raises(shutdown.RunInterrupted) as info:
        shutdown.execute_cleanly(object(), _Request())  # type: ignore[arg-type]
    assert swept == ["run-interrupted-1"]
    assert info.value.removed == ["container:meridian-trial-x", "volume:meridian-work-x"]
    assert "SIGTERM" in str(info.value) and "run-interrupted-1" in str(info.value)


def test_a_normal_run_does_not_sweep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fine(client: Any, request: Any) -> str:
        return "outcome"

    monkeypatch.setattr(shutdown, "execute", fine)
    monkeypatch.setattr(shutdown, "sweep_orphans", lambda *a, **k: pytest.fail("swept"))
    assert shutdown.execute_cleanly(object(), _Request()) == "outcome"  # type: ignore[arg-type]
