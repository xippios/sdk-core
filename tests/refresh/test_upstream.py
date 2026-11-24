"""The snapshot frame, ``xippios.core.refresh`` (ADR-0062): a source's declaration run
against answers served in memory.

The tests of sdk-template's skeleton, ``tests/test_capture.py`` there (#123, #188), moved
here with the frame, a ``Snapshot`` in place of the script's constants; the frame's own
rules and its hooks follow them. The frame sends through core's client, and ``Site`` answers
every request from its routes through respx, so no socket is opened and nothing leaves the
process.
"""

import ast
import hashlib
import inspect
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Generator, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from importlib import metadata
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from xippios.core import refresh
from xippios.core.client import AsyncClient, ClientConfig, RetryPolicy
from xippios.core.errors import ConfigError, RateLimitError, XippiosError
from xippios.core.refresh import (
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

BASE = "https://docs.example.org"
API = "https://api.example.org/v1"
ALLOWLIST = "<!-- pragma: allowlist secret (an ETag, not a key) -->"
TABLE_HEADER = "| File | URL | Fetched | HTTP | Bytes | sha256 | ETag | Last-Modified | Note |"
NOT_FETCHED_HEADER = "| URL | HTTP | Redirects to | Reason |"
VERSION = "1.0.0"
"""The version of the installed distribution ``xippios-example``, as the site fixture has it."""
USER_AGENT = f"xippios-example/{VERSION} (+https://github.com/xippios)"
WRITTEN_AGENT = "xippios-example/<version> (+https://github.com/xippios)"
"""The User-Agent as FETCHED.md names it, with no version that a release would move."""
HAND = "written by hand: what upstream does but never documents; not fetched or checked"
SPLIT = "one of the files split from one page; Bytes and sha256 are the page's"
MARK = "<!-- form 2 of the FETCHED.md that xippios.core.refresh writes -->"
ROOT = Path(__file__).resolve().parents[2]

Answer = tuple[int, dict[str, str], bytes]


@dataclass
class Site:
    """Answers served in memory, each URL's ``(status, headers, body)``, and what was asked.

    ``later`` holds answers a URL gives in turn before its route, a 429 before its page.
    """

    routes: dict[str, Answer] = field(default_factory=dict)
    later: dict[str, list[Answer]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)

    def page(self, name: str, text: str | bytes, headers: Mapping[str, str] | None = None) -> str:
        """Serve ``text`` at ``BASE/name``, typed by its extension, and return its URL."""
        url = f"{BASE}/{name}"
        kind = mimetypes.guess_type(name)[0]
        typed = {"Content-Type": kind} if kind else {}
        body = text.encode() if isinstance(text, str) else text
        self.routes[url] = (200, {**typed, **(headers or {})}, body)
        return url

    def asked(self, url: str) -> list[httpx.Request]:
        """The requests sent to ``url``."""
        return [request for request in self.requests if str(request.url) == url]

    def answer(self, request: httpx.Request) -> httpx.Response:
        """The answer to ``request``; a URL that is not served is a network error."""
        self.requests.append(request)
        url = str(request.url)
        waiting = self.later.get(url)
        if waiting:
            status, headers, body = waiting.pop(0)
        elif url in self.routes:
            status, headers, body = self.routes[url]
        else:
            raise httpx.ConnectError(f"{url} is not served", request=request)
        return httpx.Response(status, headers=headers, content=body)


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> Iterator[Site]:
    """Every request of core's client answers from the site, the distribution
    ``xippios-example`` stands installed at ``VERSION``, and no pause waits."""
    served = Site()
    installed = metadata.version

    def version(distribution: str) -> str:
        return VERSION if distribution == "xippios-example" else installed(distribution)

    monkeypatch.setattr(metadata, "version", version)
    monkeypatch.setattr(time, "sleep", served.sleeps.append)
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(side_effect=served.answer)
        yield served


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


# --- a statement recorded with a link, and an image's alternative text --------------------
#
# https://github.com/xippios/sdk-core/issues/437 (ADR-0046, decision 7): a statement recorded
# with a link passes the search only as the text of a link to its target, on any page, while a
# statement without a link and the vocabulary pass anywhere, and an image's alternative text is
# text of the page where the image stands. The trial of the release met both
# (https://github.com/xippios/sdk-google-mail/issues/72, https://github.com/xippios/sdk-x/issues/57,
# https://github.com/xippios/sdk-cashctrl/issues/134).

TOS = "https://example.org/tos"
FOOTER = f"<footer><a href='{TOS}'>Terms of Service</a></footer>"


def linked_terms(url: str) -> Statement:
    """The footer's link to the terms, recorded from the page at ``url``."""
    return Statement("Terms of Service", url, "a link in the footer", TOS)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param("<p>By using the API you accept the Terms of Service.</p>", id="in-prose"),
        pytest.param(
            "<p>Read the <a href='https://example.org/terms'>Terms of Service</a>.</p>",
            id="a-link-to-another-target",
        ),
    ],
)
def test_a_linked_statement_s_words_on_another_page_stop_the_run(
    site: Site, out: Path, words: str
) -> None:
    """Misfit 1 of sdk-google-mail's trial: the words of a statement recorded with a link stop the
    run on another page, in prose or as the text of a link to another target, as its script had
    it, the stop naming the link that the words pass as, and nothing is written."""
    index = site.page("index.html", f"<p>Index</p>{FOOTER}")
    guide = site.page("guide.html", f"{words}{FOOTER}")
    snapshot = declare(
        out,
        Page(index, "pages/index.html"),
        Page(guide, "pages/guide.html"),
        attribution=(linked_terms(index),),
    )
    with pytest.raises(
        SystemExit, match=f"GET {re.escape(guide)}: the page states 'Terms of"
    ) as stop:
        go(snapshot)
    named = f"records 'Terms of Service' as a link to {TOS}, and the check reads past it only"
    assert named in str(stop.value)
    assert not out.exists(), "nothing written"


def test_a_second_link_with_the_statement_s_text_on_its_page_stops_the_run(
    site: Site, out: Path
) -> None:
    """On the statement's own page the recorded link passes, and a link beside it with the same
    text and another target stops the run."""
    url = site.page("index.html", f"<p>Index</p>{FOOTER}")
    snapshot = declare(out, Page(url, "pages/index.html"), attribution=(linked_terms(url),))
    assert go(snapshot) == 0
    other = "<p>Index, <a href='https://example.org/terms'>Terms of Service</a></p>"
    site.page("index.html", f"{other}{FOOTER}")
    with pytest.raises(SystemExit, match="the page states 'Terms of Service'"):
        go(snapshot)


def test_the_recorded_link_passes_on_every_page_that_prints_it(site: Site, out: Path) -> None:
    """sdk-google-mail records the link of a footer that seven pages print from one of them: it
    passes on every page, its target absolute or relative to the page and written with white
    space around it, which a browser strips as sdk-google-mail's script did (finding 1 of the
    review of https://github.com/xippios/sdk-core/pull/451), and only its text leaves the page,
    so other words of the page are still searched."""
    terms = f"{BASE}/legal/tos"
    index = site.page("index.html", f"<footer><a href='{terms} '>Terms of Service</a></footer>")
    footer = "<footer><a href=' /legal/tos '>Terms of Service</a></footer>"
    guide = site.page("guide.html", f"<p>Guide</p>{footer}")
    statement = Statement("Terms of Service", index, "a link in the footer", terms)
    snapshot = declare(
        out,
        Page(index, "pages/index.html"),
        Page(guide, "pages/guide.html"),
        attribution=(statement,),
    )
    assert go(snapshot) == 0
    site.page(
        "guide.html", "<p>All rights reserved.</p><footer><a href='legal/tos'>Terms of Service"
    )
    with pytest.raises(SystemExit, match="the page states 'All rights reserved'"):
        go(snapshot)


