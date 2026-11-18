from io import StringIO
from rich.console import Console

from speedtest.display import (
    format_bytes,
    format_speed,
    format_time_ms,
    print_comparison,
    print_summary,
    print_verbose_results,
)
from speedtest.models import RequestResult, TimingBreakdown
from speedtest.stats import ComparisonSummary, SpeedSummary


class TestFormatSpeed:

    def test_megabytes_per_second(self):
        assert format_speed(10_000_000) == "10.00 MB/s"

    def test_kilobytes_per_second(self):
        assert format_speed(500_000) == "500.00 KB/s"

    def test_gigabytes_per_second(self):
        assert format_speed(1_500_000_000) == "1.50 GB/s"

    def test_bytes_per_second(self):
        assert format_speed(500) == "500.00 B/s"

    def test_zero(self):
        assert format_speed(0) == "0.00 B/s"


class TestFormatTimeMs:

    def test_milliseconds(self):
        assert format_time_ms(0.0452) == "45.20 ms"

    def test_seconds(self):
        assert format_time_ms(2.345) == "2345.00 ms"

    def test_zero(self):
        assert format_time_ms(0.0) == "0.00 ms"


class TestFormatBytes:

    def test_bytes(self):
        assert format_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert format_bytes(50_000) == "50.00 KB"

    def test_megabytes(self):
        assert format_bytes(10_000_000) == "10.00 MB"

    def test_gigabytes(self):
        assert format_bytes(2_500_000_000) == "2.50 GB"


class TestPrintFunctions:

    def _sample_summary(self, failed_count: int = 1) -> SpeedSummary:
        return SpeedSummary(
            mean_speed_bps=10_000_000.0,
            min_speed_bps=8_000_000.0,
            max_speed_bps=12_000_000.0,
            std_speed_bps=1_000_000.0,
            avg_dns_seconds=0.020,
            avg_tcp_seconds=0.030,
            avg_tls_seconds=0.050,
            avg_ttfb_seconds=0.015,
            avg_transfer_seconds=1.000,
            avg_overhead_seconds=0.100,
            total_bytes=10_000_000,
            total_requests=10,
            successful_count=10 - failed_count,
            failed_count=failed_count,
        )

    def test_print_summary_runs_without_error(self, monkeypatch):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)
        import speedtest.display
        monkeypatch.setattr(speedtest.display, "console", test_console)

        summary = self._sample_summary(failed_count=1)
        print_summary(summary)
        output = buf.getvalue()
        assert "Avg Speed" in output
        assert "10.00 MB/s" in output
        assert "Failed" in output

    def test_print_summary_no_failures(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)

        summary = self._sample_summary(failed_count=0)
        print_summary(summary, console=test_console)
        output = buf.getvalue()
        assert "Avg Speed" in output
        assert "Failed" not in output

    def test_print_comparison_runs_without_error(self, monkeypatch):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)
        import speedtest.display
        monkeypatch.setattr(speedtest.display, "console", test_console)

        s1 = self._sample_summary()
        s2 = self._sample_summary()
        comparison = ComparisonSummary(
            fresh_summary=s1,
            reuse_summary=s2,
            overhead_pct=15.0,
            speed_gain_pct=20.0,
            overhead_ms_saved=80.0,
        )
        print_comparison(comparison)
        output = buf.getvalue()
        assert "Connection Mode Comparison" in output
        assert "Connection Setup Overhead Analysis" in output
        assert "Connection setup overhead (DNS + TCP + TLS)" in output
        assert "15.0%" in output
        assert "80.0 ms" in output

    def test_print_comparison_no_failures(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)

        s1 = self._sample_summary(failed_count=0)
        s2 = self._sample_summary(failed_count=0)
        comparison = ComparisonSummary(
            fresh_summary=s1,
            reuse_summary=s2,
            overhead_pct=15.0,
            speed_gain_pct=20.0,
            overhead_ms_saved=80.0,
        )
        print_comparison(comparison, console=test_console)
        output = buf.getvalue()
        assert "Connection Mode Comparison" in output
        assert "Failed" not in output

    def test_print_verbose_results(self, monkeypatch):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)
        import speedtest.display
        monkeypatch.setattr(speedtest.display, "console", test_console)

        tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 1.0)
        r1 = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)
        r2 = RequestResult(timing=tb, bytes_downloaded=0, status_code=0, error="Timeout")
        summary = self._sample_summary()

        print_verbose_results(results=[r1, r2], summary=summary)
        output = buf.getvalue()
        assert "Per-Request Detail" in output
        assert "200" in output
        assert "FAIL (Timeout)" in output

    def test_print_verbose_results_direct_console_and_results_only(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)

        tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 1.0)
        r1 = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)
        r2 = RequestResult(timing=tb, bytes_downloaded=0, status_code=0, error="Timeout")

        # Passing results as first argument, with console injection
        print_verbose_results(results=[r1, r2], console=test_console)
        output = buf.getvalue()
        assert "Per-Request Detail" in output
        assert "200" in output
        assert "FAIL (Timeout)" in output

    def test_print_verbose_results_status_code_colors(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, color_system="standard", width=120)

        tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 1.0)
        r_200 = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)
        r_404 = RequestResult(timing=tb, bytes_downloaded=500, status_code=404, error=None)
        r_500 = RequestResult(timing=tb, bytes_downloaded=500, status_code=500, error=None)
        r_fail = RequestResult(timing=tb, bytes_downloaded=0, status_code=0, error="ConnReset")

        print_verbose_results(results=[r_200, r_404, r_500, r_fail], console=test_console)
        output = buf.getvalue()

        # Check that 200 (green \x1b[32m), 404 (yellow \x1b[33m), 500 (red \x1b[31m), FAIL (red) are present
        assert "\x1b[32m200\x1b[0m" in output
        assert "\x1b[33m404\x1b[0m" in output
        assert "\x1b[31m500\x1b[0m" in output
        assert "FAIL (ConnReset)" in output
