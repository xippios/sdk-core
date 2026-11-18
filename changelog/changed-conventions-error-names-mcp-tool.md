- Conventions §8: an error that a tool can return and that names another task, the one to
  call instead or the list task that names the known values, names that task's MCP tool
  too, as sdk-usda-nass's does: `list_param_values('state_alpha') lists the known values
  (over MCP, the tool usda_nass_list_param_values).` A task of `BULK_TASKS`, which has no
  tool, is named alone.
  (ADR-0022, §8, https://github.com/xippios/sdk-core/issues/111)
  - Hand-apply: `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — the messages that
    name `list_order_categories` (line 279), `create_person` (line 289), `update_order`
    (line 2263) and `list_accounts` (line 2358) → each names the task's tool beside it,
    `cashctrl_<task>`, and the tests that pin a message follow it — §8.
    `src/xippios/comtrade/errors.py` (sdk-comtrade) — `QueryTooLarge`'s advice naming
    `get_counts` (line 53) → its tool beside it — as above.
    `src/xippios/comtrade/params.py` (sdk-comtrade) — the reasons naming `list_codes`
    (line 232) and the list task of `{task}` (line 305), and the refusals naming
    `get_commodity_series` (lines 1008 and 1017), `get_data` (line 1048) and
    `get_bilateral_data` (line 1140) → each tool beside its task — as above.
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — the refusals naming `get_data`
    (lines 558, 617, 671 and 747), `get_cross_section` (line 622), `list_codes` (lines
    1007, 1018, 1116 and 1278), `list_products` (line 1114), `list_cn8` and `list_hs`
    (line 1272) and the task of `{task}` (line 1119) → each tool beside its task — as
    above.
    `src/xippios/faostat/_client.py` (sdk-faostat) — the refusal naming `list_domains`
    (line 384) → its tool beside it — as above.
    `src/xippios/faostat/tasks.py` (sdk-faostat) — the refusal naming `get_data` (line
    510) → its tool beside it — as above.
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — the refusal naming
    `list_messages` (line 235) → its tool beside it — as above.
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — the refusals naming
    `search_publications` (lines 497 and 708) and `list_releases` (line 628) → each tool
    beside its task — as above.
    `src/xippios/usda/gats/errors.py` (sdk-usda-gats) — `HS6_REASON`, naming
    `list_hs6_commodities` (line 46) → its tool beside it — as above.
    `src/xippios/usda/gats/params.py` (sdk-usda-gats) — the messages naming
    `list_countries` (lines 235, 251 and 389), `list_customs_districts` (lines 438 and
    452) and `list_hs6_commodities` (line 561) → each tool beside its task — as above.
    `src/xippios/usda/psd/params.py` (sdk-usda-psd) — the messages naming
    `get_world_data` (lines 63 and 270), `list_commodity_attributes` (lines 196 and 210),
    and `list_regions` with `list_countries` (lines 254, 269 to 271 and 285) → each tool
    beside its task — as above.
    `src/xippios/usda/wasde/tasks.py` (sdk-usda-wasde) — the reasons naming `list_tables`
    (line 621), `list_commodities` (line 666) and `list_regions` (line 707), and the
    refusal naming `get_table` (line 781) → each tool beside its task — as above.