def test_a_statement_without_a_link_and_the_vocabulary_pass_anywhere(site: Site, out: Path) -> None:
    """sdk-comtrade's and sdk-faostat's statements carry no link and pass on every page as
    before, a word of the vocabulary too, and so does a statement without a link that holds a
    linked one's words, as sdk-google-mail's step of enabling an API does."""
    notice = "\N{COPYRIGHT SIGN} 2026 Example Ltd."
    step = "If prompted, read and accept the API's Terms of Service."
    footer = "<footer>&copy; 2026 Example Ltd.</footer>"
    index = site.page("index.html", f"<p>Index</p>{footer}{FOOTER}")
    guide = site.page("guide.html", f"<p>{step} An import license is required.</p>{footer}")
    snapshot = declare(
        out,
        Page(index, "pages/index.html"),
        Page(guide, "pages/guide.html"),
        attribution=(
            Statement(notice, index, "the footer"),
            linked_terms(index),
            Statement(step, guide, "a step of enabling the API"),
        ),
        vocabulary=("import license",),
    )
    assert go(snapshot) == 0


def test_a_page_that_is_no_html_has_no_link_for_a_linked_statement(site: Site, out: Path) -> None:
    """A page that is no HTML has no link, so the words of a statement recorded with a link stop
    the run there wherever they stand, as sdk-x's script searched its Markdown pages whole; a
    statement without a link passes there as on any page."""
    index = site.page("index.html", f"<p>Index</p>{FOOTER}")
    notes = f"{BASE}/notes.md"
    markdown = f"# Notes\n\nSee [Terms of Service]({TOS}).\n".encode()
    site.routes[notes] = (200, {"Content-Type": "text/markdown; charset=utf-8"}, markdown)
    snapshot = declare(
        out,
        Page(index, "pages/index.html"),
        Page(notes, "pages/notes.md"),
        attribution=(linked_terms(index),),
    )
    with pytest.raises(SystemExit, match=f"GET {re.escape(notes)}: the page states 'Terms of"):
        go(snapshot)
    unlinked = Statement("Terms of Service", notes, "a link of the Markdown page")
    assert go(replace(snapshot, attribution=(linked_terms(index), unlinked))) == 0


def test_an_api_document_s_licence_recorded_with_its_link_passes(site: Site, out: Path) -> None:
    """sdk-x records its document's licence by its name, its URL the link: the document is no HTML,
    and the licence, the terms and the contact of its ``info`` leave its text before the search,
    so the statement passes as before."""
    licence = {"name": "Example License", "url": "https://example.org/license"}
    info = {"title": "Example", "license": licence, "termsOfService": licence["url"]}
    url = site.page("openapi.json", json.dumps({"openapi": "3.1.0", "info": info, "paths": {}}))
    statement = Statement(licence["name"], url, "info.license", licence["url"])
    assert go(declare(out, Page(url, "openapi/openapi.json"), attribution=(statement,))) == 0


def test_a_statement_in_an_image_s_alternative_text_is_checked_on_its_page(
    site: Site, out: Path
) -> None:
    """Misfit 6 of sdk-cashctrl's trial: a notice that stands in the alternative text of the
    footer's logo is read where the image stands, so the statement names its page, which must
    print it, and FETCHED.md quotes it as printed there."""
    statement = "\N{COPYRIGHT SIGN} 2026 Example Ltd. All rights reserved."
    footer = (
        "<footer><img src='logo.svg' alt='&copy; {} Example Ltd.'>All rights reserved.</footer>"
    )
    url = site.page("index.html", "<p>Guide</p>" + footer.format(2026))
    where = "the alternative text of the footer's logo and the line after it"
    snapshot = declare(
        out, Page(url, "pages/index.html"), attribution=(Statement(statement, url, where),)
    )
    assert go(snapshot) == 0
    assert f"`{statement}`, printed at {url}: {where}" in flat(fetched(out))
    site.page("index.html", "<p>Guide</p>" + footer.format(2027))
    with pytest.raises(SystemExit, match="no longer prints"):
        go(snapshot)


@pytest.mark.parametrize(
    "image",
    [
        "<img src='logo.svg' alt='Copyright Example'>",
        "<img src='logo.svg' alt='&copy; 2026 Example' />",
        "<a href='https://example.org/'><img src='logo.svg' alt='Licensed under CC BY 4.0'></a>",
    ],
)
def test_an_alternative_text_that_no_statement_records_stops_the_run(
    site: Site, out: Path, image: str
) -> None:
    """An image's alternative text that holds a word of the search and that no statement records
    stops the run, as any text of the page does."""
    url = site.page("index.html", f"<p>Guide {image}</p>")
    with pytest.raises(SystemExit, match="attribution does not record"):
        go(declare(out, Page(url, "pages/index.html")))


def test_an_image_s_alternative_text_alone_is_read(site: Site, out: Path) -> None:
    """The decision names an image's alternative text and nothing else: a title, an aria-label,
    an image inside a template and an empty alternative text state nothing, and an image inside
    the recorded link is the link's text."""
    quiet = (
        "<p title='Terms of Service'>Guide</p><span aria-label='Copyright'>x</span>"
        "<template><img src='old.png' alt='&copy; 2019 Old Owner'></template>"
        "<img src='spacer.png' alt=''>"
        f"<footer><a href='{TOS}'><img src='tos.png' alt='Terms of Service'></a></footer>"
    )
    url = site.page("index.html", quiet)
    assert go(declare(out, Page(url, "pages/index.html"), attribution=(linked_terms(url),))) == 0


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(
            "Read the Terms of<img src='i.svg' alt='icon'> Service.", id="terms-of-service"
        ),
        pytest.param("Copy<img src='x.svg' alt='x'>right 2026 Example", id="copyright"),
        pytest.param(
            "Copy<img src='x.svg' alt='&copy; 2026 Example Ltd.'>right", id="a-recorded-alt-text"
        ),
        pytest.param(
            "Shared under CC <img src='l.svg' alt='logo'> BY 4.0.", id="space-on-both-sides"
        ),
    ],
)
def test_an_alternative_text_between_words_of_the_search_does_not_part_them(
    site: Site, out: Path, words: str
) -> None:
    """Finding 3 of the review of https://github.com/xippios/sdk-core/pull/451: the words that
    an image's alternative text stands between are searched as the text without it reads them,
    as before the alternative text was read, its white space flattened (finding 1 of the second
    review), so they stop the run, even where the alternative text is a statement that the
    attribution records."""
    notice = Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", "", "the footer, read by hand")
    url = site.page("index.html", f"<p>{words}</p>")
    with pytest.raises(SystemExit, match="read without its images' alternative text"):
        go(declare(out, Page(url, "pages/index.html"), attribution=(notice,)))


