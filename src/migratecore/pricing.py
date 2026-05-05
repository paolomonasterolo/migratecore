"""Anthropic pricing table.

Prices are in USD per million tokens. Update from
https://www.anthropic.com/pricing when Anthropic publishes changes.

Cache modifiers per Anthropic's prompt caching pricing:
  - Cache creation (writing to cache):  1.25x base input rate
  - Cache read (hitting cached prefix): 0.10x base input rate
"""

from __future__ import annotations

# Per-million-token rates in USD, indexed by model substring match.
# Listed most-specific to least-specific so the matcher prefers exact families.
_BASE_RATES: list[tuple[str, float, float]] = [
    # (model_substring, input_per_M, output_per_M)
    ("claude-opus-4", 15.00, 75.00),
    ("claude-sonnet-4", 3.00, 15.00),
    ("claude-haiku-4", 1.00, 5.00),
    ("claude-3-7-sonnet", 3.00, 15.00),
    ("claude-3-5-sonnet", 3.00, 15.00),
    ("claude-3-5-haiku", 1.00, 5.00),
    ("claude-3-opus", 15.00, 75.00),
    ("claude-3-sonnet", 3.00, 15.00),
    ("claude-3-haiku", 0.25, 1.25),
]

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def rates_for(model: str) -> tuple[float, float]:
    """Return (input_per_M, output_per_M) for a model identifier.

    Falls back to Sonnet pricing if the model is unknown — conservative
    middle-of-the-road default.
    """
    for prefix, in_rate, out_rate in _BASE_RATES:
        if prefix in model:
            return in_rate, out_rate
    return 3.00, 15.00


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    """Compute the realized cost of a usage bucket in USD."""
    in_rate, out_rate = rates_for(model)
    base_input = input_tokens * in_rate / 1_000_000
    base_output = output_tokens * out_rate / 1_000_000
    cache_write = cache_creation_input_tokens * in_rate * CACHE_WRITE_MULTIPLIER / 1_000_000
    cache_read = cache_read_input_tokens * in_rate * CACHE_READ_MULTIPLIER / 1_000_000
    return base_input + base_output + cache_write + cache_read


# Cheapest model — Haiku — used for "what if we downgraded?" projections.
HAIKU_INPUT_RATE = 1.00
HAIKU_OUTPUT_RATE = 5.00


def haiku_equivalent_cost(input_tokens: int, output_tokens: int) -> float:
    """Cost if these tokens had run on Haiku 4 instead."""
    return (input_tokens * HAIKU_INPUT_RATE + output_tokens * HAIKU_OUTPUT_RATE) / 1_000_000
