- `download` refuses a `dest` that is a directory, or whose directory does not exist, with
  `InvalidRequestError` in the client's source's name, where it raised `ValueError`, with
  the same two texts and still before anything is sent, `before_request` included. Code
  that caught `ValueError` for it catches `InvalidRequestError`. Its documents and
  `Downloaded`'s state the mode of the file it writes, `0600`, as `tempfile.mkstemp`
  creates it, also over a file of another mode.
  (ADR-0019, ADR-0007, §5, §6, https://github.com/xippios/sdk-core/issues/152)
  - Hand-apply: `src/xippios/eurostat/tasks.py` (sdk-eurostat) — `_target` (lines 1508 to
    1522) goes, and `download_dataset_async` (line 1651) and `download_trade_async` (line
    1767) pass `Path(dest)` — core refuses a bad `dest` with eurostat's two texts before
    any request, as `tests/test_tasks.py` asserts at lines 1482, 1485, 2650 and 2653,
    which pass unchanged.
    `src/xippios/eurostat/api/sdmx.py` (sdk-eurostat) — `data_query`'s `Raises:` names
    `InvalidRequestError` for a bad `dest` where it names `ValueError` (line 195) — core's
    refusal is the taxonomy's.
    `src/xippios/cashctrl/api/_download.py` (sdk-cashctrl) — the docstrings of `check_dest`
    and `download` drop "where core's `download` raises `ValueError`" (lines 96 to 98 and
    128 to 130). `check_dest` stays, since `download` streams into a temporary file of its
    own, which core's check never sees, and a report's tree is read before it — core no
    longer raises `ValueError`.
