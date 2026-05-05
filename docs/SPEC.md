# MigrateCore

> Cut your Claude bill. We tell you exactly what to migrate.

MigrateCore analyzes your Anthropic API usage and produces ranked, dollar-denominated migration plans across five categories: prompt caching, model routing, batch API, metadata tagging, and prompt deduplication.

It does not sit in your API request path, store your prompts, or modify your code. It reads your usage via the Anthropic Admin API, runs a set of heuristics, and outputs a prioritized list of changes you can make — each one with an estimated dollar impact.

**Repository:** github.com/paolomonasterolo/migratecore
**Website:** migratecore.com
**License (CLI):** Apache 2.0
**License (Cloud):** proprietary, hosted at migratecore.com

---

## What MigrateCore does

The MigrateCore CLI ingests the last N days of your Anthropic API usage data via your own Admin API key and produces a one-page report with a headline number — *"$4,217/month addressable, 3 high-confidence migrations ready"* — followed by ranked migration plans.

A migration is a discrete, scoped change with three parts: an estimated dollar impact, an effort estimate, and a verification step. The CLI doesn't auto-apply anything. Humans approve and execute every change.

### The five migration types

| Migration | What it does | Typical impact |
|---|---|---|
| **Cache** | Adds `cache_control` blocks to repeated prompt prefixes | Up to 90% reduction on cached input tokens |
| **Model** | Routes appropriate Sonnet/Opus calls to Haiku | 10–20× cost reduction on migrated calls |
| **Batch** | Moves async/non-interactive workloads to the Batch API | 50% reduction on migrated calls |
| **Tag** | Adds `metadata` field for per-feature/per-customer attribution | Visibility — prerequisite for chargeback |
| **Dedup** | Eliminates identical or near-identical repeated prompts | 5–15% on chatty workloads |

Each migration produces a discrete artefact: a markdown plan, a code-diff suggestion, and a "what to monitor afterwards" checklist.

### Detection heuristics

| Migration | Detection signal | Confidence |
|---|---|---|
| Cache | Same prompt prefix sent ≥3 times in 24h with no `cache_control` block | High |
| Model | High Sonnet/Opus volume on short, structured prompts (classification, extraction, simple Q&A) | Medium — recommendation, never auto-apply |
| Batch | Calls flagged with metadata or naming patterns suggesting non-interactive workloads | Medium |
| Tag | % of spend with no `metadata` field set | High |
| Dedup | Identical request bodies within a 1h window | High |

---

## What MigrateCore is not

- **Not a runtime proxy.** MigrateCore does not sit in the API request path. Zero added latency, zero trust surface for production traffic.
- **Not multi-provider.** No OpenAI, no Gemini, no Bedrock. Claude-native by design — depth over breadth.
- **Not a generic LLM observability platform.** Different category. If you need traces and prompt logs, use Helicone or Langfuse.
- **Not an evaluation framework.** MigrateCore recommends migrations; it doesn't run the evals that prove a model downgrade is safe for your workload. That step is yours.
- **Not a billing system.** It surfaces insights from your existing Anthropic bill.
- **Not auto-applying.** Every migration is reviewed and approved by a human.

---

## CLI — free, open source

The core analysis engine, distributed as a Python package and run locally. **Your Admin API key never leaves your machine.**

### Install

```bash
pipx install migratecore
```

### Configure

```bash
export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...
# or
mc auth
```

### Use

```bash
mc analyze                       # last 30 days, all migrations, headline number
mc plan cache                    # detailed plan for a specific migration type
mc report --format html          # full HTML report
mc report --format json          # structured output for piping
mc diff --since 30d              # month-over-month cost change with top contributors
```

The HTML report is a single self-contained file — email it, attach it to a Notion page, share it in Slack.

### Sample output

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

---

## Cloud — paid, hosted

Same engine, plus continuous monitoring, multi-workspace support, migration tracking, and the things teams need beyond a local CLI.

### Tiers

| Tier | Price | For | Features |
|---|---|---|---|
| **Solo** | $49/mo | Indie devs, small teams | 1 workspace, weekly auto-report, email alerts, 90-day history |
| **Team** | $199/mo | Startups, scale-ups | Up to 5 workspaces, daily monitoring, Slack alerts, per-project chargeback, budget guardrails, migration tracking, 1-year history |
| **Business** | $999/mo | Mid-market, regulated | Unlimited workspaces, RBAC + SSO, custom alerts, audit log export, DPA, self-hosted option, 3-year history, priority support |

### What Cloud adds beyond the CLI

- **Continuous ingestion.** Cloud pulls usage daily; you don't need to remember to run anything.
- **Migration tracking.** When you apply a recommended migration, Cloud measures the actual savings against the prediction.
- **Per-customer / per-feature chargeback.** For SaaS companies passing Claude costs to their own customers — *"Customer A cost us $1,240 in Claude tokens this month."*
- **Forecasting.** Surfaces anomalies before the bill arrives.
- **Budget guardrails.** Slack-pinged at 50/75/90% of monthly cap; optionally trigger automated downgrade rules.
- **Migration simulator.** *"If you executed the model migration on these endpoints, savings = $X / month, blast radius = Y endpoints."*
- **Roles & access.** A finance person needs read-only spend visibility without an Admin API key.
- **Audit log.** Who looked at what, when. SOC 2-friendly.
- **Self-hosted option** (Business tier). Same Docker image we run, deployed in your VPC.

### What Cloud does not do

- Does not proxy or relay Claude API calls.
- Does not store prompts or completions — only metadata, token counts, and aggregates pulled from the Admin API.
- Does not auto-apply migrations or modify customer code.

---

## Architecture

### CLI

- **Language:** Python 3.11+
- **CLI framework:** typer
- **Anthropic client:** official `anthropic` Python SDK
- **Reporting:** rich (terminal), jinja2 (single static HTML template)
- **Tests:** pytest with recorded API fixtures (vcrpy) for deterministic CI
- **Packaging:** hatchling, published to PyPI as `migratecore`

### Cloud

- **Backend:** Python (FastAPI), reusing the CLI's analyzer as a library
- **Frontend:** Next.js + Tailwind
- **Database:** Postgres (managed)
- **Hosting:** EU region, single-tenant for Business tier
- **Auth:** Clerk
- **Billing:** Stripe

### Repository layout

```
migratecore/
├── README.md
├── LICENSE                    Apache-2.0
├── pyproject.toml
├── docs/
│   ├── SPEC.md                this document
│   ├── ARCHITECTURE.md        deep dive into the analyzer (later)
│   └── MIGRATIONS.md          per-migration detection logic & examples (later)
├── src/
│   └── migratecore/
│       ├── __init__.py
│       ├── cli.py             typer entrypoint
│       ├── client.py          Anthropic Admin API wrapper
│       ├── analyzer.py        migration heuristics
│       ├── report.py          terminal + HTML rendering
│       └── templates/
│           └── report.html.j2
└── tests/
    ├── fixtures/
    ├── test_analyzer.py
    └── test_cli.py
```

Cross-platform: macOS, Linux, Windows (WSL).

---

## License

The CLI is licensed under **Apache 2.0**. You can use, modify, fork, and redistribute the source under the terms of that license.

The hosted Cloud service at migratecore.com is proprietary. The MigrateCore name and logo are protected and may not be used to designate forks or derivative services without permission.

---

## Contributing

Issues and pull requests welcome. See `CONTRIBUTING.md` (forthcoming).

---

## Disclaimer

MigrateCore is an independent project and is not affiliated with, endorsed by, or sponsored by Anthropic, PBC. Claude® is a trademark of Anthropic, PBC.
