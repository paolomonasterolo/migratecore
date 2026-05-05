"""Anthropic Admin API client.

Reads usage data from the Anthropic Admin API and converts it to the internal
`UsageRecord` shape. Supports a fixture mode for offline development and demos.

The exact endpoint and response shape for the Admin API's usage report
should be verified against current docs at:
    https://docs.claude.com/en/api/admin-api

This module isolates the upstream contract so heuristics never deal with raw
JSON. If Anthropic changes the response shape, only `_parse_usage_response`
needs to change.
"""

from __future__ import annotations

import importlib.resources
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from .models import UsageRecord

ADMIN_API_BASE = "https://api.anthropic.com"
USAGE_ENDPOINT = "/v1/organizations/usage_report/messages"
DEFAULT_TIMEOUT = 30.0


class AdminAPIError(Exception):
    """Raised when the Admin API returns an error or an unexpected shape."""


class AdminClient:
    """Thin wrapper around the Anthropic Admin API."""

    def __init__(
        self,
        admin_key: str,
        base_url: str = ADMIN_API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not admin_key.startswith("sk-ant-admin-"):
            raise ValueError(
                "Admin keys start with 'sk-ant-admin-'. Regular API keys "
                "(sk-ant-api...) cannot read usage data."
            )
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "x-api-key": admin_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

    def fetch_usage(self, days: int = 30) -> list[UsageRecord]:
        """Fetch the last `days` of usage and return normalized records."""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        params = {
            "starting_at": start.isoformat(),
            "ending_at": end.isoformat(),
            "bucket_width": "1d",
        }
        try:
            resp = self._client.get(USAGE_ENDPOINT, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise AdminAPIError(
                f"Admin API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.HTTPError as e:
            raise AdminAPIError(f"Admin API request failed: {e}") from e

        return _parse_usage_response(resp.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AdminClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _parse_usage_response(payload: dict[str, Any]) -> list[UsageRecord]:
    """Convert an Admin API JSON payload into UsageRecord objects.

    Expected shape (verify against current docs):
        {
          "data": [
            {
              "starting_at": "2026-04-04T00:00:00Z",
              "results": [
                {
                  "workspace_id": "ws_...",
                  "api_key_id": "ak_...",
                  "model": "claude-sonnet-4-...",
                  "uncached_input_tokens": 1234,
                  "output_tokens": 567,
                  "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0,
                  "metadata": {...}
                }
              ]
            }
          ]
        }
    """
    records: list[UsageRecord] = []
    for bucket in payload.get("data", []):
        ts_raw = bucket.get("starting_at")
        ts = _parse_iso(ts_raw) if ts_raw else datetime.now(UTC)
        for row in bucket.get("results", []):
            records.append(
                UsageRecord(
                    timestamp=ts,
                    workspace_id=row.get("workspace_id"),
                    api_key_id=row.get("api_key_id"),
                    model=row.get("model", "unknown"),
                    input_tokens=int(row.get("uncached_input_tokens", row.get("input_tokens", 0))),
                    output_tokens=int(row.get("output_tokens", 0)),
                    cache_creation_input_tokens=int(row.get("cache_creation_input_tokens", 0)),
                    cache_read_input_tokens=int(row.get("cache_read_input_tokens", 0)),
                    metadata=row.get("metadata") or {},
                )
            )
    return records


def _parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting trailing Z."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------------------
# Fixture loader — for offline demo, tests, and the `--fixture` CLI flag.
# ---------------------------------------------------------------------------


def load_fixture(name: str = "sample") -> list[UsageRecord]:
    """Load a bundled fixture by name (e.g. 'sample').

    Fixtures live in `migratecore/data/{name}_usage.json` and use the same
    JSON shape as the Admin API response.
    """
    filename = f"{name}_usage.json"
    try:
        data_pkg = importlib.resources.files("migratecore.data")
        payload_text = (data_pkg / filename).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as e:
        raise FileNotFoundError(
            f"Fixture '{name}' not found. Available: 'sample'"
        ) from e
    return _parse_usage_response(json.loads(payload_text))


def load_fixture_from_path(path: str | Path) -> list[UsageRecord]:
    """Load a fixture from an arbitrary filesystem path. Used in tests."""
    payload_text = Path(path).read_text(encoding="utf-8")
    return _parse_usage_response(json.loads(payload_text))
