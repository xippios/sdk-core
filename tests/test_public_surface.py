import subprocess
import sys
from pathlib import Path

import xippios.core as core

EXPECTED = {
    # client
    "AsyncClient", "CacheBackend", "ClientConfig", "MemoryCache",
    "QuotaPolicy", "QuotaSnapshot", "RateLimit", "RetryPolicy", "Timeouts",
    "EnvKeyAuth", "QueryKeyAuth", "HeaderKeyAuth", "BearerAuth", "BasicKeyAuth",
    # errors
    "AuthError", "ConfigError", "InvalidRequestError", "NotFoundError", "RateLimitError",
    "TransportError", "UpstreamError", "ValidationError", "XippiosError",
    # models, helpers
    "Result", "ResultMeta", "UpstreamModel", "parse", "parse_decimal", "Tenants",
    "collect", "paginate_offset",
    "load_csv", "load_json", "load_table",
    "sync", "__version__",
}  # fmt: skip


def test_public_surface_is_exactly_what_the_readme_promises() -> None:
    assert set(core.__all__) == EXPECTED
    for name in core.__all__:
        assert getattr(core, name) is not None


def test_the_client_package_exports_its_helpers() -> None:
    import xippios.core.client as client

    for name in ("QuotaPolicy", "QuotaSnapshot", "decode_json"):
        assert name in client.__all__
    assert client.QuotaPolicy is core.QuotaPolicy


def test_optional_adapters_are_not_imported_eagerly() -> None:
    code = (
        "import sys, xippios.core; "
        "print(sorted(m for m in sys.modules if m.startswith('xippios.core.')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout
    assert "xippios.core.client" in out
    for adapter in ("xippios.core.mcp", "xippios.core.http", "xippios.core.testing"):
        assert adapter not in out


def test_namespace_package_has_no_init_file() -> None:
    import xippios

    assert getattr(xippios, "__file__", None) is None
    package_dir = Path(core.__file__).parent
    assert not (package_dir.parent / "__init__.py").exists()
    assert (package_dir / "py.typed").exists()
