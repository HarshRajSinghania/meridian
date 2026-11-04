"""`meridian doctor`: check a setup before a run, and say how to fix what is wrong.

Each check returns a `Check`, and only a `fail` means a run cannot work (exit 2).
A missing provider key is a warning, not a failure: replay runs need none.
Dependencies are passed in, so every check is testable without Docker or a network.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from meridian.runtime.secrets import PROVIDER_ENV_VARS, ProviderCredential, redact

OK = "ok"
WARN = "warn"
FAIL = "fail"

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
PING = {"max_tokens": 8, "messages": [{"role": "user", "content": "Reply with the word OK."}]}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def check_docker(get_client: Callable[[], Any]) -> tuple[Check, Any]:
    try:
        client = get_client()
        version = client.version().get("Version", "unknown")
    except Exception as exc:  # any failure to reach the daemon is the same answer
        message = str(exc)
        if not message.lower().startswith("cannot reach"):
            message = f"cannot reach the Docker daemon: {message}"
        return Check("docker", FAIL, message, "Start Docker and retry."), None
    return Check("docker", OK, f"Docker {version} is reachable"), client


def check_proxy_image(client: Any, tag: str) -> Check:
    try:
        image = client.images.get(tag)
    except Exception:
        return Check(
            "proxy image",
            FAIL,
            f"{tag} is not built",
            "Run `meridian setup` (or `make images` in a checkout).",
        )
    return Check("proxy image", OK, f"{tag} is built ({str(image.id)[:19]})")


def check_credentials(env: Mapping[str, str]) -> Check:
    present = [name for name in PROVIDER_ENV_VARS if env.get(name, "").strip()]
    if not present:
        return Check(
            "credentials",
            WARN,
            "no provider key is set; replay runs work, recording against a model does not",
            f"Set one of {', '.join(PROVIDER_ENV_VARS)} to record or gate against a real model.",
        )
    api = env.get("MERIDIAN_UPSTREAM_API", "anthropic")
    wanted = "ANTHROPIC_API_KEY" if api == "anthropic" else None
    if wanted and wanted not in present:
        return Check(
            "credentials",
            WARN,
            f"found {', '.join(present)} but the upstream is Anthropic, which needs {wanted}",
            "Set ANTHROPIC_API_KEY, or set MERIDIAN_UPSTREAM_API=openai and "
            "MERIDIAN_UPSTREAM_BASE_URL for an OpenAI-compatible provider.",
        )
    return Check("credentials", OK, f"{', '.join(present)} set (values not shown)")


def check_database(env: Mapping[str, str], connect: Callable[[str], Any]) -> Check:
    url = env.get("MERIDIAN_DATABASE_URL", "").strip()
    if not url:
        return Check("database", OK, "not configured (only `meridian history` needs one)")
    where = url.split("@")[-1]
    try:
        connect(url)
    except Exception as exc:
        return Check(
            "database",
            FAIL,
            f"cannot connect to {where}: {redact(str(exc))[:200]}",
            "Start Postgres (`make db`) or unset MERIDIAN_DATABASE_URL.",
        )
    return Check("database", OK, f"connected to {where}")


def check_upstream(env: Mapping[str, str], post: Callable[..., Any]) -> Check:
    """Send one tiny request through the configured upstream. Costs a few tokens."""
    from meridian.runtime.proxy.openai_compat import to_openai_request
    from meridian.runtime.secrets import MissingCredentialError, load_credential

    api = env.get("MERIDIAN_UPSTREAM_API", "anthropic")
    base = env.get(
        "MERIDIAN_UPSTREAM_BASE_URL",
        "https://api.anthropic.com" if api == "anthropic" else "",
    ).rstrip("/")
    model = env.get("MERIDIAN_UPSTREAM_MODEL") or (
        DEFAULT_ANTHROPIC_MODEL if api == "anthropic" else ""
    )
    if not base or not model:
        return Check(
            "upstream",
            FAIL,
            "the upstream is not fully configured",
            "Set MERIDIAN_UPSTREAM_BASE_URL and MERIDIAN_UPSTREAM_MODEL.",
        )
    try:
        credential: ProviderCredential = load_credential(dict(env))
    except MissingCredentialError:
        return Check("upstream", FAIL, "no provider key is set", "Set a provider key first.")
    headers = {"content-type": "application/json", credential.header_name: credential.header_value}
    body = {"model": model, **PING}
    if api == "openai":
        url, payload = f"{base}/chat/completions", to_openai_request(body)
    else:
        url, payload = f"{base}/v1/messages", body
        headers["anthropic-version"] = "2023-06-01"
    try:
        response = post(url, json=payload, headers=headers, timeout=30)
    except Exception as exc:
        return Check(
            "upstream", FAIL, f"could not reach {base}: {exc}", "Check the URL and network."
        )
    said = redact(" ".join(str(getattr(response, "text", "")).split()))[:240]
    status = int(response.status_code)
    if status == 200:
        return Check("upstream", OK, f"{model} at {base} answered")
    if status in (401, 403):
        return Check(
            "upstream", FAIL, f"the provider rejected the key ({status}): {said}", "Check the key."
        )
    if status == 404:
        return Check(
            "upstream",
            FAIL,
            f"model {model} not found ({status}): {said}",
            "Check MERIDIAN_UPSTREAM_MODEL.",
        )
    if status == 429:
        return Check(
            "upstream", WARN, f"rate limited right now: {said}", "Wait, or use a lower concurrency."
        )
    return Check(
        "upstream", FAIL, f"unexpected {status}: {said}", "See the provider's message above."
    )


def exit_code(checks: list[Check]) -> int:
    return 2 if any(c.status == FAIL for c in checks) else 0


def render(checks: list[Check]) -> str:
    marks = {OK: "ok  ", WARN: "warn", FAIL: "FAIL"}
    lines = []
    for check in checks:
        lines.append(f"[{marks[check.status]}] {check.name:<12} {check.detail}")
        if check.fix and check.status != OK:
            lines.append(f"       {'':<12} fix: {check.fix}")
    return "\n".join(lines)


def run(
    *,
    get_client: Callable[[], Any],
    proxy_tag: str,
    connect: Callable[[str], Any],
    post: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[Check]:
    environment = dict(os.environ if env is None else env)
    docker_check, client = check_docker(get_client)
    checks = [docker_check]
    if client is not None:
        checks.append(check_proxy_image(client, proxy_tag))
    checks.append(check_credentials(environment))
    checks.append(check_database(environment, connect))
    if post is not None:
        checks.append(check_upstream(environment, post))
    return checks
