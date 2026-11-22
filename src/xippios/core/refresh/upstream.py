"""The frame of a source's snapshot script, ``scripts/refresh_upstream.py`` (ADR-0046).

A source's script declares its snapshot, its pages, its attribution and its hooks, and runs
it; the frame does the rest, the same in every source::

    SNAPSHOT = Snapshot(name="Example", slug="example", pages=(Page(DOCS_URL, "pages/a.md"),))

    if __name__ == "__main__":
        raise SystemExit(run(SNAPSHOT))

Everything is fetched before anything is written, one request at a time after a pause,
each URL retried at most once after a network error or a 5xx. No redirect to another host
is followed, no browser is imitated, and only a keyed sample sends a credential
(conventions §3). Each page with a file is written under ``docs/upstream/``, and
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
the text of a link to its target (ADR-0046, decision 7).

``--check`` compares content: it exits 1 when a file differs from what upstream serves now,
compared after the snapshot's ``canonical``, or when ``FETCHED.md`` would change in more than
its rows' measures, Fetched, Bytes, sha256, ETag and Last-Modified. A measure that moved
while the content stayed is an information line, never a change.

The last line of ``FETCHED.md`` names the form of the file, ``FORM``. ``compare_fetched``
compares a committed file of that form with the declaration and sends no request: every line
that follows from the declaration and the frame's own text, each declared page's row, the form
of an ETag's cell and each row's file on the disk. What only a response knows is read back
from the file and not judged (ADR-0046, decision 6).
"""

import argparse
import difflib
import hashlib
import http.client
import json
import os
import re
import textwrap
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import IO, Any
from urllib.parse import urljoin, urlsplit

COMMAND = "uv run scripts/refresh_upstream.py"
"""How a source runs its snapshot script, from its repository's root."""
TIMEOUT = 60.0
PAUSE = 2.0
"""Seconds before every request, unless the snapshot says otherwise; never in parallel."""
RETRY_PAUSE = 10.0
"""Seconds before the one retry after a network error or a 5xx."""
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
FORM = 1
"""The form of the ``FETCHED.md`` this module writes, which the file's last line names.

Every change of what the frame writes into the file raises it, so that ``compare_fetched``
judges a file of this form alone (ADR-0046, decision 6)."""
_MARK = "<!-- form {} of the FETCHED.md that xippios.core.refresh writes -->"
_MARK_LINE = re.compile(
    r"<!-- form (\d+) of the FETCHED\.md that xippios\.core\.refresh writes -->"
)
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
        keep_recorded: A writing run leaves the recorded file as it is where this run's
            content is the same after the snapshot's ``canonical``, for a document served
            in a new order on each request, so that a refresh shows real changes only.
        split: The page gives several files, which the snapshot's ``split`` makes from its
            answer: it names no ``file`` of its own.
        origin: The page's URL on a second origin the publisher runs itself (conventions
            §2), from which its file is kept where ``url`` answers 403: that answer then
            has a row in ``Not fetched``.
        keyed: A sample whose operation needs the source's credentials: it is requested
            with what the snapshot's ``credentials`` give, follows no redirect and is never
            retried (conventions §3).
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
    keep_recorded: bool = False
    split: bool = False
    origin: str | None = None
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
        body: The body as fetched.
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


