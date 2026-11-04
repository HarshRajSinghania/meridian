# Changelog

## 0.2.0

First release on PyPI, as `meridian-eval` (the command and import are still `meridian`).

### Real models
- The proxy can translate to any OpenAI-compatible provider (Groq, OpenAI, vLLM, Ollama) as well as
  Anthropic, and the operator, not the agent, chooses the model.
- A provider failure is no longer scored as an agent failure. Every `harness_error` carries a cause
  (`sandbox`, `adapter_config`, `entrypoint`, `grader`, `model_provider`, `internal`); a trial whose
  last model call failed after the proxy's retries is excluded and retried once.
- Retries are bounded and jittered, honour `Retry-After` (seconds or HTTP-date; NaN, infinity and
  negatives rejected), and cover transport errors and 408/429/5xx/529.
- Time spent backing off from a throttling provider is added to the trial's deadline, capped at twice
  the deadline. Each run prints how much throttling it absorbed, in the provider's own words.

### Benchmarks
- `meridian import-harbor` converts tasks in Harbor's format (Terminal-Bench 2.0 and others) and
  skips, with the reason, every task Meridian cannot run faithfully.
- `verifier_script` assertion: runs a benchmark's hidden verifier in a network-less sandbox and reads
  its reward between per-run random markers. Grader-only files are never visible to the agent.
- `meridian suite build-images` builds and pins one image per task; `--drop-failed` keeps going.
- A general terminal agent (one `bash` tool) with an append-only transcript; a timeout verdict
  quotes the agent's last activity.

### Reporting
- Small-sample Student-t and Wilson intervals (adapted from Inspect, MIT), shown beside the bootstrap.
- A static React and TypeScript dashboard, published at
  https://patsypppe.github.io/meridian/dashboard/, whose statistics are tested against the Python ones.

### Packaging
- `pip install meridian-eval` ships the proxy Dockerfile and the terminal agent inside the wheel;
  `meridian setup` builds the proxy image from the installed package.
- Dropped three dependencies nothing imported (`structlog`, `opentelemetry-sdk`, `python-dotenv`), so
  the install is smaller.

### Contributing
- A rewritten `CONTRIBUTING.md`, issue and pull-request templates, `SECURITY.md`, a code of conduct,
  Dependabot for Actions, Python and npm, and unit tests on both supported Pythons in CI.

## 0.1.0

The MVP: isolated trials, host-side grading, pass^k with task-level bootstrap intervals, a paired
significance gate that reports its minimum detectable effect, record/replay cassettes, manifests and
replay, and a self-evaluation against a deterministic stand-in model.
