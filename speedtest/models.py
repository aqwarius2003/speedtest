"""Immutable data models for speed test results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConnectionMode(Enum):
    """Connection reuse strategy for measurement."""

    FRESH = "fresh"
    REUSE = "reuse"


@dataclass(frozen=True)
class TimingBreakdown:
    """Per-phase timing for a single HTTP request.

    All values are in seconds (float). Phases are computed from
    libcurl's cumulative timing fields:
      dns  = NAMELOOKUP_TIME
      tcp  = CONNECT_TIME - NAMELOOKUP_TIME
      tls  = APPCONNECT_TIME - CONNECT_TIME
      ttfb = STARTTRANSFER_TIME - APPCONNECT_TIME
      transfer = TOTAL_TIME - STARTTRANSFER_TIME
    """

    dns_seconds: float
    tcp_seconds: float
    tls_seconds: float
    ttfb_seconds: float
    transfer_seconds: float

    @property
    def total_seconds(self) -> float:
        return (
            self.dns_seconds
            + self.tcp_seconds
            + self.tls_seconds
            + self.ttfb_seconds
            + self.transfer_seconds
        )

    @property
    def overhead_seconds(self) -> float:
        """Connection setup overhead: DNS + TCP + TLS."""
        return self.dns_seconds + self.tcp_seconds + self.tls_seconds


@dataclass(frozen=True)
class RequestResult:
    """Result of a single download request."""

    timing: TimingBreakdown
    bytes_downloaded: int
    status_code: int
    error: str | None

    @property
    def is_success(self) -> bool:
        return self.error is None and 200 <= self.status_code < 400

    @property
    def speed_bytes_per_second(self) -> float:
        if self.timing.transfer_seconds <= 0:
            return 0.0
        return self.bytes_downloaded / self.timing.transfer_seconds


@dataclass(frozen=True)
class SessionStats:
    """Aggregated statistics for a measurement session."""

    results: tuple[RequestResult, ...]
    mode: ConnectionMode
    url: str

    def __post_init__(self) -> None:
        # Ensure results is always a tuple, even if a list is passed
        if isinstance(self.results, list):
            object.__setattr__(self, "results", tuple(self.results))

    @property
    def successful_results(self) -> list[RequestResult]:
        return [r for r in self.results if r.is_success]

    @property
    def total_requests(self) -> int:
        return len(self.results)

    @property
    def successful_count(self) -> int:
        return len(self.successful_results)

    @property
    def failed_count(self) -> int:
        return self.total_requests - self.successful_count

    @property
    def total_bytes(self) -> int:
        return sum(r.bytes_downloaded for r in self.successful_results)
