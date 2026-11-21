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
does not record, or no longer prints one that it records.

``--check`` compares content: it exits 1 when a file differs from what upstream serves now,
compared after the snapshot's ``canonical``, or when ``FETCHED.md`` would change in more than
its rows' measures, Fetched, Bytes, sha256, ETag and Last-Modified. A measure that moved
while the content stayed is an information line, never a change.
"""

import argparse
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
from collections.abc import Callable, Mapping, Sequence
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
            reads the page's text; a statement on a PDF, a sample or a page an anonymous
            client cannot read is quoted as one no run checks. ``""`` for a line that only a
            browser shows, such as a footer a script assembles, which no fetch sees.
        where: Where it stands and what it is, for ``FETCHED.md``'s Attribution; for a line
            only a browser shows, the page and the date it was read on by hand.
        link: The URL it links to, where it is a link (a footer's Terms of Service): the
            page must link its text there.
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
        base: The URL every keyed sample starts with, the only place a credential goes.
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
_TEXT_TYPE = re.compile(r"text/.+|application/(?:[\w.-]+\+)?(?:json|xml|yaml|x-yaml)")
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_CHARSET = re.compile(r"""charset=["']?([\w.:-]+)""", re.IGNORECASE)
_BINARY = (b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"GIF8", b"\xff\xd8\xff", b"\x1f\x8b")
"""The first bytes of a binary body sent without a type: a PDF, a ZIP, a PNG, a GIF, a JPEG
or a gzip file."""
_MEASURES = ("Bytes", "sha256", "ETag", "Last-Modified")
_CELL = re.compile(r"(?<!\\)\|")
_FILES = "| File | URL | Fetched | HTTP | Bytes | sha256 | ETag | Last-Modified | Note |"
_LEFT_OUT = "| URL | HTTP | Redirects to | Reason |"


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
        credentials is None or not page.sample or not page.url.startswith(credentials.base)
    ):
        raise SystemExit(
            f"{page.url}: a keyed page is a sample under the base of the snapshot's "
            "credentials, the only requests that send one (conventions §3)"
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


class _Reader(HTMLParser):
    """An HTML page's visible text and links: comments, scripts, styles and templates left out."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._hidden = 0
        self._open: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter a hidden element, or open a link."""
        if tag in _HIDDEN:
            self._hidden += 1
        elif tag == "a":
            self._open.append((dict(attrs).get("href") or "", []))

    def handle_endtag(self, tag: str) -> None:
        """Leave a hidden element, or close a link with its text."""
        if tag in _HIDDEN and self._hidden:
            self._hidden -= 1
        elif tag == "a" and self._open:
            href, parts = self._open.pop()
            self.links.append((href, _flat("".join(parts))))

    def handle_data(self, data: str) -> None:
        """Keep visible text, in the page and in each open link."""
        if self._hidden:
            return
        self.parts.append(data)
        for _, parts in self._open:
            parts.append(data)


@dataclass(frozen=True)
class _Reading:
    """What the attribution check reads of a page.

    ``text`` is its text, white space flattened, and ``links`` an HTML page's links as
    ``(href, text)``, ``None`` for another text.
    """

    text: str
    links: tuple[tuple[str, str], ...] | None


def _read_text(response: Response) -> _Reading | None:
    """The text the attribution check reads, or ``None`` for a binary body.

    A text body is decoded by the charset its ``Content-Type`` declares, else as UTF-8, a
    byte it cannot decode replaced. An HTML page gives its visible text and its links;
    another text body gives its text. A binary body, by its type or, sent without one, by
    its first bytes or a NUL, is not read, and its sha256 tells a change.
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
        return _Reading(_flat("".join(reader.parts)), tuple(reader.links))
    return _Reading(_flat(text), None)


def _links(page: Page, statement: Statement, reading: _Reading) -> bool:
    """Whether the page links the statement: by a link of its text, or, not HTML, its URL."""
    if reading.links is None:
        return str(statement.link) in reading.text
    wanted = (statement.link, _flat(statement.text))
    return any((urljoin(page.url, href), text) == wanted for href, text in reading.links)


def _api_document(response: Response) -> dict[str, Any] | None:
    """The body as an OpenAPI or Swagger document in JSON, or ``None`` where it is none."""
    try:
        document = json.loads(response.body)
    except ValueError:
        return None
    if isinstance(document, dict) and ("openapi" in document or "swagger" in document):
        return document
    return None


def _searched(page: Page, response: Response, text: str, recorded: list[Statement]) -> str:
    """The text the search reads: an API document's without its ``info``'s ``INFO_TERMS``.

    Each of them the document holds is checked first against the statements recorded from it.
    """
    document = _api_document(response)
    info = document.get("info") if document else None
    if document is None or not isinstance(info, dict):
        return text
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
    return _flat(json.dumps({**document, "info": rest}, ensure_ascii=False))


def _reading(page: Page, response: Response) -> _Reading | None:
    """What the check reads of a page: none of a sample or of a page no client may read."""
    return None if page.sample or _unread(page) else _read_text(response)


def check_attribution(snapshot: Snapshot, page: Page, response: Response) -> None:
    """Stop when the page states a copyright, licence or terms that the attribution lacks.

    The check reads a page's visible text, so a commented-out footer, a script's strings and
    a PDF's bytes state nothing. It stops, too, when the page no longer prints a statement
    recorded from it, or no longer links one that is a link. A terms page must print each
    statement recorded from it and is searched no further; an API document's ``info`` names
    a licence, terms or a contact only as the attribution records them from it. A sample and
    a page an anonymous client cannot read are not read.
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
    text = _searched(page, response, text, recorded)
    for words in (*(statement.text for statement in snapshot.attribution), *snapshot.vocabulary):
        text = text.replace(_flat(words), " ")
    match = _STATEMENT.search(text)
    if match:
        around = text[max(match.start() - 60, 0) : match.end() + 60]
        raise SystemExit(
            f"GET {page.url}: the page states {match.group(0)!r} ({around!r}), a copyright, "
            "licence or terms of use that the attribution does not record.\nRead it by hand "
            "and record it in the snapshot's attribution, or, where the words state nothing, "
            "narrow the check: add them to its vocabulary, which FETCHED.md lists, and say why "
            "in its capture. Nothing was written."
        )


# --- FETCHED.md ----------------------------------------------------------------------


def _iso_http_date(value: str | None) -> str:
    if value is None:
        return "-"
    return parsedate_to_datetime(value).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(value: str) -> str:
    return value.replace("|", r"\|")


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


def _note(row: Row) -> str:
    page, response = row.page, row.response
    parts = [f"redirected ({code}) to {target}" for code, target in response.redirects]
    if page.origin and response.url == page.origin:
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
    if row.note:
        parts.append(row.note)
    return "; ".join(parts) or "-"


def _attribution(snapshot: Snapshot, rows: Sequence[Row]) -> list[str]:
    """``FETCHED.md``'s Attribution: every recorded statement, as printed, and where."""
    read = {row.page.url for row in rows if _reading(row.page, row.response) is not None}
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
                text += ", a page this script does not read, so no run checks it"
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
        "page the page's. Last-Modified is the HTTP header in UTC, and ETag is as sent, in a",
        "code span, on a row that ends in a comment telling the secret scan it is no key. A",
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


def render_fetched(snapshot: Snapshot, rows: Sequence[Row], fetched: str, observed: bool) -> str:
    """The whole of ``FETCHED.md``, in the frame's one form.

    ``fetched`` is the UTC time the run started, and ``observed`` whether ``docs/upstream/``
    holds ``OBSERVED.md``.
    """
    vocabulary = []
    if snapshot.vocabulary:
        words = "; ".join(f"`{word}`" for word in snapshot.vocabulary)
        vocabulary = _paragraph(
            f"The check reads past these words, which state none here: {words}. How this is",
            "captured says why.",
        )
    capture = [part for part in snapshot.capture.split("\n\n") if part.strip()]
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
        *_attribution(snapshot, rows),
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
        *[line for part in capture for line in _paragraph(part)],
        *_how(snapshot),
    ]
    for section in snapshot.sections(rows):
        lines += [f"## {section.heading}", "", *section.text.strip("\n").splitlines(), ""]
    lines += ["## Files and pages", "", _FILES, "| --- " * 9 + "|"]
    for row in rows:
        if _unread(row.page):
            continue
        response, kept = row.response, row.page.stable
        etag = response.etag if kept and response.etag else None
        line = _row(
            [
                row.page.file or "(no file)",
                response.url,
                fetched,
                str(response.status),
                str(len(response.body)) if kept else "-",
                hashlib.sha256(response.body).hexdigest() if kept else "-",
                _code(etag) if etag else "-",
                _iso_http_date(response.last_modified),
                _note(row),
            ]
        )
        lines.append(f"{line} {ALLOWLIST}" if etag else line)
    if observed:
        lines.append(_row([OBSERVED, *["-"] * 7, HAND]))
    left_out = [
        _row(
            [
                row.page.url,
                str(row.response.status),
                urlsplit(row.response.redirects[-1][1]).netloc if row.response.redirects else "-",
                row.note or "-",
            ]
        )
        for row in rows
        if _unread(row.page)
    ]
    left_out += [
        _row([page.url, "(not requested)", "-", page.reason]) for page in snapshot.not_fetched
    ]
    lines += ["", "## Not fetched", "", _LEFT_OUT, "| --- " * 4 + "|", *left_out, ""]
    credentials = snapshot.credentials
    if credentials is None:
        lines.append(f"Regenerate: `{COMMAND}`")
    else:
        names = " and ".join(f"`{name}`" for name in credentials.variables)
        lines.append(f"Regenerate, with {names} set: `{COMMAND}`")
    return "\n".join(lines) + "\n"


# --- the write and the check ---------------------------------------------------------


def _files(rows: Sequence[Row]) -> dict[str, bytes]:
    return {row.page.file: row.content for row in rows if row.page.file and row.content is not None}


def _stale(out: Path, files: dict[str, bytes]) -> list[str]:
    """The files under the subdirectories the run writes to that it does not produce."""
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


def _measured(text: str) -> _Table:
    """Split ``FETCHED.md`` into what ``--check`` compares and what it reports."""
    table, inside, previous = _Table(), False, ""
    for line in text.splitlines():
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