@dataclass(frozen=True)
class Credentials:
    """The source's credentials, for the keyed samples alone (conventions §3).

    Attributes:
        variables: The environment variables the login reads, by name: each must be set
            before anything is fetched, and ``FETCHED.md`` names them, never a value.
        base: The URL every keyed sample lies under, the only place a credential goes: a
            sample has its origin, its scheme, host and port as parsed, as core's client
            holds its own credentials (ADR-0037, decision 4), and a path under its path by
            segments, so that a trailing slash changes nothing.
        login: Called once, right before the first keyed sample: it logs in, reading the
            variables itself, and returns the headers every keyed sample sends, such as
            ``{"Authorization": f"Bearer {token}"}``. The frame prints, logs and writes
            none of them; the login prints nothing of its answer either.
    """

    variables: tuple[str, ...]
    base: str
    login: Callable[[], Mapping[str, str]]


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
        name: The source's name as ``FETCHED.md``'s title gives it (``USDA NASS Quick
            Stats``).
        slug: The source's slug, which names the script's ``User-Agent``.
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
        out: The snapshot's directory, ``docs/upstream/`` of the repository; ``--out``
            overrides it.
        pause: Seconds before every request.
        reduce: The content a page's file is written with, from the page and its answer:
            the body as fetched by default. An HTML page becomes Markdown through the
            source's converter, its own dependency; a shared document is cut to the
            source's part with ``load_json`` and ``dump_json``, its page an excerpt.
        canonical: The form ``--check`` compares a page's file in, and a page marked
            ``keep_recorded`` is kept in: its content as written by default; for a
            document served in a new order on each request, the form with the order fixed.
        linked: The pages whose URL a row's page gives, captured right after it, such as
            the newest release's page read from the first row of a list of releases.
        note: The row's note made from the row, its answer included, where the note says
            what the answer holds (a count, a version, the bundle a shell loads): the
            page's note by default.
        split: The files a page marked ``split`` gives, by name under ``docs/upstream/``,
            in their order, from the page and its answer.
        sections: The sections of the source's own in ``FETCHED.md``, made from the rows.
        quota_wait: The seconds to wait before the one retry of a 429, read from its
            headers; it stops the run where the wait is too long. ``None``: a 429 stops the
            run as any refusal does.
        credentials: The source's credentials, for the samples marked ``keyed``; ``None``
            for a source whose snapshot sends none, which has no ``--keyless`` either.
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
    quota_wait: Callable[[Message], float] | None = None
    credentials: Credentials | None = None


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


def dump_json(value: Any, indent: int = 2) -> bytes:
    """``value`` as JSON in the order it holds, ``ensure_ascii=False``, with a final newline.

    Args:
        value: The document or the part of it a file keeps.
        indent: The indent upstream serves the document with.

    Returns:
        The file's content.
    """
    return (json.dumps(value, indent=indent, ensure_ascii=False) + "\n").encode("utf-8")


def load_json(response: Response, indent: int = 2) -> Any:
    """The JSON document of ``response``, once re-serialising it reproduces the fetched text.

    A source that keeps a JSON document cut to its part, or in the form ``canonical`` gives
    it, writes it with ``dump_json``; this check makes sure that the whole document, written
    the same way, is the fetched text up to line endings, so what is written is upstream's
    text. A duplicate key, which ``json.loads`` would drop silently, stops the run too.

    Args:
        response: The answer that holds the document.
        indent: The indent upstream serves it with.

    Returns:
        The document.
    """
    try:
        document = json.loads(response.body, object_pairs_hook=_no_duplicates)
    except ValueError as error:
        raise SystemExit(f"GET {response.url}: not usable JSON ({error})") from None
    fetched = response.body.replace(b"\r\n", b"\n").rstrip(b"\n")
    if dump_json(document, indent).rstrip(b"\n") != fetched:
        raise SystemExit(
            f"GET {response.url}: re-serialised with json.dumps(indent={indent}, "
            "ensure_ascii=False), the document no longer reproduces the fetched text up to "
            "line endings, so what is written from it would not be upstream's text."
            "\nLook at the document by hand and update scripts/refresh_upstream.py. Nothing "
            "was written."
        )
    return document


# --- the fetch -----------------------------------------------------------------------


class _RetryableError(Exception):
    """A network error, a 5xx or a 429 the snapshot waits for: worth one more attempt."""

    def __init__(self, message: str, wait: float) -> None:
        super().__init__(message)
        self.wait = wait


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects on the page's host as urllib does, remembering each status and target.

    A redirect to another host is remembered and not followed, and a keyed request follows
    none: the page then answers its 3xx (conventions §3).
    """

    def __init__(self, *, follow: bool) -> None:
        super().__init__()
        self.follow = follow
        self.hops: list[tuple[int, str]] = []
        self.followed = 0

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Record the hop, then let urllib build the follow-up request on the same host."""
        self.hops.append((code, newurl))
        if not self.follow or urlsplit(newurl).netloc != urlsplit(req.full_url).netloc:
            return None
        self.followed += 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _user_agent(snapshot: Snapshot) -> str:
    return f"xippios-{snapshot.slug} refresh_upstream (+https://github.com/xippios)"


def _unread(page: Page) -> bool:
    """Whether the page is one an anonymous client cannot read: its row goes to Not fetched."""
    return page.status in (401, 403) or 300 <= page.status < 400


_PORTS = {"http": 80, "https": 443}
"""The schemes a credential may go to, with the port each one means where a URL names none."""


