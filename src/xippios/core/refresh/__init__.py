"""The frames of the scripts a source runs to refresh what it commits from upstream (ADR-0046).

``upstream`` is the frame of ``scripts/refresh_upstream.py``, the snapshot of the documentation
in ``docs/upstream/``: a source declares a ``Snapshot`` with its pages, its attribution and its
hooks, and calls ``run``. The frame needs the standard library alone, and a converter a source
uses stays its own dependency. Nothing else in core imports this package.
"""

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
    decode,
    dump_json,
    load_json,
    run,
)

__all__ = [
    "Credentials",
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
    "load_json",
    "run",
]
