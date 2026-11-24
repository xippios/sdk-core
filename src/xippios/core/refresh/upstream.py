"""The frame of a source's snapshot script, ``scripts/refresh_upstream.py`` (ADR-0062).

A source's script declares its snapshot, its pages, its attribution and its hooks, and runs
it; the frame does the rest, the same in every source::

    SNAPSHOT = Snapshot(name="Example", slug="example", pages=(Page(DOCS_URL, "pages/a.md"),))

    if __name__ == "__main__":
        raise SystemExit(run(SNAPSHOT))

Every request goes through core's client, the source's own that the snapshot hands the frame
or one that the frame builds from the slug, on core's loop, and the frame keeps its own record
of redirects, since the client follows none (ADR-0062, decision 4). Everything is fetched
before anything is written, one request at a time after a pause, each URL retried at most
once after a network error or a 5xx, and after a 429 where the client's retry policy gives it
a wait, the retry no sooner than ``RETRY_PAUSE`` or the pause. No redirect to another host
is followed, no browser is imitated, and only a keyed sample sends a credential, the
client's (conventions §3). Each page with a file is written under ``docs/upstream/``, and
``FETCHED.md`` is regenerated whole, in the one form this module writes: the UTC time of
the run with an explicit ``Z``, the attribution, one row per file with its page's HTTP
status, the size and sha256 of the body as fetched, its ETag in a code span and its
Last-Modified where sent, a row for ``OBSERVED.md`` where it exists, and the table ``Not
fetched``, with its heading even where it has no row. A row with an ETag ends in the secret
scan's allowlist mark. Files the run does not produce are removed from the subdirectories
it writes to; nothing else under ``docs/upstream/`` is touched. Every run stops, before
writing, when a page states a copyright, a licence or terms of use that the attribution
does not record, or no longer prints one that it records: a page's visible text is read, an
image's alternative text included, and a statement recorded with a link is read past only as
the text of a link to its target (ADR-0062, decision 10).

``--check`` compares content: it exits 1 when a file differs from what upstream serves now,
compared after the snapshot's ``canonical``, or when ``FETCHED.md`` would change in more than
its rows' measures, Fetched, Bytes, sha256, ETag and Last-Modified. A measure that moved
while the content stayed is an information line, never a change.

The last line of ``FETCHED.md`` names the form of the file, ``FORM``, so that a file the frame
wrote tells itself from a copy's and from an older frame's (ADR-0062, decision 8). No check
compares a committed ``FETCHED.md`` with the declaration without a request: ``--check`` at a
refresh is the one comparison, and each refresh writes the file whole (ADR-0062, decision 9).
"""

import argparse
import hashlib
import json
import os
import re
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from xippios.core._loop import run as _run_coroutine
from xippios.core.client import AsyncClient, ClientConfig, RenewingBearerAuth
from xippios.core.errors import RateLimitError, TransportError, XippiosError, parse_retry_after

COMMAND = "uv run scripts/refresh_upstream.py"
"""How a source runs its snapshot script, from its repository's root."""
PAUSE = 2.0
"""Seconds before every request, unless the snapshot says otherwise; never in parallel."""
RETRY_PAUSE = 10.0
"""Seconds before the one retry after a network error, a 5xx or a 429, at least: a 429 waits
longer where the client gives it a longer wait, and every retry waits the snapshot's pause
where that is longer still."""
REDIRECTS = 10
"""The most redirects on a page's host that the frame follows for one request, as many as
``urllib`` followed before the frame sent through core's client."""
FETCHED = "FETCHED.md"
OBSERVED = "OBSERVED.md"
"""What upstream does but never documents, each note with its evidence: the one file under
``docs/upstream/`` written by hand, which the frame neither writes nor checks."""
ALLOWLIST = "<!-- pragma: allowlist secret (an ETag, not a key) -->"
"""The end of a row with an ETag: the secret scan reads a quoted ETag of hex digits as a
secret, and a line that ends in this mark as audited."""
INFO_TERMS = ("license", "termsOfService", "contact")
"""The fields of an API document's ``info`` that state a licence, terms, or whom to ask:
each one it holds must be recorded in the attribution from that document."""
HAND = "written by hand: what upstream does but never documents; not fetched or checked"
"""The note of ``OBSERVED.md``'s row, whose first cell is the file's name."""
FORM = 2
"""The form of the ``FETCHED.md`` this module writes, which the file's last line names.

Every change of what the frame writes into the file raises it, so that the mark tells which
frame wrote the file (ADR-0062, decision 8). Core 0.4.1 wrote form 1; form 2 is the fetch
through core's client, which names the client's User-Agent and leaves the clauses of a file
kept as recorded and of a second origin (ADR-0062, decisions 4 and 6)."""
_MARK = "<!-- form {} of the FETCHED.md that xippios.core.refresh writes -->"
_NO_FILE = "(no file)"
_NOT_REQUESTED = "(not requested)"
_UNREAD = ", a page this script does not read, so no run checks it"
"""The clause of a statement whose page the run did not read, which follows its answer."""


@dataclass(frozen=True)
class Page:
    """One page the snapshot records, and the file it is kept as, if any.

    Attributes:
        url: Where the page is fetched from.
        file: Its path under ``docs/upstream/`` (``pages/guide.md``,
            ``openapi/openapi.json``, ``samples/<operation>.json``), or ``None`` for a page
            recorded without a file.
        status: The HTTP status it must answer with: 200, or the 404 of a page recorded by
            its status; a 401 or a 403, or the 3xx of a redirect to another host, for a page
            an anonymous client cannot read, whose row goes to ``Not fetched``.
        note: The row's note in ``FETCHED.md``: how the file was made, or why there is
            none; in ``Not fetched``, the reason.
        stable: ``False`` for a body that changes on every request (a per-request
            reference, a script's nonce): its row records no size, sha256 or ETag, which
            name the bytes, and keeps Last-Modified; its note says why.
        excerpt: The file is this source's part of a shared document (conventions §3);
            the row keeps the whole document's size and sha256, and its note says so.
        terms: The page is itself the terms: it must print each statement the attribution
            records from it, and nothing else on it is searched.
        sample: The file is a small answer of the API, kept verbatim under ``samples/``,
            which documents the answer's shape and is no test fixture; its row says so,
            and it is not searched, being no documentation.
        names: A text the page must hold as served, such as the URL of the API document
            for the page that names it: a page that no longer holds it stops the run.
        split: The page gives several files, which the snapshot's ``split`` makes from its
            answer: it names no ``file`` of its own.
        keyed: A sample whose operation needs the source's credentials: it is sent with
            those of the snapshot's ``client``, on the origin of the client's base URL alone,
            follows no redirect and is never retried by the frame; a renewing auth sends it
            once more after a refused bearer, and the run counts both sends and each token
            request (conventions §3; ADR-0062, decision 4; ADR-0025).
    """

    url: str
    file: str | None = None
    status: int = 200
    note: str = ""
    stable: bool = True
    excerpt: bool = False
    terms: bool = False
    sample: bool = False
    names: str = ""
    split: bool = False
    keyed: bool = False


@dataclass(frozen=True)
class Statement:
    """A copyright line, licence or terms of use the documentation states, as printed.

    Attributes:
        text: The statement as the page prints it: a footer's line, a line of a terms
            page, a link's text, the name of the licence an API document's ``info`` gives.
        source: The URL of the page that prints it, which every run checks for it where it
            reads the page's text, an image's alternative text included; a statement on a
            PDF, a sample or a page an anonymous client cannot read is quoted as one no run
            checks. ``""`` for a line that only a browser shows, such as a footer a script
            assembles, which no fetch sees.
        where: Where it stands and what it is, for ``FETCHED.md``'s Attribution; for a line
            only a browser shows, the page and the date it was read on by hand.
        link: The URL it links to, where it is a link (a footer's Terms of Service): the
            page must link its text there, and the check reads past its text only as the text
            of a link there, on every page, so the same words elsewhere, or on a page that is
            no HTML, stop the run. A statement without a link passes wherever it stands.
    """

    text: str
    source: str
    where: str = ""
    link: str | None = None