def _place(url: str) -> tuple[tuple[str, str, int], tuple[str, ...]] | None:
    """A URL's origin, its scheme, host and port as parsed, and its path's segments.

    ``None`` for a URL that cannot be compared so: not http or https, with no host, with a
    user before the host, with a port out of range, or with a ``.`` or ``..`` segment.
    """
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    segments = tuple(segment for segment in parts.path.split("/") if segment)
    if scheme not in _PORTS or not parts.hostname or "@" in parts.netloc:
        return None
    if {".", ".."} & set(segments):
        return None
    return (scheme, parts.hostname, port or _PORTS[scheme]), segments


def _comparable(base: str) -> bool:
    """Whether a credentials' base can be compared with a page's URL: no query, no fragment."""
    parts = urlsplit(base)
    return _place(base) is not None and not parts.query and not parts.fragment


def _under(base: str, url: str) -> bool:
    """Whether ``url`` has the origin of ``base`` and a path under the base's, by segments.

    Core's client sends its credentials to its base URL's origin alone, its scheme, host and
    port (ADR-0037, decision 4); a keyed sample is held to the same origin, and to the
    base's path, so that a base with or without its trailing slash admits the same URLs.
    """
    at, within = _place(base), _place(url)
    if at is None or within is None or within[0] != at[0]:
        return False
    return within[1][: len(at[1])] == at[1]


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
    if page.origin and (not page.file or page.status != 200 or page.keyed or page.split):
        raise SystemExit(f"{page.url}: a page with a second origin keeps one file, answering 200")
    credentials = snapshot.credentials
    if page.keyed and (
        credentials is None or not page.sample or not _under(credentials.base, page.url)
    ):
        raise SystemExit(
            f"{page.url}: a keyed page is a sample under the base of the snapshot's "
            "credentials, its origin and the base's path, the only requests that send one "
            "(conventions §3; ADR-0037, decision 4)"
        )


class _Capture:
    """One run's requests: the pause, the one retry, the login and the count."""

    def __init__(self, snapshot: Snapshot, *, keyless: bool) -> None:
        self.snapshot = snapshot
        self.keyless = keyless
        self.headers: dict[str, str] | None = None
        self.sent = 0

    def _login(self) -> dict[str, str]:
        if self.headers is None:
            credentials = self.snapshot.credentials
            if credentials is None:  # _check_page refuses a keyed page without them
                raise SystemExit("a keyed page needs the snapshot's credentials")
            self.headers = dict(credentials.login())
            _log("  logged in for the keyed samples; nothing of the login is shown")
        return self.headers

    def _get(self, url: str, expect: tuple[int, ...], keyed: bool) -> Response:
        headers = {"User-Agent": _user_agent(self.snapshot)}
        if keyed:
            headers.update(self._login())
        redirects = _Redirects(follow=not keyed)
        opener = urllib.request.build_opener(redirects)
        request = urllib.request.Request(url, headers=headers)
        self.sent += 1
        try:
            with opener.open(request, timeout=TIMEOUT) as answer:
                body: bytes = answer.read()
                status: int = answer.status
                received: Message = answer.headers
        except urllib.error.HTTPError as error:
            self.sent += redirects.followed
            wait = self.snapshot.quota_wait
            if error.code == 429 and wait is not None and not keyed:
                raise _RetryableError(f"HTTP 429 {error.reason}", wait(error.headers)) from None
            if error.code >= 500:
                raise _RetryableError(f"HTTP {error.code} {error.reason}", RETRY_PAUSE) from None
            hop = redirects.hops[-1] if redirects.hops else None
            if keyed and hop:
                raise SystemExit(
                    f"GET {url}: redirected ({error.code}), and a keyed request follows no "
                    "redirect. Nothing was written."
                ) from None
            if error.code not in expect and hop and urlsplit(hop[1]).netloc != urlsplit(url).netloc:
                raise SystemExit(
                    f"GET {url}: redirected ({error.code}) to another host, {hop[1]}, and no "
                    "redirect to another host is followed (conventions §3).\nFetch the target "
                    f"where it is documentation, or record the page with status={error.code} "
                    "where it asks for a login. Nothing was written."
                ) from None
            if error.code not in expect:
                raise SystemExit(f"GET {url}: HTTP {error.code} {error.reason}") from None
            body, status, received = error.read(), error.code, error.headers
        except (http.client.HTTPException, OSError) as error:  # URLError is an OSError
            self.sent += redirects.followed
            raise _RetryableError(str(error), RETRY_PAUSE) from None
        else:
            self.sent += redirects.followed
        if status not in expect:
            raise SystemExit(f"GET {url}: expected HTTP {expect[0]}, got {status}")
        encoding = received.get("Content-Encoding", "identity").strip().lower()
        if encoding != "identity":
            raise SystemExit(f"GET {url}: unexpected Content-Encoding {encoding!r}")
        return Response(
            url,
            status,
            body,
            received.get("Content-Type"),
            received.get("ETag"),
            received.get("Last-Modified"),
            tuple(redirects.hops),
        )

    def fetch(self, url: str, expect: tuple[int, ...], *, keyed: bool = False) -> Response:
        """GET ``url`` after the pause; retry once on a network error, a 5xx or a 429 waited.

        A keyed request is never retried, so a failure costs one keyed call and stops the run.
        """
        time.sleep(self.snapshot.pause)
        try:
            response = self._get(url, expect, keyed)
        except _RetryableError as error:
            if keyed:
                raise SystemExit(
                    f"GET {url}: {error}; a keyed request is not retried. Nothing was written."
                ) from None
            _log(f"  {url}: {error}; retrying once in {error.wait:g} s")
            time.sleep(error.wait)
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
        """Fetch ``page``, from its second origin where it answers 403, and read it."""
        _check_page(self.snapshot, page)
        if page.origin is None:
            response = self.fetch(page.url, (page.status,), keyed=page.keyed)
            return self.read(page, response)
        response = self.fetch(page.url, (200, 403))
        if response.status == 200:
            return self.read(page, response)
        reason = f"answers 403 to this script; kept from {page.origin}"
        refused = replace(page, file=None, status=403, origin=None, stable=False, note=reason)
        return [
            self.row(refused, response, None),
            *self.read(page, self.fetch(page.origin, (200,))),
        ]

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
    them (ADR-0046, decision 7).
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
    the vocabulary, are read past nowhere (ADR-0046, decision 7).
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


