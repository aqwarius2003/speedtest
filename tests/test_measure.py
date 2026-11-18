"""Tests for the measurement module.

Unit tests test timing extraction offline.
Integration tests make real HTTP calls and are marked with @pytest.mark.integration.
"""

from typing import cast
from curl_cffi import Curl, CurlInfo
import pytest
from speedtest.measure import (
    _extract_timing_and_status,
    measure_single,
    run_session,
    validate_url,
)
from speedtest.models import ConnectionMode, RequestResult

# A stable, public URL that returns a known response.
# httpbin.org /bytes/N returns exactly N random bytes.
TEST_URL = "https://httpbin.org/bytes/1024"


class TestExtractTimingAndStatus:
    """Offline unit tests for _extract_timing_and_status."""

    def _make_curl_stub(self, info_dict: dict[CurlInfo, float | int]) -> Curl:
        class StubCurl:
            def getinfo(self, info: CurlInfo):
                return info_dict.get(info, 0.0)

        return cast(Curl, StubCurl())

    def test_https_normal_timing(self):
        curl = self._make_curl_stub({
            CurlInfo.NAMELOOKUP_TIME: 0.02,
            CurlInfo.CONNECT_TIME: 0.05,
            CurlInfo.APPCONNECT_TIME: 0.09,
            CurlInfo.STARTTRANSFER_TIME: 0.12,
            CurlInfo.TOTAL_TIME: 0.15,
            CurlInfo.RESPONSE_CODE: 200,
        })
        timing, status = _extract_timing_and_status(curl)
        assert status == 200
        assert pytest.approx(timing.dns_seconds) == 0.02
        assert pytest.approx(timing.tcp_seconds) == 0.03
        assert pytest.approx(timing.tls_seconds) == 0.04
        assert pytest.approx(timing.ttfb_seconds) == 0.03
        assert pytest.approx(timing.transfer_seconds) == 0.03

    def test_plain_http_timing(self):
        curl = self._make_curl_stub({
            CurlInfo.NAMELOOKUP_TIME: 0.02,
            CurlInfo.CONNECT_TIME: 0.05,
            CurlInfo.APPCONNECT_TIME: 0.0,
            CurlInfo.STARTTRANSFER_TIME: 0.08,
            CurlInfo.TOTAL_TIME: 0.10,
            CurlInfo.RESPONSE_CODE: 200,
        })
        timing, status = _extract_timing_and_status(curl)
        assert status == 200
        assert pytest.approx(timing.dns_seconds) == 0.02
        assert pytest.approx(timing.tcp_seconds) == 0.03
        assert timing.tls_seconds == 0.0
        assert pytest.approx(timing.ttfb_seconds) == 0.03
        assert pytest.approx(timing.transfer_seconds) == 0.02

    def test_reused_connection_timing(self):
        curl = self._make_curl_stub({
            CurlInfo.NAMELOOKUP_TIME: 0.0,
            CurlInfo.CONNECT_TIME: 0.0,
            CurlInfo.APPCONNECT_TIME: 0.0,
            CurlInfo.STARTTRANSFER_TIME: 0.04,
            CurlInfo.TOTAL_TIME: 0.06,
            CurlInfo.RESPONSE_CODE: 200,
        })
        timing, status = _extract_timing_and_status(curl)
        assert status == 200
        assert timing.dns_seconds == 0.0
        assert timing.tcp_seconds == 0.0
        assert timing.tls_seconds == 0.0
        assert pytest.approx(timing.ttfb_seconds) == 0.04
        assert pytest.approx(timing.transfer_seconds) == 0.02

    def test_zero_or_negative_guard(self):
        curl = self._make_curl_stub({
            CurlInfo.NAMELOOKUP_TIME: 0.05,
            CurlInfo.CONNECT_TIME: 0.04,
            CurlInfo.APPCONNECT_TIME: 0.03,
            CurlInfo.STARTTRANSFER_TIME: 0.02,
            CurlInfo.TOTAL_TIME: 0.01,
            CurlInfo.RESPONSE_CODE: 500,
        })
        timing, status = _extract_timing_and_status(curl)
        assert status == 500
        assert pytest.approx(timing.dns_seconds) == 0.05
        assert timing.tcp_seconds == 0.0
        assert timing.tls_seconds == 0.0
        assert timing.ttfb_seconds == 0.0
        assert timing.transfer_seconds == 0.0


