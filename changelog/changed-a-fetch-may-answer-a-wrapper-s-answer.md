- A list's fetch in the reference frame and a fetch of `LIVE_LISTS` may answer an `api/`
  wrapper's `Answer`, read by its `payload`, so a wrapper is a fetch as it stands, and
  `assert_list_current` takes one as `current`. An `Answer` whose payload is not the list, the
  body that holds the records say, stops the frame's run or fails the comparison, and so does a
  mapping, a text or bytes handed to the comparison as either side, no longer read as codes of
  its keys or characters; each says to hand the records.
  (ADR-0062, ADR-0055, https://github.com/xippios/sdk-core/issues/577)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-comtrade, sdk-eurostat, sdk-faostat,
    sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd, sdk-usda-wasde)
    — a records wrapper of the script's own, which only takes a wrapper's `Answer.payload`,
    may give way to the wrapper itself in its `Listed` — the frame reads the payload.
    `tests/test_live.py` — a records wrapper of the test's own, which only takes a wrapper's
    `Answer.payload`, may give way to the wrapper itself in `LIVE_LISTS` or in the call of
    `assert_list_current` — the comparison reads the payload.