@dataclass(frozen=True)
class NotFetched:
    """A page the documentation links that the snapshot deliberately does not request.

    Attributes:
        url: The page.
        reason: Why: a feed, a third-party specification (cited, not snapshotted), an API
            answer, a page that is no API documentation.
    """

    url: str
    reason: str


@dataclass(frozen=True)
class Response:
    """One GET as served.

    Attributes:
        url: The URL requested; where redirects on its host were followed, the last of
            ``redirects`` is the URL that answered.
        status: The final HTTP status.
        body: The body as fetched, as core's client gives it, a compressed transfer
            decoded.
        content_type: The ``Content-Type`` header, if sent.
        etag: The ``ETag`` header, if sent.
        last_modified: The ``Last-Modified`` header, if sent.
        redirects: Each redirect on the way, its status and its target, a redirect to
            another host included, which is not followed.
    """

    url: str
    status: int
    body: bytes
    content_type: str | None
    etag: str | None
    last_modified: str | None
    redirects: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class Row:
    """One row of ``FETCHED.md``: the page, its response, its file's content and its note.

    Attributes:
        page: The page, as declared or as ``linked`` gave it; a file split from a page has
            the page with that file.
        response: The answer it was read from.
        content: The file's content, or ``None`` for a page recorded without a file.
        note: The row's note: the page's, or what the snapshot's ``note`` made of it.
    """

    page: Page
    response: Response
    content: bytes | None
    note: str = ""


@dataclass(frozen=True)
class Section:
    """A section of the source's own in ``FETCHED.md``, after "How this is captured".

    Attributes:
        heading: Its heading, without the ``##``.
        text: Its Markdown, written as given.
    """

    heading: str
    text: str


def _as_fetched(page: Page, response: Response) -> bytes:
    return response.body


def _as_written(page: Page, content: bytes) -> bytes:
    return content


def _nothing_linked(row: Row) -> Sequence[Page]:
    return ()


def _no_sections(rows: Sequence[Row]) -> Sequence[Section]:
    return ()


@dataclass(frozen=True)
class Snapshot:
    """A source's snapshot: what its ``scripts/refresh_upstream.py`` declares to the frame.

    Every hook stops the run with ``changed`` on a page it does not recognise, before
    anything is written.

    Attributes:
        name: The source's name as ``FETCHED.md``'s title gives it (``Example Statistics``).
        slug: The source's slug, from which the frame builds its client where the snapshot
            hands it none, named ``xippios-<slug>/<version>`` in every request.
        pages: Every page the snapshot records, in the order of ``FETCHED.md``'s rows; the
            API document is one of them.
        attribution: Every copyright line, licence or terms of use the documentation
            states, as printed; empty where it states none. ``FETCHED.md`` quotes them.
        not_fetched: Every page the documentation links that the snapshot leaves out.
        vocabulary: Words a page prints that state no copyright, licence or terms, such as
            a field named ``license``: the search reads past them, ``FETCHED.md`` lists
            them, and ``capture`` says why.
        capture: ``FETCHED.md``'s "How this is captured": what is converted, cut or left
            out, and why, its paragraphs parted by a blank line.
        out: The snapshot's directory, ``docs/upstream/`` of the repository.
        pause: Seconds before every request.
        reduce: The content a page's file is written with, from the page and its answer:
            the body as fetched by default. An HTML page becomes Markdown through the
            source's converter, its own dependency; a shared document is cut to the
            source's part with ``read_json`` and ``dump_json``, its page an excerpt; a
            document served in a new order on each request is kept as recorded where only
            that noise moved, the hook returning the recorded file's content where it is
            the answer's after ``canonical`` (ADR-0062, decision 5).
        canonical: The form ``--check`` compares a page's file in: its content as written
            by default; for a document served in a new order on each request, the form
            with the order fixed.
        linked: The pages whose URL a row's page gives, captured right after it, such as
            the newest release's page read from the first row of a list of releases.
        note: The row's note made from the row, its answer included, where the note says
            what the answer holds (a count, a version, the bundle a shell loads): the
            page's note by default.
        split: The files a page marked ``split`` gives, by name under ``docs/upstream/``,
            in their order, from the page and its answer.
        sections: The sections of the source's own in ``FETCHED.md``, made from the rows.
            It sees every row at once, before anything is written, in every mode, so a
            check of one page against another runs here, a documentation page against the
            API document it renders say: it returns ``()`` where it adds no section, and
            raises ``changed`` where the pages disagree (ADR-0062, decisions 3 and 5).
        client: The source's own client, which every request goes through, for its
            credentials, sent on the samples marked ``keyed`` alone, or for its pace, its
            headers or the wait its retry policy gives a 429; ``None``: the frame builds one
            from the slug, which holds no credentials (ADR-0062, decision 4).
        variables: The environment variables that the credentials of ``client`` read, by
            name, for a snapshot with keyed samples: each must be set before anything is
            fetched, ``FETCHED.md`` names them, never a value, and they give the command
            line ``--keyless``. Empty for a snapshot that sends no credential.
    """

    name: str
    slug: str
    pages: tuple[Page, ...]
    attribution: tuple[Statement, ...] = ()
    not_fetched: tuple[NotFetched, ...] = ()
    vocabulary: tuple[str, ...] = ()
    capture: str = ""
    out: Path = Path("docs/upstream")
    pause: float = PAUSE
    reduce: Callable[[Page, Response], bytes] = _as_fetched
    canonical: Callable[[Page, bytes], bytes] = _as_written
    linked: Callable[[Row], Sequence[Page]] = _nothing_linked
    note: Callable[[Row], str] | None = None
    split: Callable[[Page, Response], Mapping[str, bytes]] | None = None
    sections: Callable[[Sequence[Row]], Sequence[Section]] = _no_sections
    client: AsyncClient | None = None
    variables: tuple[str, ...] = ()


_STATEMENT = re.compile(
    r"\N{COPYRIGHT SIGN}|copyright|licen[cs]e|terms\s*of\s*(?:use|service)"
    r"|terms\s+and\s+conditions|all\s+rights\s+reserved|public\s+domain|creative\s+commons"
    r"|\bCC[\s-]BY\b",
    re.IGNORECASE,
)
_HIDDEN = frozenset({"script", "style", "template"})
_HTML_SPACE = " \t\n\f\r"
"""HTML's white space, which a browser strips from around an ``href``."""
_TEXT_TYPE = re.compile(r"text/.+|application/(?:[\w.-]+\+)?(?:json|xml|yaml|x-yaml)")
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_CHARSET = re.compile(r"""charset=["']?([\w.:-]+)""", re.IGNORECASE)
_BINARY = (b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"GIF8", b"\xff\xd8\xff", b"\x1f\x8b")
"""The first bytes of a binary body sent without a type: a PDF, a ZIP, a PNG, a GIF, a JPEG
or a gzip file."""
_MEASURES = ("Bytes", "sha256", "ETag", "Last-Modified")
_CELL = re.compile(r"(?<!\\)\|")
_FILES = "| File | URL | Fetched | HTTP | Bytes | sha256 | ETag | Last-Modified | Note |"
_FILES_RULE = "| --- " * 9 + "|"
_LEFT_OUT = "| URL | HTTP | Redirects to | Reason |"
_LEFT_OUT_RULE = "| --- " * 4 + "|"


