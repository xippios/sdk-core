"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It sends one request
through the source's client, its base URL, authentication, rate limit and hooks as in
production, and records the answer, an error response included, rather than raising it.
A recording is one live exchange: never retried and never answered from the cache, so a
5xx spends no second request on an upstream that counts a quota or bills a call
(ADR-0037, decision 6). The body is read up to a bound (``MAX_READ_BYTES``), and the
exchange is scrubbed in memory, rewritten by the source's own step where it passes one,
checked and written once (``Scrub``, ``rewrite=``; ADR-0048). ``send_once`` is that one
request without the write, for a source that needs the answer itself; an answer of a 1xx
or a 3xx status, no final answer of its operation, is refused on every path.
``record_task`` records every exchange that a task makes, each through the same frame,
all of them written or none (ADR-0057).
"""

import inspect
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, Literal

import httpx

from xippios.core._loop import as_async, sync
from xippios.core.client import AsyncClient
from xippios.core.client._core import (
    _CLIENT_AUTH,
    Params,
    _ClientAuth,
    _collecting,
    _Collector,
)
from xippios.core.testing.fixtures import (
    _WRITE_SENT,
    Fixture,
    Rewrite,
    _check_cut,
    _check_rewrite,
    _refuse_interim,
    fixture_from_response,
    fixture_path,
    fixture_text,
    write_fixture,
)
from xippios.core.testing.scrub import Scrub

__all__ = [
    "MAX_READ_BYTES",
    "record",
    "record_sync",
    "record_task",
    "record_task_sync",
    "send_once",
    "send_once_sync",
]

MAX_READ_BYTES: Final = 32 * 1024 * 1024
"""The most bytes of a body a recording reads by default, 32 MiB.

