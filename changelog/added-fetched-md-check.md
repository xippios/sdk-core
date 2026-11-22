- `compare_fetched(snapshot)` of `xippios.core.refresh` compares a source's committed
  `FETCHED.md` with its `Snapshot` and sends no request, returning the lines that differ, and
  the family check holds every source to it through the declaration that its
  `scripts/refresh_upstream.py` names `SNAPSHOT`. The frame ends `FETCHED.md` with a line that
  names the file's form, and a file without it or of an older form passes, so an adoption
  passes and a source is held from its first refresh on. What only a response knows, the times,
  ETags, sizes, hashes and what the hooks made from answers, is read back from the file and not
  judged. (ADR-0046, §3, https://github.com/xippios/sdk-core/issues/426,
  https://github.com/xippios/sdk-core/issues/428)
  - Hand-apply: `scripts/refresh_upstream.py` — its `Snapshot` named `SNAPSHOT` at the top
    level, which imports and declares alone, sends no request and writes no file, its run
    under `if __name__ == "__main__":`, and no `linked` where the script links no page — the
    family check loads the script by that name and passes one that names its declaration
    otherwise, so no test breaks without it and the committed `FETCHED.md` goes unheld, and a
    `linked` hook makes the check read back every row that no declared page owns.
