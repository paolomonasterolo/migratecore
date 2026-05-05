# Contributing to MigrateCore

Thanks for considering a contribution. Issues and pull requests are welcome.

## Quick start

```bash
git clone https://github.com/paolomonasterolo/migratecore
cd migratecore
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## What we accept

- **Bug reports.** Please include a minimal reproduction.
- **New migration heuristics.** Open an issue first to discuss the signal and the confidence model. Heuristics that overstate savings hurt user trust more than missing migrations do.
- **Pricing table updates.** When Anthropic changes pricing, update `src/migratecore/pricing.py` and reference the announcement.
- **Doc improvements.** Always welcome.

## What we don't accept (yet)

- Multi-provider support (OpenAI, Gemini, etc.). Claude-native is the wedge by design — see [`docs/SPEC.md`](docs/SPEC.md).
- Runtime proxy mode. Considered for v0.2 as opt-in; not on the v0.1 roadmap.
- Auto-applying migrations to user code. Recommendations only; humans approve.

## Code style

- Python 3.11+
- `ruff` for lint and format (configured in `pyproject.toml`)
- Type hints required on public functions
- Tests required for new heuristics and bug fixes

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
