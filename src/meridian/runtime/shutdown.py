"""Stopping a run without leaving anything behind.

A run owns Docker containers, volumes and networks. Ctrl-C (SIGINT) already unwinds
through the orchestrator's `finally`, which removes them. SIGTERM did not: Python's
default handler exits on the spot, and SIGTERM is exactly what a cancelled CI job,
`docker stop` and Kubernetes send. Every cancelled CI run could leak trial containers.

So SIGTERM (and SIGHUP) are turned into the same orderly interruption as Ctrl-C, and
after the event loop has fully stopped, including the worker threads that make the
blocking Docker calls, everything labelled with the run's id is swept once more. A
Docker call that finished after the orchestrator's own cleanup would otherwise leave
the container it just created.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import threading
from collections.abc import Iterator
from types import FrameType
from typing import TYPE_CHECKING

from meridian.runtime.orchestrator import RunOutcome, RunRequest, execute
from meridian.runtime.trial_runner import sweep_orphans

if TYPE_CHECKING:  # pragma: no cover - typing only
    from docker import DockerClient

# Signals that mean "stop now" from a supervisor rather than from a person.
TERMINATING_SIGNALS: tuple[signal.Signals, ...] = tuple(
    s for s in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)) if s is not None
)


class RunInterrupted(Exception):
    """The run was stopped by a signal; its resources have been removed."""

    def __init__(self, run_id: str, removed: list[str], reason: str) -> None:
        self.run_id = run_id
        self.removed = removed
        self.reason = reason
        super().__init__(
            f"interrupted ({reason}); removed {len(removed)} leftover container(s) or "
            f"volume(s) for run {run_id}"
        )


@contextlib.contextmanager
def terminate_as_interrupt() -> Iterator[None]:
    """Within the block, SIGTERM and SIGHUP raise KeyboardInterrupt, like Ctrl-C."""
    if threading.current_thread() is not threading.main_thread():
        yield  # signal handlers can only be installed from the main thread
        return

    def interrupt(signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt(signal.Signals(signum).name)

    previous = {sig: signal.signal(sig, interrupt) for sig in TERMINATING_SIGNALS}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextlib.contextmanager
def signals_ignored() -> Iterator[None]:
    """Hold off further interruptions while cleanup runs (an impatient second Ctrl-C)."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    sigs = (signal.SIGINT, *TERMINATING_SIGNALS)
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in sigs}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def execute_cleanly(client: DockerClient, request: RunRequest) -> RunOutcome:
    """Run `request`; if a signal stops it, remove everything it created and say so."""
    with terminate_as_interrupt():
        try:
            return asyncio.run(execute(client, request))
        except KeyboardInterrupt as exc:
            reason = str(exc) or "SIGINT"
            with signals_ignored():
                removed = sweep_orphans(client, run_id=request.run_id)
            raise RunInterrupted(request.run_id, removed, reason) from exc
