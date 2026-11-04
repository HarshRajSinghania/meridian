"""`meridian doctor` reports each check and fails only when a run cannot work."""

from __future__ import annotations

from typing import Any

import pytest

from meridian import doctor

pytestmark = pytest.mark.unit


class _Images:
    def __init__(self, present: bool) -> None:
        self.present = present

    def get(self, tag: str) -> Any:
        if not self.present:
            raise LookupError(tag)
        return type("Image", (), {"id": "sha256:" + "a" * 64})()


class _Client:
    def __init__(self, image: bool = True) -> None:
        self.images = _Images(image)

    def version(self) -> dict[str, str]:
        return {"Version": "27.3.1"}


class _Response:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code = status
        self.text = text


def no_db(url: str) -> None:
    raise AssertionError("database should not be contacted")


def run(**kwargs: Any) -> list[doctor.Check]:
    defaults: dict[str, Any] = {
        "get_client": _Client,
        "proxy_tag": "meridian-proxy:dev",
        "connect": no_db,
        "env": {},
    }
    return doctor.run(**{**defaults, **kwargs})


def by_name(checks: list[doctor.Check]) -> dict[str, doctor.Check]:
    return {c.name: c for c in checks}


def test_a_ready_machine_passes() -> None:
    checks = run(env={"ANTHROPIC_API_KEY": "sk-ant-x"})
    assert doctor.exit_code(checks) == 0
    assert by_name(checks)["docker"].detail == "Docker 27.3.1 is reachable"


def test_no_docker_fails_and_skips_the_image_check() -> None:
    def broken() -> Any:
        raise RuntimeError("connection refused")

    checks = run(get_client=broken)
    assert by_name(checks)["docker"].status == doctor.FAIL
    assert "proxy image" not in by_name(checks)
    assert doctor.exit_code(checks) == 2


def test_a_missing_proxy_image_fails_with_the_fix() -> None:
    check = by_name(run(get_client=lambda: _Client(image=False)))["proxy image"]
    assert check.status == doctor.FAIL and "meridian setup" in check.fix


def test_no_key_is_only_a_warning_because_replay_needs_none() -> None:
    checks = run()
    assert by_name(checks)["credentials"].status == doctor.WARN
    assert doctor.exit_code(checks) == 0


def test_a_key_for_the_wrong_provider_is_flagged() -> None:
    check = by_name(run(env={"GROQ_API_KEY": "gsk_x"}))["credentials"]
    assert check.status == doctor.WARN and "ANTHROPIC_API_KEY" in check.detail


def test_credential_values_are_never_shown() -> None:
    check = by_name(run(env={"ANTHROPIC_API_KEY": "sk-ant-secret-value-123"}))["credentials"]
    assert "secret-value" not in check.detail


def test_database_is_optional_but_checked_when_configured() -> None:
    assert by_name(run())["database"].status == doctor.OK

    def refuse(url: str) -> None:
        raise OSError("refused")

    check = by_name(
        run(env={"MERIDIAN_DATABASE_URL": "postgresql://u:pw@db:5432/m"}, connect=refuse)
    )["database"]
    assert check.status == doctor.FAIL and "db:5432/m" in check.detail and "pw" not in check.detail


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (200, doctor.OK),
        (401, doctor.FAIL),
        (404, doctor.FAIL),
        (429, doctor.WARN),
        (500, doctor.FAIL),
    ],
)
def test_upstream_outcomes(status: int, expected: str) -> None:
    env = {
        "GROQ_API_KEY": "gsk_abcdefghijklmnop",
        "MERIDIAN_UPSTREAM_API": "openai",
        "MERIDIAN_UPSTREAM_BASE_URL": "https://api.groq.com/openai/v1",
        "MERIDIAN_UPSTREAM_MODEL": "openai/gpt-oss-20b",
    }
    seen: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> _Response:
        seen["url"] = url
        seen["auth"] = kwargs["headers"]["authorization"]
        return _Response(status, "provider says gsk_abcdefghijklmnop is bad")

    check = by_name(run(env=env, post=post))["upstream"]
    assert check.status == expected
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert "gsk_abcdefghijklmnop" not in check.detail  # the provider's echo is redacted


def test_an_unconfigured_openai_upstream_says_what_is_missing() -> None:
    check = by_name(
        run(
            env={"GROQ_API_KEY": "gsk_x", "MERIDIAN_UPSTREAM_API": "openai"},
            post=lambda *a, **k: None,
        )
    )["upstream"]
    assert check.status == doctor.FAIL and "MERIDIAN_UPSTREAM_MODEL" in check.fix


def test_render_shows_fixes_only_for_problems() -> None:
    text = doctor.render(
        [
            doctor.Check("docker", doctor.OK, "fine", "never shown"),
            doctor.Check("db", doctor.FAIL, "down", "start it"),
        ]
    )
    assert "never shown" not in text and "fix: start it" in text and "[FAIL]" in text
