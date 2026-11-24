- Core's pytest plugin sets the placeholder key in each secret variable of the source's
  `_client.ENV_VARS` in every test not marked `live`, a pattern such as
  `EXAMPLE_<NAME>_API_KEY` once for each reserved tenant of the `Tenants` that `_client.py`
  holds, and a fixture of the source's own that sets one of them runs after it. It replaces the
  ini option `xippios_placeholder_key_envs`, which leaves, so a source declares its variables
  once. (ADR-0035, §10, https://github.com/xippios/sdk-core/issues/475)
  - Hand-apply: `pyproject.toml` (sdk-cashctrl `:109-112`, sdk-comtrade `:107-109`,
    sdk-faostat `:105-107`, sdk-google-mail `:110-113`, sdk-usda-esr `:105-107`, sdk-usda-gats
    `:105-107`, sdk-usda-nass `:108-110`, sdk-usda-psd `:105-107`, sdk-x `:108-110`) — the
    line `xippios_placeholder_key_envs = [...]` and the comment above it leave, with
    sdk-template's update where the template rendered them and by hand where the source wrote
    its own, sdk-faostat's comment — pytest warns `Unknown config option` on every run until
    they leave, and no test breaks, since each source's `ENV_VARS` declares the same
    variables secret.
    `tests/conftest.py` (sdk-cashctrl `:9-10`, sdk-comtrade `:3`, sdk-google-mail `:17`) —
    the comment that names `xippios_placeholder_key_envs` names `_client.ENV_VARS`, with
    sdk-template's update — no test breaks, and sdk-cashctrl's `demo_only` still sets the
    reserved organisation's subdomain after the plugin has set it to the placeholder.
    `CLAUDE.md` (sdk-cashctrl `:290`, sdk-comtrade `:159` and `:334`, sdk-faostat `:244`,
    sdk-google-mail `:187`, sdk-usda-esr `:180`, sdk-usda-gats `:113`, sdk-usda-nass `:113`,
    sdk-usda-psd `:116`, sdk-x `:121`) — the sentence that names `xippios_placeholder_key_envs`
    in `pyproject.toml` names the secret variables of `_client.ENV_VARS` — the option has left
    core, and no test breaks.
    `tests/test_auth.py` (sdk-google-mail) — the module's docstring (lines 8 and 9) names
    `_client.ENV_VARS` in place of `xippios_placeholder_key_envs` — no test breaks.
    `tests/test_client.py` (sdk-faostat) — the module's docstring (lines 12 and 13) names
    `_client.ENV_VARS` in place of `pyproject.toml`'s `xippios_placeholder_key_envs` — no
    test breaks.
