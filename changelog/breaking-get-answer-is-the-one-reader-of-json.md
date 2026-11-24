- `get_answer` is the client's one reader of JSON, and `get_json` leaves `AsyncClient`. A
  wrapper reads `answer.payload` and hands `answer.retrieved_at` to its task's `ResultMeta`,
  since `retrieved_at` is the client's fact for every answer and the oldest one where a task
  assembles several. `get_answer` alone stores an answer, so a client with a cache now keeps
  the answers of every path its lifetimes name.
  (ADR-0037, §4, §6, https://github.com/xippios/sdk-core/issues/479)
  - Hand-apply: `src/xippios/cashctrl/api/account_category_list.py` (sdk-cashctrl) — at
    `:25`, `raw = await client_for(org).get_json(...)` becomes `answer = await
    client_for(org).get_answer(...)`, the wrapper reading `answer.payload` and returning
    `answer.retrieved_at` with its value for the task's `ResultMeta` (§4) — `get_json`
    leaves, and until it stands every test of the wrapper fails at the call, as do the
    other 24 wrappers of `src/xippios/cashctrl/api/` below.
    `src/xippios/cashctrl/api/account_costcenter_list.py` — at `:92`, the same — the same.
    `src/xippios/cashctrl/api/account_list.py` — at `:92`, the same — the same.
    `src/xippios/cashctrl/api/account_read.py` — at `:26`, the same — the same.
    `src/xippios/cashctrl/api/currency_list.py` — at `:21`, the same — the same.
    `src/xippios/cashctrl/api/customfield_list.py` — at `:35`, the same — the same.
    `src/xippios/cashctrl/api/fiscalperiod_list.py` — at `:21`, the same — the same.
    `src/xippios/cashctrl/api/fiscalperiod_read.py` — at `:34`, the same — the same.
    `src/xippios/cashctrl/api/history_list.py` — at `:91`, the same — the same.
    `src/xippios/cashctrl/api/journal_list.py` — at `:142`, the same — the same.
    `src/xippios/cashctrl/api/journal_read.py` — at `:27`, the same — the same.
    `src/xippios/cashctrl/api/location_list.py` — at `:23`, the same — the same.
    `src/xippios/cashctrl/api/order_bookentry_list.py` — at `:26`, the same — the same.
    `src/xippios/cashctrl/api/order_bookentry_read.py` — at `:30`, the same — the same.
    `src/xippios/cashctrl/api/order_category_list.py` — at `:42`, the same — the same.
    `src/xippios/cashctrl/api/order_document_read.py` — at `:29`, the same — the same.
    `src/xippios/cashctrl/api/order_list.py` — at `:135`, the same — the same.
    `src/xippios/cashctrl/api/order_read.py` — at `:28`, the same — the same.
    `src/xippios/cashctrl/api/person_category_list.py` — at `:24`, the same — the same.
    `src/xippios/cashctrl/api/person_list.py` — at `:135`, the same — the same.
    `src/xippios/cashctrl/api/person_read.py` — at `:28`, the same — the same.
    `src/xippios/cashctrl/api/person_title_list.py` — at `:23`, the same — the same.
    `src/xippios/cashctrl/api/report_element_data.py` — at `:81`, the same — the same.
    `src/xippios/cashctrl/api/report_tree.py` — at `:24`, the same — the same.
    `src/xippios/cashctrl/api/tax_list.py` — at `:21`, the same — the same.
    `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — at `:243-263`, `_meta` takes the
    wrappers' `retrieved_at` for every answer, not for a download's alone — a task's
    `meta.retrieved_at` is the client's fact (§4), which no test asserts yet.
    `tests/test_errors.py` (sdk-cashctrl) — at `:418`, `:566`, `:575` and `:584`,
    `.get_json(path)` becomes `.get_answer(path)` — the tests fail at `get_json`.
    `tests/test_record_fixture.py` (sdk-cashctrl) — at `:2252`,
    `recorder.sync(AsyncClient(config).get_json)` takes `get_answer` and reads `.payload`
    — the test fails at `get_json`.
    `src/xippios/comtrade/api/get.py` (sdk-comtrade) — at `:89` and `:148-150`, `raw =
    await client.get_json(...)` becomes `answer = await client.get_answer(...)`, the
    wrapper reading `answer.payload` and returning `answer.retrieved_at` for the task's
    `ResultMeta` (§4) — `get_json` leaves, and until it stands every test of the wrapper
    fails at the call, as do the seven wrappers below.
    `src/xippios/comtrade/api/get_bilateral_data.py` — at `:79-90`, the same — the same.
    `src/xippios/comtrade/api/get_comtrade_releases.py` — at `:35`, the same, `auth=None`
    kept — the same.
    `src/xippios/comtrade/api/get_da.py` — at `:62-71`, the same — the same.
    `src/xippios/comtrade/api/get_live_update.py` — at `:24`, the same — the same.
    `src/xippios/comtrade/api/get_metadata.py` — at `:46-49`, the same — the same.
    `src/xippios/comtrade/api/get_trade_balance.py` — at `:88`, the same — the same.
    `src/xippios/comtrade/api/get_world_share.py` — at `:72-76`, the same, `auth=None`
    kept — the same.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — at `:131`, `:408`, `:447`, `:464`,
    `:570`, `:667`, `:695`, `:747` and `:1066`, each `ResultMeta` takes the wrapper's
    `retrieved_at` — a task's `meta.retrieved_at` is the client's fact (§4).
    `tests/test_tasks.py` (sdk-comtrade) — at `:1129-1131` and `:1274-1276`,
    `once.get_json(...)` and `client.get_json(...)` become `get_answer(...)` — the two
    tests fail at `get_json`.
    `src/xippios/google/mail/api/get_profile.py` (sdk-google-mail) — at `:27`,
    `client.get_json(...)` becomes `client.get_answer(...)`, the wrapper reading
    `answer.payload` and returning `answer.retrieved_at` for the task's `ResultMeta` (§4)
    — `get_json` leaves, and until it stands every test of the wrapper fails at the call,
    as do the five wrappers below.
    `src/xippios/google/mail/api/labels_list.py` — at `:26`, the same — the same.
    `src/xippios/google/mail/api/messages_attachments_get.py` — at `:43`, the same — the
    same.
    `src/xippios/google/mail/api/messages_get.py` — at `:55`, the same — the same.
    `src/xippios/google/mail/api/messages_list.py` — at `:54`, the same — the same.
    `src/xippios/google/mail/api/threads_get.py` — at `:51`, the same — the same.
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — at `:93-100`, `_meta` takes the
    wrappers' `retrieved_at` — a task's `meta.retrieved_at` is the client's fact (§4),
    and `tests/test_tasks.py:134-146` then compares it with the answer's time.
    `tests/test_tasks.py` (sdk-google-mail) — at `:246`, `client.get_json("messages",
    ...)` becomes `get_answer` with `.payload` — the test fails at `get_json`.
    `src/xippios/usda/esmis/api/agency_find_all.py` (sdk-usda-esmis) — at `:26`, `raw =
    await client.get_json(...)` becomes `answer = await client.get_answer(...)`, the
    wrapper reading `answer.payload` and returning `answer.retrieved_at` for the task's
    `ResultMeta` (§4) — `get_json` leaves, and until it stands every test of the wrapper
    fails at the call, as do the eleven wrappers below.
    `src/xippios/usda/esmis/api/agency_find_by_acronym.py` — at `:36`, the same — the same.
    `src/xippios/usda/esmis/api/agency_find_by_id.py` — at `:35`, the same — the same.
    `src/xippios/usda/esmis/api/publication_find_all.py` — at `:31`, the same — the same.
    `src/xippios/usda/esmis/api/publication_find_by_agency.py` — at `:37`, the same — the
    same.
    `src/xippios/usda/esmis/api/publication_find_by_id.py` — at `:36`, the same — the same.
    `src/xippios/usda/esmis/api/publication_find_by_identifier.py` — at `:45`, the same —
    the same.
    `src/xippios/usda/esmis/api/publication_search.py` — at `:36`, the same — the same.
    `src/xippios/usda/esmis/api/release_find_all.py` — at `:29`, the same — the same.
    `src/xippios/usda/esmis/api/release_find_by_id.py` — at `:34`, the same — the same.
    `src/xippios/usda/esmis/api/release_find_by_identifier.py` — at `:49`, the same — the
    same.
    `src/xippios/usda/esmis/api/release_find_by_pub_id.py` — at `:39`, the same — the same.
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — at `:355`, `:385`, `:467`, `:477`,
    `:505`, `:574` and `:669`, each `ResultMeta` takes the wrapper's `retrieved_at` — a
    task's `meta.retrieved_at` is the client's fact (§4).
    `src/xippios/usda/esr/api/get_commodities.py` (sdk-usda-esr) — at `:29`,
    `client.get_json(...)` becomes `client.get_answer(...)`, the wrapper reading
    `answer.payload` and returning `answer.retrieved_at` for the task's `ResultMeta` (§4)
    — `get_json` leaves, and until it stands every test of the wrapper fails at the call,
    as do the six wrappers below. The answers then reach the cache that the source's
    adoption gives its client (ADR-0061, decision 11).
    `src/xippios/usda/esr/api/get_all_countries_data.py` — at `:48`, the same — the same.
    `src/xippios/usda/esr/api/get_countries.py` — at `:30`, the same — the same.
    `src/xippios/usda/esr/api/get_country_data.py` — at `:52`, the same — the same.
    `src/xippios/usda/esr/api/get_data_release_info.py` — at `:32`, the same — the same.
    `src/xippios/usda/esr/api/get_regions.py` — at `:30`, the same — the same.
    `src/xippios/usda/esr/api/get_units_of_measure.py` — at `:31`, the same — the same.
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — at `:298`, `:369`, `:422`, `:516`,
    `:579` and `:701`, each `ResultMeta` takes the wrapper's `retrieved_at` — a task's
    `meta.retrieved_at` is the client's fact (§4).
    `tests/test_client.py` (sdk-usda-esr) — at `:217`, `:304` and `:455`, `get_json(...)`
    becomes `get_answer(...)` with `.payload` where its value is compared — the three tests
    fail at `get_json`.
    `src/xippios/usda/gats/api/get_census_exports.py` (sdk-usda-gats) — at `:50`,
    `client.get_json(...)` becomes `client.get_answer(...)`, the wrapper reading
    `answer.payload` and returning `answer.retrieved_at` for the task's `ResultMeta` (§4)
    — `get_json` leaves, and until it stands every test of the wrapper fails at the call,
    as do the thirteen wrappers below.
    `src/xippios/usda/gats/api/get_census_import.py` — at `:46`, the same — the same.
    `src/xippios/usda/gats/api/get_census_re_exports.py` — at `:48`, the same — the same.
    `src/xippios/usda/gats/api/get_countries.py` — at `:34`, the same — the same.
    `src/xippios/usda/gats/api/get_customs_districts.py` — at `:36`, the same — the same.
    `src/xippios/usda/gats/api/get_customs_districts_exports.py` — at `:51`, the same —
    the same.
    `src/xippios/usda/gats/api/get_customs_districts_imports.py` — at `:50`, the same —
    the same.
    `src/xippios/usda/gats/api/get_customs_districts_re_exports.py` — at `:53`, the same —
    the same.
    `src/xippios/usda/gats/api/get_hs6_commodities.py` — at `:35`, the same — the same.
    `src/xippios/usda/gats/api/get_regions.py` — at `:32`, the same — the same.
    `src/xippios/usda/gats/api/get_un_trade_exports.py` — at `:56`, the same — the same.
    `src/xippios/usda/gats/api/get_un_trade_imports.py` — at `:52`, the same — the same.
    `src/xippios/usda/gats/api/get_un_trade_re_exports.py` — at `:52`, the same — the
    same.
    `src/xippios/usda/gats/api/get_units_of_measure.py` — at `:35`, the same — the same.
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) — at `:605`, `:1050` and `:1540`, the
    data tasks' `ResultMeta` takes the wrapper's `retrieved_at` beside `published_at` — a
    task's `meta.retrieved_at` is the client's fact (§4).
    `tests/test_client.py` (sdk-usda-gats) — at `:208`, `:231`, `:341` and `:601`,
    `get_json(...)` becomes `get_answer(...)` — the four tests fail at `get_json`.
    `src/xippios/usda/nass/api/api_get.py` (sdk-usda-nass) — at `:28`, `client.get_json(...)`
    becomes `client.get_answer(...)`, the wrapper reading `answer.payload` and returning
    `answer.retrieved_at` for the task's `ResultMeta` (§4) — `get_json` leaves, and until
    it stands every test of the wrapper fails at the call.
    `src/xippios/usda/nass/api/get_counts.py` — at `:22`, the same — the same.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — at `:202-203`, `_meta` takes the
    wrappers' `retrieved_at` — a task's `meta.retrieved_at` is the client's fact (§4).
    `src/xippios/usda/psd/api/get_commodities.py` (sdk-usda-psd) — at `:30`,
    `client.get_json(...)` becomes `client.get_answer(...)`, the wrapper reading
    `answer.payload` and returning `answer.retrieved_at` for the task's `ResultMeta` (§4)
    — `get_json` leaves, and until it stands every test of the wrapper fails at the call,
    as do the eight wrappers below.
    `src/xippios/usda/psd/api/get_commodity_attributes.py` — at `:30`, the same — the same.
    `src/xippios/usda/psd/api/get_commodity_data_by_year.py` — at `:40`, the same — the
    same.
    `src/xippios/usda/psd/api/get_countries.py` — at `:31`, the same — the same.
    `src/xippios/usda/psd/api/get_country_commodity_data_by_year.py` — at `:48`, the same
    — the same.
    `src/xippios/usda/psd/api/get_data_release_info.py` — at `:37`, the same — the same.
    `src/xippios/usda/psd/api/get_regions.py` — at `:30`, the same — the same.
    `src/xippios/usda/psd/api/get_units_of_measure.py` — at `:30`, the same — the same.
    `src/xippios/usda/psd/api/get_world_commodity_data_by_year.py` — at `:40`, the same —
    the same.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — at `:211`, `:246`, `:300`, `:425`,
    `:547`, `:644` and `:703`, each `ResultMeta` takes the wrapper's `retrieved_at` — a
    task's `meta.retrieved_at` is the client's fact (§4).
    `tests/test_client.py` (sdk-usda-psd) — at `:156`, `:170` and `:353`, `get_json(...)`
    becomes `get_answer(...)` with `.payload` where its value is compared — the three tests
    fail at `get_json`.
    `src/xippios/x/api/get_lists_members.py` (sdk-x) — at `:79`, `raw = await
    client.get_json(...)` becomes `answer = await client.get_answer(...)`, the wrapper
    reading `answer.payload` and returning `answer.retrieved_at` for the task's
    `ResultMeta` (§4) — `get_json` leaves, and until it stands every test of the wrapper
    fails at the call, as do the eight wrappers below.
    `src/xippios/x/api/get_lists_posts.py` — at `:83`, the same — the same.
    `src/xippios/x/api/get_posts_by_ids.py` — at `:71`, the same — the same.
    `src/xippios/x/api/get_posts_counts_all.py` — at `:83`, the same — the same.
    `src/xippios/x/api/get_posts_counts_recent.py` — at `:81`, the same — the same.
    `src/xippios/x/api/get_usage.py` — at `:55`, the same — the same.
    `src/xippios/x/api/get_users_by_usernames.py` — at `:72`, the same — the same.
    `src/xippios/x/api/get_users_posts.py` — at `:91`, the same — the same.
    `src/xippios/x/api/search_posts_recent.py` — at `:130`, the same — the same.
    `src/xippios/x/tasks.py` (sdk-x) — at `:189-191`, `_meta` takes the wrappers'
    `retrieved_at` — a task's `meta.retrieved_at` is the client's fact (§4).
    `tests/test_client.py` (sdk-x) — at `:214`, `:232` and `:246`, `get_json(...)` becomes
    `get_answer(...)` — the three tests fail at `get_json`.
    `scripts/probe_accounts.py` (sdk-x) — at `:1181`, `partial(client.get_json,
    USAGE_PATH)` takes `get_answer` and reads `.payload` — mypy over `scripts/` fails at
    `get_json`, and the script at its call.
