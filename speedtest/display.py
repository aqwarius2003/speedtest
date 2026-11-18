"""Rich console output for speed test results."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from speedtest.models import RequestResult
from speedtest.stats import ComparisonSummary, SpeedSummary

default_console = Console()
console = default_console



def format_speed(bps: float) -> str:
    """Format bytes/second into human-readable units (decimal)."""
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.2f} GB/s"
    elif bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} MB/s"
    elif bps >= 1_000:
        return f"{bps / 1_000:.2f} KB/s"
    else:
        return f"{bps:.2f} B/s"


def format_time_ms(seconds: float) -> str:
    """Format seconds as milliseconds string."""
    return f"{seconds * 1000:.2f} ms"


def format_bytes(total_bytes: int) -> str:
    """Format byte count into human-readable units."""
    if total_bytes >= 1_000_000_000:
        return f"{total_bytes / 1_000_000_000:.2f} GB"
    elif total_bytes >= 1_000_000:
        return f"{total_bytes / 1_000_000:.2f} MB"
    elif total_bytes >= 1_000:
        return f"{total_bytes / 1_000:.2f} KB"
    else:
        return f"{total_bytes} B"


def print_summary(
    summary: SpeedSummary,
    title: str = "Results",
    console: Console | None = None,
) -> None:
    """Print a single session's summary as a Rich table."""
    out = console if console is not None else globals().get("console", default_console)
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=24)
    table.add_column("Value", justify="right")

    table.add_row("Avg DNS", format_time_ms(summary.avg_dns_seconds))
    table.add_row("Avg TCP Connect", format_time_ms(summary.avg_tcp_seconds))
    table.add_row("Avg TLS Handshake", format_time_ms(summary.avg_tls_seconds))
    table.add_row("Avg TTFB", format_time_ms(summary.avg_ttfb_seconds))
    table.add_row("Avg Transfer", format_time_ms(summary.avg_transfer_seconds))
    table.add_section()
    table.add_row("Avg Speed", format_speed(summary.mean_speed_bps))
    table.add_row("Min Speed", format_speed(summary.min_speed_bps))
    table.add_row("Max Speed", format_speed(summary.max_speed_bps))
    table.add_row("Std Dev", format_speed(summary.std_speed_bps))
    table.add_section()
    table.add_row("Total Downloaded", format_bytes(summary.total_bytes))
    table.add_row("Requests", f"{summary.successful_count}/{summary.total_requests}")
    if summary.failed_count > 0:
        table.add_row("Failed", f"[red]{summary.failed_count}[/red]")

    out.print(table)


def print_comparison(
    comparison: ComparisonSummary,
    console: Console | None = None,
) -> None:
    """Print side-by-side comparison of fresh vs reuse modes."""
    out = console if console is not None else globals().get("console", default_console)
    f = comparison.fresh_summary
    r = comparison.reuse_summary

    table = Table(
        title="Connection Mode Comparison",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="dim", width=24)
    table.add_column("Fresh", justify="right")
    table.add_column("Reuse", justify="right")

    # Timing rows
    table.add_row("Avg DNS", format_time_ms(f.avg_dns_seconds), format_time_ms(r.avg_dns_seconds))
    table.add_row("Avg TCP Connect", format_time_ms(f.avg_tcp_seconds), format_time_ms(r.avg_tcp_seconds))
    table.add_row("Avg TLS Handshake", format_time_ms(f.avg_tls_seconds), format_time_ms(r.avg_tls_seconds))
    table.add_row("Avg TTFB", format_time_ms(f.avg_ttfb_seconds), format_time_ms(r.avg_ttfb_seconds))
    table.add_row("Avg Transfer", format_time_ms(f.avg_transfer_seconds), format_time_ms(r.avg_transfer_seconds))
    table.add_section()

    # Speed rows
    table.add_row("Avg Speed", format_speed(f.mean_speed_bps), format_speed(r.mean_speed_bps))
    table.add_row("Min Speed", format_speed(f.min_speed_bps), format_speed(r.min_speed_bps))
    table.add_row("Max Speed", format_speed(f.max_speed_bps), format_speed(r.max_speed_bps))
    table.add_row("Std Dev", format_speed(f.std_speed_bps), format_speed(r.std_speed_bps))
    table.add_section()

    # Totals
    table.add_row("Total Downloaded", format_bytes(f.total_bytes), format_bytes(r.total_bytes))
    table.add_row(
        "Requests",
        f"{f.successful_count}/{f.total_requests}",
        f"{r.successful_count}/{r.total_requests}",
    )
    if f.failed_count > 0 or r.failed_count > 0:
        table.add_row(
            "Failed",
            f"[red]{f.failed_count}[/red]" if f.failed_count > 0 else "0",
            f"[red]{r.failed_count}[/red]" if r.failed_count > 0 else "0",
        )

    out.print(table)

    # Overhead summary panel
    overhead_text = Text()
    overhead_text.append("Connection setup overhead (DNS + TCP + TLS): ", style="bold")
    overhead_text.append(f"{comparison.overhead_pct:.1f}%", style="bold yellow")
    overhead_text.append(" of total request time in fresh mode.\n")
    overhead_text.append("Connection reuse saves ", style="bold")
    overhead_text.append(f"{comparison.overhead_ms_saved:.1f} ms", style="bold green")
    overhead_text.append(" per request.")
    if comparison.speed_gain_pct > 0:
        overhead_text.append("\nReuse mode is ", style="bold")
        overhead_text.append(f"{comparison.speed_gain_pct:.1f}%", style="bold green")
        overhead_text.append(" faster than fresh connections.")

    out.print(Panel(overhead_text, title="Connection Setup Overhead Analysis", border_style="yellow"))


def print_verbose_results(
    results: Sequence[RequestResult],
    summary: SpeedSummary | None = None,
    console: Console | None = None,
) -> None:
    """Print per-request detail table (for --verbose flag)."""
    out = console if console is not None else globals().get("console", default_console)

    table = Table(title="Per-Request Detail", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", width=4)
    table.add_column("Status")
    table.add_column("DNS", justify="right")
    table.add_column("TCP", justify="right")
    table.add_column("TLS", justify="right")
    table.add_column("TTFB", justify="right")
    table.add_column("Transfer", justify="right")
    table.add_column("Speed", justify="right")
    table.add_column("Size", justify="right")

    for i, r in enumerate(results, 1):
        if r.error:
            table.add_row(
                str(i),
                f"[red]FAIL ({r.error})[/red]",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
            )
        else:
            if 200 <= r.status_code < 400:
                status_str = f"[green]{r.status_code}[/green]"
            elif 400 <= r.status_code < 500:
                status_str = f"[yellow]{r.status_code}[/yellow]"
            else:
                status_str = f"[red]{r.status_code}[/red]"

            table.add_row(
                str(i),
                status_str,
                format_time_ms(r.timing.dns_seconds),
                format_time_ms(r.timing.tcp_seconds),
                format_time_ms(r.timing.tls_seconds),
                format_time_ms(r.timing.ttfb_seconds),
                format_time_ms(r.timing.transfer_seconds),
                format_speed(r.speed_bytes_per_second),
                format_bytes(r.bytes_downloaded),
            )

    out.print(table)
