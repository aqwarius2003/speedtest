"""CLI entry point using Typer."""

from __future__ import annotations

from enum import Enum

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from speedtest.display import (
    console,
    print_comparison,
    print_summary,
    print_verbose_results,
)
from speedtest.measure import run_session, validate_url
from speedtest.models import ConnectionMode, SessionStats
from speedtest.stats import compute_comparison, compute_speed_stats

app = typer.Typer(
    name="speedtest",
    help="Measure download speed with per-phase timing breakdown (DNS, TCP, TLS, TTFB, transfer).",
    add_completion=False,
)


class ModeChoice(str, Enum):
    fresh = "fresh"
    reuse = "reuse"
    both = "both"


def _run_with_progress(
    url: str,
    count: int,
    mode: ConnectionMode,
    timeout: int,
    label: str,
) -> SessionStats:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(label, total=count)
        return run_session(
            url,
            count=count,
            mode=mode,
            timeout=timeout,
            on_progress=lambda _i, _r: progress.advance(task),
        )


@app.command()
def measure(
    url: str = typer.Argument(..., help="URL to download (e.g., a large image or file)"),
    requests: int = typer.Option(10, "--requests", "-n", help="Number of sequential requests", min=1),
    mode: ModeChoice = typer.Option(ModeChoice.both, "--mode", "-m", help="Connection mode: fresh, reuse, or both"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Per-request timeout in seconds", min=1),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-request detail table"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip URL reachability pre-validation check"),
) -> None:
    """Measure download speed for a given URL.

    In FRESH mode, each request opens a new TCP/TLS connection —
    measuring real user experience including connection setup overhead.

    In REUSE mode, all requests share a single persistent connection —
    measuring raw channel throughput without setup overhead.

    In BOTH mode (default), runs both and shows a side-by-side comparison
    with TLS overhead analysis.
    """
    console.print(f"\n[bold]Target:[/bold] {url}")
    console.print(f"[bold]Requests:[/bold] {requests} per mode")
    console.print(f"[bold]Timeout:[/bold] {timeout}s\n")

    if not skip_validation:
        console.print("[dim]Validating URL...[/dim]", end=" ")
        is_valid, message = validate_url(url, timeout=min(timeout, 10))
        if not is_valid:
            console.print(f"[red]✗ {message}[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]✓ {message}[/green]\n")

    if mode == ModeChoice.both:
        console.print("[bold cyan]Running fresh connection mode...[/bold cyan]")
        fresh_stats = _run_with_progress(
            url,
            count=requests,
            mode=ConnectionMode.FRESH,
            timeout=timeout,
            label="Fresh",
        )

        if verbose:
            print_verbose_results(
                results=fresh_stats.results,
                summary=compute_speed_stats(fresh_stats),
            )

        console.print("\n[bold cyan]Running reuse connection mode...[/bold cyan]")
        reuse_stats = _run_with_progress(
            url,
            count=requests,
            mode=ConnectionMode.REUSE,
            timeout=timeout,
            label="Reuse",
        )

        if verbose:
            print_verbose_results(
                results=reuse_stats.results,
                summary=compute_speed_stats(reuse_stats),
            )

        console.print()
        comparison = compute_comparison(fresh_stats, reuse_stats)
        print_comparison(comparison)

    else:
        conn_mode = ConnectionMode.FRESH if mode == ModeChoice.fresh else ConnectionMode.REUSE
        label = "fresh" if conn_mode == ConnectionMode.FRESH else "reuse"

        console.print(f"[bold cyan]Running {label} connection mode...[/bold cyan]")
        stats = _run_with_progress(
            url,
            count=requests,
            mode=conn_mode,
            timeout=timeout,
            label=label.capitalize(),
        )

        summary = compute_speed_stats(stats)

        if verbose:
            print_verbose_results(results=stats.results, summary=summary)

        console.print()
        print_summary(summary, title=f"Results ({label.capitalize()} Mode)")
