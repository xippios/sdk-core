"""The frames of the scripts a source runs to refresh what it commits from upstream (ADR-0062).

``upstream`` is the frame of ``scripts/refresh_upstream.py``, the snapshot of the documentation
in ``docs/upstream/``: a source declares a ``Snapshot`` with its pages, its attribution and its
hooks, and calls ``run``. The frame sends through core's client, the source's own or one that
it builds from the slug, so it needs no extra, and a converter a source uses stays its own
dependency. ``reference`` is the frame of ``scripts/refresh_reference.py``, the packaged lists
under ``reference/`` and ``enums.py``: a source declares a ``Lists`` with its package, its
client and one ``Listed`` per list, with its fetch, its enum and its origin, and calls the
same ``run``, whose one signature, ``run(declaration, argv=None)``, takes either declaration
(ADR-0062, decision 2). Nothing in core imports this package, and no check compares a
source's committed ``FETCHED.md`` with its ``Snapshot`` without a request: ``--check`` at a
refresh is the one comparison (ADR-0062, decisions 1 and 9).
"""

from xippios.core.refresh.reference import Enumeration, Listed, Lists, run
from xippios.core.refresh.upstream import (
    NotFetched,
    Page,
    Response,
    Row,
    Section,
    Snapshot,
    Statement,
    changed,
    decode,
    dump_json,
    read_json,
)

__all__ = [
    "Enumeration",
    "Listed",
    "Lists",
    "NotFetched",
    "Page",
    "Response",
    "Row",
    "Section",
    "Snapshot",
    "Statement",
    "changed",
    "decode",
    "dump_json",
    "read_json",
    "run",
]