def _log(message: str) -> None:
    print(message, flush=True)  # noqa: T201


def _flat(text: str) -> str:
    """``text`` with each run of white space, a no-break space or a line break, as one space."""
    return " ".join(text.split())


def changed(url: str, what: str) -> SystemExit:
    """The error a hook raises to stop the run on a page the script does not recognise.

    Args:
        url: The page, ``page.url`` or ``response.url``.
        what: What changed, ``"there is no div#indexbody"``.

    Returns:
        The ``SystemExit`` to raise, which says that nothing was written.
    """
    return SystemExit(
        f"{url} changed: {what}.\nLook at the page by hand and update "
        "scripts/refresh_upstream.py. Nothing was written."
    )


def decode(response: Response) -> str:
    """The body as UTF-8 text; a body that is not UTF-8 stops the run.

    Args:
        response: The answer a hook reads.

    Returns:
        The text, a byte order mark stripped.
    """
    try:
        return response.body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise changed(response.url, f"the body is not UTF-8 ({error})") from None


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    counts = Counter(key for key, _ in pairs)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate keys {duplicates}")
    return dict(pairs)


def dump_json(value: Any) -> bytes:
    """``value`` as JSON in the order it holds, with a final newline.

    Indented by two, ``ensure_ascii=False``: the form that ``read_json`` holds a fetched
    document to.

    Args:
        value: The document or the part of it a file keeps.

    Returns:
        The file's content.
    """
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse_json(response: Response) -> Any:
    """The JSON document of ``response`` as served, a key twice stopping the run.

    The frame's plain reader of a JSON answer, for a hook that reads the document and writes
    the body as fetched, or nothing of it: an API document whose version a ``note`` names, a
    page a ``sections`` check compares, a sample whose shape it checks (ADR-0062, decision 4).
    It holds the document to no form, so compact JSON kept as served is read. A duplicate key,
    which ``json.loads`` would drop silently, and a body that is no JSON stop the run with
    ``changed``. ``read_json`` reads through it.

    Args:
        response: The answer that holds the document.

    Returns:
        The document, its objects as ``dict`` in the order served.
    """
    try:
        return json.loads(response.body, object_pairs_hook=_no_duplicates)
    except ValueError as error:
        raise changed(response.url, f"not usable JSON ({error})") from None


def read_json(response: Response) -> Any:
    """The JSON document of ``response``, once re-serialising it reproduces the fetched text.

    The frame's reader of a JSON answer that a source writes again, named apart from the
    root's ``load_json``, which reads a packaged file (ADR-0062, decision 4). A source that
    keeps a JSON document cut to its part, or in the form ``canonical`` gives it, writes it
    with ``dump_json``; this check makes sure that the whole document, written the same way,
    is the fetched text up to line endings, so what is written is upstream's text. It reads
    the document with ``parse_json``, so a duplicate key or a body that is no JSON stops the
    run too; a hook that writes nothing of the document reads it with ``parse_json`` alone.

    Args:
        response: The answer that holds the document.

    Returns:
        The document.
    """
    document = parse_json(response)
    fetched = response.body.replace(b"\r\n", b"\n").rstrip(b"\n")
    if dump_json(document).rstrip(b"\n") != fetched:
        raise SystemExit(
            f"GET {response.url}: re-serialised with json.dumps(indent=2, "
            "ensure_ascii=False), the document no longer reproduces the fetched text up to "
            "line endings, so what is written from it would not be upstream's text."
            "\nLook at the document by hand and update scripts/refresh_upstream.py. Nothing "
            "was written."
        )
    return document


# --- the fetch -----------------------------------------------------------------------


class _RetryableError(Exception):
    """A network error, a 5xx or a 429 the client waits for: worth one more attempt."""

    def __init__(self, message: str, wait: float) -> None:
        super().__init__(message)
        self.wait = wait


def _user_agent(snapshot: Snapshot) -> str:
    """The User-Agent of the frame's requests as ``FETCHED.md`` names it, without a version.

    The client's own form (``ClientConfig.user_agent``), its source the client's that the
    snapshot hands the frame or else the slug, and ``<version>`` where the request names the
    source package's version, which a release moves.
    """
    source = snapshot.slug if snapshot.client is None else snapshot.client.source
    return f"xippios-{source}/<version> (+https://github.com/xippios)"


def _built(snapshot: Snapshot) -> AsyncClient:
    """The client the frame builds where the snapshot hands it none.

    It names itself as every client of the source does, ``xippios-<slug>/<version>``, the
    version that of the installed distribution ``xippios-<slug>``, holds no credentials, and
    takes the first page's origin for its base URL, the frame's every URL being absolute.
    """
    distribution = f"xippios-{snapshot.slug}"
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        raise SystemExit(
            f"{distribution} is not installed, and the frame names itself in each request as "
            "the source's client does, by the package's version. Run the script in the "
            f"source's project, {COMMAND}, or hand the frame the source's client as "
            "Snapshot.client. Nothing was fetched or written."
        ) from None
    first = urlsplit(snapshot.pages[0].url)
    config = ClientConfig(
        source=snapshot.slug, version=version, base_url=f"{first.scheme}://{first.netloc}"
    )
    return AsyncClient(config)


def _unread(page: Page) -> bool:
    """Whether the page is one an anonymous client cannot read: its row goes to Not fetched."""
    return page.status in (401, 403) or 300 <= page.status < 400


def _origin(url: str) -> tuple[str, str, int | None] | None:
    """A URL's origin as core's client compares it, or ``None`` for one httpx cannot parse.

    Its scheme, its host in lower case and its port, ``None`` for the scheme's default, as
    httpx parses them (ADR-0037, decision 4).
    """
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL:
        return None
    return parsed.scheme, parsed.host, parsed.port


def _on_base(client: AsyncClient, url: str) -> bool:
    """Whether ``url`` lies on the origin of the client's base URL, where it sends its auth."""
    at = _origin(url)
    return at is not None and at == _origin(client.config.base_url)


def _quota_wait(client: AsyncClient, answer: httpx.Response) -> float | None:
    """The client's wait before the one retry of a 429, or ``None`` where it gives none.

    As the client waits before it repeats a read (ADR-0037): its ``classify`` may name the wait
    in a ``RateLimitError``, from a header of upstream's own, else the answer's ``Retry-After``
    names it, and the client's retry policy bounds it for the first attempt, so a policy of one
    attempt, a wait past its ``backoff_max`` or another error of ``classify`` gives none
    (ADR-0062, decision 4).
    """
    config = client.config
    retry_after = parse_retry_after(answer.headers.get("Retry-After"))
    if config.classify is not None:
        classified = config.classify(answer)
        if isinstance(classified, RateLimitError):
            if classified.retry_after is not None:
                retry_after = classified.retry_after
        elif classified is not None:
            return None
    return config.retry.delay(1, retry_after=retry_after)


def _check_file(url: str, name: str) -> None:
    if name == OBSERVED:
        raise SystemExit(f"{url}: {OBSERVED} is written by hand, never by this script")
    if name == FETCHED or Path(name).is_absolute() or ".." in Path(name).parts:
        raise SystemExit(f"{url}: {name!r} is no file of the snapshot's own")


