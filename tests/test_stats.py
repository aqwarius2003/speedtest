import math

from speedtest.models import (
    ConnectionMode,
    RequestResult,
    SessionStats,
    TimingBreakdown,
)
from speedtest.stats import SpeedSummary, compute_speed_stats, compute_comparison


def _make_result(transfer_sec: float, downloaded: int) -> RequestResult:
    """Helper to create a RequestResult with controlled values."""
    tb = TimingBreakdown(
        dns_seconds=0.01,
        tcp_seconds=0.02,
        tls_seconds=0.03,
        ttfb_seconds=0.005,
        transfer_seconds=transfer_sec,
    )
    return RequestResult(timing=tb, bytes_downloaded=downloaded, status_code=200, error=None)


def _make_session(
    results: list[RequestResult], mode: ConnectionMode = ConnectionMode.FRESH
) -> SessionStats:
    return SessionStats(results=tuple(results), mode=mode, url="https://example.com/file")


class TestSpeedSummary:

    def test_basic_stats(self):
        r1 = _make_result(1.0, 10_000_000)
        r2 = _make_result(2.0, 20_000_000)
        stats = _make_session([r1, r2])
        summary = compute_speed_stats(stats)

        assert summary.mean_speed_bps == 10_000_000.0
        assert summary.min_speed_bps == 10_000_000.0
        assert summary.max_speed_bps == 10_000_000.0
        assert summary.std_speed_bps == 0.0

    def test_varied_speeds(self):
        r1 = _make_result(2.0, 10_000_000)  # 5 MB/s
        r2 = _make_result(1.0, 15_000_000)  # 15 MB/s
        stats = _make_session([r1, r2])
        summary = compute_speed_stats(stats)

        assert summary.mean_speed_bps == 10_000_000.0
        assert summary.min_speed_bps == 5_000_000.0
        assert summary.max_speed_bps == 15_000_000.0
        assert summary.std_speed_bps == 5_000_000.0

    def test_timing_averages(self):
        tb1 = TimingBreakdown(0.010, 0.020, 0.030, 0.005, 1.0)
        tb2 = TimingBreakdown(0.030, 0.040, 0.050, 0.015, 2.0)
        r1 = RequestResult(timing=tb1, bytes_downloaded=1000, status_code=200, error=None)
        r2 = RequestResult(timing=tb2, bytes_downloaded=2000, status_code=200, error=None)
        stats = _make_session([r1, r2])
        summary = compute_speed_stats(stats)

        assert math.isclose(summary.avg_dns_seconds, 0.020, abs_tol=1e-9)
        assert math.isclose(summary.avg_tcp_seconds, 0.030, abs_tol=1e-9)
        assert math.isclose(summary.avg_tls_seconds, 0.040, abs_tol=1e-9)
        assert math.isclose(summary.avg_ttfb_seconds, 0.010, abs_tol=1e-9)
        assert math.isclose(summary.avg_transfer_seconds, 1.500, abs_tol=1e-9)

    def test_failed_requests_excluded(self):
        r_ok = _make_result(1.0, 10_000_000)
        r_fail = RequestResult(
            timing=TimingBreakdown(0, 0, 0, 0, 0),
            bytes_downloaded=0,
            status_code=0,
            error="Timeout",
        )
        stats = _make_session([r_ok, r_fail])
        summary = compute_speed_stats(stats)

        assert summary.total_requests == 2
        assert summary.successful_count == 1
        assert summary.failed_count == 1
        assert summary.mean_speed_bps == 10_000_000.0

    def test_single_request(self):
        r1 = _make_result(1.0, 10_000_000)
        stats = _make_session([r1])
        summary = compute_speed_stats(stats)
        assert summary.mean_speed_bps == 10_000_000.0
        assert summary.std_speed_bps == 0.0

    def test_all_failed_requests(self):
        r_fail1 = RequestResult(TimingBreakdown(0, 0, 0, 0, 0), 0, 0, "Timeout")
        r_fail2 = RequestResult(TimingBreakdown(0, 0, 0, 0, 0), 0, 0, "ConnRefused")
        stats = _make_session([r_fail1, r_fail2])
        summary = compute_speed_stats(stats)
        assert summary.total_requests == 2
        assert summary.successful_count == 0
        assert summary.failed_count == 2
        assert summary.mean_speed_bps == 0.0
        assert summary.total_bytes == 0

    def test_empty_session(self):
        stats = _make_session([])
        summary = compute_speed_stats(stats)
        assert summary.mean_speed_bps == 0.0
        assert summary.total_bytes == 0


class TestComparison:

    def test_overhead_percentage(self):
        r_fresh = _make_result(0.5, 5_000_000)
        tb_reuse = TimingBreakdown(0.0, 0.0, 0.0, 0.005, 0.4)
        r_reuse = RequestResult(timing=tb_reuse, bytes_downloaded=5_000_000, status_code=200, error=None)

        fresh_stats = _make_session([r_fresh], ConnectionMode.FRESH)
        reuse_stats = _make_session([r_reuse], ConnectionMode.REUSE)

        comparison = compute_comparison(fresh_stats, reuse_stats)

        assert comparison.fresh_summary is not None
        assert comparison.reuse_summary is not None
        assert comparison.overhead_pct > 0
        assert comparison.speed_gain_pct > 0
        assert math.isclose(comparison.overhead_ms_saved, 60.0, abs_tol=1e-9)

    def test_comparison_zero_speed_and_zero_timing(self):
        stats1 = _make_session([])
        stats2 = _make_session([])
        comparison = compute_comparison(stats1, stats2)
        assert comparison.overhead_pct == 0.0
        assert comparison.speed_gain_pct == 0.0
        assert comparison.overhead_ms_saved == 0.0
