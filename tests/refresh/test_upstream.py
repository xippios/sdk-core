"""The snapshot frame, ``xippios.core.refresh`` (ADR-0046): a source's declaration run
against answers served in memory.

The tests of sdk-template's skeleton, ``tests/test_capture.py`` there (#123, #188), moved
here with the frame, a ``Snapshot`` in place of the script's constants; the frame's own
rules and its hooks follow them. ``Site`` answers every request from its routes through a
urllib handler, so no socket is opened and nothing leaves the process.
"""

import ast
import hashlib
import http.client
import io
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from xippios.core.refresh import (
    Credentials,
    NotFetched,
    Page,
    Response,
    Row,
    Section,
    Snapshot,
    Statement,
    run,
    upstream,
)

from xippios.core import refresh

BASE = "https://docs.example.org"
API = "https://api.example.org/v1"
ALLOWLIST = "<!-- pragma: allowlist secret (an ETag, not a key) -->"
TABLE_HEADER = "| File | URL | Fetched | HTTP | Bytes | sha256 | ETag | Last-Modified | Note |"
NOT_FETCHED_HEADER = "| URL | HTTP | Redirects to | Reason |"
USER_AGENT = "xippios-example refresh_upstream (+https://github.com/xippios)"
HAND = "written by hand: what upstream does but never documents; not fetched or checked"
SPLIT = "one of the files split from one page; Bytes and sha256 are the page's"
ROOT = Path(__file__).resolve().parents[2]

Answer = tuple[int, dict[str, str], bytes]


@dataclass
class Site:
    """Answers served in memory, each URL's ``(status, headers, body)``, and what was asked.

    ``later`` holds answers a URL gives in turn before its route, a 429 before its page.
    """

    routes: dict[str, Answer] = field(default_factory=dict)
    later: dict[str, list[Answer]] = field(default_factory=dict)
    requests: list[urllib.request.Request] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)

    def page(self, name: str, text: str | bytes, headers: Mapping[str, str] | None = None) -> str:
        """Serve ``text`` at ``BASE/name``, typed by its extension, and return its URL."""
        url = f"{BASE}/{name}"
        kind = mimetypes.guess_type(name)[0]
        typed = {"Content-Type": kind} if kind else {}
        body = text.encode() if isinstance(text, str) else text
        self.routes[url] = (200, {**typed, **(headers or {})}, body)
        return url

    def asked(self, url: str) -> list[urllib.request.Request]:
        """The requests sent to ``url``."""
        return [request for request in self.requests if request.full_url == url]

    def answer(self, request: urllib.request.Request) -> urllib.response.addinfourl:
        """The answer to ``request``; a URL that is not served is a network error."""
        self.requests.append(request)
        url = request.full_url
        waiting = self.later.get(url)
        if waiting:
            status, headers, body = waiting.pop(0)
        elif url in self.routes:
            status, headers, body = self.routes[url]
        else:
            raise urllib.error.URLError(f"{url} is not served")
        message = http.client.HTTPMessage()
        for name, value in headers.items():
            message[name] = value
        message["Content-Length"] = str(len(body))
        answer = urllib.response.addinfourl(io.BytesIO(body), message, url, status)
        answer.msg = http.client.responses.get(status, "")  # type: ignore[attr-defined]
        return answer


class Served(urllib.request.HTTPSHandler, urllib.request.HTTPHandler):
    """Answer every http and https request from the site.

    ``build_opener`` then adds neither of urllib's own handlers, so no socket is opened, and
    the handler's order puts it before the proxy handler.
    """

    handler_order = 50

    def __init__(self, site: Site) -> None:
        super().__init__()
        self.site = site

    def http_open(self, req: urllib.request.Request) -> Any:
        return self.site.answer(req)

    def https_open(self, req: urllib.request.Request) -> Any:
        return self.site.answer(req)


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> Site:
    """Every opener the frame builds answers from the site, and no pause waits."""
    served = Site()
    build = urllib.request.build_opener

    def build_opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
        return build(Served(served), *handlers)

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(time, "sleep", served.sleeps.append)
    return served


@pytest.fixture
def out(tmp_path: Path) -> Path:
    return tmp_path / "docs/upstream"


def declare(out: Path, *pages: Page, **fields: Any) -> Snapshot:
    """The source's declaration, as a short script holds it, with no pause."""
    return Snapshot(
        name="Example", slug="example", pages=pages, out=out, **{"pause": 0.0, **fields}
    )


def go(snapshot: Snapshot, *args: str) -> int:
    return run(snapshot, list(args))


def fetched(out: Path) -> str:
    return (out / "FETCHED.md").read_text()


def flat(text: str) -> str:
    return " ".join(text.split())


def file_row(text: str, name: str) -> str:
    (row,) = [line for line in text.splitlines() if line.startswith(f"| {name} |")]
    return row


def cells(row: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)[1:-1]]


# --- the skeleton's tests ----------------------------------------------------------------