def test_words_that_read_with_an_alternative_text_are_recorded_pass(site: Site, out: Path) -> None:
    """Finding 1 of the second review of https://github.com/xippios/sdk-core/pull/451: words that,
    read with an image's alternative text, are a statement that the attribution records or a word
    of its vocabulary pass, as the decision reads the alternative text, where the words without
    it stopped before it was read."""
    url = site.page("index.html", "<p><img src='l.svg' alt='logo'>Copyright</p>")
    page = Page(url, "pages/index.html")
    assert go(declare(out, page, vocabulary=("logo Copyright",))) == 0
    assert go(declare(out, page, attribution=(Statement("logo Copyright", url, "the logo"),))) == 0


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"vocabulary": ("",)}, id="an-empty-word-of-the-vocabulary"),
        pytest.param({"vocabulary": (" \N{NO-BREAK SPACE}",)}, id="a-blank-word-of-the-vocabulary"),
        pytest.param(
            {"attribution": (Statement(" ", "", "a blank line, read by hand"),)},
            id="a-blank-statement",
        ),
    ],
)
def test_an_empty_word_or_statement_is_read_past_nowhere(
    site: Site, out: Path, fields: dict[str, Any]
) -> None:
    """Finding 2 of the second review of https://github.com/xippios/sdk-core/pull/451: a statement
    whose text is empty or white space, and such a word of the vocabulary, are read past nowhere,
    where reading past the empty text parted every character of the page with a space, so that
    no word of the search matched and any page passed."""
    url = site.page("index.html", "<p>Copyright 2026</p>")
    with pytest.raises(SystemExit, match="the page states 'Copyright'"):
        go(declare(out, Page(url, "pages/index.html"), **fields))