Four times the largest body a source records whole (sdk-usda-gats, 7.6 MB), and a
fifth of the unfiltered Eurostat dataset upstream may answer at once, 145 MB
(https://github.com/xippios/sdk-core/issues/62; ADR-0040, decision 5).
"""


async def send_once(
    client: AsyncClient,
    path: str,
    *,
    method: str = "GET",
    params: Params = None,
    json: Any = None,
    data: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    max_read_bytes: int | None = MAX_READ_BYTES,
) -> httpx.Response:
    """Send a recording's one request through ``client`` and return its answer, nothing written.

    The request ``record`` sends, for a source that needs the answer itself before or
    instead of a fixture, such as the bytes it cuts a sample from or a write's answer it
    reports, and that builds the fixture with ``fixture_from_response`` (ADR-0048, decision
    3). It is sent once, whatever ``client.config.retry`` says, and never answered from
    the cache nor stored in it, so no recorder needs a client built for one attempt; the
    client's base URL, timeouts, rate limit, ``before_request`` and ``observe`` apply as
    for any request (ADR-0037, decision 6). The answer is returned whatever its final
    status, a 4xx or a 5xx included, its body read and decoded, with the request as sent.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``, or an absolute URL on another host.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
        data: Form body for write methods, sent form-encoded, e.g. ``{"id": 4}``.
        headers: Extra headers for this request only.
        auth: Credentials for this request only, as for ``AsyncClient.request``: ``None``
            sends none, an ``httpx.Auth`` replaces the client's; the default sends the
            client's to the base URL's origin.
        max_read_bytes: The most bytes of the response body to read, as decoded:
            ``MAX_READ_BYTES``, 32 MiB, by default; ``None`` reads the body whole.

    Raises:
        ValueError: Both ``json`` and ``data``, or ``max_read_bytes`` below 1, before
            anything is sent. After the request: a body over ``max_read_bytes``, the
            message naming the method, the path and the bound; an answer of a 1xx or a 3xx
            status, which is no final answer of its operation (ADR-0048, decision 4), the
            message naming the method, the path and the status, never a header's value,
            and what to record instead. ``observe`` has seen the answer either way.
        XippiosError: ``before_request`` refused the request (a ``QuotaPolicy``'s
            ``RateLimitError``), or ``TransportError`` for a failure in transit.
    """
    if max_read_bytes is not None and max_read_bytes < 1:
        raise ValueError("max_read_bytes must be at least 1")
    response = await client._send_once(
        method,
        path,
        params=params,
        json=json,
        data=data,
        headers=headers,
        auth=auth,
        max_read_bytes=max_read_bytes,
    )
    _refuse_interim(response)
    return response


send_once_sync = sync(send_once)


async def record(
    client: AsyncClient,
    path: str,
    fixture: Path,
    *,
    method: str = "GET",
    params: Params = None,
    json: Any = None,
    data: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    scrub: Scrub | None = None,
    auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    max_bytes: int | None = None,
    array_key: str | None = None,
    keep: Literal["first", "last"] = "first",
    max_read_bytes: int | None = MAX_READ_BYTES,
    rewrite: Rewrite | None = None,
) -> Fixture:
    """Send one live request through ``client`` and write the scrubbed exchange.

    The request is the one ``send_once`` sends: once, whatever ``client.config.retry``
    says, and never answered from the cache nor stored in it, so a 429 or a 5xx is
    recorded as it came, and a recording needs no client of its own (ADR-0037, decision
    6). The client's base URL, timeouts, rate limit, ``before_request`` and ``observe``
    apply as for any request. The order is fixed: the scrub, the source's ``rewrite``
    step, the check that no value the step replaced survives, the one write (ADR-0048,
    decisions 1 and 2). The file is laid out as ``write_fixture`` writes it, without the
    response headers that only identify a request (``REQUEST_ID_HEADERS``).

    A refusal writes nothing. One raised after the request was sent (a 1xx or a 3xx, a
    body over ``max_read_bytes``, a binary body, a body ``max_bytes`` cannot cut, the
    verify step finding a secret value, or the rewrite step's refusal or a value it
    replaced left in the fixture) comes after upstream has answered: a write may have
    been applied all the same.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``.
        fixture: Destination file, usually from ``fixture_path``.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
        data: Form body for write methods, sent form-encoded, e.g. ``{"id": 4}``.
        headers: Extra headers for this request only.
        scrub: What to remove besides credentials, e.g. ``Scrub(secrets=[tenant])``, or
            a login answer's tokens with ``Scrub(response_secrets=...)``; ``None`` is
            ``Scrub()``.
        auth: Credentials for this recording only, as for ``AsyncClient.request``:
            ``None`` records a keyless endpoint without the client's key, an
            ``httpx.Auth`` replaces it; the default sends the client's.
        max_bytes: Keep at most this many bytes of a large response body, e.g.
            ``80_000``: a JSON array keeps its first whole elements, a text its first
            bytes, and the fixture is marked ``truncated`` with the whole body's size,
            sha256 and, for an array, length (ADR-0040, decision 5; see
            ``fixture_from_response``). It bounds the body, not the file, which escapes
            the body as a JSON string, text outside ASCII up to three times as long:
            ``80_000`` keeps a file under the 256 KiB cap. ``None`` keeps it whole.
        array_key: The top-level key of a JSON object whose array ``max_bytes`` cuts,
            the rest of the object kept as upstream wrote it, e.g. ``"data"`` for
            ``{"data": [...]}``. ``None`` cuts a body that is an array.
        keep: ``"first"`` keeps an array's first whole elements, ``"last"`` its last,
            for a list ordered oldest first.
        max_read_bytes: The most bytes of the response body to read, as decoded, the
            measure of ``original_bytes``: past it the reading stops, the rest of the
            body is never fetched, and the recording raises, so an answer far larger
            than expected costs neither its download nor the memory to hold it
            (ADR-0040, decision 5). ``MAX_READ_BYTES``, 32 MiB, by default;
            ``None`` reads the body whole.
        rewrite: The source's own step for what it replaces beyond the secret values, a
            tenant's host or a field by key: a function of the scrubbed ``Fixture`` that
            returns it rewritten and the values it replaced, ``(fixture, [value, ...])``,
            and raises ``ValueError`` to refuse (see ``fixture_from_response``). ``None``
            rewrites nothing.

    Raises:
        ValueError: Both ``json`` and ``data``, ``max_bytes`` or ``max_read_bytes``
            below 1, ``keep`` neither ``"first"`` nor ``"last"``, or ``array_key`` or
            ``keep="last"`` without ``max_bytes``, before anything is sent. After the
            request: an answer of a 1xx or a 3xx status, no final answer of its operation
            (ADR-0048, decision 4); a body over ``max_read_bytes``, the message naming the
            request's method and path and the bound; a request or response body that is
            not UTF-8 text without ``Scrub(allow_binary=True)``; a value
            ``Scrub.response_secrets`` returned empty; the verify step finding a secret
            value left by the scrub or brought back by the step; the step's refusal; a
            value the step replaced left in the URL, a header value or a body, the
            message naming the place, never the value; a body ``max_bytes`` cannot cut (a
            JSON object without ``array_key``, XML, ZIP, XLSX, gzip, XLS, or not UTF-8
            text: record a small real answer or sample instead).
        TypeError: ``rewrite`` is no function, before anything is sent. After the
            request: ``Scrub.response_secrets`` returned one string, or a value that is
            no string; the step returned no pair of a ``Fixture`` and its values, one
            string for its values, or a value that is no string.
        XippiosError: ``before_request`` refused the request (a ``QuotaPolicy``'s
            ``RateLimitError``), or ``TransportError`` for a failure in transit.
    """
    _check_cut(max_bytes, array_key, keep)
    _check_rewrite(rewrite)
    response = await send_once(
        client,
        path,
        method=method,
        params=params,
        json=json,
        data=data,
        headers=headers,
        auth=auth,
        max_read_bytes=max_read_bytes,
    )
    recorded = fixture_from_response(
        response, scrub=scrub, max_bytes=max_bytes, array_key=array_key, keep=keep, rewrite=rewrite
    )
    return write_fixture(recorded, fixture)


record_sync = sync(record)


_OWN_KEYWORDS: Final = ("fixtures", "case", "scrub", "rewrite")
"""The keywords ``record_task`` takes as its own, which a task's keyword would clash with."""
_KEYWORD_KINDS: Final = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
_SENT = "every request of the task was sent, so a write among them may have been applied"


async def record_task(
    task: Callable[..., Any],
    /,
    *args: Any,
    fixtures: Path,
    case: str,
    scrub: Scrub | None = None,
    rewrite: Rewrite | None = None,
    **kwargs: Any,
) -> list[Fixture]:
    """Run ``task`` live and write every exchange it makes, in order, under its name.

    The task runs as the MCP adapter awaits it, a sync facade through its async twin, with
    ``args`` and ``kwargs``, and every ``AsyncClient`` it reaches, from a registry, a module
    or one it builds, hands each answer it read whole to the recording, in the order the
    answers arrived. Meanwhile each request is sent once, whatever the client's
    ``RetryPolicy`` says, and the response cache is neither read nor filled; the client's
    base URL, auth, rate limit, ``before_request`` and ``observe`` apply as for any request
    (ADR-0057, decision 2). The recording is a context of the running task: a task the
    recorded one starts is recorded with it, a request of another task never is, and two
    recordings at once never mix. A task whose requests run at once is recorded in the
    order its answers arrived, which may change from one recording to the next.

    What a recording does not see: a token request that runs inside an auth flow, and the
    answer after which an auth flow sends a request again, both answered inside httpx's
    flow, so a login's or a refresh's exchange keeps a fixture of its own (conventions
    §10); and a download's success, whose body goes to a file unread, so a download is
    refused before it is sent, and the recording with it (decision 3). A task's answers are
    read whole, as its client reads them: ``max_read_bytes`` bounds none of them.

    Each answer passes the frame of ``record``: the refusal of a 1xx or a 3xx, the scrub,
    the ``rewrite`` step and the check that no value it replaced survives, through
    ``fixture_from_response`` (ADR-0048), and its text is built in memory. Only once every
    exchange passed is anything written: the first at ``fixture_path(fixtures, <task>,
    case)``, ``<task>`` the task's name without ``_async``, and the k-th, from the second
    on, at ``<case>_<k>.json`` beside it (decision 6). A refusal of any exchange, a task
    that raises and a task that sends no request write nothing. A task's error is raised as
    it came, unless an answer of a 1xx or a 3xx or a download came before it: the frame's
    refusal of the first of them is raised then, the task's error as its cause, since the
    recorder refuses such an answer on every path, whatever the task made of it (ADR-0048,
    decision 4). Every request of the task was sent by then: a write among them may have
    been applied.

    Args:
        task: The task, e.g. ``tasks.search_messages`` or ``tasks.search_messages_async``;
            positional only, so a keyword of the task named ``task`` reaches it.
        *args: The task's positional arguments, e.g. a tenant.
        fixtures: The fixtures directory, e.g. ``Path("tests/fixtures")``.
        case: The case of the first exchange, e.g. ``"ok"``: ``ok.json``, ``ok_2.json``...
        scrub: What to remove besides credentials, as for ``record``; ``None`` is
            ``Scrub()``.
        rewrite: The source's step, run on each exchange, as for ``record``; ``None``
            rewrites nothing.
        **kwargs: The task's keyword arguments, e.g. ``q="newer_than:1y"``.

    Returns:
        The fixtures written, in the order of the exchanges.

    Raises:
        TypeError: ``rewrite`` is no function; the task has no name; or it takes
            ``fixtures``, ``case``, ``scrub`` or ``rewrite`` by keyword, which this function
            takes as its own: the message names the clash, and the task does not run. After
            the task: a ``TypeError`` of the frame for an exchange, named as below.
        RuntimeError: A task is recorded inside another recording; the task does not run.
        ValueError: The task downloaded, the message naming the exchange's number and the
            request; it sent no request; a refusal of the frame for an exchange, the message
            naming the exchange's number, its file and the place within the fixture or the
            status of a 1xx or a 3xx, never a value, also where the task raised on such an
            answer or after it, its error the cause; or a numbered file of the case stands
            beyond the last exchange, as when a task is recorded again with fewer exchanges,
            the message naming each: delete it in the pull request, or record under another
            case. Nothing is written.
        Exception: What the task raised, as it came, where no 1xx or 3xx answer and no
            download came before it; nothing is written.
    """
    _check_rewrite(rewrite)
    name = _task_name(task)
    target = as_async(task)
    _refuse_clash(target, name)
    with _collecting() as collector:
        try:
            await target(*args, **kwargs)
        except Exception as exc:
            refusal = _refusal_before_the_error(collector, fixtures, name, case)
            if refusal is None:
                raise
            raise refusal from exc
    answers, download = collector.answers, collector.download
    before = answers if download is None else answers[: download[0] - 1]
    if not answers and download is None:
        raise ValueError(
            f"the task {name} sent no request through a client, so there is nothing to "
            "record; nothing is written"
        )
    count = len(answers)
    built: list[tuple[Path, Fixture, str]] = []
    for number, response in enumerate(before, start=1):
        path = _fixture_file(fixtures, name, case, number)
        try:
            fixture = fixture_from_response(response, scrub=scrub, rewrite=rewrite)
            text = fixture_text(fixture)
        except ValueError as exc:
            raise ValueError(_exchange_refusal(name, number, count, path, exc)) from None
        except TypeError as exc:
            raise TypeError(_exchange_refusal(name, number, count, path, exc)) from None
        built.append((path, fixture, text))
    if download is not None:
        raise ValueError(_download_refusal(name, *download))
    _refuse_stale(fixtures / name, name, case, count)
    for path, _, text in built:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return [fixture for _, fixture, _ in built]


record_task_sync = sync(record_task)


def _fixture_file(fixtures: Path, name: str, case: str, number: int) -> Path:
    """The file of exchange ``number``: ``<case>.json`` for the first, ``<case>_<k>.json`` after."""
    return fixture_path(fixtures, name, case if number == 1 else f"{case}_{number}")


def _refusal_before_the_error(
    collector: _Collector, fixtures: Path, name: str, case: str
) -> ValueError | None:
    """The frame's refusal of the first 1xx or 3xx answer or download before a task's error.

    The recorder refuses an answer that is no final answer of its operation on every path
    (ADR-0048, decision 4), so a task that raised on one, decoding a redirect's empty body
    say, or after one, is refused for it, the exchange's number and its status named, and
    not by its own error alone; ``None`` when the task met neither.
    """
    answers, download = collector.answers, collector.download
    last = len(answers) if download is None else download[0] - 1
    for number, response in enumerate(answers[:last], start=1):
        try:
            _refuse_interim(response)
        except ValueError as exc:
            path = _fixture_file(fixtures, name, case, number)
            return ValueError(_exchange_refusal(name, number, len(answers), path, exc))
    return None if download is None else ValueError(_download_refusal(name, *download))


def _task_name(task: Callable[..., Any]) -> str:
    """The task's name without ``_async``: the directory of its fixtures (conventions §10).

    Raises:
        TypeError: The task has no name.
    """
    name = getattr(task, "__name__", None)
    if not isinstance(name, str) or not name:
        raise TypeError(
            "record_task writes a task's fixtures under the task's name, and this task has "
            "no __name__: give it one with functools.update_wrapper, or wrap it in an "
            "async def"
        )
    return name.removesuffix("_async")


def _refuse_clash(task: Callable[..., Any], name: str) -> None:
    """Refuse a task that takes one of ``_OWN_KEYWORDS`` by keyword, before it runs.

    Raises:
        TypeError: The message names each clash.
    """
    try:
        parameters = inspect.signature(task).parameters.values()
    except (TypeError, ValueError):  # no signature to read: nothing to clash with
        return
    clashes = [p.name for p in parameters if p.name in _OWN_KEYWORDS and p.kind in _KEYWORD_KINDS]
    if clashes:
        keywords = "its own keyword" if len(clashes) == 1 else "keywords of its own"
        raise TypeError(
            f"the task {name} takes {', '.join(clashes)}, which record_task takes as {keywords}, "
            "so the task's could not be passed: record it through a function of your own that "
            "takes them under other names; the task does not run (ADR-0057)"
        )


def _exchange_refusal(name: str, number: int, count: int, path: Path, exc: Exception) -> str:
    """The message of a refused exchange: its number, its file and the frame's reason.

    The reason's own clause that a write may have been applied gives way to the task's, which
    says it of every request, so the message says it once.
    """
    reason = str(exc).removesuffix(_WRITE_SENT)
    return (
        f"the task {name}: exchange {number} of {count} ({name}/{path.name}) is refused, and "
        f"no fixture of the task is written: {reason}; {_SENT} (ADR-0057)"
    )


def _download_refusal(name: str, number: int, described: str) -> str:
    """The message of a task that downloaded: the exchange's number and the request."""
    return (
        f"the task {name}: exchange {number}, {described}, is a download, refused before it "
        "was sent, since its body goes to a file unread and no fixture of the task keeps it; "
        "nothing is written, and the requests before it were sent, so a write among them may "
        "have been applied: record such a task's exchanges one by one with record or "
        "send_once, and its download with its sample (ADR-0057)"
    )


def _refuse_stale(directory: Path, name: str, case: str, count: int) -> None:
    """Refuse while a numbered file of ``case`` stands beyond the ``count`` exchanges.

    ``<case>_<k>.json`` with ``k`` above ``count``, as a recording with more exchanges left
    it. The recorder deletes no fixture: the pull request does, and names it (conventions
    §10, ADR-0039, decision 8), and a case of its own may carry such a name.

    Raises:
        ValueError: The message names each such file; nothing is written.
    """
    if not directory.is_dir():
        return
    numbered = re.compile(rf"{re.escape(case)}_([1-9][0-9]*)\.json")
    stale = sorted(
        (int(match.group(1)), entry.name)
        for entry in directory.iterdir()
        if (match := numbered.fullmatch(entry.name)) and int(match.group(1)) > count
    )
    if stale:
        files = ", ".join(f"{name}/{file}" for _, file in stale)
        raise ValueError(
            f"the task {name} made {count} exchange{'s' if count != 1 else ''}, and {files} "
            f"stand{'s' if len(stale) == 1 else ''} beyond, numbered as an exchange of the case "
            f"{case!r}; nothing is written, and {_SENT}: delete what a recording with more "
            "exchanges left, in a pull request that names it (conventions §10), or record under "
            "another case (ADR-0057)"
        )
