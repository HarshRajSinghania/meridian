## What this changes

<!-- One or two sentences. Link the issue: "Closes #123". -->

## How it was checked

- [ ] `make check` passes (ruff, `mypy --strict`, unit tests)
- [ ] `make integration` / `make e2e`, if this touches `runtime/`, `snapshots/`, `store/`, `gate/`, `manifest/` or the proxy
- [ ] `cd web && npm test && npm run build`, if this touches `web/`
- [ ] New behaviour has a test at the cheapest tier that can catch it, including the case that should fail

## Anything a reviewer should know

<!-- Trade-offs, follow-ups, or "this changes the manifest, so old runs are no longer replayable". -->
