# Continuous integration

The repository ships with two GitHub Actions workflows:

| Workflow | File | Purpose |
|----------|------|---------|
| Default CI | [`ci.yml`](ci.yml) | Runs linting, unit tests, and packaging checks on pull requests and default branch pushes. |
| Polling trigger smoke test | [`polling_trigger.yml`](polling_trigger.yml) | Exercises the event polling pipeline against fixture data to ensure trigger detection remains stable. |

## Extending the pipelines

1. Update the job matrix to cover new Python versions when dependencies add support.
2. Pin secret names or environment variables through repository settings rather than hard-coding credentials.
3. Mirror any new observability or compliance checks described in [`docs/architecture.md`](../../docs/architecture.md) and [`docs/compliance.md`](../../docs/compliance.md) so automated gates stay aligned with runtime expectations.

Refer back to [`README.md`](../../README.md#system-architecture) for the architectural context that CI validates.