@pytest.mark.integration
class TestMeasureSingle:

    def test_returns_request_result_on_success(self):
        result = measure_single(TEST_URL, fresh=True, timeout=30)
        assert result.is_success
        assert result.status_code == 200
        assert result.bytes_downloaded == 1024
        assert result.error is None

    def test_calling_with_defaults(self):
        result = measure_single(TEST_URL)
        assert result.is_success
        assert result.status_code == 200
        assert result.bytes_downloaded == 1024
        assert result.error is None

    def test_timing_breakdown_has_positive_values(self):
        result = measure_single(TEST_URL, fresh=True, timeout=30)
        t = result.timing
        assert t.dns_seconds >= 0
        assert t.tcp_seconds >= 0
        assert t.tls_seconds >= 0
        assert t.ttfb_seconds >= 0
        assert t.transfer_seconds >= 0
        assert t.total_seconds > 0

    def test_fresh_connection_has_nonzero_tls(self):
        result = measure_single(TEST_URL, fresh=True, timeout=30)
        assert result.timing.tls_seconds > 0

    def test_invalid_url_returns_error(self):
        result = measure_single(
            "https://this-domain-does-not-exist-xyz123987.com/file",
            fresh=True,
            timeout=5,
        )
        assert result.is_success is False
        assert result.error is not None


@pytest.mark.integration
class TestRunSession:

    def test_returns_session_stats(self):
        stats = run_session(TEST_URL, count=2, mode=ConnectionMode.FRESH, timeout=30)
        assert stats.total_requests == 2
        assert stats.successful_count == 2
        assert stats.mode == ConnectionMode.FRESH
        assert stats.url == TEST_URL

    def test_reuse_mode_has_zero_overhead_after_first(self):
        stats = run_session(TEST_URL, count=3, mode=ConnectionMode.REUSE, timeout=30)
        assert stats.successful_count == 3
        second = stats.successful_results[1]
        # Connection phases should be near-zero (< 1ms) for reused connections
        assert second.timing.dns_seconds < 0.001
        assert second.timing.tcp_seconds < 0.001
        assert second.timing.tls_seconds < 0.001

    def test_progress_callback_invoked(self):
        calls: list[tuple[int, RequestResult]] = []

        def on_progress(idx: int, res: RequestResult) -> None:
            calls.append((idx, res))

        stats = run_session(
            TEST_URL,
            count=2,
            mode=ConnectionMode.FRESH,
            timeout=30,
            on_progress=on_progress,
        )
        assert stats.successful_count == 2
        assert len(calls) == 2
        assert calls[0][0] == 0
        assert calls[0][1].is_success
        assert calls[1][0] == 1
        assert calls[1][1].is_success


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_validate_url_reachable(self, monkeypatch):
        class MockCurl:
            def setopt(self, opt, val):
                pass

            def perform(self):
                pass

            def getinfo(self, info):
                return 200

            def close(self):
                pass

        monkeypatch.setattr("speedtest.measure.Curl", MockCurl)
        is_valid, msg = validate_url("https://example.com")
        assert is_valid is True
        assert "URL reachable (HTTP 200)" in msg

    def test_validate_url_http_405_method_not_allowed(self, monkeypatch):
        class MockCurl:
            def setopt(self, opt, val):
                pass

            def perform(self):
                pass

            def getinfo(self, info):
                return 405

            def close(self):
                pass

        monkeypatch.setattr("speedtest.measure.Curl", MockCurl)
        is_valid, msg = validate_url("https://example.com/no-head")
        assert is_valid is True
        assert "URL reachable (HTTP 405 - HEAD method not allowed, GET permitted)" in msg

    def test_validate_url_http_error(self, monkeypatch):
        class MockCurl:
            def setopt(self, opt, val):
                pass

            def perform(self):
                pass

            def getinfo(self, info):
                return 404

            def close(self):
                pass

        monkeypatch.setattr("speedtest.measure.Curl", MockCurl)
        is_valid, msg = validate_url("https://example.com/notfound")
        assert is_valid is False
        assert "Server returned HTTP 404" in msg

    def test_validate_url_server_error(self, monkeypatch):
        class MockCurl:
            def setopt(self, opt, val):
                pass

            def perform(self):
                pass

            def getinfo(self, info):
                return 500

            def close(self):
                pass

        monkeypatch.setattr("speedtest.measure.Curl", MockCurl)
        is_valid, msg = validate_url("https://example.com/error")
        assert is_valid is False
        assert "Server returned HTTP 500" in msg

    def test_validate_url_unreachable_exception(self, monkeypatch):
        class MockCurl:
            def setopt(self, opt, val):
                pass

            def perform(self):
                raise RuntimeError("Could not resolve host")

            def getinfo(self, info):
                return 0

            def close(self):
                pass

        monkeypatch.setattr("speedtest.measure.Curl", MockCurl)
        is_valid, msg = validate_url("https://nonexistent.domain.invalid")
        assert is_valid is False
        assert "URL unreachable: Could not resolve host" in msg

