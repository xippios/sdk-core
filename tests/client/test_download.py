import gzip
import inspect
import io
import os
import stat
import tempfile
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

import anyio
import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    Downloaded,
    KeyAuth,
    MemoryCache,
    RetryPolicy,
    check_dest,
    decode_csv,
)
from xippios.core.errors import (
    AuthError,
    InvalidRequestError,
    NotFoundError,
    TransportError,
    UpstreamError,
    ValidationError,
)
from xippios.core.testing import REDACTED, sent_urls

BASE = "https://api.example.test"
CSV = '\ufeffcommodity,Value (1000 MT)\nCORN,"15,341"\n'


async def no_sleep(_: float) -> None:
    return None


def make_client(
    *,
    auth: httpx.Auth | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    **changes: object,
) -> AsyncClient:
    arguments: dict[str, object] = {
        "source": "example",
        "version": "1",
        "base_url": BASE,
        "retry": RetryPolicy(max_attempts=3, jitter=False),
    }
    arguments.update(changes)
    config = ClientConfig(**arguments)  # type: ignore[arg-type]
    return AsyncClient(config, auth=auth, transport=transport, sleep=no_sleep)


class Chunks(httpx.AsyncByteStream):
    """A body sent in 1 KiB chunks, counting the chunks read; ``fail_after`` breaks it."""

    def __init__(self, count: int, fail_after: int | None = None) -> None:
        self.count = count
        self.fail_after = fail_after
        self.read = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self.count):
            if self.read == self.fail_after:
                raise httpx.ReadError("connection reset")
            self.read += 1
            yield b"x" * 1024


def leftovers(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir() if path.name.endswith(".part"))