def test_an_alternative_text_inside_a_recorded_link_is_part_of_its_text(
    site: Site, out: Path
) -> None:
    """Finding 3 of the review of https://github.com/xippios/sdk-core/pull/451: an image with an
    alternative text inside a recorded link, beside its words, is part of the link's text, so
    the page no longer links the statement as recorded, and the statement recorded as the page
    reads the link, its alternative text included, passes on the page."""
    url = site.page("index.html", f"<footer><a href='{TOS}'><img alt='icon'> Terms of Service</a>")
    page = Page(url, "pages/index.html")
    with pytest.raises(SystemExit, match="no longer links 'Terms of Service'"):
        go(declare(out, page, attribution=(linked_terms(url),)))
    as_read = Statement("icon Terms of Service", url, "a link in the footer, its icon first", TOS)
    assert go(declare(out, page, attribution=(as_read,))) == 0


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
    without the mark the same row is flagged, the code span alone being no exemption. The
    file's last line, the mark of its form, passes the scan too
    (https://github.com/xippios/sdk-core/issues/428)."""
    etag = '"' + hashlib.md5(b"an object store's ETag", usedforsecurity=False).hexdigest() + '"'
    site.page("openapi.json", '{"openapi": "3.1.0"}', {"ETag": etag})
    assert go(declare(out, Page(f"{BASE}/openapi.json", "openapi/openapi.json"))) == 0
    text = fetched(out)
    assert text.endswith(f"\n{MARK}\n")
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


def test_the_frame_names_itself_as_the_client_does_and_pauses_as_the_snapshot_says(
    site: Site, out: Path
) -> None:
    """ADR-0062, decision 4: the client that the frame builds from the slug sends the User-Agent
    of every client of the source, its version that of the installed distribution, and FETCHED.md
    names it without the version, which a release would move; the frame pauses before every
    request as long as the snapshot says."""
    page = Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html")
    assert go(declare(out, page, pause=5.0)) == 0
    (request,) = site.requests
    assert request.headers["User-Agent"] == USER_AGENT
    config = ClientConfig(source="example", version=VERSION, base_url=BASE)
    assert request.headers["User-Agent"] == config.user_agent, "the client's one form"
    assert "Authorization" not in request.headers
    assert site.sleeps == [5.0]
    text = flat(fetched(out))
    assert "5 s apart, through core's client, each retried at most once" in text
    assert f"identified as `{WRITTEN_AGENT}`, the source package's version in place of" in text
    assert VERSION not in text


def test_the_client_built_from_the_slug_needs_the_installed_distribution(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The frame names itself by the version of ``xippios-<slug>``, so a script run where the
    source's distribution is not installed stops before any request, naming the distribution and
    the two ways on; a snapshot that hands the frame its client needs none."""
    page = Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html")
    with pytest.raises(SystemExit, match="xippios-other is not installed") as stop:
        go(replace(declare(out, page), slug="other"))
    assert "Snapshot.client" in str(stop.value)
    assert not site.requests
    assert not out.exists()
    handed = AsyncClient(ClientConfig(source="other", version="2.0.0", base_url=BASE))
    assert go(replace(declare(out, page), slug="other", client=handed)) == 0
    (request,) = site.requests
    assert request.headers["User-Agent"] == "xippios-other/2.0.0 (+https://github.com/xippios)"


def test_the_frame_sends_through_the_client_the_snapshot_hands_it(site: Site, out: Path) -> None:
    """ADR-0062, decision 4: a source that hands the frame its client, one for its website's
    pace and wait say, has every request sent through it, its headers and its hooks included,
    and without its credentials on a page that is no keyed sample."""
    seen: list[str] = []
    config = ClientConfig(
        source="example",
        version=VERSION,
        base_url=BASE,
        headers={"From": "maintainer@example.org"},
        observe=lambda response: seen.append(str(response.request.url)),
    )
    client = AsyncClient(config, auth=Session())
    url = site.page("guide.html", "<p>Guide</p>")
    assert go(declare(out, Page(url, "pages/guide.html"), client=client)) == 0
    (request,) = site.requests
    assert request.headers["From"] == "maintainer@example.org"
    assert request.headers["User-Agent"] == USER_AGENT
    assert "X-Session" not in request.headers, "a page that is no keyed sample sends none"
    assert seen == [url], "the client's observe saw the answer"


def test_a_5xx_is_retried_once(site: Site, out: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The skeleton's fetch: a 5xx or a network error is retried once after RETRY_PAUSE, and a
    second one stops the run; every request is counted, the retry's too."""
    url = site.page("guide.html", "<p>Guide</p>")
    site.later[url] = [(503, {}, b"")]
    assert go(declare(out, Page(url, "pages/guide.html"))) == 0
    assert site.sleeps == [0.0, 10.0], "the pause, then RETRY_PAUSE"
    assert len(site.asked(url)) == 2
    printed = capsys.readouterr().out
    assert "retrying once in 10 s" in printed
    assert "2 requests sent, each redirect and retry counted" in printed
    site.later[url] = [(503, {}, b""), (502, {}, b"")]
    with pytest.raises(SystemExit, match=r"\(after one retry\)"):
        go(declare(out, Page(url, "pages/guide.html")))
    missing = f"{BASE}/missing.html"
    with pytest.raises(SystemExit, match=r"is not served.*\(after one retry\)"):
        go(declare(out, Page(missing, "pages/missing.html")))
    assert len(site.asked(missing)) == 2, "a network error is retried once"


def test_a_redirect_on_the_page_s_host_is_followed_and_counted(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The client follows no redirect, so the frame keeps its own record of them: it follows a
    redirect on the page's host, a relative target made absolute against the URL that answered,
    notes each hop in the row, counts each request, and stops on a page that redirects on its
    host more than ten times."""
    site.routes[f"{BASE}/old.html"] = (301, {"Location": "/moved/guide.html"}, b"")
    site.routes[f"{BASE}/moved/guide.html"] = (307, {"Location": "../guide.html"}, b"")
    site.page("guide.html", "<p>Guide</p>")
    snapshot = declare(out, Page(f"{BASE}/old.html", "pages/guide.html"))
    capsys.readouterr()
    assert go(snapshot) == 0
    assert "3 requests sent, each redirect and retry counted" in capsys.readouterr().out
    row = cells(file_row(fetched(out), "pages/guide.html"))
    assert row[1] == f"{BASE}/old.html"
    hops = f"redirected (301) to {BASE}/moved/guide.html; redirected (307) to {BASE}/guide.html"
    assert row[8] == hops
    assert (out / "pages/guide.html").read_bytes() == b"<p>Guide</p>"
    site.routes[f"{BASE}/loop.html"] = (302, {"Location": f"{BASE}/loop.html"}, b"")
    with pytest.raises(SystemExit, match="more than 10 redirects on its host"):
        go(declare(out, Page(f"{BASE}/loop.html", "pages/loop.html")))
    assert len(site.asked(f"{BASE}/loop.html")) == 11


def test_two_pages_never_write_one_file(site: Site, out: Path) -> None:
    """A file is one page's: two rows that would write one file stop the run before any
    write."""
    one = Page(site.page("a.html", "<p>A</p>"), "pages/same.html")
    two = Page(site.page("b.html", "<p>B</p>"), "pages/same.html")
    with pytest.raises(SystemExit, match=r"pages/same\.html: written by two pages"):
        go(declare(out, one, two))
    assert not out.exists()


def test_the_frame_imports_core_s_client_and_no_extra() -> None:
    """ADR-0062, decision 1, and https://github.com/xippios/sdk-core/issues/363, part 1: the
    frame imports the standard library, httpx and core's own modules, the client among them,
    which core's base dependencies hold, so it needs no extra and pins no converter, which
    stays the source's own dependency; ``urllib`` serves it nothing but the parsing of a URL."""
    tree = ast.parse(Path(upstream.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    tops = {name.split(".")[0] for name in imported}
    allowed = set(sys.stdlib_module_names) | {"httpx", "xippios"}
    assert tops <= allowed, tops - allowed
    assert "xippios.core.client" in imported
    assert {name for name in imported if name.startswith("urllib")} == {"urllib.parse"}
    assert not any(name.startswith(("xippios.core.mcp", "xippios.core.http")) for name in tops)


def test_fetched_md_cites_the_standing_record_of_upstream_fidelity(site: Site, out: Path) -> None:
    """What the sources' tests of their copies held, now the frame's
    (https://github.com/xippios/sdk-core/issues/425): the two sentences on the snapshot's role
    cite sdk-core ADR-0028, which superseded ADR-0003, by the repository's name, and the file
    names ADR-0003 nowhere."""
    assert go(declare(out, Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html"))) == 0
    text = flat(fetched(out))
    assert "Source of truth for every endpoint wrapper (sdk-core ADR-0028)." in text
    assert "reproduced here as this package's reference (sdk-core ADR-0028)" in text
    assert text.count("(sdk-core ADR-0028)") == 2
    assert "ADR-0003" not in text


def test_fetched_md_says_that_nothing_but_observed_md_is_edited_by_hand(
    site: Site, out: Path
) -> None:
    """The frame's one form (ADR-0046, decision 3), where each source's copy wrote its own
    (https://github.com/xippios/sdk-core/issues/425): FETCHED.md says that nothing under
    ``docs/upstream/`` is edited by hand but OBSERVED.md, where it exists, with the file and
    without it."""
    sentence = (
        "This file is generated by the same script; nothing here is edited by hand but "
        "`OBSERVED.md`, where it exists: what upstream does but never documents, each note "
        "with its evidence."
    )
    snapshot = declare(out, Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html"))
    assert go(snapshot) == 0
    assert sentence in flat(fetched(out)), "without the file"
    (out / "OBSERVED.md").write_text("# Observed\n")
    assert go(snapshot) == 0
    assert sentence in flat(fetched(out)), "with the file"


def test_a_file_no_longer_produced_goes_from_the_subdirectories_the_run_writes_to(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-0046, Consequences, and sdk-cashctrl's test of a stale file
    (https://github.com/xippios/sdk-core/issues/425): a file the run no longer produces, under
    a subdirectory it writes to, is named by ``--check`` as no longer produced and removed by
    the write; a file at the top of ``docs/upstream/`` and one under a subdirectory the run no
    longer writes to are left as they are, and ``--check`` names neither."""
    kept = Page(site.page("a.html", "<p>A</p>"), "pages/a.html")
    stale = Page(site.page("b.html", "<p>B</p>"), "pages/b.html")
    top = Page(site.page("top.html", "<p>Top</p>"), "top.html")
    elsewhere = Page(site.page("old.html", "<p>Old</p>"), "old/old.html")
    assert go(declare(out, kept, stale, top, elsewhere)) == 0
    snapshot = declare(out, kept)
    capsys.readouterr()
    assert go(snapshot, "--check") == 1
    output = capsys.readouterr().out
    assert "differs: pages/b.html (no longer produced)" in output
    assert "top.html (no longer produced)" not in output
    assert "old/old.html (no longer produced)" not in output
    assert (out / "pages/b.html").is_file(), "--check writes nothing"
    assert go(snapshot) == 0
    assert "removed pages/b.html: no longer produced" in capsys.readouterr().out
    assert not (out / "pages/b.html").exists()
    assert (out / "pages/a.html").read_bytes() == b"<p>A</p>"
    assert (out / "top.html").read_bytes() == b"<p>Top</p>"
    assert (out / "old/old.html").read_bytes() == b"<p>Old</p>"
    assert go(snapshot, "--check") == 0


def test_every_declared_page_is_checked_before_the_first_request(site: Site, out: Path) -> None:
    """sdk-google-mail's and sdk-x's tests of a page kept as OBSERVED.md
    (https://github.com/xippios/sdk-core/issues/425): a declared page that the frame cannot
    record as declared stops the run before any request, wherever it stands among the pages,
    and nothing is written."""
    guide = Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html")
    notes = Page(site.page("notes.html", "<p>Notes</p>"), "OBSERVED.md")
    sample = Page(site.page("items.json", "[]"), "pages/items.json", sample=True)
    for refused, stop in [(notes, "written by hand"), (sample, "under samples/")]:
        with pytest.raises(SystemExit, match=stop):
            go(declare(out, guide, refused))
    assert not site.requests
    assert not out.exists()


# --- the hooks ---------------------------------------------------------------------------


VARIABLES = ("EXAMPLE_ACCOUNT", "EXAMPLE_LOGIN")
SESSION = "session-of-the-login"


class Session(httpx.Auth):
    """A source's own auth, as a login's is: it reads ``EXAMPLE_LOGIN`` at each request, which
    the plugin's placeholder does not pin, sends it as the header ``X-Session``, and refuses an
    unset variable with the client's ``ConfigError``, naming it."""

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        value = os.environ.get("EXAMPLE_LOGIN")
        if not value:
            raise ConfigError("EXAMPLE_LOGIN is not set; export it", source="example")
        request.headers["X-Session"] = value
        yield request


def keyed_client(base: str = f"{API}/") -> AsyncClient:
    """The source's own client, which sends its credential, read from ``EXAMPLE_LOGIN``, as the
    header ``X-Session`` to its base URL's origin alone (ADR-0037, decision 4)."""
    config = ClientConfig(source="example", version=VERSION, base_url=base)
    return AsyncClient(config, auth=Session())


def keyed_snapshot(site: Site, out: Path) -> Snapshot:
    guide = site.page("guide.html", "<p>Guide</p>")
    site.routes[f"{API}/items"] = (200, {"Content-Type": "application/json"}, b'{"items": []}')
    site.routes[f"{API}/codes"] = (200, {"Content-Type": "application/json"}, b'{"codes": []}')
    return declare(
        out,
        Page(guide, "pages/guide.html"),
        Page(f"{API}/items", "samples/items.json", sample=True, keyed=True),
        Page(f"{API}/codes", "samples/codes.json", sample=True, keyed=True),
        client=keyed_client(),
        variables=VARIABLES,
    )


def test_a_keyed_sample_alone_sends_the_client_s_credentials(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Conventions §3, ADR-0028, decision 7, and ADR-0062, decision 4: the credentials are
    the client's that the snapshot hands the frame, sent on the keyed
    samples alone and printed nowhere; FETCHED.md names the variables, never a value."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", SESSION)
    snapshot = keyed_snapshot(site, out)
    assert go(snapshot) == 0
    guide, items, codes = site.requests
    assert "X-Session" not in guide.headers, "the guide is no keyed sample"
    assert items.headers["X-Session"] == codes.headers["X-Session"] == SESSION
    assert items.headers["User-Agent"] == USER_AGENT
    output = capsys.readouterr().out
    assert SESSION not in output
    text = fetched(out)
    assert SESSION not in text
    assert "someone" not in text
    assert "Regenerate, with `EXAMPLE_ACCOUNT` and `EXAMPLE_LOGIN` set: `uv run" in text
    assert (
        "Only the keyed samples send a credential, the one the source's client reads from "
        "`EXAMPLE_ACCOUNT` and `EXAMPLE_LOGIN`, to its base URL's origin alone"
    ) in flat(text)
    assert (out / "samples/items.json").read_bytes() == b'{"items": []}'


def test_a_keyed_sample_follows_no_redirect_and_is_never_retried(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sdk-faostat's rule: a request with the credentials reaches the base alone, so a
    redirect stops the run unfollowed, and a 5xx, a 429 or a network error costs one keyed
    call and stops it."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", SESSION)
    snapshot = keyed_snapshot(site, out)
    site.routes[f"{API}/items"] = (302, {"Location": f"{API}/items/"}, b"")
    with pytest.raises(SystemExit, match="a keyed request follows no redirect"):
        go(snapshot)
    assert not site.asked(f"{API}/items/")
    for refusal, stop in [
        ((503, {}, b""), "a keyed request is not retried"),
        ((429, {"Retry-After": "1"}, b""), "HTTP 429"),
    ]:
        snapshot = keyed_snapshot(site, out)
        site.later[f"{API}/items"] = [refusal]
        site.requests.clear()
        with pytest.raises(SystemExit, match=stop):
            go(snapshot)
        assert len(site.asked(f"{API}/items")) == 1
    snapshot = keyed_snapshot(site, out)
    del site.routes[f"{API}/items"]
    site.requests.clear()
    with pytest.raises(SystemExit, match="is not served; a keyed request is not retried"):
        go(snapshot)
    assert len(site.asked(f"{API}/items")) == 1
    assert not out.exists(), "nothing written"


def test_the_variables_are_checked_by_name_before_anything_is_fetched(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A variable that the snapshot names and the environment does not set stops the run,
    named, before the first request, with the way to run without it."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.delenv("EXAMPLE_LOGIN", raising=False)
    with pytest.raises(SystemExit, match="EXAMPLE_LOGIN is not set") as stop:
        go(keyed_snapshot(site, out))
    assert "--keyless" in str(stop.value)
    assert not site.requests


def test_a_credential_the_client_cannot_read_stops_the_run_before_writing(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client reads its credential itself: one that it cannot read, here a variable that
    the snapshot does not name, stops the run at its keyed sample with the client's message,
    which names the variable and no value, and nothing is written."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.delenv("EXAMPLE_LOGIN", raising=False)
    snapshot = replace(keyed_snapshot(site, out), variables=("EXAMPLE_ACCOUNT",))
    with pytest.raises(SystemExit, match=r"EXAMPLE_LOGIN is not set.*Nothing was written"):
        go(snapshot)
    assert [str(request.url) for request in site.requests] == [f"{BASE}/guide.html"]
    assert not out.exists()


def test_keyless_compares_the_pages_that_send_no_credential(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--keyless``, a free trial before a run that spends keyed calls: it
    fetches and compares the pages that send no credential, needs no variable and writes
    nothing; a snapshot that names no variables has no such option."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", SESSION)
    snapshot = keyed_snapshot(site, out)
    assert go(snapshot) == 0
    monkeypatch.delenv("EXAMPLE_LOGIN")
    site.requests.clear()
    assert go(snapshot, "--keyless") == 0
    assert [str(request.url) for request in site.requests] == [f"{BASE}/guide.html"]
    site.page("guide.html", "<p>Guide, revised</p>")
    before = fetched(out)
    assert go(snapshot, "--keyless") == 1
    assert "differs: pages/guide.html" in capsys.readouterr().out
    assert fetched(out) == before, "nothing written"
    with pytest.raises(SystemExit):
        go(declare(out, Page(f"{BASE}/guide.html", "pages/guide.html")), "--keyless")


def test_a_keyed_page_is_a_sample_of_the_client_s_origin(site: Site, out: Path) -> None:
    """Conventions §3 and ADR-0062, decision 4: only a sample's request sends a credential, the
    client's that the snapshot hands the frame, whose variables it names; a keyed page that is
    no sample, lies on another origin, or has no client or no variables to send it with is
    refused before any request."""
    items = Page(f"{API}/items", "samples/items.json", sample=True, keyed=True)
    unsampled = replace(items, file="pages/items.json", sample=False)
    refused = [
        declare(out, unsampled, client=keyed_client(), variables=("A",)),
        declare(out, replace(items, url=f"{BASE}/items"), client=keyed_client(), variables=("A",)),
        declare(out, items, variables=("A",)),
        declare(out, items, client=keyed_client()),
    ]
    for snapshot in refused:
        with pytest.raises(SystemExit, match="a keyed page is a sample on the origin"):
            go(snapshot, "--check")
    assert not site.requests


def test_the_credentials_go_to_the_origin_of_the_client_s_base_alone(
    site: Site, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 4 of the review of #386, now the client's own rule (ADR-0037, decision 4;
    ADR-0062, decision 4): a keyed sample has the origin of the client's base URL, its scheme,
    host and port as httpx parses them, a default port written or not and the host in any
    case, and any path there. A look-alike host that shares the base's text, another port,
    another scheme and a user before another host are refused before any request."""
    monkeypatch.setenv("EXAMPLE_ACCOUNT", "someone")
    monkeypatch.setenv("EXAMPLE_LOGIN", SESSION)

    def keyed(base: str, url: str) -> Snapshot:
        page = Page(url, "samples/items.json", sample=True, keyed=True)
        return declare(out, page, client=keyed_client(base), variables=VARIABLES)

    refused = [
        ("https://api.example.org", "https://api.example.org.elsewhere.net/v1/items"),
        ("https://api.example.org/v1/", "https://api.example.org:8443/v1/items"),
        ("https://api.example.org/v1/", "http://api.example.org/v1/items"),
        ("https://api.example.org/v1/", "https://api.example.org@elsewhere.net/v1/items"),
        ("https://api.example.org/v1/", "https://[api.example.org/v1/items"),
    ]
    for base, url in refused:
        with pytest.raises(SystemExit, match="a keyed page is a sample on the origin"):
            go(keyed(base, url))
    assert not site.requests
    accepted = [
        ("https://api.example.org/v1", f"{API}/items"),
        ("https://API.example.org:443/v1/", f"{API}/items"),
        (f"{API}/", "https://api.example.org/v10/items"),
        ("https://api.example.org/", f"{API}/items"),
    ]
    for base, url in accepted:
        site.routes[url] = (200, {"Content-Type": "application/json"}, b'{"items": []}')
        assert go(keyed(base, url)) == 0
    assert [request.headers.get("X-Session") for request in site.requests] == [SESSION] * 4


@pytest.mark.parametrize("name", ["../a.md", "/a.md", "pages/../../a.md", "FETCHED.md"])
def test_a_file_name_stays_inside_the_snapshot(site: Site, out: Path, name: str) -> None:
    """Finding 3 of the review of #386: the one guard between the names a ``split`` makes
    from upstream's answer and a write outside ``docs/upstream/`` refuses ``FETCHED.md``, an
    absolute name and a ``..`` part, from a split and from a declared page alike, before
    anything is written."""
    url = site.page("index.html", "<p>A</p>")

    def split(page: Page, response: Response) -> dict[str, bytes]:
        return {"pages/a.md": b"a", name: b"x"}

    with pytest.raises(SystemExit, match="is no file of the snapshot's own"):
        go(declare(out, Page(url, split=True), split=split))
    with pytest.raises(SystemExit, match="is no file of the snapshot's own"):
        go(declare(out, Page(url, name)))
    assert not out.exists(), "nothing written"
    assert not (out.parent / "a.md").exists()


@pytest.fixture
def east_of_utc() -> Iterator[None]:
    """The process's local time one hour east of UTC, where a date read as local shifts."""
    before = os.environ.get("TZ")
    os.environ["TZ"] = "TEST-1"
    time.tzset()
    yield
    if before is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = before
    time.tzset()


@pytest.mark.usefixtures("east_of_utc")
def test_last_modified_stands_in_utc_or_as_sent(site: Site, out: Path) -> None:
    """Finding 1 of the review of #386: an HTTP date is GMT in every form a recipient reads
    (RFC 9110, section 5.6.7), the asctime form and a ``-0000`` zone included, so the frame
    writes it in UTC whatever the machine's zone; a Last-Modified that is no HTTP date is
    written as sent, in a code span, and the capture goes on."""
    dates = {
        "a": "Mon Nov 16 10:00:00 2026",
        "b": "Mon, 16 Nov 2026 10:00:00 -0000",
        "c": "Mon, 16 Nov 2026 11:00:00 +0100",
        "d": "Mon, 16 Nov 2026 10:00:00 GMT",
        "e": "0",
        "f": "yesterday | noon",
    }
    pages = [
        Page(site.page(f"{name}.html", f"<p>{name}</p>", {"Last-Modified": date}), f"p/{name}.html")
        for name, date in dates.items()
    ]
    snapshot = declare(out, *pages)
    assert go(snapshot) == 0
    text = fetched(out)
    for name in "abcd":
        assert cells(file_row(text, f"p/{name}.html"))[7] == "2026-11-16T10:00:00Z", name
    assert cells(file_row(text, "p/e.html"))[7] == "`0`"
    assert cells(file_row(text, "p/f.html"))[7] == r"`yesterday \| noon`"
    assert (out / "p/e.html").read_bytes() == b"<p>e</p>"
    assert go(snapshot, "--check") == 0


def test_a_reduce_hook_keeps_a_file_as_recorded_where_only_noise_moved(
    site: Site, out: Path
) -> None:
    """A document served in a new order on each request, which ADR-0062, decision 5, gives the
    source's ``reduce`` hook: a hook that returns the recorded file's content where it is this
    answer's after ``canonical`` leaves the file as it is in a writing run, so a refresh shows
    real changes only, and a real change is written; the frame writes what the hook returns,
    and its row says nothing of it."""
    url = site.page("api.wadl", "<a/>\n<b/>\n")

    def canonical(page: Page, content: bytes) -> bytes:
        return b"\n".join(sorted(content.split(b"\n")))

    def reduce(page: Page, response: Response) -> bytes:
        recorded = out / str(page.file)
        if recorded.is_file():
            kept = recorded.read_bytes()
            if canonical(page, kept) == canonical(page, response.body):
                return kept
        return response.body

    snapshot = declare(out, Page(url, "wadl/api.wadl"), canonical=canonical, reduce=reduce)
    assert go(snapshot) == 0
    site.page("api.wadl", "<b/>\n<a/>\n")
    assert go(snapshot) == 0
    assert (out / "wadl/api.wadl").read_bytes() == b"<a/>\n<b/>\n"
    assert cells(file_row(fetched(out), "wadl/api.wadl"))[8] == "-"
    assert go(snapshot, "--check") == 0
    site.page("api.wadl", "<b/>\n<c/>\n")
    assert go(snapshot) == 0
    assert (out / "wadl/api.wadl").read_bytes() == b"<b/>\n<c/>\n"
    with pytest.raises(TypeError, match="keep_recorded"):
        Page(url, "wadl/api.wadl", keep_recorded=True)  # type: ignore[call-arg]


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


def test_a_page_refused_with_403_and_its_second_origin_are_two_pages(site: Site, out: Path) -> None:
    """A page that the publisher's edge refuses and serves from a second origin of its own
    (conventions §2), which ADR-0062, decision 5, gives two declared pages: the page that
    answers 403, recorded by that status in ``Not fetched``, and its copy from the second
    origin, kept as a file; a run stops once the refused page answers otherwise, so the
    declaration moves with the edge."""
    canonical = f"{BASE}/faq"
    origin = "https://origin.example.net/faq"
    site.routes[canonical] = (403, {"Content-Type": "text/html"}, b"<p>Access Denied</p>")
    site.routes[origin] = (200, {"Content-Type": "text/html"}, b"<p>FAQ</p>")
    snapshot = declare(
        out,
        Page(canonical, status=403, note=f"answers 403 to this script; kept from {origin}"),
        Page(origin, "pages/faq.html", note=f"the copy of {canonical} on the second origin"),
    )
    assert go(snapshot) == 0
    assert (out / "pages/faq.html").read_bytes() == b"<p>FAQ</p>"
    text = fetched(out)
    row = cells(file_row(text, "pages/faq.html"))
    assert row[1] == origin
    assert row[8] == f"the copy of {canonical} on the second origin"
    refused = f"answers 403 to this script; kept from {origin}"
    assert f"| {canonical} | 403 | - | {refused} |" in text
    site.routes[canonical] = (200, {"Content-Type": "text/html"}, b"<p>FAQ</p>")
    with pytest.raises(SystemExit, match="expected HTTP 403, got 200"):
        go(snapshot)
    with pytest.raises(TypeError, match="origin"):
        Page(canonical, "pages/faq.html", origin=origin)  # type: ignore[call-arg]


def test_a_429_waits_as_the_client_says_then_retries_once(site: Site, out: Path) -> None:
    """ADR-0062, decision 4: the wait after a 429 is the client's, its retry policy's for the
    first attempt with the ``Retry-After`` that the answer sends or that its ``classify`` reads
    from a header of upstream's own, and FETCHED.md says so; a 429 that the
    policy retries no more, by its one attempt or a wait past its bound, stops the run, and a
    second 429 stops it after the one retry."""
    url = site.page("data.html", "<p>Data</p>")
    page = Page(url, "pages/data.html")
    site.later[url] = [(429, {"Retry-After": "30"}, b"")]
    assert go(declare(out, page)) == 0
    assert site.sleeps == [0.0, 30.0], "the built client's policy honours Retry-After"
    assert len(site.asked(url)) == 2
    assert "each retried at most once, a 429 after the wait the client gives it" in flat(
        fetched(out)
    )

    def own_header(response: httpx.Response) -> XippiosError | None:
        if response.status_code == 429:
            wait = float(response.headers["X-Rate-Limit-Retry-After-Seconds"])
            return RateLimitError("the quota is spent", retry_after=wait, source="example")
        return None

    def client(retry: RetryPolicy) -> AsyncClient:
        config = ClientConfig(
            source="example", version=VERSION, base_url=BASE, retry=retry, classify=own_header
        )
        return AsyncClient(config)

    waiting = client(RetryPolicy(max_attempts=2, backoff_base=10.0, backoff_max=900.0))
    site.sleeps.clear()
    site.later[url] = [(429, {"X-Rate-Limit-Retry-After-Seconds": "600"}, b"")]
    assert go(declare(out, page, client=waiting)) == 0
    assert site.sleeps == [0.0, 600.0], "classify names the wait, the policy bounds it"
    for policy, wait in [(RetryPolicy(max_attempts=1), "60"), (RetryPolicy(), "60")]:
        site.later[url] = [(429, {"X-Rate-Limit-Retry-After-Seconds": wait}, b"")]
        site.requests.clear()
        with pytest.raises(SystemExit, match="HTTP 429"):
            go(declare(out, page, client=client(policy)))
        assert len(site.asked(url)) == 1, "no retry the policy refuses"
    site.later[url] = [(429, {}, b""), (429, {}, b"")]
    with pytest.raises(SystemExit, match=r"429 .*\(after one retry\)"):
        go(declare(out, page))


def test_read_json_reads_a_document_that_dump_json_writes_again(site: Site, out: Path) -> None:
    """ADR-0062, decision 4: the frame's reader of a JSON answer takes a name of its own beside
    the root's ``load_json``, and neither it nor ``dump_json`` takes an indent. A document that
    ``dump_json`` writes again as fetched is read and its part written; one served with another
    indent, or with a key twice, stops the run before anything is written."""
    url = site.page("openapi.json", '{\n  "openapi": "3.1.0",\n  "título": "é"\n}\n')

    def reduce(page: Page, response: Response) -> bytes:
        document = refresh.read_json(response)
        return refresh.dump_json({"openapi": document["openapi"], "título": document["título"]})

    snapshot = declare(out, Page(url, "openapi/part.json", excerpt=True), reduce=reduce)
    assert go(snapshot) == 0
    written = '{\n  "openapi": "3.1.0",\n  "título": "é"\n}\n'
    assert (out / "openapi/part.json").read_text(encoding="utf-8") == written
    before = fetched(out)
    site.page("openapi.json", '{\n    "openapi": "3.1.0"\n}\n')
    with pytest.raises(SystemExit, match=r"json\.dumps\(indent=2, ensure_ascii=False\)"):
        go(snapshot)
    site.page("openapi.json", '{\n  "openapi": "3.1.0",\n  "openapi": "3.1.1"\n}\n')
    with pytest.raises(SystemExit, match="duplicate keys"):
        go(snapshot)
    assert fetched(out) == before, "nothing written"
    for function in (refresh.read_json, refresh.dump_json):
        assert "indent" not in inspect.signature(function).parameters
    assert not hasattr(refresh, "load_json")


def test_the_command_line_takes_no_out(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-0062, decision 3: the declaration's ``out`` names where the snapshot stands, so the
    command line takes ``--check``, and ``--keyless`` where the snapshot names its variables,
    and refuses ``--out`` before any request."""
    snapshot = declare(out, Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html"))
    with pytest.raises(SystemExit) as stop:
        go(snapshot, "--out", str(out.parent / "elsewhere"))
    assert stop.value.code == 2
    assert "unrecognized arguments: --out" in capsys.readouterr().err
    assert not site.requests


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


# --- a cell on one line, the file read at its line feeds, and the mark of its form --------
#
# https://github.com/xippios/sdk-core/issues/434: the frame wrote a value into its cell as given,
# so a line feed broke the table, and --check split the file at every character that splits a
# text into lines, where the frame splits it at line feeds alone. --check at a refresh is the one
# comparison of a snapshot, and no check reads a committed FETCHED.md without a request
# (ADR-0062, decision 9).

FEED = "https://example.org/feed.xml"
GUIDE = f"{BASE}/guide.html"

LINE_FEEDS = [
    pytest.param("one line\nand a line feed", id="a-line-feed"),
    pytest.param("one line\r\nand a carriage return with it", id="a-carriage-return-and-line-feed"),
]


@pytest.mark.parametrize("note", LINE_FEEDS)
def test_a_line_feed_in_a_note_or_a_reason_keeps_its_row_on_one_line(
    site: Site, out: Path, note: str
) -> None:
    """A line feed in a page's note, in a note that ``note`` makes and in a reason of Not
    fetched is written as a space, as a paragraph of the frame writes it, so every row stays one
    line, and ``--check`` passes the file right after the write."""
    site.routes[f"{BASE}/admin"] = (401, {}, b"")

    def made(row: Row) -> str:
        return note if row.page.file == "pages/b.html" else row.note

    snapshot = declare(
        out,
        Page(site.page("a.html", "<p>A</p>"), "pages/a.html", note=note),
        Page(site.page("b.html", "<p>B</p>"), "pages/b.html", note="as served"),
        Page(f"{BASE}/admin", status=401, note=note),
        not_fetched=(NotFetched(FEED, note),),
        note=made,
    )
    assert go(snapshot) == 0
    written = " ".join(note.split())
    lines = fetched(out).split("\n")
    assert sum(line.startswith("| pages/") for line in lines) == 2
    assert sum(line.endswith(f"| {written} |") for line in lines) == 4, "two rows and two reasons"
    assert all(line.startswith("| ") for line in lines if written in line)
    assert go(snapshot, "--check") == 0


@pytest.mark.parametrize(
    "note",
    [
        pytest.param("one line\rand a carriage return", id="a-carriage-return"),
        pytest.param("one line\x85and a next-line mark", id="a-next-line-mark"),
        pytest.param("one line\N{LINE SEPARATOR}and a line separator", id="a-line-separator"),
        pytest.param("one line\x0cand a form feed", id="a-form-feed"),
        pytest.param("one line\x1eand a record separator", id="a-record-separator"),
    ],
)
def test_check_reads_the_file_at_its_line_feeds_as_the_frame_wrote_it(
    site: Site, out: Path, note: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A note that holds a character that splits a text into lines, but not a line of
    FETCHED.md, is written as given, and ``--check`` passes the file right after the write,
    reading it at its line feeds alone."""
    snapshot = declare(out, Page(site.page("a.html", "<p>A</p>"), "pages/a.html", note=note))
    assert go(snapshot) == 0
    assert f"| {note} |" in (out / "FETCHED.md").read_bytes().decode()
    capsys.readouterr()
    assert go(snapshot, "--check") == 0
    assert "differs" not in capsys.readouterr().out


def test_check_reads_a_checkout_that_ends_its_lines_in_crlf(
    site: Site, out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A checkout that ends every line of the file the frame wrote in CRLF passes ``--check``,
    which drops the carriage return before each line feed."""
    snapshot = declare(out, Page(site.page("a.html", "<p>A</p>"), "pages/a.html"))
    assert go(snapshot) == 0
    path = out / "FETCHED.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    capsys.readouterr()
    assert go(snapshot, "--check") == 0
    assert "differs" not in capsys.readouterr().out


def test_fetched_md_ends_with_the_mark_of_its_form(site: Site, out: Path) -> None:
    """The frame's last line of FETCHED.md names the file's form, so a file that the frame wrote
    tells itself from a copy's and from an older frame's (ADR-0062, decision 8)."""
    assert upstream.FORM == 2, "the fetch through core's client raised it (ADR-0062, decision 6)"
    assert go(declare(out, Page(site.page("guide.html", "<p>Guide</p>"), "pages/guide.html"))) == 0
    assert fetched(out).endswith(f"`\n\n{MARK}\n")


def response(
    url: str,
    body: bytes = b"x",
    *,
    status: int = 200,
    kind: str = "text/html",
    etag: str | None = None,
    modified: str | None = None,
    redirects: tuple[tuple[int, str], ...] = (),
) -> Response:
    return Response(url, status, body, kind, etag, modified, redirects)


def every_sentence_rendered() -> str:
    """FETCHED.md rendered from made-up rows that reach every sentence and cell the frame
    writes, with and without each option: a pipe escaped in a cell, and an ETag in a longer
    fence and in a padded one among them (finding 3 of the review of
    https://github.com/xippios/sdk-core/pull/429), and a line feed in a note and in a reason,
    each written as a space (https://github.com/xippios/sdk-core/issues/434)."""
    plain = Snapshot(name="Plain", slug="plain", pages=(Page(f"{BASE}/a.html", "pages/a.html"),))
    first = upstream.render_fetched(
        plain,
        [Row(plain.pages[0], response(f"{BASE}/a.html"), b"x")],
        "2026-11-22T09:00:00Z",
        False,
    )
    guide = Page(GUIDE, "pages/guide.md", note="converted")
    part = Page(f"{BASE}/fas.json", "openapi/part.json", excerpt=True)
    sample = Page(f"{API}/items", "samples/items.json", sample=True, keyed=True)
    wadl = Page(f"{BASE}/api.wadl", "wadl/api.wadl")
    toc = Page(f"{BASE}/toc.html", split=True, note="one file per heading")
    faq = Page("https://origin.example.net/faq", "pages/faq.html")
    status = Page(f"{BASE}/status", stable=False, note="a nonce,\nnew in every body")
    admin = Page(f"{BASE}/admin", status=302, note="a login\r\non another host")
    pdf = Page(f"{BASE}/layout.pdf", "files/layout.pdf")
    refused = Page(f"{BASE}/faq", status=403, stable=False, note="kept elsewhere")
    full = Snapshot(
        name="Full",
        slug="full",
        pages=(guide, part, sample, wadl, toc, refused, faq, status, admin, pdf),
        attribution=(
            Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", GUIDE, "the footer"),
            Statement("Terms of Service", GUIDE, "the footer", "https://example.org/tos"),
            Statement("Copyright 2026 Example", pdf.url, "the PDF's producer"),
            Statement("Copyright (c) Example", "", "the footer, read on 2026-11-18"),
        ),
        not_fetched=(NotFetched(FEED, "a feed"),),
        vocabulary=("import license",),
        capture="The first paragraph.\n\nThe second paragraph.",
        pause=5.0,
        sections=lambda rows: [Section("Products found", "| Product |\n| --- |\n| one |")],
        client=AsyncClient(ClientConfig(source="full", version=VERSION, base_url=f"{API}/")),
        variables=("EXAMPLE_ACCOUNT",),
    )
    modified = "Mon, 16 Nov 2026 10:00:00 GMT"
    rows = [
        Row(
            guide,
            response(GUIDE, etag='W/"5-abc"', modified=modified, redirects=((301, f"{GUIDE}/"),)),
            b"# Guide\n",
            guide.note,
        ),
        Row(
            part,
            response(part.url, b'{"whole": 1}', kind="application/json", etag="`x`"),
            b'{"part": 1}',
            "a pipe | and a backslash \\",
        ),
        Row(sample, response(sample.url, b"[]", kind="application/json"), b"[]"),
        Row(wadl, response(wadl.url, b"<a/>", kind="application/xml", modified="0"), b"<a/>"),
        Row(replace(toc, file="entries/a.md"), response(toc.url), b"a", toc.note),
        Row(replace(toc, file="entries/b.md"), response(toc.url), b"b", toc.note),
        Row(refused, response(refused.url, b"", status=403), None, refused.note),
        Row(faq, response(faq.url), b"x"),
        Row(status, response(status.url, etag='"nonce"', modified=modified), None, status.note),
        Row(
            admin,
            response(admin.url, b"", status=302, redirects=((302, "https://login.example.net/"),)),
            None,
            admin.note,
        ),
        Row(pdf, response(pdf.url, b"%PDF-1.4", kind="application/pdf"), b"%PDF-1.4"),
    ]
    return first + upstream.render_fetched(full, rows, "2026-11-22T09:00:00Z", True)


FORMS = {
    # pragma: allowlist nextline secret (a digest of the render, not a key)
    1: "4a19cba319af24e05fc71ebd50586fe9b9d891cf6beb661b0cee492bcf997cf7",
    # pragma: allowlist nextline secret (a digest of the render, not a key)
    2: "734f94a0ca3b707ca6274a2064784c4558bf4c5f4b0c5397ce6262c5c690200c",
}
"""The digest of ``every_sentence_rendered`` for each form of FETCHED.md, by its number.

An entry stands as it is once a release of core writes its form; form 1 took its digest again
while unreleased, when the render gained its escaped pipe and its padded code span, and again
when a line feed in a cell came to be written as a space
(https://github.com/xippios/sdk-core/issues/434). Core 0.4.1 wrote form 1; form 2 is the
fetch through core's client, which names the client's User-Agent and leaves the clauses of a
file kept as recorded and of a second origin (ADR-0062, decisions 4 to 6), so the render of
form 1 no longer stands and its digest is the record of what 0.4.1 wrote."""


def test_a_change_of_what_the_frame_writes_raises_the_form() -> None:
    """https://github.com/xippios/sdk-core/issues/428: the mark names the form of the file that
    the frame writes, so a change of anything the frame writes into FETCHED.md raises FORM
    (ADR-0062, decision 8). A change of the render fails here until FORM is raised and the new
    render's digest stands under it, every earlier entry kept as it is."""
    assert sorted(FORMS) == list(range(1, upstream.FORM + 1))
    digest = hashlib.sha256(every_sentence_rendered().encode()).hexdigest()
    assert digest == FORMS[upstream.FORM], (
        f"the frame's render changed: raise FORM to {upstream.FORM + 1} in "
        f"xippios/core/refresh/upstream.py and add {upstream.FORM + 1}: {digest!r} to FORMS"
    )


# --- the README's short script -----------------------------------------------------------


def test_the_readmes_short_script_runs_on_the_frame(site: Site, out: Path) -> None:
    """The short script that sdk-template renders, as the README's section on the frame
    holds it, declares a snapshot that the frame runs and checks as it stands."""
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## The snapshot script's frame\n", 1)[1]
    script = section.split("```python\n", 1)[1].split("```\n", 1)[0]
    namespace: dict[str, Any] = {"__name__": "refresh_upstream", "__file__": str(out / "x.py")}
    exec(compile(script, "README.md", "exec"), namespace)
    snapshot: Snapshot = namespace["SNAPSHOT"]
    docs = "https://docs.example.org/api"
    site.routes[docs] = (
        200,
        {"Content-Type": "text/html"},
        b"<footer>&copy; 2026 Example Ltd.</footer>",
    )
    site.routes["https://api.example.org/openapi.json"] = (
        200,
        {"Content-Type": "application/json"},
        b"{}",
    )
    site.routes["https://example.org/legal/terms"] = (
        200,
        {"Content-Type": "text/html"},
        b"<h1>Terms of Use</h1>",
    )
    site.routes[f"{docs}/v1/items?limit=2"] = (200, {"Content-Type": "application/json"}, b"[]")
    site.routes[f"{docs}/admin"] = (302, {"Location": "https://login.example.net/"}, b"")
    local = Snapshot(**{**vars(snapshot), "out": out, "pause": 0.0})
    assert go(local) == 0
    assert sorted(path.name for path in out.rglob("*.*")) == [
        "FETCHED.md",
        "api.md",
        "items.json",
        "openapi.json",
        "terms.md",
    ]
    assert go(local, "--check") == 0
    assert local.linked is Snapshot.linked, "a snapshot that links no page declares no linked"
