import inspect
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import anyio
import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    Downloaded,
    MemoryCache,
    QueryKeyAuth,
    RetryPolicy,
    decode_csv,
    decode_text,
)
from xippios.core.errors import (
    AuthError,
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
        "Content-Disposition": "attachment; filename*=UTF-8''psd_alldata_%C3%A9.csv",
        "ETag": '"abc"',
        "Last-Modified": "Tue, 27 Oct 2026 08:00:00 GMT",
    }
    route = respx_mock.get(f"{BASE}/files/psd.csv").respond(200, text=CSV, headers=headers)
    cache = MemoryCache()
    client = make_client(cache=cache, auth=QueryKeyAuth("key", "EXAMPLE_API_KEY"))
    before = datetime.now(UTC)
    got = await client.download("/files/psd.csv", tmp_path / "psd.csv")
    assert got == Downloaded(
        path=tmp_path / "psd.csv",
        bytes=len(CSV.encode()),
        content_type="text/csv; charset=utf-8",
        filename="psd_alldata_é.csv",
        etag='"abc"',
        last_modified="Tue, 27 Oct 2026 08:00:00 GMT",
        retrieved_at=got.retrieved_at,
    )
    assert before <= got.retrieved_at <= datetime.now(UTC)
    assert (tmp_path / "psd.csv").read_text(encoding="utf-8") == CSV
    await client.download(f"{BASE}/files/psd.csv", tmp_path / "again.csv", auth=None)
    assert sent_urls(route) == [f"{BASE}/files/psd.csv?key={REDACTED}", f"{BASE}/files/psd.csv"]
    assert len(cache) == 0  # never the cache
    assert leftovers(tmp_path) == []


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
async def test_a_redirect_or_a_directory_is_refused(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/moved.csv").respond(302, headers={"Location": "/new.csv"})
    client = make_client()
    with pytest.raises(UpstreamError, match=r"^302 from GET /moved.csv: a download writes a 2xx"):
        await client.download("/moved.csv", tmp_path / "moved.csv")
    with pytest.raises(ValueError, match="dest is a directory"):
        await client.download("/moved.csv", tmp_path)
    with pytest.raises(ValueError, match="dest's directory does not exist"):
        await client.download("/moved.csv", tmp_path / "missing" / "moved.csv")
    assert route.call_count == 1
    assert list(tmp_path.iterdir()) == []


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


def test_decode_text_reads_the_charset_and_strips_a_bom() -> None:
    plain = {"Content-Type": "text/plain; charset=latin-1"}
    latin = httpx.Response(200, content="Côte".encode("latin-1"), headers=plain)
    assert decode_text(latin) == "Côte"
    assert decode_text(httpx.Response(200, content="\ufeffCôte".encode())) == "Côte"
    request = httpx.Request("GET", f"{BASE}/v1/file.txt")
    broken = httpx.Response(200, content=b"\xff\xfe", request=request)
    message = (
        r"^example: response from /v1/file.txt is not utf-8 text: invalid start byte at byte 0$"
    )
    with pytest.raises(ValidationError, match=message):
        decode_text(broken, source="example")


def test_decode_csv_reads_a_file_row_by_row(tmp_path: Path) -> None:
    path = tmp_path / "psd.tsv"
    path.write_text("\ufeffCommodity\tValue (1000 MT)\nCORN\t15,341\nWHEAT\t\n", encoding="utf-8")
    rows = decode_csv(path, delimiter="\t")
    assert inspect.isgenerator(rows)
    assert next(rows) == {"Commodity": "CORN", "Value (1000 MT)": "15,341"}  # as printed
    assert list(rows) == [{"Commodity": "WHEAT", "Value (1000 MT)": ""}]
    response = httpx.Response(200, text=CSV, headers={"Content-Type": "text/csv"})
    assert list(decode_csv(response)) == [{"commodity": "CORN", "Value (1000 MT)": "15,341"}]
    (tmp_path / "latin.csv").write_bytes("a\nC\xf4te\n".encode("latin-1"))
    with pytest.raises(
        ValidationError, match=r"^latin.csv is not UTF-8 text: invalid continuation"
    ):
        list(decode_csv(tmp_path / "latin.csv"))
    (tmp_path / "wide.csv").write_text("a\n" + "x" * 200_000 + "\n")  # over csv's field limit
    with pytest.raises(ValidationError, match=r"^usda-nass: wide.csv is not CSV the csv") as info:
        list(decode_csv(str(tmp_path / "wide.csv"), source="usda-nass"))  # a str path too
    assert info.value.source == "usda-nass"
