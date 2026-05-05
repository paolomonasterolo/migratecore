"""Migration analyzers.

Each function inspects normalized usage data and produces zero or more
`Migration` recommendations. Heuristics are intentionally conservative —
we'd rather miss a real opportunity than overstate a fragile one.

Limitations of v0.1 (deliberate, documented):
- The Admin API returns aggregates, not per-request rows. We cannot see
  individual prompts, only token totals grouped by model / api key /
  workspace / day. This shapes what each heuristic can detect.
- A future v0.2 mode (`--proxy`) will accept richer per-request logs to
  enable dedup and prompt-level model recommendations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from .models import (
    Confidence,
    Migration,
    MigrationKind,
    Report,
    UsageRecord,
)
from .pricing import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    cost_usd,
    haiku_equivalent_cost,
    rates_for,
)

# Heuristic thresholds — these are the dials.
# Tune from real usage data after launch.
CACHE_MIN_INPUT_TOKENS_PER_KEY = 1_000_000  # need meaningful volume to recommend caching
CACHE_NO_ACTIVITY_THRESHOLD = 0.01  # <1% of input tokens going through cache
CACHE_ASSUMED_REUSE_RATE = 0.50  # fraction of input plausibly cacheable
CACHE_AVG_HIT_RATE = 0.70  # of cacheable, fraction we'd expect to hit cache

MODEL_MIN_HIGH_TIER_COST = 50.0  # USD/period — ignore tiny workloads
MODEL_DOWNGRADE_FRACTION = 0.30  # assume 30% of high-tier calls could move to Haiku
MODEL_HIGH_TIER_PREFIXES = ("claude-opus", "claude-sonnet", "claude-3-opus", "claude-3-7-sonnet", "claude-3-5-sonnet")

TAG_UNTAGGED_THRESHOLD = 0.50  # >50% of spend untagged → recommend tagging


# ---------------------------------------------------------------------------
# Cache migration
# ---------------------------------------------------------------------------


def find_cache_migrations(records: list[UsageRecord]) -> list[Migration]:
    """Detect API keys with substantial input volume and no caching activity.

    The Admin API doesn't expose prompt content, so we can't prove that prompts
    are cacheable. We can prove the user isn't *trying* — zero cache_creation
    plus zero cache_read tokens against millions of input tokens is a very
    strong signal that caching has not been adopted on that surface.
    """
    by_key: dict[str | None, list[UsageRecord]] = defaultdict(list)
    for r in records:
        by_key[r.api_key_id].append(r)

    out: list[Migration] = []
    for api_key_id, rows in by_key.items():
        total_input = sum(r.input_tokens for r in rows)
        total_cache = sum(
            r.cache_creation_input_tokens + r.cache_read_input_tokens for r in rows
        )
        if total_input < CACHE_MIN_INPUT_TOKENS_PER_KEY:
            continue
        if total_cache / max(total_input, 1) > CACHE_NO_ACTIVITY_THRESHOLD:
            continue  # they're already caching; deeper analysis needed

        # Estimate savings: assume CACHE_ASSUMED_REUSE_RATE of input tokens
        # are cacheable, and CACHE_AVG_HIT_RATE of those become cache reads.
        # Savings per cached read token vs uncached = (1 - CACHE_READ_MULT) of input rate.
        # First-time cache write costs (CACHE_WRITE_MULT - 1) of input rate extra (small).
        # Use the dominant model in the bucket for the rate.
        model = _dominant_model(rows)
        in_rate, _ = rates_for(model)

        cacheable_input = total_input * CACHE_ASSUMED_REUSE_RATE
        hit_input = cacheable_input * CACHE_AVG_HIT_RATE
        miss_input = cacheable_input - hit_input

        savings_per_M = in_rate * (1 - CACHE_READ_MULTIPLIER)  # USD per M cached-read tokens
        write_overhead_per_M = in_rate * (CACHE_WRITE_MULTIPLIER - 1)  # one-time write cost

        period_savings = (
            (hit_input * savings_per_M / 1_000_000)
            - (miss_input * write_overhead_per_M / 1_000_000)
        )
        # Normalize to monthly — fixture/API window may be 30 days; assume so.
        monthly = max(0.0, period_savings)

        if monthly < 5.0:
            continue  # not worth flagging

        out.append(
            Migration(
                kind=MigrationKind.CACHE,
                headline=f"Add prompt caching to api_key {_fmt_key(api_key_id)}",
                detail=(
                    f"This key processed {total_input/1_000_000:.1f}M input tokens "
                    f"with no detectable cache activity. Repeated prompt prefixes "
                    f"on this surface are likely paying full rate."
                ),
                estimated_monthly_savings_usd=round(monthly, 2),
                confidence=Confidence.HIGH,
                affected_scope=f"api_key:{_fmt_key(api_key_id)}",
                next_step=(
                    "Identify the longest stable prompt prefix on this key "
                    "(system prompt, tool definitions, document context) and "
                    "wrap it with `cache_control: {type: 'ephemeral'}` in your "
                    "Anthropic SDK call."
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Model migration
# ---------------------------------------------------------------------------


def find_model_migrations(records: list[UsageRecord]) -> list[Migration]:
    """Detect API keys spending heavily on high-tier models.

    Cannot see prompts, so cannot judge per-call which would downgrade safely.
    Recommendation is directional: investigate which calls on this surface
    handle simple/structured tasks suitable for Haiku.
    """
    by_key: dict[str | None, list[UsageRecord]] = defaultdict(list)
    for r in records:
        by_key[r.api_key_id].append(r)

    out: list[Migration] = []
    for api_key_id, rows in by_key.items():
        high_tier_rows = [
            r for r in rows
            if any(p in r.model for p in MODEL_HIGH_TIER_PREFIXES)
        ]
        if not high_tier_rows:
            continue

        high_tier_cost = sum(
            cost_usd(
                r.model,
                r.input_tokens,
                r.output_tokens,
                r.cache_creation_input_tokens,
                r.cache_read_input_tokens,
            )
            for r in high_tier_rows
        )
        if high_tier_cost < MODEL_MIN_HIGH_TIER_COST:
            continue

        # If we moved DOWNGRADE_FRACTION of these tokens to Haiku:
        movable_input = sum(r.input_tokens for r in high_tier_rows) * MODEL_DOWNGRADE_FRACTION
        movable_output = sum(r.output_tokens for r in high_tier_rows) * MODEL_DOWNGRADE_FRACTION

        current_movable_cost = high_tier_cost * MODEL_DOWNGRADE_FRACTION
        haiku_cost = haiku_equivalent_cost(int(movable_input), int(movable_output))
        monthly_savings = max(0.0, current_movable_cost - haiku_cost)

        if monthly_savings < 10.0:
            continue

        dominant = _dominant_model(high_tier_rows)
        out.append(
            Migration(
                kind=MigrationKind.MODEL,
                headline=f"Route part of {_short_model(dominant)} traffic to Haiku on api_key {_fmt_key(api_key_id)}",
                detail=(
                    f"This key spent ${high_tier_cost:,.0f} on high-tier models. "
                    f"Common pattern: 30–50% of high-tier calls handle classification, "
                    f"extraction, or simple Q&A that Haiku can do at ~10× lower cost."
                ),
                estimated_monthly_savings_usd=round(monthly_savings, 2),
                confidence=Confidence.MEDIUM,
                affected_scope=f"api_key:{_fmt_key(api_key_id)}",
                next_step=(
                    "Sample 50 representative requests from this key. Build an "
                    "eval set. Run them through Haiku and compare quality. "
                    "Migrate categories that pass."
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Tag migration
# ---------------------------------------------------------------------------


def find_tag_migrations(records: list[UsageRecord]) -> list[Migration]:
    """Recommend metadata tagging if a large fraction of spend is untagged.

    Untagged spend can't be attributed to features or customers, which makes
    chargeback and cost optimization impossible. This is a visibility
    prerequisite, not a direct dollar-saver — but we estimate impact
    indirectly: untagged spend tends to grow 15–25% faster than tagged
    spend because nobody owns it. We size the recommendation against 5%
    of total spend as a conservative directional savings estimate.
    """
    if not records:
        return []
    total_spend = sum(
        cost_usd(
            r.model,
            r.input_tokens,
            r.output_tokens,
            r.cache_creation_input_tokens,
            r.cache_read_input_tokens,
        )
        for r in records
    )
    untagged_spend = sum(
        cost_usd(
            r.model,
            r.input_tokens,
            r.output_tokens,
            r.cache_creation_input_tokens,
            r.cache_read_input_tokens,
        )
        for r in records
        if not r.has_metadata
    )

    if total_spend < 100.0:
        return []
    untagged_fraction = untagged_spend / total_spend
    if untagged_fraction < TAG_UNTAGGED_THRESHOLD:
        return []

    estimated_monthly = round(untagged_spend * 0.05, 2)
    return [
        Migration(
            kind=MigrationKind.TAG,
            headline=f"Tag {untagged_fraction:.0%} of untagged Anthropic spend",
            detail=(
                f"${untagged_spend:,.0f} of your ${total_spend:,.0f} period spend "
                f"is untagged. Without metadata, you can't attribute cost to "
                f"features or customers — and untagged surfaces tend to grow "
                f"unmonitored."
            ),
            estimated_monthly_savings_usd=estimated_monthly,
            confidence=Confidence.HIGH,
            affected_scope="organization",
            next_step=(
                "Add a `metadata.user_id` (and optionally `metadata.feature`) "
                "field to every Anthropic API call. The Anthropic SDK accepts "
                "metadata as a top-level kwarg on `messages.create`."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


MONTHLY_DAYS = 30.0


def analyze(records: list[UsageRecord]) -> Report:
    """Run all migration heuristics and return a Report.

    Heuristics produce *period* savings (savings observed over whatever window
    the data covers). This function scales them to monthly using the actual
    observed period length — so a 7-day fixture and a 30-day API pull both
    produce sensible monthly projections.
    """
    if not records:
        now = datetime.now(UTC)
        return Report(period_start=now, period_end=now, total_spend_usd=0.0, migrations=[])

    period_start = min(r.timestamp for r in records)
    period_end = max(r.timestamp for r in records) + timedelta(days=1)
    period_days = max((period_end - period_start).total_seconds() / 86400.0, 1.0)
    monthly_factor = MONTHLY_DAYS / period_days

    period_spend = sum(
        cost_usd(
            r.model,
            r.input_tokens,
            r.output_tokens,
            r.cache_creation_input_tokens,
            r.cache_read_input_tokens,
        )
        for r in records
    )

    raw_migrations: list[Migration] = []
    raw_migrations.extend(find_cache_migrations(records))
    raw_migrations.extend(find_model_migrations(records))
    raw_migrations.extend(find_tag_migrations(records))

    # Scale period savings to monthly. We rebuild migrations because the
    # dataclass has a frozen-on-init validator on the savings field.
    scaled: list[Migration] = []
    for m in raw_migrations:
        scaled.append(
            Migration(
                kind=m.kind,
                headline=m.headline,
                detail=m.detail,
                estimated_monthly_savings_usd=round(
                    m.estimated_monthly_savings_usd * monthly_factor, 2
                ),
                confidence=m.confidence,
                affected_scope=m.affected_scope,
                next_step=m.next_step,
            )
        )

    return Report(
        period_start=period_start,
        period_end=period_end,
        total_spend_usd=round(period_spend * monthly_factor, 2),
        migrations=scaled,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dominant_model(rows: list[UsageRecord]) -> str:
    """Return the model accounting for the most tokens in this group."""
    by_model: dict[str, int] = defaultdict(int)
    for r in rows:
        by_model[r.model] += r.input_tokens + r.output_tokens
    return max(by_model.items(), key=lambda kv: kv[1])[0]


def _short_model(model: str) -> str:
    """Render a long model id like 'claude-sonnet-4-20250514' as 'Sonnet 4'."""
    if "opus-4" in model:
        return "Opus 4"
    if "sonnet-4" in model:
        return "Sonnet 4"
    if "haiku-4" in model:
        return "Haiku 4"
    if "3-5-sonnet" in model:
        return "Sonnet 3.5"
    if "3-5-haiku" in model:
        return "Haiku 3.5"
    if "3-opus" in model:
        return "Opus 3"
    if "3-sonnet" in model:
        return "Sonnet 3"
    if "3-haiku" in model:
        return "Haiku 3"
    return model


def _fmt_key(key_id: str | None) -> str:
    """Format an API key id for display, redacting the middle if long."""
    if not key_id:
        return "(unscoped)"
    if len(key_id) <= 12:
        return key_id
    return f"{key_id[:6]}…{key_id[-4:]}"
