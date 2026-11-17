- `build_server(..., loopback_only=True)` holds a read server to loopback as a write
  server is held: `main` serves it over `--http` on a loopback `--host` only unless
  `--allow-remote` is passed. `is_loopback_only(server)` answers for both kinds and
  `LOOPBACK_HOSTS` lists the hosts, both exported from `xippios.core.mcp`, and
  `register_tasks` takes `loopback_only` too. The usage line names the entry point that
  runs, and the refusal and the help of `--allow-remote` name the server's kind.
  (ADR-0025, ADR-0026, §8, https://github.com/xippios/sdk-core/issues/167)
  - Hand-apply: `src/xippios/google/mail/mcp.py` (sdk-google-mail) — `build_server(...,
    loopback_only=True)` for the read server — core holds it to loopback now.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — the loopback check in
    `apply_options` and the copy of `_LOOPBACK_HOSTS` deleted — core's `main` refuses the
    host itself.
    `src/xippios/mcp/app.py` (xippios-mcp) — the copy of `_LOOPBACK_HOSTS` →
    `LOOPBACK_HOSTS`, and `is_write_server` → `is_loopback_only` in the loopback check — an
    endpoint with `auth: none` holds a loopback-only read server as it holds a write server.