@pytest.mark.anyio
async def test_download_streams_the_file_and_keeps_what_upstream_said(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": "attachment; filename*=UTF-8''series_all_%C3%A9.csv",
        "ETag": '"abc"',
        "Last-Modified": "Tue, 27 Oct 2026 08:00:00 GMT",
    }
    route = respx_mock.get(f"{BASE}/files/rows.csv").respond(200, text=CSV, headers=headers)
    cache = MemoryCache()
    client = make_client(
        cache=cache, auth=KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example")
    )
    before = datetime.now(UTC)
    got = await client.download("/files/rows.csv", tmp_path / "rows.csv")
    assert got == Downloaded(
        path=tmp_path / "rows.csv",
        bytes=len(CSV.encode()),
        content_type="text/csv; charset=utf-8",
        filename="series_all_é.csv",
        etag='"abc"',
        last_modified="Tue, 27 Oct 2026 08:00:00 GMT",
        retrieved_at=got.retrieved_at,
    )
    assert before <= got.retrieved_at <= datetime.now(UTC)
    assert (tmp_path / "rows.csv").read_text(encoding="utf-8") == CSV
    await client.download(f"{BASE}/files/rows.csv", tmp_path / "again.csv", auth=None)
    assert sent_urls(route) == [f"{BASE}/files/rows.csv?key={REDACTED}", f"{BASE}/files/rows.csv"]
    assert len(cache) == 0  # never the cache
    assert leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_a_download_takes_the_query_and_the_headers_its_siblings_take(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # download(url, dest, *, params=, headers=, auth=), as get and get_answer take them.
    route = respx_mock.get(f"{BASE}/v1/export").respond(200, text=CSV)
    seen: list[str] = []
    client = make_client(before_request=lambda request: seen.append(str(request.url)))
    await client.download(
        "/v1/export",
        tmp_path / "export.csv",
        params={"year": 2025, "format": "csv"},
        headers={"Accept": "text/csv"},
    )
    assert sent_urls(route) == [f"{BASE}/v1/export?year=2025&format=csv"]
    assert route.calls.last.request.headers["accept"] == "text/csv"
    assert seen == [f"{BASE}/v1/export?year=2025&format=csv"], "before_request sees the query"
    assert list(inspect.signature(AsyncClient.download).parameters) == [
        "self",
        "url",
        "dest",
        "params",
        "headers",
        "auth",
    ]


@pytest.mark.anyio
async def test_a_download_from_another_host_carries_no_credential(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # https://github.com/xippios/sdk-core/issues/163: a catalog's file link on another host
    # got the client's key by default; it goes without it, and its request says so.
    link = "https://files.example.test/bulk/rows.csv"
    route = respx_mock.get(link).respond(200, text=CSV)
    seen: list[object] = []
    client = make_client(
        auth=KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example"),
        before_request=lambda request: seen.append(request.extensions.get("xippios_origin")),
        observe=lambda response: seen.append(response.request.extensions.get("xippios_auth")),
    )
    await client.download(link, tmp_path / "rows.csv")
    assert sent_urls(route) == [link]
    assert "authorization" not in route.calls.last.request.headers
    assert seen == ["other", "client"]
    assert (tmp_path / "rows.csv").read_text(encoding="utf-8") == CSV
    await client.download(link, tmp_path / "again.csv", auth=httpx.BasicAuth("user", "pw"))
    assert route.calls.last.request.headers["authorization"].startswith("Basic ")


@pytest.mark.anyio
async def test_a_retry_restarts_the_file_and_the_hooks_run_as_for_get(tmp_path: Path) -> None:
    # ADR-0011: a 5xx and a transport failure in the middle of the body are retried.
    bodies = [Chunks(3, fail_after=2), Chunks(2)]
    statuses = [503]
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        if statuses:
            return httpx.Response(statuses.pop(), text="busy")
        return httpx.Response(200, stream=bodies.pop(0))

    client = make_client(
        transport=httpx.MockTransport(answer),
        before_request=lambda request: seen.append(f"before {request.url.path}"),
        observe=lambda response: seen.append(f"observe {response.status_code}"),
    )
    got = await client.download("/files/big.bin", tmp_path / "big.bin")
    assert got.bytes == 2048
    assert (tmp_path / "big.bin").read_bytes() == b"x" * 2048
    assert seen == ["before /files/big.bin", "observe 503", "observe 200", "observe 200"]
    assert leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_an_error_reads_a_bounded_head_and_leaves_dest_untouched(tmp_path: Path) -> None:
    body = Chunks(1000)  # 1000 KiB that the error text never needs
    client = make_client(transport=httpx.MockTransport(lambda _: httpx.Response(404, stream=body)))
    (tmp_path / "old.csv").write_text("old")
    with pytest.raises(NotFoundError, match=r"^404 from GET /files/gone.csv: x+$"):
        await client.download("/files/gone.csv", tmp_path / "old.csv")
    assert body.read <= 17  # BODY_LIMIT is 16 KiB
    assert (tmp_path / "old.csv").read_text() == "old"
    assert leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_the_hooks_see_a_success_s_headers_only(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    def classify(response: httpx.Response) -> AuthError | None:
        if response.headers.get("x-login") == "required":
            return AuthError("the file needs a login", status=200)
        response.json()  # reads the body: unread on a download's success, so None
        return None

    def observe(response: httpx.Response) -> None:
        response.json()  # likewise: nothing observed, and nothing raised

    respx_mock.get(f"{BASE}/a.csv").respond(200, text="a\n1\n")
    respx_mock.get(f"{BASE}/b.csv").respond(200, text="<html/>", headers={"X-Login": "required"})
    client = make_client(classify=classify, observe=observe)
    assert (await client.download("/a.csv", tmp_path / "a.csv")).bytes == 4
    with pytest.raises(AuthError, match="needs a login"):
        await client.download("/b.csv", tmp_path / "b.csv")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a.csv"]


@pytest.mark.anyio
async def test_a_redirect_is_refused(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    route = respx_mock.get(f"{BASE}/moved.csv").respond(302, headers={"Location": "/new.csv"})
    client = make_client()
    with pytest.raises(UpstreamError, match=r"^302 from GET /moved.csv: a download writes a 2xx"):
        await client.download("/moved.csv", tmp_path / "moved.csv")
    assert route.call_count == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("dest", "message"),
    [
        (".", "dest is a directory; name the file to write. Nothing was sent."),
        (
            "missing/qs.crops.txt",
            "dest's directory does not exist; create it first. Nothing was sent.",
        ),
    ],
    ids=["a-directory", "in-a-missing-directory"],
)
async def test_a_bad_dest_is_an_invalid_request_and_nothing_is_sent(
    respx_mock: respx.MockRouter, tmp_path: Path, dest: str, message: str
) -> None:
    """https://github.com/xippios/sdk-core/issues/152: a bad argument is the taxonomy's
    ``InvalidRequestError`` (conventions §5), no longer a ``ValueError``."""
    route = respx_mock.get(f"{BASE}/qs.crops.txt").respond(200, content=b"x")
    hooked: list[str] = []
    client = make_client(before_request=lambda request: hooked.append(request.url.path))
    with pytest.raises(InvalidRequestError) as info:
        await client.download("/qs.crops.txt", tmp_path / dest)
    assert str(info.value) == message
    assert info.value.source == "example"
    assert not route.called
    assert hooked == []  # refused before the hook, the limiter and the wire
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("dest", "message"),
    [
        (".", "dest is a directory; name the file to write. Nothing was sent."),
        (
            "missing/report.pdf",
            "dest's directory does not exist; create it first. Nothing was sent.",
        ),
    ],
    ids=["a-directory", "in-a-missing-directory"],
)
def test_the_check_of_dest_alone_refuses_before_a_task_s_first_request(
    tmp_path: Path, dest: str, message: str
) -> None:
    # A task that sends a request of its own before its download calls the check first, so a
    # bad dest sends nothing (https://github.com/xippios/sdk-core/issues/481, part 1).
    with pytest.raises(InvalidRequestError) as info:
        check_dest(tmp_path / dest, source="example")
    assert str(info.value) == message
    assert info.value.source == "example"
    assert list(tmp_path.iterdir()) == []


def test_the_check_of_dest_returns_the_file_as_a_path(tmp_path: Path) -> None:
    assert check_dest(tmp_path / "report.pdf") == tmp_path / "report.pdf"
    assert check_dest(str(tmp_path / "report.pdf")) == tmp_path / "report.pdf"
    with pytest.raises(InvalidRequestError) as info:
        check_dest(tmp_path)
    assert info.value.source is None


@pytest.mark.anyio
@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
async def test_the_file_is_written_with_mode_0600(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    """The temporary file's mode, which the rename keeps, also over a file of another mode
    (https://github.com/xippios/sdk-core/issues/152)."""
    respx_mock.get(f"{BASE}/qs.crops.txt").respond(200, content=b"x")
    dest = tmp_path / "qs.crops.txt"
    client = make_client()
    await client.download("/qs.crops.txt", dest)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    dest.chmod(0o644)
    await client.download("/qs.crops.txt", dest)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


@pytest.mark.anyio
async def test_a_final_transport_failure_or_a_cancel_leaves_no_partial_file(
    tmp_path: Path,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = make_client(transport=httpx.MockTransport(refuse))
    with pytest.raises(TransportError, match=r"^ConnectError"):
        await client.download("/files/x.bin", tmp_path / "x.bin")
    assert list(tmp_path.iterdir()) == []

    class Stalls(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"x" * 1024
            await anyio.sleep(30)

    stalling = make_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Stalls()))
    )
    with anyio.move_on_after(0.2) as scope:
        await stalling.download("/files/x.bin", tmp_path / "x.bin")
    assert scope.cancelled_caught
    assert list(tmp_path.iterdir()) == []


def test_decode_csv_reads_a_file_or_a_stream_and_nothing_else() -> None:
    # No source read a response or another separator through it, nor decode_text
    # (https://github.com/xippios/sdk-core/issues/475).
    assert list(inspect.signature(decode_csv).parameters) == ["data", "source"]
    assert "Response" not in str(inspect.signature(decode_csv).parameters["data"].annotation)


def test_decode_csv_reads_a_file_row_by_row(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text('\ufeffCommodity,Value (1000 MT)\nCORN,"15,341"\nWHEAT,\n', encoding="utf-8")
    rows = decode_csv(path)
    assert inspect.isgenerator(rows)
    assert next(rows) == {"Commodity": "CORN", "Value (1000 MT)": "15,341"}  # as printed
    assert list(rows) == [{"Commodity": "WHEAT", "Value (1000 MT)": ""}]
    (tmp_path / "latin.csv").write_bytes("a\nC\xf4te\n".encode("latin-1"))
    with pytest.raises(
        ValidationError, match=r"^latin.csv is not UTF-8 text: invalid continuation"
    ):
        list(decode_csv(tmp_path / "latin.csv"))
    (tmp_path / "wide.csv").write_text("a\n" + "x" * 200_000 + "\n")  # over csv's field limit
    with pytest.raises(ValidationError, match=r"^example: wide.csv is not CSV the csv") as info:
        list(decode_csv(str(tmp_path / "wide.csv"), source="example"))  # a str path too
    assert info.value.source == "example"


def test_decode_csv_reads_an_open_text_stream_row_by_row(tmp_path: Path) -> None:
    """https://github.com/xippios/sdk-core/issues/89: a gzip member, read as it is taken."""
    path = tmp_path / "crops.csv.gz"
    rows = "".join(f"CORN,{year}\n" for year in range(100_000))
    with gzip.open(path, "wt", encoding="utf-8", newline="") as packed:
        packed.write("\ufeffCommodity,Year\n" + rows)
    with gzip.open(path) as raw, io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
        read = decode_csv(text, source="example")
        assert inspect.isgenerator(read)
        assert next(read) == {"Commodity": "CORN", "Year": "0"}  # the byte order mark stripped
        assert raw.tell() < len(rows) // 2  # row by row: most of the member is still unread
        assert sum(1 for _ in read) == 99_999
        assert not text.closed  # the caller's to close, as it opened it


def test_decode_csv_names_the_stream_and_the_decoder_s_reason(tmp_path: Path) -> None:
    path = tmp_path / "apro_mk_cola.csv.gz"
    with gzip.open(path, "wb") as packed:
        packed.write(b"geo,OBS_VALUE\nAT,1\nC\xf4te,2\n")
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as text:
        read = decode_csv(text, source="example")
        with pytest.raises(ValidationError) as info:
            list(read)
    assert (
        str(info.value)
        == "example: apro_mk_cola.csv.gz is not UTF-8 text: invalid continuation byte"
    )
    assert info.value.source == "example"
    assert b"C\xf4te" in info.value.raw  # type: ignore[operator]
    assert (info.value.__cause__, info.value.__suppress_context__) == (None, True)
    archive = tmp_path / "QCL.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("QCL_E_All_Data_(Normalized).csv", "a,b\n1\n")
    with (
        zipfile.ZipFile(archive) as zipped,
        zipped.open("QCL_E_All_Data_(Normalized).csv") as raw,
        io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
    ):
        assert list(decode_csv(text)) == [{"a": "1", "b": None}]  # short, as DictReader does
    latin = io.TextIOWrapper(io.BytesIO(b"a\n\x81\n"), encoding="cp1252", newline="")
    with pytest.raises(ValidationError) as unnamed:
        list(decode_csv(latin))
    assert str(unnamed.value) == "stream is not cp1252 text: character maps to <undefined>"
    wide = io.StringIO("a\n" + "x" * 200_000 + "\n", newline="")
    with pytest.raises(ValidationError, match=r"^stream is not CSV the csv module reads: field"):
        list(decode_csv(wide))


def test_decode_csv_refuses_a_binary_stream(tmp_path: Path) -> None:
    path = tmp_path / "qs.crops.txt.gz"
    with gzip.open(path, "wt", encoding="utf-8") as packed:
        packed.write("a\n1\n")
    with gzip.open(path) as raw:
        with pytest.raises(TypeError) as info:
            next(decode_csv(raw))  # type: ignore[arg-type]
        assert raw.tell() == 0  # refused before a byte was read
    assert str(info.value) == (
        "decode_csv reads text, and GzipFile is a binary stream: wrap it in "
        "io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')"
    )


def test_decode_csv_reads_a_text_stream_whatever_its_class() -> None:
    """A text stream of ``tempfile``'s: ``SpooledTemporaryFile`` is an ``io.IOBase`` but no
    ``io.TextIOBase``, and ``NamedTemporaryFile``'s wrapper no ``io`` class at all."""
    with tempfile.SpooledTemporaryFile(mode="w+", newline="") as spooled:
        spooled.write("a,b\n1,2\n")
        spooled.seek(0)
        assert list(decode_csv(spooled)) == [{"a": "1", "b": "2"}]
    with tempfile.NamedTemporaryFile("w+", newline="") as named:
        named.write("a,b\n1,2\n")
        named.seek(0)
        assert list(decode_csv(named)) == [{"a": "1", "b": "2"}]


def test_decode_csv_refuses_a_binary_stream_by_what_it_reads() -> None:
    """A binary stream of no binary ``io`` class is refused at its first line, read as
    ``bytes``, with the text a binary ``io`` stream gets."""
    with tempfile.SpooledTemporaryFile(mode="w+b") as spooled:
        assert binary_refusal(spooled) == (
            "decode_csv reads text, and SpooledTemporaryFile is a binary stream: wrap it in "
            "io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')"
        )
    with tempfile.NamedTemporaryFile("w+b") as named:
        assert binary_refusal(named) == (
            "decode_csv reads text, and _TemporaryFileWrapper is a binary stream: wrap it in "
            "io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')"
        )


def binary_refusal(binary: IO[bytes]) -> str:
    """The ``TypeError`` text of ``decode_csv`` over ``binary``, which holds a small CSV."""
    binary.write(b"a,b\n1,2\n")
    binary.seek(0)
    with pytest.raises(TypeError) as info:
        next(decode_csv(binary))  # type: ignore[arg-type]
    return str(info.value)