def test_the_frame_fetches_writes_and_checks(site: Site, out: Path) -> None:
    """Rows 35 c and 67 c of sdk-template: the frame writes a file row and a row without a
    file, and ``--check`` compares without writing; the table ``Not fetched`` stands with its
    heading where it has no row (https://github.com/xippios/sdk-core/issues/363)."""
    with pytest.raises(SystemExit, match="Nothing to fetch"):
        go(declare(out))
    spec = site.page("openapi.json", '{"openapi": "3.1.0"}\n')
    site.routes[f"{BASE}/legal"] = (404, {}, b"Not Found")
    snapshot = declare(
        out,
        Page(spec, "openapi/openapi.json", note="verbatim"),
        Page(f"{BASE}/legal", status=404, note="404 Not Found"),
    )
    assert go(snapshot, "--check") == 1, "nothing is recorded yet"
    assert go(snapshot) == 0
    assert (out / "openapi/openapi.json").read_text() == '{"openapi": "3.1.0"}\n'
    text = fetched(out)
    row = r"\| \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ \| 200 \| 21 \| [0-9a-f]{64} \| "
    assert re.search(row, text), "the UTC time with Z, the status, size and sha256"
    assert f"| (no file) | {BASE}/legal | " in text
    assert "| 404 |" in text
    assert f"{TABLE_HEADER}\n" in text
    assert "None stated: no page this script reads states" in flat(text)
    empty = f"## Not fetched\n\n{NOT_FETCHED_HEADER}\n| --- | --- | --- | --- |\n\nRegenerate"
    assert empty in text, "the heading and the table stand with no row"
    assert go(snapshot, "--check") == 0, "Fetched aside, all the same"
    site.page("openapi.json", '{"openapi": "3.1.1"}\n')
    assert go(snapshot, "--check") == 1
    assert (out / "openapi/openapi.json").read_text() == '{"openapi": "3.1.0"}\n', "unwritten"


def test_a_statement_the_attribution_lacks_stops_the_run(site: Site, out: Path) -> None:
    """Row 35 b of sdk-template: every run checks the attribution and stops before writing
    on a copyright, licence or terms it does not record; a recorded one is quoted under
    Attribution with no second period after its own (#123)."""
    url = site.page("guide.html", "<p>Guide</p><footer>&copy; 2026 Example Ltd.</footer>\n")
    with pytest.raises(SystemExit, match="attribution does not record"):
        go(declare(out, Page(url, "pages/guide.html")))
    assert not out.exists(), "nothing written"
    statement = Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", url, "the footer")
    assert go(declare(out, Page(url, "pages/guide.html"), attribution=(statement,))) == 0
    text = flat(fetched(out))
    assert f"`\N{COPYRIGHT SIGN} 2026 Example Ltd.`, printed at {url}: the footer" in text
    assert "Ltd.`." not in text, "a statement's own period takes no second one"


