# Contributing to Meridian

Thanks for taking a look. Meridian is small, the process is short, and first-time contributors are
very welcome. This page covers, in order: finding something to work on, getting set up, the checks a
pull request needs, and the handful of rules that are not negotiable.

## Just want to use it?

You do not need a clone to use Meridian:

```bash
pip install meridian-eval          # or: uv tool install meridian-eval
meridian setup                     # one-time: builds the model-proxy image (needs Docker)
meridian --help
```

The rest of this page is for changing Meridian itself.

## 1. Find something to work on

Every open issue is labelled so you can tell at a glance how big it is and what it touches.

| Label | Meaning |
|---|---|
| `good first issue` | Small, well-scoped, with the files to change named in the issue. A good start. |
| `help wanted` | Larger, but clearly described and nobody is on it. |
| `size: XS` · `S` · `M` · `L` | Rough effort: an hour, an afternoon, a few days, a week or more. |
| `area: …` | The part of the code it touches (`proxy`, `grading`, `stats`, `cli`, `importer`, `dashboard`, `ci`, `docs`, `packaging`, `runtime`, `store`, `tests`, `security`). |
| `needs discussion` | The right answer is not obvious yet. Comment before writing code. |
| `bug` · `enhancement` · `documentation` · `refactor` · `tests` | What kind of change it is. |

Comment on an issue to say you are taking it, so two people do not do the same work. If you have an idea
that is not an issue yet, open one first for anything bigger than `size: S`; it is much cheaper to agree
on an approach before the code exists.

## 2. Set up

Requires Python 3.12 or 3.13, Docker, and [uv](https://docs.astral.sh/uv/). Node 22 only if you work on
the dashboard.

```bash
git clone https://github.com/patsypppe/meridian.git
cd meridian
uv sync               # creates .venv with the dev tools
make check            # ruff + mypy --strict + unit tests: should pass on a clean checkout
```

If `make check` does not pass on a clean checkout, that is a bug worth an issue on its own.

For Docker-backed work, also build the images once: `make images` (and `make db` if you touch `store/`).
No API key is needed for any test; real-model runs are optional and only used for benchmarks.

## 3. Run the right tests

Tests come in tiers. Run the cheapest tier that can catch your change, and the others when you touch
their area. CI runs all of them on every pull request.

| Command | What it runs | When you need it |
|---|---|---|
| `make check` | ruff, `mypy --strict`, unit tests (seconds, no Docker) | Always |
| `make integration` | real containers: isolation, grading sandboxes, the proxy | `runtime/`, `snapshots/`, `store/`, `grading/`, the proxy |
| `make e2e` | a full run, replay and gate against the fixture agent | `gate/`, `manifest/`, the proxy, the CLI |
| `cd web && npm ci && npm test && npm run build` | the dashboard's type check, tests and build | `web/` |

`make fmt` applies formatting and autofixes.

## 4. Open a pull request

1. Branch from `main`: `git checkout -b fix/short-description`.
2. Make the change, with a test (see the rules below).
3. `make check`, plus the tiers for the areas you touched.
4. Push and open a PR. The template asks what changed and how you checked it; "Closes #123" links the issue.
5. CI runs lint and types on both Pythons, unit, integration, end-to-end, the dashboard, a packaging check
   that installs the wheel outside the repository, and Meridian gating itself (`gate.yml`). A failing
   self-gate is not automatically a blocker, but the PR description should explain it.

Commit messages: present tense, saying what changed, for example
`gate: block on tolerance and significance together` rather than `update decide.py`.

## 5. The rules

These are what make Meridian's numbers trustworthy. A design that conflicts with one of them loses.

1. **Every trial starts from a clean, isolated environment.** Nothing shared between trials.
2. **Grade outcomes, not trajectories.** Assertions read the final state of the environment.
3. **Report pass^k, not a mean.** `pass^k = C(c,k)/C(n,k)`, never `(c/n)**k`.
4. **Every run is reproducible from its manifest.** Digests, not tags; integers, not floats, in anything hashed.

And the ones that most often catch people out:

- **A provider failure is not an agent failure.** Rate limits and 5xx become `harness_error` with a cause,
  never a `fail`. Only `harness_error` is retried, and only once.
- **An assertion that cannot be evaluated is a harness error, never a pass.**
- **A check that cannot fail is not a check.** If you add an assertion about isolation, determinism or
  reproducibility, add the case that violates it and assert that it is caught. The contamination probe is
  the pattern to follow.
- **`mypy --strict` is not negotiable.** No new `# type: ignore` without a comment saying why.
- **Pure logic stays pure.** `stats/`, `gate/decide.py`, `manifest/build.py` and `grading/graders/` have no
  I/O and no Docker imports, and each function there has both a passing and a failing test.
- **Isolation lives in one file.** Every container security option is in `src/meridian/runtime/isolation.py`.
- Line length is 100; ruff enforces it.

## 6. Area notes

**The manifest** is the reproducibility contract. If you change what goes into it or how it is
canonicalized, update `tests/fixtures/golden-manifest.json` and its hash file in the same commit, and say
in the PR description why the old manifests are no longer replayable.

**The dashboard** (`web/`) re-implements `stats/passk.py` and `stats/intervals.py` in TypeScript. If you
change either Python module, run `uv run python -m benchmarks.export_web_vectors` and commit the
regenerated `web/src/__fixtures__/stats-vectors.json`. A Python test fails if it is stale, and the
TypeScript tests fail if the two implementations disagree.

**The importer** (`importers/harbor.py`) refuses tasks it cannot run faithfully, with a reason. When you
add support for a Harbor feature, add a test that a task using it converts, and keep a test that an
unsupported variant is still refused.

**Code from other projects** must keep its license notice: say where it came from and what you changed in
the file header, and add it to `THIRD_PARTY_NOTICES.md`.

## 7. Reporting bugs and security problems

Use the bug template, and include `meridian version`, how you installed it, and whether the run was in
`record` or `replay` mode. Say explicitly whether **the harness** errored or **the agent** got a result you
think is wrong: they are different problems.

Security problems go through private reporting, not a public issue; see [SECURITY.md](SECURITY.md).

## 8. Releasing (maintainers)

Bump `src/meridian/version.py`, add the section to `CHANGELOG.md`, merge, then run the **release**
workflow (`workflow_dispatch`, target `pypi`). It builds, checks, publishes to PyPI with trusted
publishing, and creates the `vX.Y.Z` tag and GitHub release with the same files.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE), and you
agree to follow the [code of conduct](CODE_OF_CONDUCT.md).
