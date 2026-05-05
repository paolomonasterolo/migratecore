"""Terminal report rendering.

Uses `rich` to produce the screenshot-worthy output that drives distribution.
The headline number, the ranked migrations, the dollar impacts. Designed to
be readable on a 100-column terminal and to look good in a screenshot.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Confidence, Migration, MigrationKind, Report

_KIND_LABELS: dict[MigrationKind, str] = {
    MigrationKind.CACHE: "cache",
    MigrationKind.MODEL: "model",
    MigrationKind.BATCH: "batch",
    MigrationKind.TAG: "tag",
    MigrationKind.DEDUP: "dedup",
}

_CONFIDENCE_STYLES: dict[Confidence, str] = {
    Confidence.HIGH: "bold green",
    Confidence.MEDIUM: "yellow",
    Confidence.LOW: "dim",
}


def render_terminal(report: Report, console: Console | None = None) -> None:
    """Print the full report to a terminal."""
    console = console or Console()

    period = (
        f"{report.period_start.strftime('%Y-%m-%d')} → "
        f"{report.period_end.strftime('%Y-%m-%d')}"
    )

    headline = Text()
    headline.append(f"  ${report.addressable_savings_usd:>10,.0f}", style="bold green")
    headline.append(" / mo", style="green")
    headline.append("    addressable waste\n", style="dim")
    headline.append(f"   {report.high_confidence_count} high-confidence migration", style="bold")
    headline.append("s" if report.high_confidence_count != 1 else "")
    headline.append(" ready", style="bold")

    subtitle = (
        f"period: {period}    "
        f"est. monthly spend: ${report.total_spend_usd:,.0f}"
    )

    console.print()
    console.print(
        Panel(
            headline,
            title="MigrateCore",
            subtitle=subtitle,
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not report.migrations:
        console.print(
            "\n  [dim]No migrations recommended for this period. "
            "Either you're already optimized, or there isn't enough volume "
            "to analyze.[/dim]\n"
        )
        return

    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        pad_edge=False,
        padding=(0, 2),
    )
    table.add_column("→", no_wrap=True)
    table.add_column("type", no_wrap=True)
    table.add_column("savings/mo", justify="right", no_wrap=True)
    table.add_column("scope", no_wrap=True)
    table.add_column("confidence", no_wrap=True)

    for m in report.sorted_migrations():
        table.add_row(
            "→",
            _KIND_LABELS[m.kind],
            f"${m.estimated_monthly_savings_usd:,.0f}",
            m.affected_scope,
            Text(m.confidence.value, style=_CONFIDENCE_STYLES[m.confidence]),
        )

    console.print(table)
    console.print()

    for i, m in enumerate(report.sorted_migrations(), 1):
        _render_migration_detail(console, i, m)


def _render_migration_detail(console: Console, index: int, m: Migration) -> None:
    label = _KIND_LABELS[m.kind]
    console.print(
        f"  [bold]{index}. {m.headline}[/bold]  "
        f"[dim]({label} migration · ${m.estimated_monthly_savings_usd:,.0f}/mo · "
        f"{m.confidence.value} confidence)[/dim]"
    )
    console.print(f"     {m.detail}")
    console.print(f"     [cyan]Next step:[/cyan] {m.next_step}")
    console.print()
