# Contributing

Issues and pull requests welcome — https://github.com/paolomonasterolo/migratecore/issues.

**New heuristics** need a discussion issue first describing the detection signal, the confidence level, and how you'd estimate dollar impact. Confidence calibration matters more than coverage — a wrong recommendation costs the user's trust on the first run.

**Bug reports:** include `mc analyze --format json` output (redact `api_key_id` and `workspace_id` if needed) and the version string from `mc version`.

**Local development:** `pip install -e ".[dev]"` from the repo root. Tests run against bundled fixtures with `pytest` — no Anthropic API key required. Run `ruff check .` before submitting a PR.
