import subprocess
import sys
from pathlib import Path

import pytest

import xippios.core as core

# What consumers import, and nothing else (ADR-0023, decision 5).
EXPORTS = {
    "xippios.core": {
        # client
        "AsyncClient", "ClientConfig", "MemoryCache", "QuotaPolicy", "RateLimit",
        "RetryPolicy", "Timeouts", "QueryKeyAuth", "HeaderKeyAuth", "BearerAuth",
        "BasicKeyAuth", "Downloaded", "Answer",
        # errors
        "AuthError", "ConfigError", "InvalidRequestError", "NotFoundError", "RateLimitError",
        "TransportError", "UpstreamError", "ValidationError", "XippiosError", "UnknownCode",
        "BODY_LIMIT", "error_from_response", "parse_retry_after",
        # models and helpers
        "Result", "ResultCap", "ResultMeta", "UpstreamModel", "parse", "parse_decimal",
        "collect", "paginate_offset", "load_json", "load_table", "PackagedList", "matches",
        "closest", "sync", "__version__",
    },
    "xippios.core.client": {
        "AsyncClient", "BasicKeyAuth", "BearerAuth", "CachedResponse", "ClientConfig",
        "HeaderKeyAuth", "MemoryCache", "QueryKeyAuth", "QuotaPolicy", "RateLimit",
        "RetryPolicy", "Timeouts", "cache_key", "decode_json", "decode_text", "decode_csv",
        "Downloaded", "Answer",
    },
    "xippios.core.testing": {
        "CLOCK_SLACK", "REDACTED", "Fixture", "FixtureResponse", "ReplayFixture", "Scrub",
        "assert_projection", "assert_time_between", "assert_write_tools",
        "fixture_from_response", "fixture_path", "load_fixture", "mcp_call", "mcp_call_text",
        "record", "record_sync", "recorded_query", "response_from_fixture", "sent_query",
        "sent_urls",
    },
    "xippios.core.mcp": {
        "ResultCap", "build_parser", "build_server", "cap_result", "error_to_text", "main",
        "tool_name",
    },
    "xippios.core.http": {"is_scalar", "router_from_tasks", "status_for"},
}  # fmt: skip


@pytest.mark.parametrize("module", sorted(EXPORTS))
def test_each_package_exports_exactly_what_consumers_import(module: str) -> None:
    package = __import__(module, fromlist=["__all__"])
    assert sorted(package.__all__) == sorted(EXPORTS[module])
    for name in package.__all__:
        assert getattr(package, name) is not None


def test_result_cap_is_one_class_without_the_mcp_extra() -> None:
    import xippios.core.mcp as mcp
    from xippios.core.models import ResultCap

    assert core.ResultCap is ResultCap
    assert mcp.ResultCap is ResultCap


def test_optional_adapters_are_not_imported_eagerly() -> None:
    code = (
        "import sys; from xippios.core import ResultCap; "
        "print(sorted(m for m in sys.modules if m.startswith('xippios.core.')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout
    assert "xippios.core.client" in out
    assert "xippios.core.models" in out
    for adapter in ("xippios.core.mcp", "xippios.core.http", "xippios.core.testing"):
        assert adapter not in out


def test_namespace_package_has_no_init_file() -> None:
    import xippios

    assert getattr(xippios, "__file__", None) is None
    package_dir = Path(core.__file__).parent
    assert not (package_dir.parent / "__init__.py").exists()
    assert (package_dir / "py.typed").exists()
