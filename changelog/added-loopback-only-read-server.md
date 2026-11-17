- `build_server(..., loopback_only=True)` holds a read server to loopback as a write
  server is held: `main` serves it over `--http` on a loopback `--host` only unless
  `--allow-remote` is passed. `is_loopback_only(server)` answers for both kinds and
  `LOOPBACK_HOSTS` lists the hosts, both exported from `xippios.core.mcp`, and
  `register_tasks` takes `loopback_only` too. The usage line and the prefix of `main`'s
  errors name the entry point that runs instead of `server.name`, and the refusal and the
  help of `--allow-remote` name the server's kind.
  (ADR-0025, ADR-0026, §8, https://github.com/xippios/sdk-core/issues/167)
  - Hand-apply: `src/xippios/google/mail/mcp.py` (sdk-google-mail) — `build_server(...,
    loopback_only=True)` for the read server — core holds it to loopback now.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — the loopback check in
    `apply_options` and the copy of `_LOOPBACK_HOSTS` deleted — core's `main` refuses the
    host itself.
    `tests/test_account_lock.py` (sdk-google-mail) — the `xippios-google-mail: error:`
    assertions name the entry point, with `sys.argv` set as the `entry_point` fixture of
    core's `tests/mcp/test_cli.py` sets it, and the remote refusal of the read server
    asserts core's message — `main`'s errors name the entry point that runs, `pytest` in
    a test run, and the source's own check is gone.
    `tests/test_org_lock.py` (sdk-cashctrl) — the `xippios-cashctrl: error:` assertions
    name the entry point, with `sys.argv` set as in sdk-google-mail — as there.
    `src/xippios/mcp/app.py` (xippios-mcp) — the copy of `_LOOPBACK_HOSTS` →
    `LOOPBACK_HOSTS`, and `is_write_server` → `is_loopback_only` in the loopback check — an
    endpoint with `auth: none` holds a loopback-only read server as it holds a write server.
    `tests/test_app.py` (xippios-mcp) — `test_the_loopback_hosts_are_cores`, which reads
    `core_cli._LOOPBACK_HOSTS`, deleted with the copy, and the loopback cases parametrized
    on `LOOPBACK_HOSTS` — core exports the list.
