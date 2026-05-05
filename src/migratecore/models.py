"""Domain model for MigrateCore.

The analyzer operates on `UsageRecord` lists. Anything pulled from the Anthropic
Admin API or loaded from a fixture is converted into this normalized shape first.
This keeps the heuristics decoupled from upstream API changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MigrationKind(str, Enum):
    CACHE = "cache"
    MODEL = "model"
    BATCH = "batch"
    TAG = "tag"
    DEDUP = "dedup"


@dataclass(frozen=True)
class UsageRecord:
    """One bucket of usage from the Admin API.

    The Admin API returns aggregates, not per-request rows. A typical bucket is
    "all calls from API key X to model Y in the day starting at timestamp T".
    """

    timestamp: datetime
    workspace_id: str | None
    api_key_id: str | None
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def has_cache_activity(self) -> bool:
        return (self.cache_creation_input_tokens + self.cache_read_input_tokens) > 0

    @property
    def has_metadata(self) -> bool:
        return bool(self.metadata)


@dataclass
class Migration:
    """A single migration recommendation for the user to act on."""

    kind: MigrationKind
    headline: str
    detail: str
    estimated_monthly_savings_usd: float
    confidence: Confidence
    affected_scope: str  # e.g. "api_key:ak_abc123" or "workspace:ws_xyz"
    next_step: str

    def __post_init__(self) -> None:
        if self.estimated_monthly_savings_usd < 0:
            raise ValueError("savings must be non-negative")


@dataclass
class Report:
    """The full analysis envelope rendered by `report.py`."""

    period_start: datetime
    period_end: datetime
    total_spend_usd: float
    migrations: list[Migration]

    @property
    def addressable_savings_usd(self) -> float:
        return sum(m.estimated_monthly_savings_usd for m in self.migrations)

    @property
    def high_confidence_count(self) -> int:
        return sum(1 for m in self.migrations if m.confidence == Confidence.HIGH)

    def sorted_migrations(self) -> list[Migration]:
        return sorted(
            self.migrations,
            key=lambda m: m.estimated_monthly_savings_usd,
            reverse=True,
        )
