- A cut that shows no row, since the first row alone passes the byte bound, says so in its
  note, `the first row alone exceeds the byte cap` or `the row at offset <start> alone
  exceeds the byte cap`, and names no resume offset. Until now it ended `resume with
  start=<start>`, the start the call had just used, so a tool that followed the note asked
  for the same row again.
  (ADR-0016, §8, https://github.com/xippios/sdk-core/issues/175)
