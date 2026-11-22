"""The frames of the scripts a source runs to refresh what it commits from upstream (ADR-0046).

``upstream`` is the frame of ``scripts/refresh_upstream.py``, the snapshot of the documentation
in ``docs/upstream/``: a source declares a ``Snapshot`` with its pages, its attribution and its
hooks, and calls ``run``. The frame needs the standard library alone, and a converter a source
uses stays its own dependency. ``reference`` is the frame of ``scripts/refresh_reference.py``,
the packaged lists under ``reference/`` and ``enums.py``: a source declares one ``Listed`` per
list, with its fetch, its enum and its origin, and calls the same ``run`` with its package and
its client (ADR-0051). ``compare_fetched`` compares a source's committed ``FETCHED.md`` with
its ``Snapshot`` and sends no request; the family check of ``xippios.core.testing`` calls it,
and nothing else in core imports this package (ADR-0046, decision 6).
"""

from xippios.core.refresh.reference import Enumeration, Listed, run
from xippios.core.refresh.upstream import (
    Credentials,
    NotFetched,
    Page,
    Response,
    Row,
    Section,
    Snapshot,
    Statement,
    changed,
    compare_fetched,
    decode,
    dump_json,
    load_json,
)

__all__ = [
    "Credentials",
    "Enumeration",
    "Listed",
    "NotFetched",
    "Page",
    "Response",
    "Row",
    "Section",
    "Snapshot",
    "Statement",
    "changed",
    "compare_fetched",
    "decode",
    "dump_json",
    "load_json",
    "run",
]
