# ADR-0056: The name of each country code in an answer's meta

Status: Accepted · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/375

## Context

https://github.com/xippios/sdk-core/issues/310 decided that a task's country argument takes
upstream's own code and no second code, and that every answer names the country the code stands
for. Without a name an answer for the wrong country comes without a word: in the country lists
of sdk-usda-psd and sdk-usda-gats the code `CN` is Comoros, `GB` Gabon and China `CH`, a known
code passes the check of ADR-0045, and sdk-usda-psd's records carry no name
(https://github.com/xippios/sdk-core/issues/316). Six sources take a country in 37 tasks under
nine parameter names: `country_code` (sdk-usda-psd 4, sdk-usda-esr 2), `partner_code` and
`reporter_code` (sdk-usda-gats 13), `reporter_code`, `partner_code`, `partner2_code`, `reporter`
and `partner` (sdk-comtrade 11), `reporters` and `partners` (sdk-eurostat 5) and `area`
(sdk-faostat 2). A code comes alone, in a list, as a text of several codes, `"757,842"` in
sdk-comtrade, as an integer, or not at all, where the task asks for every country.

`ResultMeta` refuses a field it does not define (ADR-0034, decision 1), so a name needs a field
of its own. ADR-0028 refuses a mapping between sources: a package never maps one source's
concept onto another's.

## Decision

1. **The field.** `ResultMeta.names`, `dict[str, dict[str, str]]`, maps each country parameter
   of the request to its codes and their names: `{"country_code": {"CN": "Comoros"}}`,
   `{"reporter_code": {"757": "Switzerland", "842": "USA"}}`. A code stands under its text as
   the caller gave it, an integer by its digits, so the pair reads beside `meta.request`, and
   its name is the one its packaged list holds, with runs of white space collapsed as a refusal
   shows it (ADR-0045). The field is empty by default and left out of a dumped answer while it
   is empty, so an answer of a task without a country parameter dumps as before, byte for
   byte, over MCP, HTTP and in a store, and the JSON schema of `meta` gains the optional
   property alone.
2. **A decorator of core fills it.** `names_codes(**codes, separator=None)`, from
   `xippios.core`, takes per parameter of the task the list's `PackagedCodes` (ADR-0045) and
   fills `meta.names` on the `Result` the task returns, from the call's arguments with their
   defaults: `@names_codes(country_code=COUNTRIES)`. It wraps an `async def`, a plain function
   and a `sync` facade, whose async twin it wraps too, so a call through the MCP adapter, the
   HTTP router or a server bound by `bind_tasks` is named as a direct call is, and it keeps the
   task's name, module, signature, annotations and docstring, so a tool's schema and a route's
   stay as they were. A parameter left `None` gives no entry: the task asked for every country.
   A text is one code, or several split on `separator`; a list, a tuple or a set gives several
   codes, each text in it split the same way; a code named twice stands once. A text of digits
   is read as the integer for a list of integer codes, and an integer as its text for a list of
   text codes, as sdk-comtrade's and sdk-faostat's tasks send them. Names the task set itself
   are kept, so a task that composes another keeps the names of its answer, and two decorators
   stack, one per separator; a parameter named twice, a name that is no parameter of the task
   and a value that is no `PackagedCodes` are refused with `TypeError` when the module is
   imported.
3. **A code the list lacks withholds the answer.** The task checks its arguments before the
   call with the source's hints and reason, so a code the list lacks never reaches the
   decorator. One that does, sent unchecked, is refused after the call with the refusal of
   `PackagedCodes.check`, `UnknownCode`, or `InvalidRequestError` for a value of the other type,
   whose reason says that the answer is withheld. An answer whose country no list names cannot
   meet the rule of https://github.com/xippios/sdk-core/issues/310, and an entry without a name
   would leave the reader where the rule found it.
4. **What is no `Result`.** A task that raises passes its error untouched and names nothing. A
   task that returns anything but a `Result` raises `TypeError`, naming the task, since every
   task returns the envelope (conventions §2). A download's `Result[Downloaded]` is a `Result`,
   and a bulk task's answer is named as any other.
5. **The family check holds it.** `test_family_country_codes_are_named_in_the_answer` fails a
   task, read or write, bulk or not, with a parameter whose name holds `country`, `countries`,
   `area`, `reporter` or `partner`, in any case, that is neither named by `names_codes` nor
   exempt. Those are the words of the 37 parameters; a word as part of a name catches
   `partner2_code` and `reporters`, and wider words would catch parameters that take no country
   code: `region_code` (a group of countries), sdk-usda-nass's `state` (a state of the United
   States), sdk-eurostat's `geo_level` and the `market_year` of sdk-usda-psd and sdk-usda-esr.
   Among the twelve sources the words catch one parameter that takes no code, sdk-faostat's
   `area_cs`, a coding system. The check fails at once from core 0.4.1 on, as every new
   family check of the package does (https://github.com/xippios/sdk-core/issues/359, part 4).
6. **The exemption.** A task whose code no packaged list can name, or whose parameter the words
   catch and that takes no code, stands in `UNNAMED_CODES` of its tasks module, beside
   `BULK_TASKS` and `NO_TENANT_TASKS`, a mapping of the task's name to its parameters, each with
   the reason: `{"get_data": {"area_cs": "The coding system of area, no code."}}`. The check
   fails an entry that names a task outside the module's `__all__`, a parameter the task does
   not take or the check does not hold, a parameter that `names_codes` names as well, and an
   entry without its reason, so a stale entry does not pass. Whether a source packages the list
   instead is its own row's decision.
7. **Naming a code by its own list is no mapping.** The name is the one the same source's
   packaged list holds for the code, the list upstream serves for that parameter, as
   `UnknownCode` names the closest codes from it. Nothing is mapped onto another source's codes
   or names, and the code stays upstream's own, sent and recorded as given: reference data
   within one source, which ADR-0028, decision 1, keeps among a package's hygiene.
8. **sdk-comtrade's ISO alpha-3.** sdk-comtrade drops its own resolution of ISO alpha-3 and
   refuses such a value with the code it stands for, as sdk-usda-gats does, which makes its
   release a minor. Core's check reads a hint table before the list's type (ADR-0045,
   decision 3), so a table keyed by the alpha-3 codes of its reporter and partner lists refuses
   `"CHE"` naming 757, and core lacks nothing for it.

## Consequences

- Each of the six sources decorates its tasks in its patch, sdk-comtrade in its minor, and
  their answers gain `meta.names`. A test that compares a whole dumped `meta` of a decorated
  task sees the key, and one of any other task sees the dump of today.
- sdk-faostat's `get_data` sends `area` under `area_cs`, ISO3 or M49 where the package holds
  FAO codes alone, and an M49 code can be an FAO code of another country: M49 156 is China, and
  FAO's 156 is New Zealand. Its `area` and `area_cs` stand in `UNNAMED_CODES` until its row
  decides (https://github.com/xippios/sdk-faostat/issues/34). Its tables per domain agree on
  every name they share, so a declaration over all of them names an FAO code of any domain.
- sdk-eurostat's `get_data` takes a country inside its free-form `filters`, which no signature
  shows: the check sees no parameter of it, and the country goes unnamed until its row decides
  (https://github.com/xippios/sdk-eurostat/issues/52).
- A refusal after the call spends the request it withholds: a source that checks its arguments
  first, as conventions §5 has it, never meets it.