def _check_page(snapshot: Snapshot, page: Page) -> None:
    """Stop on a page the frame cannot record as it is declared."""
    if page.file is not None:
        _check_file(page.url, page.file)
    if page.sample and not (page.file or "").startswith("samples/"):
        raise SystemExit(f"{page.url}: a sample is kept under samples/, not as {page.file!r}")
    if _unread(page) and (page.file or page.split):
        raise SystemExit(f"{page.url}: a page an anonymous client cannot read has no file")
    if page.split and (page.file or snapshot.split is None):
        raise SystemExit(
            f"{page.url}: a page marked split names no file, and the snapshot's split makes them"
        )
    client = snapshot.client
    if page.keyed and (
        client is None
        or not snapshot.variables
        or not page.sample
        or not _on_base(client, page.url)
    ):
        raise SystemExit(
            f"{page.url}: a keyed page is a sample on the origin of the base URL of the "
            "snapshot's client, its scheme, host and port, the one place where the client "
            "sends its credentials, and the snapshot names the variables they are read from "
            "(conventions §3; ADR-0037, decision 4)"
        )


def _logs_in(client: AsyncClient) -> bool:
    """Whether the client's auth sends requests of its own, a ``RenewingBearerAuth``'s."""
    return isinstance(client._auth, RenewingBearerAuth)


class _Capture:
    """One run's requests through the client: the pause, the redirects, the retry, the count."""

    def __init__(self, snapshot: Snapshot, client: AsyncClient, *, keyless: bool) -> None:
        self.snapshot = snapshot
        self.client = client
        self.keyless = keyless
        self._before = client._sent

    @property
    def sent(self) -> int:
        """The requests the client sent since the capture began.

        The client counts each request it hands to its transport (``AsyncClient._sent``):
        one that fails in transit, where it may have reached upstream, and each request of a
        renewing auth's flow, its token requests and its resend after a refused bearer, those
        of a call that an error ends among them, a refused login's included (ADR-0062,
        decision 4; ADR-0025).
        """
        return self.client._sent - self._before

    def _send(self, url: str, keyed: bool) -> httpx.Response:
        """One GET through the client on core's loop, its answer whatever its status.

        The client's request that is sent once, never retried, cached or raised for its
        status, as the recorder's is (ADR-0066, decision 4): the client's limiter, its hooks,
        its headers and, for a keyed sample alone, its credentials apply. A renewing auth
        sends its token request before a keyed sample and, after a refused bearer, a second
        one and the sample once more, which the client counts as it sends them (``sent``).
        """
        if keyed:
            return _run_coroutine(self.client._send_once("GET", url))
        return _run_coroutine(self.client._send_once("GET", url, auth=None))

    def report(self) -> str:
        """The requests sent, one line, which names an auth's own where the client logs in.

        The run prints it last, a failed run's too, so a refused login, which stops the run,
        stands in it with the requests before it.
        """
        line = f"{self.sent} requests sent, each redirect and retry counted"
        if _logs_in(self.client):
            line += ", and each token request and resend of the client's auth"
        return line

    def _get(self, url: str, expect: tuple[int, ...], keyed: bool) -> Response:
        """GET ``url``, following its redirects on its host, and read the final answer.

        The client follows no redirect, so the frame keeps its own record of them: each 301,
        302, 303, 307 or 308 that names a ``Location`` is noted and one on the page's host
        followed, up to ``REDIRECTS``, while one to another host is not, and a keyed request
        follows none (conventions §3). Any other 3xx is the page's own answer.
        """
        hops: list[tuple[int, str]] = []
        at = url
        try:
            answer = self._send(at, keyed)
            while answer.has_redirect_location:  # a 301, 302, 303, 307 or 308 with Location
                target = urljoin(at, answer.headers["Location"])
                hops.append((answer.status_code, target))
                if keyed or urlsplit(target).netloc != urlsplit(at).netloc:
                    break
                if len(hops) > REDIRECTS:
                    raise SystemExit(
                        f"GET {url}: more than {REDIRECTS} redirects on its host. Nothing was "
                        "written."
                    )
                at = target
                answer = self._send(at, keyed)
        except TransportError as error:
            raise _RetryableError(str(error), RETRY_PAUSE) from None
        except XippiosError as error:  # the client's hooks or its auth refused the request
            said = str(error).rstrip().removesuffix(".")
            raise SystemExit(f"GET {url}: {said}. Nothing was written.") from None
        status, reason = answer.status_code, answer.reason_phrase
        if keyed and hops:
            raise SystemExit(
                f"GET {url}: redirected ({status}), and a keyed request follows no "
                "redirect. Nothing was written."
            )
        if status >= 500:
            raise _RetryableError(f"HTTP {status} {reason}", RETRY_PAUSE)
        if status == 429 and not keyed:
            wait = _quota_wait(self.client, answer)
            if wait is not None:
                raise _RetryableError(f"HTTP 429 {reason}", max(wait, RETRY_PAUSE))
        if status not in expect and hops and urlsplit(hops[-1][1]).netloc != urlsplit(at).netloc:
            raise SystemExit(
                f"GET {url}: redirected ({status}) to another host, {hops[-1][1]}, and no "
                "redirect to another host is followed (conventions §3).\nFetch the target "
                f"where it is documentation, or record the page with status={status} "
                "where it asks for a login. Nothing was written."
            )
        if status not in expect and status < 300:
            raise SystemExit(f"GET {url}: expected HTTP {expect[0]}, got {status}")
        if status not in expect:
            raise SystemExit(f"GET {url}: HTTP {status} {reason}")
        headers = answer.headers
        return Response(
            url,
            status,
            answer.content,
            headers.get("Content-Type"),
            headers.get("ETag"),
            headers.get("Last-Modified"),
            tuple(hops),
        )

    def fetch(self, url: str, expect: tuple[int, ...], *, keyed: bool = False) -> Response:
        """GET ``url`` after the pause; retry once on a network error, a 5xx or a 429 waited.

        The retry waits ``RETRY_PAUSE``, or the longer wait that the client gives a 429, and
        never less than the snapshot's pause, since it is a request as any other. A keyed
        request is never retried, so a failure costs one keyed call and stops the run.
        """
        time.sleep(self.snapshot.pause)
        try:
            response = self._get(url, expect, keyed)
        except _RetryableError as error:
            if keyed:
                raise SystemExit(
                    f"GET {url}: {error}; a keyed request is not retried. Nothing was written."
                ) from None
            wait = max(error.wait, self.snapshot.pause)
            _log(f"  {url}: {error}; retrying once in {wait:g} s")
            time.sleep(wait)
            try:
                response = self._get(url, expect, keyed)
            except _RetryableError as again:
                raise SystemExit(f"GET {url}: {again} (after one retry)") from None
        digest = hashlib.sha256(response.body).hexdigest()
        hops = "".join(f", {code} to {target}" for code, target in response.redirects)
        _log(
            f"  {url}: HTTP {response.status}{hops}, {len(response.body)} bytes, sha256 "
            f"{digest}, Last-Modified {response.last_modified or '-'}, ETag {response.etag or '-'}"
        )
        return response

    def row(self, page: Page, response: Response, content: bytes | None) -> Row:
        row = Row(page, response, content, page.note)
        if self.snapshot.note is not None:
            row = replace(row, note=self.snapshot.note(row))
        return row

    def read(self, page: Page, response: Response) -> list[Row]:
        """Check the page and its attribution, and make its rows: one per file, or one."""
        if page.names and page.names not in response.body.decode("utf-8", "replace"):
            raise changed(page.url, f"it no longer holds {page.names!r}")
        check_attribution(self.snapshot, page, response)
        if page.split and self.snapshot.split is not None:
            files = self.snapshot.split(page, response)
            if not files:
                raise changed(page.url, "it gives no file")
            for name in files:
                _check_file(page.url, name)
            return [self.row(replace(page, file=name), response, files[name]) for name in files]
        content = self.snapshot.reduce(page, response) if page.file else None
        return [self.row(page, response, content)]

    def capture(self, page: Page) -> list[Row]:
        """Fetch ``page`` and read it."""
        _check_page(self.snapshot, page)
        return self.read(page, self.fetch(page.url, (page.status,), keyed=page.keyed))

    def capture_all(self) -> list[Row]:
        """Capture every page in order, each page that ``linked`` names right after its own.

        A file two pages would write, and a statement of the attribution whose ``source`` is
        none of the pages captured, such as its page's URL without the trailing slash, which
        would never be checked, stop the run.
        """
        rows: list[Row] = []
        waiting = list(self.snapshot.pages)
        while waiting:
            page = waiting.pop(0)
            if self.keyless and page.keyed:
                continue
            captured = self.capture(page)
            rows += captured
            waiting[:0] = self.snapshot.linked(captured[-1])
        files = Counter(row.page.file for row in rows if row.page.file)
        twice = sorted(name for name, count in files.items() if count > 1)
        if twice:
            raise SystemExit(f"{', '.join(twice)}: written by two pages. Nothing was written.")
        read = {row.page.url for row in rows}
        if self.keyless:
            read |= {page.url for page in self.snapshot.pages if page.keyed}
        for statement in self.snapshot.attribution:
            if statement.source and statement.source not in read:
                raise SystemExit(
                    f"The attribution records {statement.text!r} from {statement.source}, a "
                    "page this run does not capture, so no run would check it.\nGive the URL "
                    'of its page as the pages write it, or source="" for a line only a '
                    "browser shows. Nothing was written."
                )
        return rows


