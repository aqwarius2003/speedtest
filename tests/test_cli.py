from typer.testing import CliRunner

import speedtest.cli
from speedtest.cli import app
from speedtest.models import (
    ConnectionMode,
    RequestResult,
    SessionStats,
    TimingBreakdown,
)

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Measure download speed" in result.stdout
    assert "--requests" in result.stdout
    assert "--mode" in result.stdout
    assert "--verbose" in result.stdout
    assert "--skip-validation" in result.stdout


def test_missing_required_url():
    result = runner.invoke(app, [])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "Usage:" in result.output


def test_invalid_requests_option():
    result = runner.invoke(app, ["https://example.com", "-n", "0"])
    assert result.exit_code != 0


def test_invalid_mode_option():
    result = runner.invoke(app, ["https://example.com", "--mode", "invalid"])
    assert result.exit_code != 0


def test_measure_mocked(monkeypatch):
    tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 0.5)
    rr = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)

    def mock_validate_url(url, timeout=5):
        return True, "URL reachable (HTTP 200)"

    def mock_run_session(url, count, mode, timeout=30, on_progress=None):
        if on_progress:
            for i in range(count):
                on_progress(i, rr)
        return SessionStats(results=(rr,) * count, mode=mode, url=url)

    monkeypatch.setattr(speedtest.cli, "validate_url", mock_validate_url)
    monkeypatch.setattr(speedtest.cli, "run_session", mock_run_session)

    # Test running both modes
    result = runner.invoke(app, ["https://example.com/test.bin", "-n", "2", "--mode", "both", "-v"])
    assert result.exit_code == 0
    assert "Connection Mode Comparison" in result.stdout
    assert "Per-Request Detail" in result.stdout

    # Test running fresh mode only
    result_fresh = runner.invoke(app, ["https://example.com/test.bin", "-n", "2", "--mode", "fresh"])
    assert result_fresh.exit_code == 0
    assert "Results (Fresh Mode)" in result_fresh.stdout

    # Test running reuse mode only
    result_reuse = runner.invoke(app, ["https://example.com/test.bin", "-n", "2", "--mode", "reuse"])
    assert result_reuse.exit_code == 0
    assert "Results (Reuse Mode)" in result_reuse.stdout


def test_measure_validation_failure(monkeypatch):
    monkeypatch.setattr(
        speedtest.cli,
        "validate_url",
        lambda url, timeout=5: (False, "Server returned HTTP 404"),
    )
    result = runner.invoke(app, ["https://example.com/notfound"])
    assert result.exit_code == 1
    assert "✗ Server returned HTTP 404" in result.output


def test_measure_validation_success_proceeds(monkeypatch):
    tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 0.5)
    rr = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)

    called = {"run_session": False}

    def mock_validate_url(url, timeout=5):
        return True, "URL reachable (HTTP 200)"

    def mock_run_session(url, count, mode, timeout=30, on_progress=None):
        called["run_session"] = True
        return SessionStats(results=(rr,) * count, mode=mode, url=url)

    monkeypatch.setattr(speedtest.cli, "validate_url", mock_validate_url)
    monkeypatch.setattr(speedtest.cli, "run_session", mock_run_session)

    result = runner.invoke(app, ["https://example.com/test.bin", "-n", "1", "--mode", "fresh"])
    assert result.exit_code == 0
    assert "✓ URL reachable (HTTP 200)" in result.output
    assert called["run_session"] is True


def test_measure_skip_validation(monkeypatch):
    tb = TimingBreakdown(0.01, 0.02, 0.03, 0.01, 0.5)
    rr = RequestResult(timing=tb, bytes_downloaded=1_000_000, status_code=200, error=None)

    called = {"run_session": False, "validate_url": False}

    def mock_validate_url(url, timeout=5):
        called["validate_url"] = True
        return False, "Should not be called"

    def mock_run_session(url, count, mode, timeout=30, on_progress=None):
        called["run_session"] = True
        return SessionStats(results=(rr,) * count, mode=mode, url=url)

    monkeypatch.setattr(speedtest.cli, "validate_url", mock_validate_url)
    monkeypatch.setattr(speedtest.cli, "run_session", mock_run_session)

    result = runner.invoke(
        app,
        ["https://example.com/test.bin", "-n", "1", "--mode", "fresh", "--skip-validation"],
    )
    assert result.exit_code == 0
    assert called["validate_url"] is False
    assert called["run_session"] is True
    assert "Validating URL..." not in result.output


