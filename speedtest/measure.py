"""Core measurement logic using curl_cffi's low-level Curl API.

Uses libcurl's native timing fields for per-phase breakdown:
  NAMELOOKUP_TIME  → DNS resolution
  CONNECT_TIME     → TCP connect (cumulative, includes DNS)
  APPCONNECT_TIME  → TLS handshake (cumulative, includes DNS+TCP)
  STARTTRANSFER_TIME → Time to first byte (cumulative)
  TOTAL_TIME       → Total request time (cumulative)

Individual phase durations are computed by subtraction.
"""

from __future__ import annotations

from collections.abc import Callable
from curl_cffi import Curl, CurlInfo, CurlOpt

from speedtest.models import ConnectionMode, RequestResult, SessionStats, TimingBreakdown


def _get_float(curl: Curl, info: CurlInfo) -> float:
    val = curl.getinfo(info)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0


def _get_int(curl: Curl, info: CurlInfo) -> int:
    val = curl.getinfo(info)
    if isinstance(val, (int, float)):
        return int(val)
    return 0


def _extract_timing_and_status(curl: Curl) -> tuple[TimingBreakdown, int]:
    namelookup = _get_float(curl, CurlInfo.NAMELOOKUP_TIME)
    connect = _get_float(curl, CurlInfo.CONNECT_TIME)
    appconnect = _get_float(curl, CurlInfo.APPCONNECT_TIME)
    starttransfer = _get_float(curl, CurlInfo.STARTTRANSFER_TIME)
    total = _get_float(curl, CurlInfo.TOTAL_TIME)
    status_code = _get_int(curl, CurlInfo.RESPONSE_CODE)

    connect_done = appconnect if appconnect > 0.0 else connect
    tls = max(0.0, appconnect - connect) if appconnect > 0.0 else 0.0
    ttfb = max(0.0, starttransfer - connect_done)

    timing = TimingBreakdown(
        dns_seconds=max(0.0, namelookup),
        tcp_seconds=max(0.0, connect - namelookup),
        tls_seconds=tls,
        ttfb_seconds=ttfb,
        transfer_seconds=max(0.0, total - starttransfer),
    )
    return timing, status_code


def _perform_request(
    curl: Curl,
    url: str,
    *,
    timeout: int = 30,
    fresh: bool = False,
) -> RequestResult:
    total_bytes = 0

    def _write_callback(chunk: bytes) -> int:
        nonlocal total_bytes
        total_bytes += len(chunk)
        return len(chunk)

    try:
        curl.setopt(CurlOpt.URL, url.encode("utf-8"))
        curl.setopt(
            CurlOpt.USERAGENT,
            b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        curl.setopt(CurlOpt.WRITEFUNCTION, _write_callback)
        curl.setopt(CurlOpt.TIMEOUT, timeout)
        curl.setopt(CurlOpt.FOLLOWLOCATION, 1)
        curl.setopt(CurlOpt.MAXREDIRS, 5)

        if fresh:
            curl.setopt(CurlOpt.FRESH_CONNECT, 1)
            curl.setopt(CurlOpt.FORBID_REUSE, 1)
        else:
            curl.setopt(CurlOpt.FRESH_CONNECT, 0)
            curl.setopt(CurlOpt.FORBID_REUSE, 0)

        curl.perform()

        timing, status_code = _extract_timing_and_status(curl)

        return RequestResult(
            timing=timing,
            bytes_downloaded=total_bytes,
            status_code=status_code,
            error=None,
        )

    except Exception as exc:
        zero_timing = TimingBreakdown(0.0, 0.0, 0.0, 0.0, 0.0)
        return RequestResult(
            timing=zero_timing,
            bytes_downloaded=0,
            status_code=0,
            error=str(exc),
        )


def measure_single(url: str, fresh: bool = True, timeout: int = 30) -> RequestResult:
    """Perform a single HTTP GET and return timing + size metrics.

    Args:
        url: Target URL to download.
        fresh: If True, force a new TCP/TLS connection (no reuse).
        timeout: Request timeout in seconds.

    Returns:
        RequestResult with timing breakdown, bytes downloaded, and status code.
    """
    curl = Curl()
    try:
        return _perform_request(curl, url, timeout=timeout, fresh=fresh)
    finally:
        curl.close()


def run_session(
    url: str,
    *,
    count: int,
    mode: ConnectionMode,
    timeout: int = 30,
    on_progress: Callable[[int, RequestResult], None] | None = None,
) -> SessionStats:
    """Run a series of sequential download requests.

    In FRESH mode: each request creates and destroys its own Curl handle,
    forcing a new TCP/TLS connection every time.

    In REUSE mode: a single Curl handle is reused across all requests.
    libcurl automatically reuses the TCP/TLS connection on the same handle,
    so only the first request pays DNS/TCP/TLS overhead.
    """
    results: list[RequestResult] = []

    if mode == ConnectionMode.FRESH:
        for i in range(count):
            result = measure_single(url, fresh=True, timeout=timeout)
            results.append(result)
            if on_progress is not None:
                on_progress(i, result)
    else:
        curl = Curl()
        try:
            for i in range(count):
                result = _perform_request(curl, url, timeout=timeout, fresh=False)
                results.append(result)
                if on_progress is not None:
                    on_progress(i, result)
        finally:
            curl.close()

    return SessionStats(results=tuple(results), mode=mode, url=url)


def validate_url(url: str, timeout: int = 5) -> tuple[bool, str]:
    """Validate URL is reachable with a HEAD request before full benchmark.

    Returns:
        Tuple of (is_valid, message).
    """
    curl = Curl()
    try:
        curl.setopt(CurlOpt.URL, url.encode("utf-8"))
        curl.setopt(
            CurlOpt.USERAGENT,
            b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        curl.setopt(CurlOpt.NOBODY, 1)  # HEAD request
        curl.setopt(CurlOpt.TIMEOUT, timeout)
        curl.setopt(CurlOpt.FOLLOWLOCATION, 1)
        curl.setopt(CurlOpt.MAXREDIRS, 5)
        curl.perform()

        status = _get_int(curl, CurlInfo.RESPONSE_CODE)
        if status == 405:
            return True, "URL reachable (HTTP 405 - HEAD method not allowed, GET permitted)"
        if status < 200 or status >= 400:
            return False, f"Server returned HTTP {status}"
        return True, f"URL reachable (HTTP {status})"
    except Exception as exc:
        return False, f"URL unreachable: {exc}"
    finally:
        curl.close()

