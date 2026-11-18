"""Statistical computations for speed test results."""

from __future__ import annotations

import math
from dataclasses import dataclass

from speedtest.models import SessionStats


@dataclass(frozen=True)
class SpeedSummary:
    """Aggregated speed and timing statistics for a measurement session."""

    mean_speed_bps: float  # bytes per second
    min_speed_bps: float
    max_speed_bps: float
    std_speed_bps: float
    avg_dns_seconds: float
    avg_tcp_seconds: float
    avg_tls_seconds: float
    avg_ttfb_seconds: float
    avg_transfer_seconds: float
    avg_overhead_seconds: float
    total_bytes: int
    total_requests: int
    successful_count: int
    failed_count: int


@dataclass(frozen=True)
class ComparisonSummary:
    """Side-by-side comparison of fresh vs reuse sessions."""

    fresh_summary: SpeedSummary
    reuse_summary: SpeedSummary
    overhead_pct: float  # How much overhead (DNS+TCP+TLS) adds in fresh mode as % of total time
    speed_gain_pct: float  # How much faster reuse is vs fresh (percentage)
    overhead_ms_saved: float  # Avg ms saved per request by reusing connection


def compute_speed_stats(session: SessionStats) -> SpeedSummary:
    """Compute aggregated statistics from a measurement session.

    Failed requests are excluded from speed/timing averages.
    Population standard deviation is used.
    """
    ok = session.successful_results
    n = len(ok)

    if n == 0:
        return SpeedSummary(
            mean_speed_bps=0.0,
            min_speed_bps=0.0,
            max_speed_bps=0.0,
            std_speed_bps=0.0,
            avg_dns_seconds=0.0,
            avg_tcp_seconds=0.0,
            avg_tls_seconds=0.0,
            avg_ttfb_seconds=0.0,
            avg_transfer_seconds=0.0,
            avg_overhead_seconds=0.0,
            total_bytes=0,
            total_requests=session.total_requests,
            successful_count=0,
            failed_count=session.failed_count,
        )

    speeds = [r.speed_bytes_per_second for r in ok]
    mean_speed = sum(speeds) / n

    if n > 1:
        variance = sum((s - mean_speed) ** 2 for s in speeds) / n
        std_speed = math.sqrt(variance)
    else:
        std_speed = 0.0

    return SpeedSummary(
        mean_speed_bps=mean_speed,
        min_speed_bps=min(speeds),
        max_speed_bps=max(speeds),
        std_speed_bps=std_speed,
        avg_dns_seconds=sum(r.timing.dns_seconds for r in ok) / n,
        avg_tcp_seconds=sum(r.timing.tcp_seconds for r in ok) / n,
        avg_tls_seconds=sum(r.timing.tls_seconds for r in ok) / n,
        avg_ttfb_seconds=sum(r.timing.ttfb_seconds for r in ok) / n,
        avg_transfer_seconds=sum(r.timing.transfer_seconds for r in ok) / n,
        avg_overhead_seconds=sum(r.timing.overhead_seconds for r in ok) / n,
        total_bytes=session.total_bytes,
        total_requests=session.total_requests,
        successful_count=n,
        failed_count=session.failed_count,
    )


def compute_comparison(
    fresh_stats: SessionStats, reuse_stats: SessionStats
) -> ComparisonSummary:
    """Compute comparative metrics between fresh and reuse sessions."""
    fresh = compute_speed_stats(fresh_stats)
    reuse = compute_speed_stats(reuse_stats)

    fresh_avg_total = (
        fresh.avg_dns_seconds
        + fresh.avg_tcp_seconds
        + fresh.avg_tls_seconds
        + fresh.avg_ttfb_seconds
        + fresh.avg_transfer_seconds
    )
    overhead_pct = (
        (fresh.avg_overhead_seconds / fresh_avg_total * 100.0) if fresh_avg_total > 0 else 0.0
    )

    speed_gain_pct = (
        ((reuse.mean_speed_bps - fresh.mean_speed_bps) / fresh.mean_speed_bps * 100.0)
        if fresh.mean_speed_bps > 0
        else 0.0
    )

    overhead_ms_saved = (fresh.avg_overhead_seconds - reuse.avg_overhead_seconds) * 1000.0

    return ComparisonSummary(
        fresh_summary=fresh,
        reuse_summary=reuse,
        overhead_pct=overhead_pct,
        speed_gain_pct=speed_gain_pct,
        overhead_ms_saved=overhead_ms_saved,
    )
