import subprocess
import sys
from pathlib import Path

import pytest

import xippios.core as core

# What consumers import, and nothing else (ADR-0059, decision 3).
EXPORTS = {
    "xippios.core": {
        # client
        "AsyncClient", "ClientConfig", "MemoryCache", "QuotaPolicy", "RateLimit",
        "RetryPolicy", "Downloaded", "Answer", "RenewingBearerAuth", "BearerToken",
        # the one key class, where the key travels (ADR-0059, decision 7)
        "KeyAuth",
        # errors
        "AuthError", "ConfigError", "InvalidRequestError", "NotFoundError", "RateLimitError",
        "TransportError", "UpstreamError", "ValidationError", "XippiosError", "UnknownCode",
        "BODY_LIMIT", "error_from_response", "parse_retry_after",
        # the request description error messages use (https://github.com/xippios/sdk-core/issues/62)
        "request_description",
        # models and helpers
        "Result", "ResultCap", "ResultMeta", "UpstreamModel", "parse", "parse_decimal",
        "load_json", "PackagedList", "matches",
        "closest", "sync", "__version__",
        # the filter of a vintage taken back, each source handing its own reader (ADR-0052)
        "newer_than",
        # the mark of a redacted value, by the one path of a source's package (ADR-0059)
        "REDACTED",
        # the nearest-integer strategy of two sources (https://github.com/xippios/sdk-core/issues/107)
        "nearest",
        # tenants, back from the two sources' copies (ADR-0042, decision 1)
        "Tenants", "list_task",
        # and the lock that binds a server to one of them (the same amendment, (d))
        "TenantLock", "bind_tasks", "tenant_instructions",
        # a variable of the package contract (ADR-0026, amendment 2026-11-18, point c)
        "EnvVar",
        # a packaged list's codes, declared once, and their check (ADR-0045)
        "PackagedCodes",
        # the ceiling of a period series and its requests in order (ADR-0054)
        "Ceiling", "fetch_periods",
        # the count before a query over upstream's limit: the error and the runner (ADR-0053)
        "QueryTooLarge", "fetch_counted",
        # the one walk of pages, which refuses at its bound (ADR-0034, amendment 2026-11-24)
        "fetch_pages",
        # the name of each country code in an answer's meta (ADR-0056)
        "names_codes",
        # a source's tool functions and their names, without the mcp extra (ADR-0063)
        "tool_functions", "tool_name",
    },
    "xippios.core.client": {
        "AsyncClient", "CachedResponse", "ClientConfig", "KeyAuth", "MemoryCache",
        "QuotaPolicy", "RateLimit", "RetryPolicy", "cache_key", "decode_csv", "Downloaded",
        "Answer", "RenewingBearerAuth", "BearerToken",
    },
    "xippios.core.testing": {
        "CLOCK_SLACK", "REDACTED", "Fixture", "FixtureResponse", "ReplayFixture", "Scrub",
        "assert_projection", "assert_time_between", "fixture_from_response", "fixture_path",
        "fixture_text", "load_fixture", "mcp_call", "mcp_call_text", "record", "record_sync",
        "recorded_query", "response_from_fixture", "sent_query", "sent_urls", "write_fixture",
        # the bodies a route received (https://github.com/xippios/sdk-core/issues/183)
        "sent_bodies",
        # the write server's check and the demo-only strip (ADR-0042, decision 1)
        "assert_write_tools", "keep_reserved_tenants",
        # the recorder's one send, without the write (ADR-0048, decision 3)
        "send_once", "send_once_sync",
        # the recording of every exchange of a task (ADR-0057)
        "record_task", "record_task_sync",
        # the type of a recorder's rewrite step (ADR-0048, decision 1)
        "Rewrite",
    },
    "xippios.core.mcp": {
        "build_parser", "build_server", "cap_result", "error_to_text", "main",
        "tool_name",
        # what the host imports (https://github.com/xippios/sdk-core/issues/170, ADR-0063)
        "LOOPBACK_HOSTS", "quiet_request_logging", "register_tasks", "tool_functions",
        # the tool set of the package contract (ADR-0026, amendment 2026-11-18, point c)
        "ToolSet",
    },
    "xippios.core.http": {"is_scalar", "router_from_tasks", "status_for"},
    # the snapshot script's frame and what its hooks take (ADR-0046), the reference script's
    # declarations (ADR-0051), and the one run of both
    "xippios.core.refresh": {
        "Credentials", "NotFetched", "Page", "Response", "Row", "Section", "Snapshot",
        "Statement", "changed", "decode", "dump_json", "load_json", "run",
        "Enumeration", "Listed",
    },
}  # fmt: skip


@pytest.mark.parametrize("module", sorted(EXPORTS))
def test_each_package_exports_exactly_what_consumers_import(module: str) -> None:
    package = __import__(module, fromlist=["__all__"])
    assert sorted(package.__all__) == sorted(EXPORTS[module])
    for name in package.__all__:
        assert getattr(package, name) is not None


def test_redacted_is_one_value_by_both_paths() -> None:
    # A source's package imports it from the root, its tests from the testing extra.
    import xippios.core.testing as testing

    assert core.REDACTED is testing.REDACTED
    assert core.REDACTED == "REDACTED"


def test_result_cap_is_one_class_without_the_mcp_extra() -> None:
    # https://github.com/xippios/sdk-core/issues/475: the root's entry alone, since a
    # source's tasks.py declares its caps without the mcp extra.
    import xippios.core.mcp as mcp
    from xippios.core.models import ResultCap

    assert core.ResultCap is ResultCap
    assert "ResultCap" not in vars(mcp)


def test_the_tool_functions_and_their_names_are_one_by_both_paths() -> None:
    # ADR-0063, decision 2: the root holds them without the mcp extra, and the MCP
    # package keeps them for the sources that import them there.
    import xippios.core.mcp as mcp
    from xippios.core._tasks import tool_functions, tool_name

    assert core.tool_functions is mcp.tool_functions is tool_functions
    assert core.tool_name is mcp.tool_name is tool_name


def test_a_tool_name_needs_no_mcp_extra() -> None:
    # https://github.com/xippios/sdk-core/issues/336: a source's refusal names a tool from the
    # base package, which imports nothing of the mcp SDK or of core's MCP adapter.
    code = (
        "import sys; from xippios.core import tool_functions, tool_name; "
        "print(tool_name('example', 'get_series')); "
        "print([m for m in sys.modules if m.split('.')[0] == 'mcp' or m == 'xippios.core.mcp'])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout
    assert out.splitlines() == ["example_get_series", "[]"]


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
    assert "xippios.core.refresh" not in out, "a source's scripts import the frame themselves"


def test_namespace_package_has_no_init_file() -> None:
    import xippios

    assert getattr(xippios, "__file__", None) is None
    package_dir = Path(core.__file__).parent
    assert not (package_dir.parent / "__init__.py").exists()
    assert (package_dir / "py.typed").exists()