# --- the attribution -----------------------------------------------------------------


@dataclass(frozen=True)
class _Link:
    """A link of an HTML page, as the attribution check reads it.

    ``href`` is its target as written, ``text`` its text, white space flattened, and ``start``
    and ``end`` the parts of the page's text it spans, ``end`` past the last.
    """

    href: str
    text: str
    start: int
    end: int


class _Reader(HTMLParser):
    """An HTML page's visible text and links: comments, scripts, styles and templates left out.

    An image's alternative text is text of the page where the image stands, set apart from the
    words around it as the image is, and the text of a link it stands in; ``alts`` holds the
    parts that one gives. Nothing else of an attribute is read, a title or an aria-label among
    them (ADR-0062, decision 10).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[_Link] = []
        self.alts: set[int] = set()
        self._hidden = 0
        self._open: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter a hidden element, open a link, or read an image's alternative text."""
        if tag in _HIDDEN:
            self._hidden += 1
        elif tag == "a":
            self._open.append((dict(attrs).get("href") or "", len(self.parts)))
        elif tag == "img" and not self._hidden:
            alt = dict(attrs).get("alt") or ""
            if alt.strip():
                self.alts.add(len(self.parts))
                self.parts.append(f" {alt} ")

    def handle_endtag(self, tag: str) -> None:
        """Leave a hidden element, or close a link with its text."""
        if tag in _HIDDEN and self._hidden:
            self._hidden -= 1
        elif tag == "a" and self._open:
            href, start = self._open.pop()
            end = len(self.parts)
            self.links.append(_Link(href, _flat("".join(self.parts[start:end])), start, end))

    def handle_data(self, data: str) -> None:
        """Keep visible text."""
        if not self._hidden:
            self.parts.append(data)


@dataclass(frozen=True)
class _Reading:
    """What the attribution check reads of a page.

    ``parts`` is its text as read, an HTML page's in its pieces, ``links`` an HTML page's links,
    ``None`` for another text, which has none, and ``alts`` the parts that an image's
    alternative text gives.
    """

    parts: tuple[str, ...]
    links: tuple[_Link, ...] | None
    alts: frozenset[int] = frozenset()

    @property
    def text(self) -> str:
        """The page's text, white space flattened."""
        return _flat("".join(self.parts))

    def targets(self, page: Page) -> list[tuple[str, str]]:
        """Each link's target, made absolute against the page's URL, and its text.

        The target is taken without the white space around it, as a browser takes an ``href``.
        """
        return [
            (urljoin(page.url, link.href.strip(_HTML_SPACE)), link.text)
            for link in self.links or ()
        ]

    def unlinked(self, page: Page, linked: Collection[tuple[str, str]]) -> tuple[str, bytearray]:
        """The page's text without the text of each link whose target and text are ``linked``.

        The text is flattened, each run of white space and each link left out one space, and
        the marks hold a 1 for each character that an image's alternative text gives, a space
        among them where all of its run does. A page that is no HTML has no link, so its text is
        whole, and none has an alternative text.
        """
        dropped = {
            at
            for link, target in zip(self.links or (), self.targets(page), strict=True)
            if target in linked
            for at in range(link.start, link.end)
        }
        parts = [" " if at in dropped else part for at, part in enumerate(self.parts)]
        if not self.alts:
            text = _flat("".join(parts))
            return text, bytearray(len(text))
        chars: list[str] = []
        marks = bytearray()
        run: int | None = None
        for at, part in enumerate(parts):
            mark = 1 if at in self.alts else 0
            for char in part:
                if char.isspace():
                    run = mark if run is None else run & mark
                    continue
                if run is not None and chars:
                    chars.append(" ")
                    marks.append(run)
                run = None
                chars.append(char)
                marks.append(mark)
        return "".join(chars), marks


def _read_past(text: str, marks: bytearray, words: str) -> tuple[str, bytearray]:
    """``text`` with each of its ``words`` one space, as ``str.replace`` makes it, and its marks.

    The space is marked where every character it takes the place of is, so the text without the
    alternative text reads the words around them as before. No words leave the text whole, where
    ``str.replace`` would part every character with a space and so pass any page.
    """
    if not words:
        return text, marks
    pieces: list[str] = []
    kept = bytearray()
    start = 0
    while (found := text.find(words, start)) >= 0:
        end = found + len(words)
        pieces += [text[start:found], " "]
        kept += marks[start:found]
        kept.append(min(marks[found:end]))
        start = end
    pieces.append(text[start:])
    kept += marks[start:]
    return "".join(pieces), kept


def _read_text(response: Response) -> _Reading | None:
    """The text the attribution check reads, or ``None`` for a binary body.

    A text body is decoded by the charset its ``Content-Type`` declares, else as UTF-8, a
    byte it cannot decode replaced. An HTML page gives its visible text, its images'
    alternative text included, and its links; another text body gives its text. A binary
    body, by its type or, sent without one, by its first bytes or a NUL, is not read, and its
    sha256 tells a change.
    """
    content_type = response.content_type or ""
    media = content_type.split(";")[0].strip().lower()
    if media and not _TEXT_TYPE.fullmatch(media):
        return None
    if not media and (response.body.startswith(_BINARY) or b"\x00" in response.body[:1024]):
        return None
    declared = _CHARSET.search(content_type)
    charset = declared[1].lower() if declared else "utf-8"
    try:
        text = response.body.decode("utf-8-sig" if charset == "utf-8" else charset, "replace")
    except LookupError:
        text = response.body.decode("utf-8-sig", "replace")
    start = text.lstrip()[:15].lower()
    if media in _HTML_TYPES or (not media and start.startswith(("<!doctype html", "<html"))):
        reader = _Reader()
        reader.feed(text)
        reader.close()
        return _Reading(tuple(reader.parts), tuple(reader.links), frozenset(reader.alts))
    return _Reading((text,), None)


def _linked(statement: Statement) -> tuple[str, str] | None:
    """A statement recorded with a link as the link it is, its target and its text."""
    return (statement.link, _flat(statement.text)) if statement.link else None


