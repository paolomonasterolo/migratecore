"""Tests for the analyzer.

These tests run against the bundled sample fixture so they're deterministic
and don't require network access or an Admin API key.
"""

from __future__ import annotations

from migratecore.analyzer import (
    analyze,
    find_cache_migrations,
    find_model_migrations,
    find_tag_migrations,
)
from migratecore.client import load_fixture
from migratecore.models import Confidence, MigrationKind


def test_fixture_loads() -> None:
    records = load_fixture("sample")
    assert len(records) > 0
    assert all(r.input_tokens >= 0 for r in records)


def test_cache_migrations_detected() -> None:
    records = load_fixture("sample")
    migrations = find_cache_migrations(records)
    assert len(migrations) >= 1, "Expected cache migrations on the no-cache fixture"
    assert all(m.kind is MigrationKind.CACHE for m in migrations)
    assert all(m.confidence is Confidence.HIGH for m in migrations)
    assert all(m.estimated_monthly_savings_usd > 0 for m in migrations)


def test_model_migrations_detected() -> None:
    records = load_fixture("sample")
    migrations = find_model_migrations(records)
    assert len(migrations) >= 1, "Expected model migrations on the Sonnet-heavy fixture"
    assert all(m.kind is MigrationKind.MODEL for m in migrations)
    assert all(m.confidence is Confidence.MEDIUM for m in migrations)


def test_tag_migration_detected() -> None:
    records = load_fixture("sample")
    migrations = find_tag_migrations(records)
    assert len(migrations) == 1, "Expected exactly one organization-level tag migration"
    assert migrations[0].kind is MigrationKind.TAG
    assert migrations[0].confidence is Confidence.HIGH


def test_full_report_assembles() -> None:
    records = load_fixture("sample")
    report = analyze(records)
    assert report.total_spend_usd > 0
    assert report.addressable_savings_usd > 0
    assert len(report.migrations) >= 3
    sorted_m = report.sorted_migrations()
    savings = [m.estimated_monthly_savings_usd for m in sorted_m]
    assert savings == sorted(savings, reverse=True)


def test_empty_records_produce_empty_report() -> None:
    report = analyze([])
    assert report.total_spend_usd == 0.0
    assert report.migrations == []
    assert report.high_confidence_count == 0
