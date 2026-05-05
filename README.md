# MigrateCore

> Cut your Claude bill. We tell you exactly what to migrate.

MigrateCore analyzes your Anthropic API usage and produces ranked, dollar-denominated migration plans across five categories: prompt caching, model routing, batch API, metadata tagging, and prompt deduplication.

It does not sit in your API request path, store your prompts, or modify your code. It reads your usage via the Anthropic Admin API, runs heuristics, and outputs a prioritized list of changes with dollar-impact estimates.

Full spec: [`docs/SPEC.md`](docs/SPEC.md).

## Install

```bash
pipx install migratecore
```

## Use

```bash
export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...
mc analyze
```

```
MigrateCore — last 30 days
─────────────────────────────────────────────
  $4,217 / mo    addressable waste
   3 high-confidence migrations ready

  → cache    $2,140  /mo   (87 prompts, 12 endpoints)
  → model    $1,420  /mo   (Sonnet → Haiku, 4 endpoints)
  → batch      $657  /mo   (nightly digest job)

Run `mc plan cache` for the migration plan.
```

## License

CLI: Apache 2.0 — see [LICENSE](LICENSE).
Hosted Cloud version at [migratecore.com](https://migratecore.com): proprietary.

---

*MigrateCore is an independent project and is not affiliated with Anthropic, PBC. Claude® is a trademark of Anthropic, PBC.*
