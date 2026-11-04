# Security policy

Meridian runs code it does not trust: the agent under test, and (in a CI gate) the task files in a pull
request. Isolation and grading are designed with that in mind, so a way around them is a real bug.

## Reporting

Please **do not open a public issue** for a vulnerability. Use GitHub's private reporting instead:
**Security → Report a vulnerability** on this repository. Include what an attacker controls (an agent, a
task file, a cassette, a run result), what they can reach, and the smallest reproduction you have.

You should hear back within a week. Fixes are released as a new patch version, and the report is
credited in the changelog unless you ask otherwise.

## In scope

- An agent or task file escaping its trial container, reaching the network, or reading another trial's state
- A provider credential reaching a trial container, a log, a cassette, a manifest, or a PR comment
- An agent influencing its own grade (for example forging a verifier reward or editing hidden tests)
- Path traversal or code execution on the host from a suite, task, cassette or result file
- The dashboard executing content from a loaded run file

## Supported versions

Only the latest release on PyPI (`meridian-eval`) receives security fixes.