def _declared(page: Page, url: str) -> list[str]:
    """The clauses of a row's note that its page's declaration gives, its row's URL being ``url``.

    The clause of a second origin stands where the file was kept from it, ``url`` naming it.
    """
    parts = []
    if page.origin and url == page.origin:
        parts.append(
            f"the copy of {page.url}, which answers 403, from the publisher's second origin"
        )
    if page.split:
        parts.append("one of the files split from one page; Bytes and sha256 are the page's")
    if page.excerpt:
        parts.append("excerpt of a shared document; Bytes and sha256 are the whole document's")
    if page.sample:
        parts.append("a sample: an answer of the API, kept verbatim; no test fixture")
    if page.keep_recorded:
        parts.append(
            "kept as recorded while the answer is the same after the script's canonical form"
        )
    return parts


def _note_cell(clauses: Sequence[str], note: str) -> str:
    """A row's Note: the frame's clauses, then the row's own note, ``-`` where all are empty."""
    return "; ".join([*clauses, note] if note else clauses) or "-"


def _note(row: Row) -> str:
    redirected = [f"redirected ({code}) to {target}" for code, target in row.response.redirects]
    return _note_cell([*redirected, *_declared(row.page, row.response.url)], row.note)


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
    retried = ", a 429 after the wait it names" if snapshot.quota_wait else ""
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
        f"Requests go one at a time, {snapshot.pause:g} s apart, each retried at most",
        f"once{retried}, identified as `{_user_agent(snapshot)}`. No redirect to another",
        "host is followed and no browser is imitated.",
    ]
    credentials = snapshot.credentials
    if credentials is None:
        sentences.append("No key is sent or read.")
    else:
        names = " and ".join(f"`{name}`" for name in credentials.variables)
        sentences += [
            "Only the keyed samples send a credential: the script logs in once, right before",
            f"the first of them, with {names}, and sends what the login gives on those",
            "requests alone, which follow no redirect and are never retried; neither a",
            "credential nor a token is written.",
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

    ``render_fetched`` writes the file through it and ``compare_fetched`` the file it
    compares with, so the two never part.

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
    credentials = snapshot.credentials
    if credentials is None:
        lines.append(f"Regenerate: `{COMMAND}`")
    else:
        names = " and ".join(f"`{name}`" for name in credentials.variables)
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


def _kept(snapshot: Snapshot, out: Path, rows: Sequence[Row]) -> list[Row]:
    """The rows, each page marked ``keep_recorded`` with its recorded file's content.

    A row takes it where this run's content is the same after ``canonical``.
    """
    result: list[Row] = []
    for row in rows:
        page, path = row.page, out / (row.page.file or ".")
        if page.keep_recorded and row.content is not None and path.is_file():
            recorded = path.read_bytes()
            same = snapshot.canonical(page, recorded) == snapshot.canonical(page, row.content)
            if recorded != row.content and same:
                _log(f"  {page.file}: the same after canonical, kept as recorded")
                row = replace(row, content=recorded)
        result.append(row)
    return result


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
    dropped. ``--check`` and ``compare_fetched`` read the file so.
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


# --- the check without a request -----------------------------------------------------

_REDIRECTED = re.compile(r"redirected \(\d{3}\) to \S+?(?=; |$)")
_SPLIT_FILES = "(the files split from this page)"


def _cells(row: str) -> list[str]:
    """A row's cells as the frame writes them: the one space on each side off, pipes unescaped.

    A value's own white space at its edges, which the frame writes as given, is kept.
    """
    parts = _CELL.split(row)[1:-1]
    return [part.removeprefix(" ").removesuffix(" ").replace(r"\|", "|") for part in parts]


def _table(lines: Sequence[str], heading: str, header: str, rule: str) -> list[list[str]]:
    """The rows of the frame's table under ``heading``, each as its cells; none without it.

    The table is the last one under its heading, its header and its rule: what follows the
    frame's table of files is the frame's own, while a source's section before it may quote
    any line. A row of another width than the table's is left out, so the comparison names it
    as a line that the declaration does not give.
    """
    width = header.count("|") - 1
    found = [
        at
        for at in range(len(lines) - 3)
        if list(lines[at : at + 4]) == [heading, "", header, rule]
    ]
    if not found:
        return []
    rows = []
    for row in lines[found[-1] + 4 :]:
        if not row.startswith("| "):
            break
        cells = _cells(row)
        if len(cells) == width:
            rows.append(cells)
    return rows


def _heading_at(lines: list[str], heading: str, header: str) -> int:
    """Where the frame's table under ``heading`` stands, the last such, or past the end."""
    found = [
        at
        for at in range(len(lines) - 2)
        if lines[at] == heading and lines[at + 1] == "" and lines[at + 2] == header
    ]
    return found[-1] if found else len(lines)


def _between(lines: list[str], start: str, end: str) -> list[str]:
    """The lines after the line ``start`` and before the line ``end``; none without both."""
    try:
        first = lines.index(start)
        last = lines.index(end, first)
    except ValueError:
        return []
    return lines[first + 1 : last]


def _read_back(snapshot: Snapshot, lines: list[str]) -> set[str]:
    """The pages whose text the run read, as the committed Attribution tells them.

    A statement printed on a page that no run reads by its declaration, a sample or a page an
    anonymous client cannot read, takes the clause of an unread page from the declaration. On
    any other page the clause follows the page's answer, its type and its first bytes, so it
    is read back from the file.
    """
    attribution = _flat(" ".join(_between(lines, "## Attribution", "## How this is captured")))
    readable = {page.url for page in snapshot.pages if not (page.sample or _unread(page))}
    unread = {page.url for page in snapshot.pages} - readable
    return {
        statement.source
        for statement in snapshot.attribution
        if statement.source
        and statement.source not in unread
        and f"printed at {statement.source}{_UNREAD}" not in attribution
    }


def _sections(snapshot: Snapshot, lines: list[str]) -> list[str]:
    """The committed lines of the source's own sections, where its ``sections`` writes some.

    They stand after the frame's paragraph of how it captures, which closes "How this is
    captured" below the capture's own paragraphs, and before the frame's table of files. They
    open with a section's heading, so lines before the first ``##`` heading there are none of
    them, and a line of the capture that reads like a heading is the capture's. Where the
    frame's paragraph is not found, its place is counted from the declaration.
    """
    if snapshot.sections is _no_sections:
        return []
    try:
        heading = lines.index("## How this is captured")
    except ValueError:
        return []
    end = _heading_at(lines, "## Files and pages", _FILES)
    how = _how(snapshot)
    start = next(
        (at + len(how) for at in range(heading, end) if lines[at : at + len(how)] == how),
        heading + 2 + len(_captured(snapshot)),
    )
    region = lines[start:end]
    first = next((at for at, line in enumerate(region) if line.startswith("## ")), len(region))
    return region[first:]


def _redirects(note: str) -> tuple[list[str], str]:
    """The redirect clauses that a committed note opens with, and the rest of the note."""
    rest = "" if note == "-" else note
    clauses = []
    while (found := _REDIRECTED.match(rest)) is not None:
        clauses.append(found.group(0))
        rest = rest[found.end() :].removeprefix("; ")
    return clauses, rest


def _redirects_before(note: str, tail: str) -> list[str]:
    """The redirect clauses of a committed note that ends in ``tail``, the declaration's part.

    A page's own note may read like a redirect clause, so where the declaration gives the end
    of the note the clauses are read before it; otherwise they are those the note opens with.
    """
    if tail != "-" and note == tail:
        return []
    if tail != "-" and note.endswith(f"; {tail}"):
        clauses, rest = _redirects(note[: -len(tail) - 2])
        if not rest:
            return clauses
    return _redirects(note)[0]


def _own_note(rest: str, declared: Sequence[str]) -> str:
    """The row's own note, read back from a committed note past the declaration's clauses."""
    for clause in declared:
        if rest == clause:
            rest = ""
        elif rest.startswith(f"{clause}; "):
            rest = rest[len(clause) + 2 :]
    return rest


def _etag_cell(cell: str) -> str:
    """The ETag cell in the frame's form: ``-``, or a value in the code span the frame writes.

    A cell in that form is read back as it stands; any other is put in a code span, so the
    comparison names the cell.
    """
    if cell == "-":
        return cell
    fence = len(cell) - len(cell.lstrip("`"))
    inner = cell[fence:-fence] if 0 < 2 * fence < len(cell) and cell.endswith("`" * fence) else ""
    for value in (inner, inner[1:-1]):
        if value and _code(value) == cell:
            return cell
    return _code(cell)


def _owners(pages: Sequence[Page], rows: Sequence[Sequence[str]]) -> list[int | None]:
    """The declared page whose row each committed row of the table of files is, or ``None``.

    A row is its page's by its file, or by its URL for a page recorded without a file, each
    page taking one row; a page marked ``split`` takes every row with a file at its URL.
    """
    taken: set[int] = set()
    owners: list[int | None] = []
    for file, url, *_ in rows:
        owner = next(
            (
                k
                for k, page in enumerate(pages)
                if k not in taken
                and not page.split
                and (page.file or _NO_FILE) == file
                and (page.file is not None or page.url == url)
            ),
            None,
        )
        if owner is None:
            split = (k for k, page in enumerate(pages) if page.split and page.url == url)
            owner = next(split, None) if file != _NO_FILE else None
        else:
            taken.add(owner)
        owners.append(owner)
    return owners


def _declared_row(snapshot: Snapshot, page: Page, cells: Sequence[str]) -> list[str]:
    """The cells of a declared page's committed row as the declaration gives them.

    The file is the declaration's, or read back for a file that ``split`` made; the URL is the
    page's, or its second origin's where the row names that; the status is the declared one.
    Fetched, Bytes, sha256, the ETag's value, Last-Modified, the redirects of the note and,
    where the snapshot's ``note`` makes the row's note, that note are read back.
    """
    file, url, fetched, _, size, digest, etag, modified, note = cells
    answered = url if page.origin and url in (page.url, page.origin) else page.url
    declared = _declared(page, answered)
    if snapshot.note is None:
        own = page.note
        redirected = _redirects_before(note, _note_cell(declared, own))
    else:
        redirected, rest = _redirects(note)
        own = _own_note(rest, declared)
    return [
        file if page.split else page.file or _NO_FILE,
        answered,
        fetched,
        str(page.status),
        size,
        digest,
        _etag_cell(etag) if page.stable else "-",
        modified,
        _note_cell([*redirected, *declared], own),
    ]


def _missing_row(page: Page) -> list[str]:
    """The cells of the row a declared page has in no row of the committed file."""
    file = page.file or (_SPLIT_FILES if page.split else _NO_FILE)
    note = _note_cell(_declared(page, page.url), page.note)
    return [file, page.url, "-", str(page.status), "-", "-", "-", "-", note]


def _expected_files(snapshot: Snapshot, rows: Sequence[Sequence[str]]) -> list[str]:
    """The table of files as the declaration gives it, what only an answer knows read back.

    A committed row that no declared page owns is read back, its ETag's cell in the frame's
    form, as the row of a page that ``linked`` found, after the row it follows, where the
    snapshot declares ``linked``; otherwise it is left out, so the comparison names it.
    """
    pages = [page for page in snapshot.pages if not _unread(page)]
    linked = snapshot.linked is not _nothing_linked
    owned: dict[int, list[Sequence[str]]] = {}
    found: dict[int | None, list[Sequence[str]]] = {}
    anchor: int | None = None
    for cells, owner in zip(rows, _owners(pages, rows), strict=True):
        if owner is not None:
            owned.setdefault(owner, []).append(cells)
            anchor = owner
        elif linked:
            found.setdefault(anchor, []).append(cells)

    def read_back(anchor: int | None) -> list[str]:
        return [
            _file_line([*cells[:6], _etag_cell(cells[6]), *cells[7:]])
            for cells in found.get(anchor, [])
        ]

    lines = read_back(None)
    for k, page in enumerate(pages):
        mine = owned.get(k)
        if mine:
            lines += [_file_line(_declared_row(snapshot, page, cells)) for cells in mine]
        else:
            lines.append(_file_line(_missing_row(page)))
        lines += read_back(k)
    return lines


def _expected_left_out(snapshot: Snapshot, rows: Sequence[Sequence[str]]) -> list[str]:
    """The rows of ``Not fetched`` of the pages requested, what only an answer knows read back.

    A declared page that an anonymous client cannot read has its URL, its status and its
    reason from the declaration, the reason read back where the snapshot's ``note`` makes it,
    and the host it redirects to read back. The row of a page's 403 before its second origin
    is read back whole, and a row that no declared page owns is read back as the row of a page
    that ``linked`` found where the snapshot declares ``linked``. The rows of the pages not
    requested are the declaration's alone and follow these.
    """
    linked = snapshot.linked is not _nothing_linked
    owned: dict[int, Sequence[str]] = {}
    found: dict[int | None, list[Sequence[str]]] = {}
    anchor: int | None = None
    for cells in rows:
        url, status = cells[0], cells[1]
        if status == _NOT_REQUESTED:
            continue
        owner = next(
            (
                k
                for k, page in enumerate(snapshot.pages)
                if k not in owned
                and page.url == url
                and (_unread(page) or (page.origin is not None and status == "403"))
            ),
            None,
        )
        if owner is not None:
            owned[owner] = cells
            anchor = owner
        elif linked:
            found.setdefault(anchor, []).append(cells)
    lines = [_row(cells) for cells in found.get(None, [])]
    for k, page in enumerate(snapshot.pages):
        mine = owned.get(k)
        if _unread(page):
            host = mine[2] if mine else "-"
            reason = mine[3] if mine and snapshot.note is not None else page.note or "-"
            lines.append(_row([page.url, str(page.status), host, reason]))
        elif mine is not None:
            lines.append(_row(mine))
        lines += [_row(cells) for cells in found.get(k, [])]
    return lines


def compare_fetched(snapshot: Snapshot, out: Path | None = None) -> list[str]:
    """The lines in which the committed ``FETCHED.md`` differs from ``snapshot``, with no request.

    A file of the form this module writes, ``FORM``, is compared with the file the frame would
    write from the declaration, its committed files and what only an answer knows, which is read
    back from the file and not judged (ADR-0046, decision 6). Judged are every line that follows
    from the declaration and the frame's own text, each declared page's row with its file, URL,
    status and the clauses of its note that its flags give, the rows of ``Not fetched`` that the
    declaration gives, the row of ``OBSERVED.md`` where the file exists, the form of every ETag's
    cell with the allowlist mark, and each row's file under ``out``, with no file there without
    a row in the subdirectories that the frame writes to. Read back are the time of the fetch,
    an ETag's value, Last-Modified, sizes and hashes, a redirect, a note that the snapshot's
    ``note`` makes, the rows of the pages that ``linked`` found and of the files that ``split``
    made, the sections of the source's own, the attribution's clause on a page whose answer the
    run did not read, the host a page redirects to and the row of a page's 403 before its
    second origin. A row that no declared page owns is a difference, unless the snapshot
    declares ``linked``, whose pages no declaration names.

    A missing file, a file without the mark of its form, such as a copy's or sdk-template's
    stub, and a file of an older form are not judged, since the next run that fetches writes
    the present form.

    Args:
        snapshot: The source's declaration, ``SNAPSHOT`` of its ``scripts/refresh_upstream.py``.
        out: The snapshot's directory, ``snapshot.out`` by default.

    Returns:
        Each difference as one line, none where the file agrees or is not judged: ``line <n>
        holds: <text>`` for a line of the file that the declaration does not give, ``line <n>
        should hold: <text>`` for one that it gives in its place, and one line for each row
        whose file is missing and each file without a row.
    """
    out = snapshot.out if out is None else out
    path = out / FETCHED
    if not path.is_file():
        return []
    lines = _lines(path.read_bytes().decode("utf-8", errors="replace"))
    forms = [int(found[1]) for line in lines if (found := _MARK_LINE.fullmatch(line))]
    if not forms or forms[-1] < FORM:
        return []
    if forms[-1] > FORM:
        return [
            f"{FETCHED} is of form {forms[-1]}, which a later xippios-core writes: this one writes "
            f"and judges form {FORM}"
        ]
    table = _table(lines, "## Files and pages", _FILES, _FILES_RULE)
    files = [cells for cells in table if cells[0] != OBSERVED]
    left_out = _table(lines, "## Not fetched", _LEFT_OUT, _LEFT_OUT_RULE)
    expected = _lines(
        _compose(
            snapshot,
            read=_read_back(snapshot, lines),
            sections=_sections(snapshot, lines),
            files=_expected_files(snapshot, files),
            observed=(out / OBSERVED).is_file(),
            left_out=_expected_left_out(snapshot, left_out),
        )
    )
    differing: list[str] = []
    matcher = difflib.SequenceMatcher(None, lines, expected, autojunk=False)
    for tag, start, end, first, last in matcher.get_opcodes():
        if tag != "equal":
            differing += [f"line {at + 1} holds: {lines[at]}" for at in range(start, end)]
            differing += [
                f"line {start + k + 1} should hold: {expected[at]}"
                for k, at in enumerate(range(first, last))
            ]
    named = [cells[0] for cells in files if cells[0] != _NO_FILE]
    outside = [name for name in named if Path(name).is_absolute() or ".." in Path(name).parts]
    inside = [name for name in named if name not in outside]
    differing += [f"{name}: a row names it, a file outside the snapshot" for name in outside]
    differing += [
        f"{name}: a row names it, and the file is missing"
        for name in inside
        if not (out / name).is_file()
    ]
    differing += [f"{name}: the file has no row" for name in _stale(out, inside)]
    return differing


def run(snapshot: Snapshot, argv: Sequence[str] | None = None) -> int:
    """Fetch every page of ``snapshot``, then write the snapshot, or with ``--check`` compare it.

    The command line takes ``--out DIR`` and ``--check``, and ``--keyless`` where the
    snapshot declares credentials: it fetches and compares the pages that send none, logs
    in nowhere and writes nothing.

    Args:
        snapshot: The source's declaration.
        argv: The command line's arguments, ``sys.argv[1:]`` by default.

    Returns:
        The exit status: 1 where ``--check`` or ``--keyless`` finds a difference, else 0.
    """
    parser = argparse.ArgumentParser(description=f"Refresh docs/upstream/ from {snapshot.name}.")
    parser.add_argument("--out", type=Path, default=snapshot.out, help="snapshot directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="fetch and compare with the snapshot; write nothing"
    )
    if snapshot.credentials is not None:
        mode.add_argument(
            "--keyless",
            action="store_true",
            help="fetch and compare the pages that send no credential; no login, write nothing",
        )
    args = parser.parse_args(argv)
    out: Path = args.out
    keyless: bool = getattr(args, "keyless", False)
    if not snapshot.pages:
        raise SystemExit("Nothing to fetch: declare the snapshot's pages, the API document's too.")
    if snapshot.credentials is not None and not _comparable(snapshot.credentials.base):
        raise SystemExit(
            f"The base of the snapshot's credentials, {snapshot.credentials.base!r}, cannot be "
            "compared with a page's URL: give an http or https URL with a host, no user, no "
            "query, no fragment and no dot segment. Nothing was fetched or written."
        )
    for page in snapshot.pages:
        _check_page(snapshot, page)
    if snapshot.credentials is not None and not keyless:
        for name in snapshot.credentials.variables:
            if not os.environ.get(name):
                raise SystemExit(
                    f"{name} is not set. The keyed samples need it; set it, or run with "
                    "--keyless. Nothing was fetched or written."
                )
    fetched = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = len(snapshot.pages)
    _log(f"Fetching {count} pages and those they link; nothing is written before the last")
    capture = _Capture(snapshot, keyless=keyless)
    rows = capture.capture_all()
    if args.check or keyless:
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
        _log(f"{capture.sent} requests sent, each redirect and retry counted")
        return 1 if differ else 0
    rows = _kept(snapshot, out, rows)
    write_snapshot(out, rows, render_fetched(snapshot, rows, fetched, (out / OBSERVED).is_file()))
    written = sum(1 for row in rows if row.content is not None)
    _log(f"Wrote {written} files and {FETCHED} under {out} (Fetched {fetched})")
    _log(f"{capture.sent} requests sent, each redirect and retry counted")
    return 0