def _links(page: Page, statement: Statement, reading: _Reading) -> bool:
    """Whether the page links the statement: by a link of its text, or, not HTML, its URL."""
    if reading.links is None:
        return str(statement.link) in reading.text
    return _linked(statement) in reading.targets(page)


def _api_document(response: Response) -> dict[str, Any] | None:
    """The body as an OpenAPI or Swagger document in JSON, or ``None`` where it is none."""
    try:
        document = json.loads(response.body)
    except ValueError:
        return None
    if isinstance(document, dict) and ("openapi" in document or "swagger" in document):
        return document
    return None


def _searched(
    page: Page, response: Response, text: str, marks: bytearray, recorded: list[Statement]
) -> tuple[str, bytearray]:
    """The text the search reads and its marks, ``text`` and ``marks`` as they are but for one.

    An API document's text is the document without its ``info``'s ``INFO_TERMS``, which no
    alternative text marks; each of them the document holds is checked first against the
    statements recorded from it.
    """
    document = _api_document(response)
    info = document.get("info") if document else None
    if document is None or not isinstance(info, dict):
        return text, marks
    quoted = {value for item in recorded for value in (item.text, item.link) if value}
    for name in INFO_TERMS:
        value = info.get(name)
        values = list(value.values()) if isinstance(value, dict) else [value]
        if value is not None and not quoted.intersection(str(v) for v in values):
            raise SystemExit(
                f"GET {page.url}: info.{name} names {value!r}, which the attribution does not "
                "record from this document.\nRead it by hand, record it in the snapshot's "
                "attribution and update scripts/refresh_upstream.py. Nothing was written."
            )
    rest = {key: value for key, value in info.items() if key not in INFO_TERMS}
    searched = _flat(json.dumps({**document, "info": rest}, ensure_ascii=False))
    return searched, bytearray(len(searched))


def _reading(page: Page, response: Response) -> _Reading | None:
    """What the check reads of a page: none of a sample or of a page no client may read."""
    return None if page.sample or _unread(page) else _read_text(response)


def check_attribution(snapshot: Snapshot, page: Page, response: Response) -> None:
    """Stop when the page states a copyright, licence or terms that the attribution lacks.

    The check reads a page's visible text, an image's alternative text included where the
    image stands, so a commented-out footer, a script's strings and a PDF's bytes state
    nothing. It stops, too, when the page no longer prints a statement recorded from it, or no
    longer links one that is a link. A terms page must print each statement recorded from it
    and is searched no further; an API document's ``info`` names a licence, terms or a contact
    only as the attribution records them from it. A sample and a page an anonymous client
    cannot read are not read.

    The search reads past a statement recorded with a link only where it stands as the text of
    a link to its target, on any page, and past a statement without a link and the vocabulary
    wherever they stand. A page that is no HTML has no link, so there a linked statement's words
    are searched as any others. Where an image's alternative text stands, the search reads the
    text twice, with it and without it, each read past where the text with it stands, the text
    without it flattened again, so words that an alternative text stands between are searched
    as before it was read. A statement whose text is empty or white space, and such a word of
    the vocabulary, are read past nowhere (ADR-0062, decision 10).
    """
    reading = _reading(page, response)
    if reading is None:
        return
    text = reading.text
    recorded = [statement for statement in snapshot.attribution if statement.source == page.url]
    for statement in recorded:
        if _flat(statement.text) not in text:
            raise changed(page.url, f"it no longer prints {statement.text!r}")
        if statement.link and not _links(page, statement, reading):
            raise changed(page.url, f"it no longer links {statement.text!r} to {statement.link}")
    if page.terms:
        if not recorded:
            raise SystemExit(
                f"{page.url} is a terms page, and the attribution records no statement from "
                "it: record the lines it must print. Nothing was written."
            )
        return
    linked = {link for statement in snapshot.attribution if (link := _linked(statement))}
    text, marks = _searched(page, response, *reading.unlinked(page, linked), recorded)
    unlinked = (statement.text for statement in snapshot.attribution if not statement.link)
    for words in (*unlinked, *snapshot.vocabulary):
        text, marks = _read_past(text, marks, _flat(words))
    searches = [(text, "")]
    if any(marks):
        without = _flat("".join(char for char, mark in zip(text, marks, strict=True) if not mark))
        searches.append((without, ", read without its images' alternative text"))
    for searched, read in searches:
        if match := _STATEMENT.search(searched):
            raise _unrecorded(snapshot, page, match, searched, read)


def _unrecorded(
    snapshot: Snapshot, page: Page, match: re.Match[str], searched: str, read: str
) -> SystemExit:
    """The stop on the words that ``match`` found in the text the search read, as ``read`` says.

    Where a statement recorded with a link stands among them, the stop names it.
    """
    around = searched[max(match.start() - 60, 0) : match.end() + 60]
    named = next((s for s in snapshot.attribution if s.link and _flat(s.text) in around), None)
    aside = (
        f" The attribution records {named.text!r} as a link to {named.link}, and the check "
        "reads past it only as the text of such a link."
        if named
        else ""
    )
    return SystemExit(
        f"GET {page.url}: the page states {match.group(0)!r} ({around!r}){read}, a copyright, "
        f"licence or terms of use that the attribution does not record.{aside}\nRead it "
        "by hand and record it in the snapshot's attribution, or, where the words state "
        "nothing, narrow the check: add them to its vocabulary, which FETCHED.md lists, and "
        "say why in its capture. Nothing was written."
    )


# --- FETCHED.md ----------------------------------------------------------------------


