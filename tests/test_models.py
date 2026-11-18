from speedtest.models import TimingBreakdown, RequestResult, SessionStats, ConnectionMode


def test_timing_breakdown_is_frozen():
    tb = TimingBreakdown(
        dns_seconds=0.045,
        tcp_seconds=0.023,
        tls_seconds=0.067,
        ttfb_seconds=0.142,
        transfer_seconds=0.500,
    )
    assert tb.dns_seconds == 0.045
    assert tb.transfer_seconds == 0.500
    try:
        tb.dns_seconds = 0.1  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_timing_breakdown_total():
    tb = TimingBreakdown(
        dns_seconds=0.010,
        tcp_seconds=0.020,
        tls_seconds=0.030,
        ttfb_seconds=0.040,
        transfer_seconds=0.500,
    )
    assert tb.total_seconds == 0.010 + 0.020 + 0.030 + 0.040 + 0.500


def test_timing_breakdown_overhead_seconds():
    tb = TimingBreakdown(
        dns_seconds=0.010,
        tcp_seconds=0.020,
        tls_seconds=0.030,
        ttfb_seconds=0.005,
        transfer_seconds=0.500,
    )
    assert tb.overhead_seconds == 0.010 + 0.020 + 0.030


def test_request_result_speed_bytes_per_second():
    tb = TimingBreakdown(
        dns_seconds=0.0,
        tcp_seconds=0.0,
        tls_seconds=0.0,
        ttfb_seconds=0.0,
        transfer_seconds=2.0,
    )
    rr = RequestResult(
        timing=tb,
        bytes_downloaded=10_000_000,
        status_code=200,
        error=None,
    )
    assert rr.speed_bytes_per_second == 10_000_000 / 2.0


def test_request_result_speed_zero_transfer():
    tb = TimingBreakdown(
        dns_seconds=0.0,
        tcp_seconds=0.0,
        tls_seconds=0.0,
        ttfb_seconds=0.0,
        transfer_seconds=0.0,
    )
    rr = RequestResult(
        timing=tb,
        bytes_downloaded=0,
        status_code=200,
        error=None,
    )
    assert rr.speed_bytes_per_second == 0.0


def test_request_result_is_success():
    tb = TimingBreakdown(0.0, 0.0, 0.0, 0.0, 0.5)
    ok_200 = RequestResult(timing=tb, bytes_downloaded=100, status_code=200, error=None)
    ok_301 = RequestResult(timing=tb, bytes_downloaded=100, status_code=301, error=None)
    fail_err = RequestResult(timing=tb, bytes_downloaded=0, status_code=200, error="Timeout")
    fail_404 = RequestResult(timing=tb, bytes_downloaded=100, status_code=404, error=None)
    fail_500 = RequestResult(timing=tb, bytes_downloaded=100, status_code=500, error=None)
    assert ok_200.is_success is True
    assert ok_301.is_success is True
    assert fail_err.is_success is False
    assert fail_404.is_success is False
    assert fail_500.is_success is False


def test_session_stats_computed_properties():
    tb1 = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 1.0)
    tb2 = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 2.0)
    r1 = RequestResult(timing=tb1, bytes_downloaded=10_000_000, status_code=200, error=None)
    r2 = RequestResult(timing=tb2, bytes_downloaded=20_000_000, status_code=200, error=None)
    r_fail = RequestResult(timing=tb1, bytes_downloaded=0, status_code=200, error="DNS failed")

    # Pass a list — should be auto-converted to tuple
    stats = SessionStats(
        results=[r1, r2, r_fail],  # type: ignore[arg-type]
        mode=ConnectionMode.FRESH,
        url="https://example.com/file.bin",
    )
    assert isinstance(stats.results, tuple)
    assert stats.successful_results == [r1, r2]
    assert stats.total_requests == 3
    assert stats.successful_count == 2
    assert stats.failed_count == 1
    assert stats.total_bytes == 30_000_000


def test_session_stats_results_immutable():
    tb = TimingBreakdown(0.0, 0.0, 0.0, 0.0, 0.5)
    r = RequestResult(timing=tb, bytes_downloaded=100, status_code=200, error=None)
    stats = SessionStats(results=(r,), mode=ConnectionMode.FRESH, url="https://example.com")
    # results is a tuple — no append/pop available
    assert isinstance(stats.results, tuple)
    # Cannot reassign results on frozen dataclass
    try:
        stats.results = ()  # type: ignore[misc]
        assert False, "Should have raised AttributeError"
    except AttributeError:
        pass


def test_connection_mode_enum():
    assert ConnectionMode.FRESH.value == "fresh"
    assert ConnectionMode.REUSE.value == "reuse"
