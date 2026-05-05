"""CLI entrypoint for MigrateCore.

Commands:
    mc analyze               Run the analyzer on the last 30 days of usage
    mc analyze --fixture sample    Demo against the bundled sample data
    mc version               Print the installed version
    mc plan <type>           Generate a detailed migration plan (v0.2)
"""

from __future__ import annotations

import json
import os
import sys

import typer
from rich.console import Console

from . import __version__
from .analyzer import analyze
from .client import AdminAPIError, AdminClient, load_fixture
from .models import Report
from .report import render_terminal

app = typer.Typer(
    name="migratecore",
    help="Find waste in your Anthropic API spend.",
    no_args_is_help=True,
    add_completion=False,
)

_console = Console()
_err = Console(stderr=True)


@app.command(name="version")
def version_cmd() -> None:
    """Print the installed version."""
    _console.print(f"migratecore {__version__}")


@app.command(name="analyze")
def analyze_cmd(
    days: int = typer.Option(30, "--days", "-d", help="Days of history to analyze."),
    fixture: str | None = typer.Option(
        None,
        "--fixture",
        help="Run against a bundled fixture. Try '--fixture sample' for a demo.",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: 'terminal' (default) or 'json'.",
    ),
) -> None:
    """Run the migration analyzer."""
    if fixture:
        records = load_fixture(fixture)
    else:
        admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY")
        if not admin_key:
            _err.print(
                "[red]error:[/red] ANTHROPIC_ADMIN_KEY is not set.\n"
                "Set it to an Admin key (sk-ant-admin-...) or use "
                "[bold]--fixture sample[/bold] for a demo."
            )
            raise typer.Exit(code=2)
        try:
            with AdminClient(admin_key) as client:
                records = client.fetch_usage(days=days)
        except (AdminAPIError, ValueError) as e:
            _err.print(f"[red]error:[/red] {e}")
            raise typer.Exit(code=1) from e

    report = analyze(records)

    if output_format == "json":
        _print_json(report)
    elif output_format == "terminal":
        render_terminal(report, console=_console)
    else:
        _err.print(f"[red]error:[/red] unknown format '{output_format}'")
        raise typer.Exit(code=2)


@app.command(name="plan")
def plan_cmd(
    migration_type: str = typer.Argument(
        ...,
        help="Migration type to plan: cache | model | batch | tag | dedup",
    ),
) -> None:
    """Generate a detailed migration plan for one type. (Coming in v0.2.)"""
    _console.print(
        f"[yellow]The 'plan' command will produce a detailed code-level migration "
        f"plan for [bold]{migration_type}[/bold] in v0.2. For now, run "
        f"[bold]mc analyze[/bold] to see the recommendations and their next steps.[/yellow]"
    )


def _print_json(report: Report) -> None:
    payload = {
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "total_spend_usd": report.total_spend_usd,
        "addressable_savings_usd": report.addressable_savings_usd,
        "high_confidence_count": report.high_confidence_count,
        "migrations": [
            {
                "kind": m.kind.value,
                "headline": m.headline,
                "detail": m.detail,
                "estimated_monthly_savings_usd": m.estimated_monthly_savings_usd,
                "confidence": m.confidence.value,
                "affected_scope": m.affected_scope,
                "next_step": m.next_step,
            }
            for m in report.sorted_migrations()
        ],
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    app()