def _iso_http_date(value: str | None) -> str:
    """A ``Last-Modified`` in UTC, or as sent in a code span where it is no HTTP date.

    An HTTP date is GMT in every form a recipient reads (RFC 9110, section 5.6.7), so one
    that parses without a zone, the asctime form or a ``-0000`` zone, is read as UTC. A value
    that is no date ends no capture: it is written as the server sent it.
    """
    if not value:
        return "-"
    try:
        parsed = parsedate_to_datetime(value)
    except ValueError:
        return _code(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(value: str) -> str:
    """``value`` as a table's cell, which keeps its row on one line.

    A line feed, with a carriage return before it, is written as a space, as a paragraph of the
    frame writes it, and a pipe is escaped. Any other character that splits a text into lines
    is written as given, since the frame splits ``FETCHED.md`` at line feeds alone
    (``_lines``).
    """
    return value.replace("\r\n", " ").replace("\n", " ").replace("|", r"\|")


def _code(text: str) -> str:
    """``text`` as a Markdown code span, its fence longer than any run of backticks in it."""
    fence = "`"
    while fence in text:
        fence += "`"
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _paragraph(*sentences: str) -> list[str]:
    text = " ".join(sentences)
    wrapped = textwrap.fill(text, width=88, break_long_words=False, break_on_hyphens=False)
    return [*wrapped.splitlines(), ""]


def _bullet(text: str) -> list[str]:
    wrapped = textwrap.fill(
        text,
        width=88,
        initial_indent="- ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.splitlines()


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def _declared(page: Page) -> list[str]:
    """The clauses of a row's note that its page's declaration gives."""
    parts = []
    if page.split:
        parts.append("one of the files split from one page; Bytes and sha256 are the page's")
    if page.excerpt:
        parts.append("excerpt of a shared document; Bytes and sha256 are the whole document's")
    if page.sample:
        parts.append("a sample: an answer of the API, kept verbatim; no test fixture")
    return parts


def _note_cell(clauses: Sequence[str], note: str) -> str:
    """A row's Note: the frame's clauses, then the row's own note, ``-`` where all are empty."""
    return "; ".join([*clauses, note] if note else clauses) or "-"


def _note(row: Row) -> str:
    redirected = [f"redirected ({code}) to {target}" for code, target in row.response.redirects]
    return _note_cell([*redirected, *_declared(row.page)], row.note)


def _attribution(snapshot: Snapshot, read: Collection[str]) -> list[str]:
    """``FETCHED.md``'s Attribution: every recorded statement, as printed, and where.

    ``read`` holds the pages whose text the run read: a statement printed on another page is
    one that no run checks.
    """
    if not snapshot.attribution:
        return _paragraph(
            "None stated: no page this script reads states a copyright line, a licence or",
            "terms of use.",
        )
    lines = _paragraph("The documentation states these, as printed:")
    for statement in snapshot.attribution:
        text = f"`{statement.text}`"
        if statement.link:
            text += f", a link to {statement.link}"
        if statement.source:
            text += f", printed at {statement.source}"
            if statement.source not in read:
                text += _UNREAD
        else:
            text += ", which only a browser shows, so no run checks it"
        if statement.where:
            text += f": {statement.where}"
        lines += _bullet(text)
    return [*lines, ""]


def _how(snapshot: Snapshot) -> list[str]:
    """The sentences of "How this is captured" that the frame states for every source."""
    retry = max(RETRY_PAUSE, snapshot.pause)
    sentences = [
        "Fetched is the UTC time the run started, in ISO 8601 with an explicit Z, the same",
        "for every row. Bytes and sha256 are those of the body as fetched: a converted page's",
        "row holds the HTML page's, an excerpt's the whole document's, a file split from a",
        "page the page's. Last-Modified is the HTTP header in UTC, or as sent in a code span",
        "where it is no HTTP date, and ETag is as sent, in a code span, on a row that ends in",
        "a comment telling the secret scan it is no key. A",
        "page recorded without a file is `(no file)`, and a body that changes on every",
        "request records no size, sha256 or ETag. A sample is a small answer of the API kept",
        "verbatim under `samples/`, which documents the answer's shape and is no test fixture.",
        f"Requests go one at a time, {snapshot.pause:g} s apart, through core's client, each",
        f"retried at most once and no sooner than {retry:g} s, a 429 after the wait the client",
        "gives it where that is longer, and are identified",
        f"as `{_user_agent(snapshot)}`, the source package's version in place of",
        "`<version>`. No redirect to another host is followed and no browser is imitated.",
    ]
    if not snapshot.variables:
        sentences.append("No key is sent or read.")
    else:
        names = " and ".join(f"`{name}`" for name in snapshot.variables)
        sentences += [
            "Only the keyed samples send a credential, the one the source's client reads from",
            f"{names}, to its base URL's origin alone; they follow no redirect and are never",
            "retried, and neither a credential nor a token is written.",
        ]
    sentences.append(
        "A page an anonymous client cannot read is requested once and listed under Not fetched."
    )
    return _paragraph(*sentences)


def _captured(snapshot: Snapshot) -> list[str]:
    """The lines under "How this is captured": the capture's paragraphs, then the frame's."""
    capture = [part for part in snapshot.capture.split("\n\n") if part.strip()]
    return [*(line for part in capture for line in _paragraph(part)), *_how(snapshot)]


def _file_line(cells: Sequence[str]) -> str:
    """A row of the table of files from its nine cells, the allowlist mark after an ETag."""
    line = _row(cells)
    return f"{line} {ALLOWLIST}" if cells[6] != "-" else line


def _host(response: Response) -> str:
    """The host the last redirect of an answer points to, ``-`` for none."""
    return urlsplit(response.redirects[-1][1]).netloc if response.redirects else "-"


def render_fetched(snapshot: Snapshot, rows: Sequence[Row], fetched: str, observed: bool) -> str:
    """The whole of ``FETCHED.md``, in the frame's one form.

    ``fetched`` is the UTC time the run started, and ``observed`` whether ``docs/upstream/``
    holds ``OBSERVED.md``.
    """
    sections = [
        line
        for section in snapshot.sections(rows)
        for line in (f"## {section.heading}", "", *section.text.strip("\n").splitlines(), "")
    ]
    files = []
    for row in rows:
        if _unread(row.page):
            continue
        response, kept = row.response, row.page.stable
        etag = response.etag if kept and response.etag else None
        cells = [
            row.page.file or _NO_FILE,
            response.url,
            fetched,
            str(response.status),
            str(len(response.body)) if kept else "-",
            hashlib.sha256(response.body).hexdigest() if kept else "-",
            _code(etag) if etag else "-",
            _iso_http_date(response.last_modified),
            _note(row),
        ]
        files.append(_file_line(cells))
    left_out = [
        _row([row.page.url, str(row.response.status), _host(row.response), row.note or "-"])
        for row in rows
        if _unread(row.page)
    ]
    return _compose(
        snapshot,
        read={row.page.url for row in rows if _reading(row.page, row.response) is not None},
        sections=sections,
        files=files,
        observed=observed,
        left_out=left_out,
    )


def _compose(
    snapshot: Snapshot,
    *,
    read: Collection[str],
    sections: Sequence[str],
    files: Sequence[str],
    observed: bool,
    left_out: Sequence[str],
) -> str:
    """``FETCHED.md`` from the declaration and what a run gives beside it.

    Args:
        snapshot: The declaration, which gives every other line.
        read: The pages whose text the run read, for the attribution.
        sections: The lines of the source's own sections.
        files: The rows of the table of files, as written.
        observed: Whether ``docs/upstream/`` holds ``OBSERVED.md``.
        left_out: The rows of ``Not fetched`` of the pages that answered, before those of
            ``snapshot.not_fetched``.
    """
    vocabulary = []
    if snapshot.vocabulary:
        words = "; ".join(f"`{word}`" for word in snapshot.vocabulary)
        vocabulary = _paragraph(
            f"The check reads past these words, which state none here: {words}. How this is",
            "captured says why.",
        )
    lines = [
        f"# Upstream documentation snapshot \N{EM DASH} {snapshot.name}",
        "",
        *_paragraph(
            "Source of truth for every endpoint wrapper (sdk-core ADR-0028). The files in this",
            "directory are written by `scripts/refresh_upstream.py` (`/refresh-upstream`)",
            "from the pages in the table below and refreshed deliberately by PR, so that",
            "changes show up as diffs. This file is generated by the same script; nothing",
            f"here is edited by hand but `{OBSERVED}`, where it exists: what upstream does",
            "but never documents, each note with its evidence.",
        ),
        "## Attribution",
        "",
        *_attribution(snapshot, read),
        *vocabulary,
        *_paragraph(
            "The script stops when a page it reads states one it does not record, or no",
            "longer prints one it records. The documentation's text is reproduced here as",
            "this package's reference (sdk-core ADR-0028); the publisher's objection is met by",
            "replacing it with a summary that keeps the names and semantics the wrappers",
            "rely on.",
        ),
        "## How this is captured",
        "",
        *_captured(snapshot),
        *sections,
        "## Files and pages",
        "",
        _FILES,
        _FILES_RULE,
        *files,
    ]
    if observed:
        lines.append(_row([OBSERVED, *["-"] * 7, HAND]))
    listed = [_row([page.url, _NOT_REQUESTED, "-", page.reason]) for page in snapshot.not_fetched]
    lines += ["", "## Not fetched", "", _LEFT_OUT, _LEFT_OUT_RULE, *left_out, *listed, ""]
    if not snapshot.variables:
        lines.append(f"Regenerate: `{COMMAND}`")
    else:
        names = " and ".join(f"`{name}`" for name in snapshot.variables)
        lines.append(f"Regenerate, with {names} set: `{COMMAND}`")
    lines += ["", _MARK.format(FORM)]
    return "\n".join(lines) + "\n"


# --- the write and the check ---------------------------------------------------------


def _files(rows: Sequence[Row]) -> dict[str, bytes]:
    return {row.page.file: row.content for row in rows if row.page.file and row.content is not None}


def _stale(out: Path, files: Collection[str]) -> list[str]:
    """The files under the subdirectories the run writes to that it does not produce.

    ``files`` names the files the run produces, by their names under ``out``.
    """
    subdirs = sorted({name.split("/", 1)[0] for name in files if "/" in name})
    found = [path for subdir in subdirs for path in sorted((out / subdir).rglob("*"))]
    names = [path.relative_to(out).as_posix() for path in found if path.is_file()]
    return [name for name in names if name not in files]


def write_snapshot(out: Path, rows: Sequence[Row], fetched_md: str) -> None:
    """Write every file as the hooks made it, then ``FETCHED.md``; remove the stale files."""
    if out.exists() and any(out.iterdir()) and not (out / FETCHED).is_file():
        raise SystemExit(f"{out} is neither empty nor a snapshot (no {FETCHED}); not writing")
    files = _files(rows)
    for name in _stale(out, files):
        (out / name).unlink()
        _log(f"  removed {name}: no longer produced")
    for name, content in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(content)
    out.mkdir(parents=True, exist_ok=True)
    (out / FETCHED).write_bytes(fetched_md.encode("utf-8"))


@dataclass
class _Table:
    """``FETCHED.md`` with its rows' measures blanked.

    ``measures`` holds each row's measures and ``rows`` each row as blanked, both by the
    row's file and URL.
    """

    masked: list[str] = field(default_factory=list)
    measures: dict[str, list[str]] = field(default_factory=dict)
    rows: dict[str, str] = field(default_factory=dict)


def _lines(text: str) -> list[str]:
    """The lines of ``FETCHED.md`` as the frame joins them, at each line feed.

    A line separator or a next-line mark inside a cell or a section stays in its line, as the
    frame wrote it there, and the carriage return of a checkout that ends its lines in CRLF is
    dropped. ``--check`` reads the file so.
    """
    return text.replace("\r\n", "\n").removesuffix("\n").split("\n")


def _measured(text: str) -> _Table:
    """Split ``FETCHED.md`` into what ``--check`` compares and what it reports."""
    table, inside, previous = _Table(), False, ""
    for line in _lines(text):
        cells = [cell.strip() for cell in _CELL.split(line)[1:-1]]
        inside = inside and line.startswith("| ")
        masked = line
        if inside and len(cells) == 9:
            key = f"{cells[0]} {cells[1]}"
            table.measures[key] = cells[4:8]
            masked = " | ".join([f"| {cells[0]}", cells[1], "", cells[3], "", "", "", "", cells[8]])
            table.rows[key] = masked
        inside = inside or (previous == _FILES and line.startswith("| --- |"))
        previous = line
        table.masked.append(masked)
    return table


def compare(
    snapshot: Snapshot, out: Path, rows: Sequence[Row], *, keyless: bool = False
) -> tuple[list[str], list[str]]:
    """What differs between the snapshot and this run: the changes, and the measures that moved.

    A file differs when its content does, compared after ``canonical``, and ``FETCHED.md``
    when it would change in more than its rows' measures. With ``keyless`` only this run's
    files and rows are compared, the keyed samples' being left out.
    """
    files = _files(rows)
    pages = {row.page.file: row.page for row in rows if row.page.file}
    differ = [
        name
        for name, content in files.items()
        if not (out / name).is_file()
        or snapshot.canonical(pages[name], (out / name).read_bytes())
        != snapshot.canonical(pages[name], content)
    ]
    current = out / FETCHED
    old = _measured(current.read_bytes().decode("utf-8") if current.is_file() else "")
    new = _measured(render_fetched(snapshot, rows, "-", (out / OBSERVED).is_file()))
    if keyless:
        differ += [
            f"{FETCHED} row of {key}" for key, row in new.rows.items() if old.rows.get(key) != row
        ]
    else:
        differ += [f"{name} (no longer produced)" for name in _stale(out, files)]
        if old.masked != new.masked:
            differ.append(FETCHED)
    moved = []
    for key, measures in new.measures.items():
        before = old.measures.get(key, measures)
        steps = [
            f"{name} {was} to {now}"
            for name, was, now in zip(_MEASURES, before, measures, strict=True)
            if was != now
        ]
        if steps:
            moved.append(f"{key}: {', '.join(steps)}")
    return differ, moved


def run(snapshot: Snapshot, argv: Sequence[str] | None = None) -> int:
    """Fetch every page of ``snapshot``, then write the snapshot, or with ``--check`` compare it.

    The command line takes ``--check``, and ``--keyless`` where the snapshot names the
    variables of its client's credentials: it fetches and compares the pages that send
    none, needs no variable and writes nothing. Every request goes through the snapshot's
    client, or one built from its slug, which the run closes once it compared or wrote. The
    run prints the requests it sent as its last line, a failed run's too once it began to
    fetch, each token request and resend of a renewing auth counted, a refused login's too
    (ADR-0062, decisions 4 and 14).

    Args:
        snapshot: The source's declaration.
        argv: The command line's arguments, ``sys.argv[1:]`` by default.

    Returns:
        The exit status: 1 where ``--check`` or ``--keyless`` finds a difference, else 0.
    """
    parser = argparse.ArgumentParser(description=f"Refresh docs/upstream/ from {snapshot.name}.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="fetch and compare with the snapshot; write nothing"
    )
    if snapshot.variables:
        mode.add_argument(
            "--keyless",
            action="store_true",
            help="fetch and compare the pages that send no credential; write nothing",
        )
    args = parser.parse_args(argv)
    keyless: bool = getattr(args, "keyless", False)
    if not snapshot.pages:
        raise SystemExit("Nothing to fetch: declare the snapshot's pages, the API document's too.")
    for page in snapshot.pages:
        _check_page(snapshot, page)
    if not keyless:
        for name in snapshot.variables:
            if not os.environ.get(name):
                raise SystemExit(
                    f"{name} is not set. The keyed samples need it; set it, or run with "
                    "--keyless. Nothing was fetched or written."
                )
    client = snapshot.client if snapshot.client is not None else _built(snapshot)
    fetched = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = len(snapshot.pages)
    _log(f"Fetching {count} pages and those they link; nothing is written before the last")
    capture = _Capture(snapshot, client, keyless=keyless)
    try:
        rows = capture.capture_all()
        return _settle(snapshot, rows, fetched, compared=args.check or keyless, keyless=keyless)
    finally:
        _log(capture.report())  # a failed run's too, as the reference frame prints it
        if snapshot.client is None:
            _run_coroutine(client.aclose())


def _settle(
    snapshot: Snapshot, rows: Sequence[Row], fetched: str, *, compared: bool, keyless: bool
) -> int:
    """Compare the rows with the snapshot, or write them; the run's exit status."""
    out = snapshot.out
    if compared:
        differ, moved = compare(snapshot, out, rows, keyless=keyless)
        for line in moved:
            _log(f"  moved, no change: {line}")
        for name in differ:
            _log(f"  differs: {name}")
        _log(
            f"{len(differ)} of the snapshot's files differ from upstream; run without --check"
            if differ
            else "The snapshot is current: upstream serves what it records."
        )
        return 1 if differ else 0
    write_snapshot(out, rows, render_fetched(snapshot, rows, fetched, (out / OBSERVED).is_file()))
    written = sum(1 for row in rows if row.content is not None)
    _log(f"Wrote {written} files and {FETCHED} under {out} (Fetched {fetched})")
    return 0