def test_a_comment_a_pdf_and_a_moving_last_modified_are_no_change(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#123's proof: a copyright line inside an HTML comment, a PDF, and a page whose
    Last-Modified moves pass ``--check`` twice in a row, the moved Last-Modified an
    information line."""
    commented = "<html><body><!-- <div>&copy; 2019 Old Owner</div> --><p>Guide</p></body></html>"
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Producer (\xa9 2026 Example) >>\n%%EOF\n"
    moving = site.page(
        "moving.html", "<p>Moving</p>", {"Last-Modified": "Mon, 16 Nov 2026 10:00:00 GMT"}
    )
    snapshot = declare(
        out,
        Page(site.page("guide.html", commented), "pages/guide.html"),
        Page(site.page("layout.pdf", pdf), "files/layout.pdf"),
        Page(moving, "pages/moving.html"),
    )
    assert go(snapshot) == 0
    for step, day in enumerate(("Tue, 17", "Wed, 18"), start=1):
        site.page("moving.html", "<p>Moving</p>", {"Last-Modified": f"{day} Nov 2026 10:00:00 GMT"})
        capsys.readouterr()
        assert go(snapshot, "--check") == 0, f"check {step}"
        output = capsys.readouterr().out
        assert "differs" not in output
        assert re.search(r"moved, no change: pages/moving\.html .*Last-Modified", output)


@pytest.mark.parametrize(
    "text",
    [
        "Read the Terms\nof Use first.",
        "Read the Terms&nbsp;of&nbsp;Use first.",
        "All rights reserved.",
        "See the Terms and Conditions.",
        "Licensed under Creative Commons.",
        "Shared under CC BY 4.0.",
    ],
)
def test_the_check_reads_the_visible_text_and_knows_the_statements(
    site: Site, out: Path, text: str
) -> None:
    """#123: the search crosses a line break and a no-break space and knows each phrase the
    sources met; a script's strings and a style's names state nothing."""
    quiet = "<script>var license = 'MIT';</script><style>.copyright { color: red }</style>"
    url = site.page("quiet.html", f"<p>Guide</p>{quiet}")
    assert go(declare(out, Page(url, "pages/q.html"))) == 0
    url = site.page("page.html", f"<p>{text}</p>")
    with pytest.raises(SystemExit, match="attribution does not record"):
        go(declare(out, Page(url, "pages/page.html")))


def test_each_statement_is_required_on_its_page_and_a_link_where_it_links(
    site: Site, out: Path
) -> None:
    """#123: a statement is recorded with its page and checked there, a link by its target;
    a page that no longer prints or links it stops the run."""
    footer = "<footer>&copy; 2026 Example Ltd. <a href='{}'>Terms of Service</a></footer>"
    url = site.page("index.html", footer.format("https://example.org/tos"))
    snapshot = declare(
        out,
        Page(url, "pages/index.html"),
        attribution=(
            Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", url, "the footer"),
            Statement("Terms of Service", url, "the footer", "https://example.org/tos"),
        ),
    )
    assert go(snapshot) == 0
    assert "`Terms of Service`, a link to https://example.org/tos" in flat(fetched(out))
    site.page("index.html", footer.format("https://example.org/terms"))
    with pytest.raises(SystemExit, match="no longer links 'Terms of Service'"):
        go(snapshot)
    site.page("index.html", "<footer><a href='https://example.org/tos'>Terms of Service</a>")
    with pytest.raises(SystemExit, match="no longer prints"):
        go(snapshot)


def test_a_terms_page_must_print_its_lines_and_is_searched_no_further(
    site: Site, out: Path
) -> None:
    """#123: a page that is itself the terms requires its quoted lines and nothing else on it
    stops the run; a terms page with no line recorded is refused."""
    terms = "<h1>License Agreement</h1><p>We grant you a license to distribute the data.</p>"
    url = site.page("terms.html", terms)
    page = Page(url, "terms/terms.html", terms=True)
    with pytest.raises(SystemExit, match="records no statement from it"):
        go(declare(out, page))
    snapshot = declare(out, page, attribution=(Statement("License Agreement", url, "the title"),))
    assert go(snapshot) == 0
    site.page("terms.html", "<h1>Data Agreement</h1><p>A license to distribute.</p>")
    with pytest.raises(SystemExit, match="no longer prints 'License Agreement'"):
        go(snapshot)


def test_the_check_narrows_by_a_vocabulary_that_fetched_md_lists(site: Site, out: Path) -> None:
    """#123: the stop names the second way out, words that state nothing, which the search
    then reads past and FETCHED.md lists."""
    page = Page(site.page("trade.html", "<p>An import license is required.</p>"), "p/t.html")
    with pytest.raises(SystemExit, match="vocabulary") as stop:
        go(declare(out, page))
    assert "capture" in str(stop.value)
    assert go(declare(out, page, vocabulary=("import license",))) == 0
    assert "`import license`" in fetched(out)


def test_a_page_in_its_declared_charset_is_read(site: Site, out: Path) -> None:
    """Finding 1 of sdk-template#188: a text page is decoded by the charset its Content-Type
    declares, and one that declares none and is not UTF-8 is read with replacement; only a
    binary body goes unread, a PDF sent without a type among them."""
    footer = "<p>Guide</p><footer>\N{COPYRIGHT SIGN} 2026 Example Ltd.</footer>"
    url = f"{BASE}/latin.html"
    site.routes[url] = (
        200,
        {"Content-Type": "text/html; charset=iso-8859-1"},
        footer.encode("latin-1"),
    )
    with pytest.raises(SystemExit, match="attribution does not record"):
        go(declare(out, Page(url, "pages/latin.html")))
    statement = Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", url)
    assert go(declare(out, Page(url, "pages/latin.html"), attribution=(statement,))) == 0
    site.routes[f"{BASE}/untyped.html"] = (200, {}, b"<p>All rights reserved \xa9 2026</p>")
    with pytest.raises(SystemExit, match="attribution does not record"):
        go(declare(out, Page(f"{BASE}/untyped.html", "pages/untyped.html")))
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n<< /Producer (Copyright 2026 Example) >>\n%%EOF\n"
    site.routes[f"{BASE}/layout"] = (200, {}, pdf)
    assert go(declare(out, Page(f"{BASE}/layout", "files/layout.pdf"))) == 0


def test_a_statement_names_a_page_the_run_captures(site: Site, out: Path) -> None:
    """Finding 2 of sdk-template#188: a statement whose page is no page of the run, such as
    its URL without the trailing slash, would never be checked, so the run stops and names
    it."""
    site.routes[f"{BASE}/docs/"] = (
        200,
        {"Content-Type": "text/html"},
        b"<footer>&copy; 2026 Ex</footer>",
    )
    page = Page(f"{BASE}/docs/", "pages/docs.html")
    statement = Statement("\N{COPYRIGHT SIGN} 2026 Ex", f"{BASE}/docs", "the footer")
    with pytest.raises(SystemExit, match=f"from {re.escape(BASE)}/docs, a page this run"):
        go(declare(out, page, attribution=(statement,)))
    assert not out.exists(), "nothing written"
    statement = Statement(statement.text, f"{BASE}/docs/", "the footer")
    assert go(declare(out, page, attribution=(statement,))) == 0


def test_a_statement_on_a_page_the_check_does_not_read_is_quoted_as_unchecked(
    site: Site, out: Path
) -> None:
    """The second review of sdk-template#188: a statement recorded from a page whose text
    the check does not read, a PDF here, is quoted with its page as one no run checks; one on
    a page it reads is quoted as printed there."""
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n<< /Producer (Copyright 2026 Example) >>\n%%EOF\n"
    pdf_url = site.page("layout.pdf", pdf)
    html_url = site.page("guide.html", "<footer>&copy; 2026 Example Ltd.</footer>")
    snapshot = declare(
        out,
        Page(html_url, "pages/guide.html"),
        Page(pdf_url, "f/l.pdf"),
        attribution=(
            Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", html_url, "the footer"),
            Statement("Copyright 2026 Example", pdf_url, "the PDF's producer"),
        ),
    )
    assert go(snapshot) == 0
    text = flat(fetched(out))
    unchecked = "a page this script does not read, so no run checks it"
    assert f"printed at {pdf_url}, {unchecked}: the PDF's producer" in text
    assert f"printed at {html_url}: the footer" in text


def test_a_line_only_a_browser_shows_is_quoted_and_never_checked(site: Site, out: Path) -> None:
    """#123: a copyright line that a script assembles in the browser is recorded without a
    page, quoted under Attribution as such, and no run looks for it."""
    page = Page(site.page("app.html", "<div id='app'></div>"), "pages/app.html")
    statement = Statement("Copyright (c) United Nations", "", "the footer, read on 2026-11-18")
    assert go(declare(out, page, attribution=(statement,))) == 0
    assert "`Copyright (c) United Nations`, which only a browser shows" in flat(fetched(out))


@pytest.mark.parametrize(
    ("name", "value", "quoted"),
    [
        ("license", {"name": "CC BY 4.0", "url": "https://example.org/by"}, "CC BY 4.0"),
        ("termsOfService", "https://example.org/terms", "https://example.org/terms"),
        ("contact", {"email": "data@example.org"}, "data@example.org"),
    ],
)
def test_an_api_documents_info_states_only_what_the_attribution_records(
    site: Site, out: Path, name: str, value: Any, quoted: str
) -> None:
    """#123: an API document's ``info`` that names a licence, terms or a contact stops the
    run until the attribution records it from that document."""
    document = {"openapi": "3.1.0", "info": {"title": "Example", name: value}, "paths": {}}
    url = site.page("openapi.json", json.dumps(document))
    page = Page(url, "openapi/openapi.json")
    with pytest.raises(SystemExit, match=f"info.{name} names"):
        go(declare(out, page))
    assert go(declare(out, page, attribution=(Statement(quoted, url, f"info.{name}"),))) == 0


def test_check_compares_content_after_canonical(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#123: a document served in a new order is a change by its bytes, and none once the
    source's ``canonical`` fixes the order; its row's moved sha256 is an information line."""
    url = site.page("openapi.json", '{"openapi": "3.1.0", "paths": {}}')
    page = Page(url, "openapi/openapi.json")
    assert go(declare(out, page)) == 0
    site.page("openapi.json", '{"paths": {}, "openapi": "3.1.0"}')
    assert go(declare(out, page), "--check") == 1

    def canonical(page: Page, body: bytes) -> bytes:
        return json.dumps(json.loads(body), sort_keys=True).encode()

    capsys.readouterr()
    assert go(declare(out, page, canonical=canonical), "--check") == 0
    assert "moved, no change: openapi/openapi.json" in capsys.readouterr().out


def test_a_page_rendered_again_with_the_same_text_is_no_change(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#123: a converted page whose HTML moves, a nonce in a script, while its converted text
    stays, is no change to ``--check``; only its row's measures move."""
    url = site.page("guide.html", "<p>Guide</p><script>nonce='a1'</script>")

    def reduce(page: Page, response: Response) -> bytes:
        return re.sub(rb"<script>.*</script>", b"", response.body)

    snapshot = declare(out, Page(url, "pages/guide.md", note="converted"), reduce=reduce)
    assert go(snapshot) == 0
    site.page("guide.html", "<p>Guide</p><script>nonce='b2c3'</script>")
    capsys.readouterr()
    assert go(snapshot, "--check") == 0
    assert re.search(r"moved, no change: pages/guide\.md .*Bytes .*sha256", capsys.readouterr().out)


def test_a_volatile_body_keeps_last_modified_and_its_own_note(site: Site, out: Path) -> None:
    """#123: ``stable=False`` drops what names the bytes, size, sha256 and ETag, keeps the
    Last-Modified, and the row's note is the page's own."""
    headers = {"Last-Modified": "Mon, 16 Nov 2026 10:00:00 GMT", "ETag": '"v1"'}
    url = site.page("missing.html", "<p>Not here</p>", headers)
    assert go(declare(out, Page(url, stable=False, note="a status page with a nonce"))) == 0
    row = cells(file_row(fetched(out), "(no file)"))
    assert row[4:7] == ["-", "-", "-"]
    assert row[7] == "2026-11-16T10:00:00Z"
    assert row[8] == "a status page with a nonce"


def test_a_page_read_from_another_follows_it(site: Site, out: Path) -> None:
    """#123: ``linked`` names the pages a page gives the URL of, captured right after it."""
    newest = site.page("release-7.html", "<p>Release 7</p>")
    index = site.page("releases.html", f"<a href='{newest}'>Release 7</a>")

    def linked(row: Row) -> tuple[Page, ...]:
        if row.page.url != index:
            return ()
        href = re.search(rb"href='([^']+)'", row.response.body)
        assert href is not None
        return (Page(href[1].decode(), "pages/release.html", note="the newest"),)

    snapshot = declare(
        out,
        Page(index, "pages/releases.html"),
        Page(site.page("about.html", "<p>About</p>"), "pages/about.html"),
        linked=linked,
    )
    assert go(snapshot) == 0
    files = re.findall(r"^\| (pages/\S+) \|", fetched(out), re.MULTILINE)
    assert files == ["pages/releases.html", "pages/release.html", "pages/about.html"]


def test_the_page_that_names_the_api_document_must_go_on_naming_it(site: Site, out: Path) -> None:
    """#123: a row with no file for the page that names the API document stops the run once
    the page no longer holds its URL."""
    spec = f"{BASE}/openapi.json"
    url = site.page("swagger.html", f"<script>ui({{url: '{spec}'}})</script>")
    snapshot = declare(out, Page(url, names=spec, stable=False, note="names the API document"))
    assert go(snapshot) == 0
    assert f"| (no file) | {url} |" in fetched(out)
    site.page("swagger.html", "<script>ui({url: '/v2.json'})</script>")
    with pytest.raises(SystemExit, match="no longer holds"):
        go(snapshot)


def test_observed_md_has_its_row_and_is_left_as_written(site: Site, out: Path) -> None:
    """Conventions §3: OBSERVED.md, written by hand, has a row of its own, whose first cell is
    the file's name and whose last says so, which the family check matches (step 6 of sdk-core
    0.4.1); the frame neither writes nor checks it."""
    snapshot = declare(out, Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html"))
    assert go(snapshot) == 0
    assert "| OBSERVED.md |" not in fetched(out), "listed where it exists"
    notes = "# Observed\n\nThe API answers 200 with an empty list where it documents a 404.\n"
    (out / "OBSERVED.md").write_text(notes)
    assert go(snapshot, "--check") == 1, "FETCHED.md does not list it yet"
    assert go(snapshot) == 0
    row = cells(file_row(fetched(out), "OBSERVED.md"))
    assert row[0] == "OBSERVED.md"
    assert row[1:8] == ["-"] * 7
    assert row[8] == HAND
    assert (out / "OBSERVED.md").read_text() == notes
    assert go(snapshot, "--check") == 0
    with pytest.raises(SystemExit, match="written by hand"):
        go(declare(out, Page(site.page("o.html", "<p>O</p>"), "OBSERVED.md")))


def test_not_fetched_lists_the_pages_left_out_and_those_no_anonymous_client_reads(
    site: Site, out: Path
) -> None:
    """Conventions §3 and sdk-template#41: a page left out has a row with its reason; a page
    behind a login is requested once, its redirect to another host never followed, and its
    row gives the status and that host; a redirect on the page's host is followed and noted
    (https://github.com/xippios/sdk-core/issues/320)."""
    site.routes[f"{BASE}/admin"] = (302, {"Location": "https://login.example.net/sso"}, b"")
    site.routes[f"{BASE}/old.html"] = (301, {"Location": f"{BASE}/guide.html"}, b"")
    site.routes[f"{BASE}/members"] = (403, {"Content-Type": "text/html"}, b"<p>Forbidden</p>")
    site.page("guide.html", "<p>Guide</p>")
    with pytest.raises(SystemExit, match="to another host"):
        go(declare(out, Page(f"{BASE}/admin", note="a login")))
    feed = "https://example.org/feed.xml"
    snapshot = declare(
        out,
        Page(f"{BASE}/old.html", "pages/guide.html"),
        Page(f"{BASE}/admin", status=302, note="a login on another host"),
        Page(f"{BASE}/members", status=403, note="members only"),
        not_fetched=(NotFetched(feed, "a feed"),),
    )
    assert go(snapshot) == 0
    text = fetched(out)
    assert f"redirected (301) to {BASE}/guide.html" in text
    assert f"## Not fetched\n\n{NOT_FETCHED_HEADER}\n" in text
    assert f"| {BASE}/admin | 302 | login.example.net | a login on another host |" in text
    assert f"| {BASE}/members | 403 | - | members only |" in text
    assert f"| {feed} | (not requested) | - | a feed |" in text
    assert f"| (no file) | {BASE}/admin |" not in text
    assert not site.asked("https://login.example.net/sso"), "the other host is never asked"


def test_a_sample_is_kept_under_samples_and_says_so(site: Site, out: Path) -> None:
    """Conventions §3: an answer sample lives under ``samples/``, its row says it is one, and
    it is not searched, being an answer and no documentation."""
    url = site.page("items.json", '{"items": [{"license": "L-1"}]}')
    with pytest.raises(SystemExit, match="under samples/"):
        go(declare(out, Page(url, "pages/items.json", sample=True)))
    assert go(declare(out, Page(url, "samples/items.json", sample=True))) == 0
    row = file_row(fetched(out), "samples/items.json")
    assert f"| {url} |" in row
    assert "a sample" in row


def test_a_row_with_an_etag_passes_the_secret_scan(site: Site, out: Path, tmp_path: Path) -> None:
    """sdk-template#42 carrying #47, and https://github.com/xippios/sdk-core/issues/340: the
    row of a quoted ETag of hex digits holds it in a code span and ends in the scan's
    allowlist mark, so the hook passes FETCHED.md against sdk-core's unchanged baseline;
    without the mark the same row is flagged, the code span alone being no exemption."""
    etag = '"' + hashlib.md5(b"an object store's ETag", usedforsecurity=False).hexdigest() + '"'
    site.page("openapi.json", '{"openapi": "3.1.0"}', {"ETag": etag})
    assert go(declare(out, Page(f"{BASE}/openapi.json", "openapi/openapi.json"))) == 0
    text = fetched(out)
    (row,) = [line for line in text.splitlines() if etag in line]
    assert f"| `{etag}` |" in row
    assert row.endswith(f" | {ALLOWLIST}")
    scan = tmp_path / "scan"
    scan.mkdir()
    shutil.copy(ROOT / ".secrets.baseline", scan / ".secrets.baseline")
    (scan / "FETCHED.md").write_text(text)
    (scan / "unmarked.md").write_text(text.replace(f" {ALLOWLIST}", ""))
    hook = [
        sys.executable,
        "-m",
        "detect_secrets.pre_commit_hook",
        "--baseline",
        ".secrets.baseline",
    ]
    passed = subprocess.run(
        [*hook, "FETCHED.md"], cwd=scan, capture_output=True, text=True, check=False
    )
    assert passed.returncode == 0, passed.stdout + passed.stderr
    flagged = subprocess.run(
        [*hook, "unmarked.md"], cwd=scan, capture_output=True, text=True, check=False
    )
    assert flagged.returncode == 1, "without the mark the ETag must be flagged"
    assert "Hex High Entropy String" in flagged.stdout, flagged.stdout


# --- the frame's own rules ---------------------------------------------------------------


def test_every_etag_stands_in_a_code_span_with_the_mark(site: Site, out: Path) -> None:
    """https://github.com/xippios/sdk-core/issues/363, part 4: every ETag, hex or not, is
    written in a code span on a row that ends in the allowlist mark, with no test for hex; a
    row without an ETag carries neither."""
    site.page("a.html", "<p>A</p>", {"ETag": 'W/"5-abc"'})
    site.page("b.html", "<p>B</p>", {"ETag": '"a`b"'})
    site.page("c.html", "<p>C</p>")
    snapshot = declare(
        out,
        Page(f"{BASE}/a.html", "pages/a.html"),
        Page(f"{BASE}/b.html", "pages/b.html"),
        Page(f"{BASE}/c.html", "pages/c.html"),
    )
    assert go(snapshot) == 0
    text = fetched(out)
    weak = file_row(text, "pages/a.html")
    assert cells(weak)[6] == '`W/"5-abc"`'
    assert weak.endswith(f" | {ALLOWLIST}")
    assert cells(file_row(text, "pages/b.html"))[6] == '``"a`b"``', "a longer fence"
    plain = file_row(text, "pages/c.html")
    assert cells(plain)[6] == "-"
    assert ALLOWLIST not in plain
    assert go(snapshot, "--check") == 0


def test_the_user_agent_and_the_pause_are_the_snapshots(site: Site, out: Path) -> None:
    """The frame identifies itself by the source's slug and pauses before every request as
    long as the snapshot says (sdk-eurostat's five seconds), stated in FETCHED.md."""
    page = Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html")
    assert go(declare(out, page, pause=5.0)) == 0
    (request,) = site.requests
    assert request.get_header("User-agent") == USER_AGENT
    assert site.sleeps == [5.0]
    assert f"5 s apart, each retried at most once, identified as `{USER_AGENT}`" in flat(
        fetched(out)
    )


def test_a_5xx_is_retried_once(site: Site, out: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The skeleton's fetch: a 5xx or a network error is retried once after RETRY_PAUSE, and a
    second one stops the run."""
    url = site.page("guide.html", "<p>Guide</p>")
    site.later[url] = [(503, {}, b"")]
    assert go(declare(out, Page(url, "pages/guide.html"))) == 0
    assert site.sleeps == [0.0, 10.0], "the pause, then RETRY_PAUSE"
    assert len(site.asked(url)) == 2
    assert "retrying once in 10 s" in capsys.readouterr().out
    site.later[url] = [(503, {}, b""), (502, {}, b"")]
    with pytest.raises(SystemExit, match=r"\(after one retry\)"):
        go(declare(out, Page(url, "pages/guide.html")))


def test_two_pages_never_write_one_file(site: Site, out: Path) -> None:
    """A file is one page's: two rows that would write one file stop the run before any
    write."""
    one = Page(site.page("a.html", "<p>A</p>"), "pages/same.html")
    two = Page(site.page("b.html", "<p>B</p>"), "pages/same.html")
    with pytest.raises(SystemExit, match=r"pages/same\.html: written by two pages"):
        go(declare(out, one, two))
    assert not out.exists()


def test_the_frame_imports_the_standard_library_alone() -> None:
    """https://github.com/xippios/sdk-core/issues/363, part 1: the frame needs no extra and
    pins no converter, which stays the source's own dependency."""
    tree = ast.parse(Path(upstream.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)


# --- the hooks ---------------------------------------------------------------------------


def login_counter(site: Site, calls: list[int]) -> Credentials:
    """Credentials whose login records how many requests went before it."""

    def login() -> Mapping[str, str]:
        calls.append(len(site.requests))
        return {"X-Session": "session-of-the-login"}

    return Credentials(("EXAMPLE_ACCOUNT", "EXAMPLE_LOGIN"), f"{API}/", login)


def keyed_snapshot(site: Site, out: Path, calls: list[int]) -> Snapshot:
    guide = site.page("guide.html", "<p>Guide</p>")
    site.routes[f"{API}/items"] = (200, {"Content-Type": "application/json"}, b'{"items": []}')
    site.routes[f"{API}/codes"] = (200, {"Content-Type": "application/json"}, b'{"codes": []}')
    return declare(
        out,
        Page(guide, "pages/guide.html"),
        Page(f"{API}/items", "samples/items.json", sample=True, keyed=True),
        Page(f"{API}/codes", "samples/codes.json", sample=True, keyed=True),
        credentials=login_counter(site, calls),
    )


def test_a_keyed_sample_alone_sends_the_credentials(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Conventions §3 and ADR-0028, decision 7 (sdk-faostat's samples): the frame logs in
    once, right before the first keyed sample, sends what the login gives on the keyed
    samples alone, and prints none of it; FETCHED.md names the variables, never a value."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", "placeholder")
    calls: list[int] = []
    snapshot = keyed_snapshot(site, out, calls)
    assert go(snapshot) == 0
    assert calls == [1], "one login, after the keyless page"
    guide, items, codes = site.requests
    assert guide.get_header("X-session") is None
    assert items.get_header("X-session") == codes.get_header("X-session") == "session-of-the-login"
    output = capsys.readouterr().out
    assert "session-of-the-login" not in output
    text = fetched(out)
    assert "session-of-the-login" not in text
    assert "someone" not in text
    assert "Regenerate, with `EXAMPLE_ACCOUNT` and `EXAMPLE_LOGIN` set: `uv run" in text
    assert "Only the keyed samples send a credential" in flat(text)
    assert (out / "samples/items.json").read_bytes() == b'{"items": []}'


def test_a_keyed_sample_follows_no_redirect_and_is_never_retried(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sdk-faostat's rule: a request with the credentials reaches the base alone, so a
    redirect stops the run unfollowed, and a 5xx costs one keyed call and stops it."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", "placeholder")
    calls: list[int] = []
    snapshot = keyed_snapshot(site, out, calls)
    site.routes[f"{API}/items"] = (302, {"Location": f"{API}/items/"}, b"")
    with pytest.raises(SystemExit, match="a keyed request follows no redirect"):
        go(snapshot)
    assert not site.asked(f"{API}/items/")
    snapshot = keyed_snapshot(site, out, calls)
    site.later[f"{API}/items"] = [(503, {}, b"")]
    site.requests.clear()
    with pytest.raises(SystemExit, match="a keyed request is not retried"):
        go(snapshot)
    assert len(site.asked(f"{API}/items")) == 1
    assert not out.exists(), "nothing written"


def test_the_credentials_are_checked_by_name_before_anything_is_fetched(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sdk-faostat's rule: an unset variable stops the run, named, before the first request."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.delenv("EXAMPLE_LOGIN", raising=False)
    calls: list[int] = []
    with pytest.raises(SystemExit, match="EXAMPLE_LOGIN is not set") as stop:
        go(keyed_snapshot(site, out, calls))
    assert "--keyless" in str(stop.value)
    assert not site.requests
    assert not calls


def test_keyless_compares_the_pages_that_send_no_credential(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """sdk-faostat's ``--keyless``, a free trial before a run that spends keyed calls: it
    fetches and compares the pages that send no credential, logs in nowhere and writes
    nothing; a snapshot without credentials has no such option."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", "placeholder")
    calls: list[int] = []
    snapshot = keyed_snapshot(site, out, calls)
    assert go(snapshot) == 0
    monkeypatch.delenv("EXAMPLE_LOGIN")
    site.requests.clear()
    assert go(snapshot, "--keyless") == 0
    assert calls == [1], "no second login"
    assert [request.full_url for request in site.requests] == [f"{BASE}/guide.html"]
    site.page("guide.html", "<p>Guide, revised</p>")
    before = fetched(out)
    assert go(snapshot, "--keyless") == 1
    assert "differs: pages/guide.html" in capsys.readouterr().out
    assert fetched(out) == before, "nothing written"
    with pytest.raises(SystemExit):
        go(declare(out, Page(f"{BASE}/guide.html", "pages/guide.html")), "--keyless")


def test_a_keyed_page_is_a_sample_under_the_credentials_base(site: Site, out: Path) -> None:
    """Conventions §3: only a sample's request sends a credential, and only to the base the
    credentials name; a keyed page without credentials is refused before any request."""
    calls: list[int] = []
    credentials = login_counter(site, calls)
    pages = [
        (Page(f"{API}/items", "pages/items.json", keyed=True), credentials),
        (Page(f"{BASE}/items", "samples/items.json", sample=True, keyed=True), credentials),
        (Page(f"{API}/items", "samples/items.json", sample=True, keyed=True), None),
    ]
    for page, given in pages:
        with pytest.raises(SystemExit, match="keyed"):
            go(declare(out, page, credentials=given), "--keyless" if given else "--check")
    assert not site.requests


def test_a_file_kept_as_recorded_where_only_noise_moved(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """sdk-eurostat's WADL: a page marked ``keep_recorded`` whose content is the recorded
    file's after ``canonical`` leaves the file as it is in a writing run, so a refresh shows
    real changes only; a real change is written, and an unmarked page is written as
    fetched."""
    url = site.page("api.wadl", "<a/>\n<b/>\n")

    def canonical(page: Page, content: bytes) -> bytes:
        return b"\n".join(sorted(content.split(b"\n")))

    kept = declare(out, Page(url, "wadl/api.wadl", keep_recorded=True), canonical=canonical)
    assert go(kept) == 0
    site.page("api.wadl", "<b/>\n<a/>\n")
    capsys.readouterr()
    assert go(kept) == 0
    assert (out / "wadl/api.wadl").read_bytes() == b"<a/>\n<b/>\n"
    assert "wadl/api.wadl: the same after canonical, kept as recorded" in capsys.readouterr().out
    assert "kept as recorded while" in file_row(fetched(out), "wadl/api.wadl")
    assert go(kept, "--check") == 0
    site.page("api.wadl", "<b/>\n<c/>\n")
    assert go(kept) == 0
    assert (out / "wadl/api.wadl").read_bytes() == b"<b/>\n<c/>\n"
    site.page("api.wadl", "<c/>\n<b/>\n")
    assert go(declare(out, Page(url, "wadl/api.wadl"), canonical=canonical)) == 0
    assert (out / "wadl/api.wadl").read_bytes() == b"<c/>\n<b/>\n", "unmarked: as fetched"


def test_one_page_gives_several_files(site: Site, out: Path) -> None:
    """sdk-cashctrl's one page: ``split`` makes a file per entry from a page marked
    ``split``, each with a row that holds the page's URL, size and sha256 and says so; a split
    that gives no file, a hand-written file's name, or a page that also names a file is
    refused before any write."""
    body = "<h1>A</h1><p>alpha</p><h1>B</h1><p>beta</p>"
    url = site.page("index.html", body)

    def split(page: Page, response: Response) -> dict[str, bytes]:
        parts = re.findall(rb"<h1>(\w)</h1><p>(\w+)</p>", response.body)
        return {f"{name.decode().lower()}.md": text + b"\n" for name, text in parts}

    snapshot = declare(out, Page(url, split=True, note="one file per heading"), split=split)
    assert go(snapshot) == 0
    assert (out / "a.md").read_bytes() == b"alpha\n"
    assert (out / "b.md").read_bytes() == b"beta\n"
    text = fetched(out)
    digest = hashlib.sha256(body.encode()).hexdigest()
    for name in ("a.md", "b.md"):
        row = cells(file_row(text, name))
        assert row[1] == url
        assert row[4:6] == [str(len(body)), digest]
        assert row[8] == f"{SPLIT}; one file per heading"
    assert go(snapshot, "--check") == 0
    for given, stop in [
        (lambda page, response: {}, "gives no file"),
        (lambda page, response: {"OBSERVED.md": b"x"}, "written by hand"),
    ]:
        with pytest.raises(SystemExit, match=stop):
            go(declare(out, Page(url, split=True), split=given))
    with pytest.raises(SystemExit, match="split"):
        go(declare(out, Page(url, "pages/index.md", split=True), split=split))
    with pytest.raises(SystemExit, match="split"):
        go(declare(out, Page(url, split=True)))


def test_a_page_refused_with_403_is_kept_from_the_second_origin(site: Site, out: Path) -> None:
    """sdk-usda-wasde's CDN origin (conventions §2): where the page's URL answers 403, that
    answer is a row of ``Not fetched`` and the file is kept from the publisher's second
    origin, whose answer ``reduce`` reads; where it answers 200, the page is kept from there
    and the origin is never asked."""
    canonical = f"{BASE}/faq"
    origin = "https://origin.example.net/faq"
    site.routes[canonical] = (403, {"Content-Type": "text/html"}, b"<p>Access Denied</p>")
    site.routes[origin] = (200, {"Content-Type": "text/html"}, b"<p>FAQ</p>")
    seen: list[tuple[str, str]] = []

    def reduce(page: Page, response: Response) -> bytes:
        seen.append((page.url, response.url))
        return response.body

    snapshot = declare(
        out, Page(canonical, "pages/faq.html", origin=origin, note="the FAQ"), reduce=reduce
    )
    assert go(snapshot) == 0
    assert (out / "pages/faq.html").read_bytes() == b"<p>FAQ</p>"
    assert seen == [(canonical, origin)]
    text = fetched(out)
    row = cells(file_row(text, "pages/faq.html"))
    assert row[1] == origin
    copy = f"the copy of {canonical}, which answers 403, from the publisher's second origin"
    assert row[8] == f"{copy}; the FAQ"
    refused = f"answers 403 to this script; kept from {origin}"
    assert f"| {canonical} | 403 | - | {refused} |" in text
    site.routes[canonical] = (200, {"Content-Type": "text/html"}, b"<p>FAQ</p>")
    site.requests.clear()
    assert go(snapshot) == 0
    assert cells(file_row(fetched(out), "pages/faq.html"))[1] == canonical
    assert not site.asked(origin)
    with pytest.raises(SystemExit, match="second origin"):
        go(declare(out, Page(canonical, origin=origin)))


def test_a_429_waits_as_the_snapshot_says_then_retries_once(site: Site, out: Path) -> None:
    """sdk-eurostat's quota: with ``quota_wait`` a 429 is retried once, after the wait the
    hook reads from its headers, and FETCHED.md says so; without it a 429 stops the run, and
    a second 429 stops it after the one retry."""
    url = site.page("data.html", "<p>Data</p>")

    def quota_wait(headers: Message) -> float:
        return float(str(headers.get("Retry-After", "60")))

    snapshot = declare(out, Page(url, "pages/data.html"), quota_wait=quota_wait)
    site.later[url] = [(429, {"Retry-After": "30"}, b"")]
    assert go(snapshot) == 0
    assert 30.0 in site.sleeps
    assert len(site.asked(url)) == 2
    assert "each retried at most once, a 429 after the wait it names" in flat(fetched(out))
    site.later[url] = [(429, {}, b"")]
    with pytest.raises(SystemExit, match="HTTP 429"):
        go(declare(out, Page(url, "pages/data.html")))
    site.later[url] = [(429, {}, b""), (429, {}, b"")]
    with pytest.raises(SystemExit, match=r"429 .*\(after one retry\)"):
        go(snapshot)


def test_a_section_of_the_sources_own_stands_before_the_files(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """sdk-comtrade's "Products found": ``sections`` adds a section of the source's own,
    made from the rows, after "How this is captured", whose paragraphs ``capture`` holds;
    ``--check`` counts a change to it."""
    url = site.page("bundle.txt", "products: comtrade, tariffline")

    def sections(rows: Sequence[Row]) -> list[Section]:
        names = rows[0].response.body.decode().split(": ")[1].split(", ")
        table = "\n".join(["| Product |", "| --- |", *(f"| {name} |" for name in names)])
        return [Section("Products found", table)]

    snapshot = declare(
        out,
        Page(url, note="the bundle"),
        sections=sections,
        capture="The first paragraph.\n\nThe second paragraph.",
    )
    assert go(snapshot) == 0
    text = fetched(out)
    assert "## How this is captured\n\nThe first paragraph.\n\nThe second paragraph.\n\n" in text
    section = "## Products found\n\n| Product |\n| --- |\n| comtrade |\n| tariffline |\n\n## Files"
    assert section in text
    assert text.index("## How this is captured") < text.index("## Products found")
    assert go(snapshot, "--check") == 0
    site.page("bundle.txt", "products: comtrade")
    capsys.readouterr()
    assert go(snapshot, "--check") == 1
    assert "differs: FETCHED.md" in capsys.readouterr().out


def test_a_rows_note_is_made_from_its_answer(site: Site, out: Path) -> None:
    """sdk-faostat's and the FAS kit's notes, which count what the answer holds: ``note``
    makes the row's note from the row, and stops the run with ``changed`` on an answer it does
    not recognise, before anything is written."""
    url = site.page("openapi.json", '{"openapi": "3.1.0", "paths": {"/a": {}, "/b": {}}}')

    def note(row: Row) -> str:
        document = json.loads(row.response.body)
        if "paths" not in document:
            raise refresh.changed(row.page.url, "no paths")
        return f"{row.note}; {len(document['paths'])} paths"

    snapshot = declare(out, Page(url, "openapi/openapi.json", note="verbatim"), note=note)
    assert go(snapshot) == 0
    assert cells(file_row(fetched(out), "openapi/openapi.json"))[8] == "verbatim; 2 paths"
    before = fetched(out)
    site.page("openapi.json", '{"openapi": "3.1.0"}')
    with pytest.raises(SystemExit, match=r"openapi\.json changed: no paths"):
        go(snapshot)
    assert fetched(out) == before
