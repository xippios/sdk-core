# ADR-0067: What the envelope carries: notes, the names of codes and integers

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/478 · Supersedes ADR-0056

## Context

ADR-0056 put the name of each country code of a request into `meta.names`, filled by the
decorator `names_codes`, and its family check found the parameters that take a country by five
words of their names. The boundary of a source package says that a value which upstream's record
does not state stands in the envelope, never on the record, and that core gives it its place: the
names of the codes in an answer's rows and one place for a task's note (ADR-0060, decision 8).
The question on https://github.com/xippios/sdk-core/issues/478 asked what the envelope carries
beyond the request's own codes, and its answer decided five parts.

- Four tasks say something about their answer that no row states: the market years that
  sdk-usda-esr's `get_weekly_series` and sdk-usda-psd's `get_time_series` pass over, the years
  without data that sdk-usda-nass's `get_data` skips under `split_by_year`, and the rule that ends
  the walk of sdk-usda-esmis's `list_recent_releases`. Each says it in its docstring alone.
- The rows of sdk-usda-psd, sdk-usda-esr and sdk-usda-gats carry a country's code, and some a
  unit's, without its name, and a request's names cover only the codes the caller gave: an answer
  for every country names none. sdk-faostat's rows carry the area's name beside its code.
- ADR-0056, decision 5, caught sdk-faostat's `area_cs`, a coding system and no code, by the word
  `area`, and decision 6 exempted it in `UNNAMED_CODES`. The answer removes the exemption and
  keeps `area_cs`, since a caller can set what upstream documents (ADR-0060, decision 4).
- ADR-0031, decision 1, serialises every `Decimal` as a JSON number through a float, so a whole
  number that upstream sent reads `16217.0`. Nine of the twelve sources serve a `Decimal`.

ADR-0056 changes in decisions 1, 2, 5 and 6, so this record supersedes it and restates each of its
decisions that stands. Every piece here is part of the result envelope, the family's contract, for
which one consumer is enough (ADR-0059, decision 4); each has its consumers among the sources all
the same, named in its decision.

## Decision

1. **Notes.** `ResultMeta.notes`, `list[str]`, holds one sentence per fact that a task says about
   its answer and that neither a record nor another field of `meta` states: the periods that a
   series passed over, the rule that ended a walk of pages, a record's code that its list does not
   name (decision 7). It is empty by default and left out of a dumped answer while it is empty, so
   an answer without a note dumps as before, byte for byte, and the JSON schema of `meta` gains an
   optional property. A blank note is refused. A cursor is no note: ADR-0034 keeps it on the data
   under upstream's name. A note is text, with no kind and no field per case, since a closed list
   of kinds would be core's for four tasks and a field per case would grow with each new one
   (https://github.com/xippios/sdk-core/issues/478, part 1). Its consumers are the four tasks of
   the context.
2. **The field `names`,** from ADR-0056, decision 1, widened to the records. `ResultMeta.names`,
   `dict[str, dict[str, str]]`, maps each code parameter of the request, and each code field of the
   answer's records that its model names by a packaged list, to its codes and their names:
   `{"country_code": {"CN": "Comoros"}}`. A request's code stands under its text as the caller gave
   it and a record's under its text as upstream sent it, an integer by its digits, and its name is
   the one its packaged list holds, with runs of white space collapsed as a refusal shows it
   (ADR-0045). A parameter and a field of one name share one entry. The field is empty by default
   and left out of a dumped answer while it is empty, as before.
3. **A decorator names a request's codes,** ADR-0056, decision 2, without its separator.
   `names_codes(**codes)`, from `xippios.core`, takes per parameter of the task the list's
   `PackagedCodes` and fills `meta.names` on the `Result` the task returns, from the call's
   arguments with their defaults. It wraps an `async def`, a plain function and a `sync` facade,
   whose async twin it wraps too, and keeps the task's name, module, signature, annotations and
   docstring. A parameter left `None` gives no entry. A text is one code, and a list, a tuple or a
   set gives several. A text of digits is read as the integer for a list of integer codes, and an
   integer as its text for a list of text codes. Names the answer carries already are kept, its
   records' among them, and the decorator's own take a code's place where both name it, so two
   decorators stack; a parameter named twice, a name that is no parameter of the task and a value
   that is no `PackagedCodes` are refused with `TypeError` when the module is imported. This
   reverses the `separator` of ADR-0056, decision 2: several values of one filter are a list
   (ADR-0061, decision 1), so no caller passes a text of several codes, and a stale
   `separator=","` is refused as a value that is no `PackagedCodes`.
4. **A request's code that the list lacks withholds the answer,** ADR-0056, decision 3, as
   ADR-0045's amendment of 2026-11-24 words it. The task checks its arguments before the call, so
   such a code never reaches the decorator. One that does is refused after the call with the
   list's refusal, whose reason says that upstream was asked and that the answer is withheld.
5. **What is no `Result`,** ADR-0056, decision 4, unchanged. A task that raises passes its error
   untouched. A decorated task that returns anything but a `Result` raises `TypeError`, naming the
   task. A download's `Result[Downloaded]` is a `Result`, and a bulk task's answer is named as any
   other.
6. **A record's model names its codes** (https://github.com/xippios/sdk-core/issues/478, parts 2
   and 4). `NamedBy`, exported from `xippios.core`, marks a code field in its annotation, with the
   packaged list that names its codes, `Annotated[str, NamedBy(REGIONS)]`, or with the field of
   the same record in which upstream sends the name, `Annotated[int, NamedBy("item")]`. A
   `Result`, built or validated, reads the records its data holds, in a list, a tuple, a set or a
   mapping's values and in the fields of a record whose annotation names a model, and puts each
   code of a field marked with a list into `meta.names` under the field's name, beside the names
   already there, so every task that returns the model is named without a decorator; a new
   `ResultMeta` takes the place of the task's, whose object is not changed. A field marked with a
   field's name takes no entry: the name stands on the record beside its code in upstream's
   words, and a value that upstream's record states stays on the record (ADR-0060, decisions 3, 7
   and 8). A field holds one code, text or an integer, or a list of them, and `None` holds none. A
   mark reads on the field and on an optional code, `Annotated[str, NamedBy(REGIONS)] | None` or
   `Optional` of it, the plain spelling. A mark that cannot name, a field marked twice, a mark on
   a list's items or in a union of codes, which no answer would read, a marked field that holds
   no code, or a named field that is no other field of the model or holds no text, raises
   `TypeError` when an answer holds the record. `NamedBy` is one public name, and its consumers are sdk-usda-psd, sdk-usda-esr and
   sdk-usda-gats by their lists and sdk-faostat by its label field.
7. **A record's code that the list lacks is left out and noted.** It is left out of `meta.names`,
   and one note per field and list names the codes left out, the list and its fetch date, so
   that where two models of one answer mark fields of one name with two lists, each note says
   its own list's gaps and no code that the other list names in `meta.names`. The answer is not
   withheld, as it is for a code of the request, since upstream returned the code
   (https://github.com/xippios/sdk-core/issues/478, part 5 of its recommendation, which the
   answer kept). A composed answer built again says the note once.
8. **The family check reads the model's declaration.**
   `test_family_code_names_are_declared_on_the_model` reads every pydantic model that a task's
   `Result[T]` reaches, read and write tasks alike, bulk or not, and fails each mark that cannot
   name, as decision 6 has them, so a code and its label stand side by side. It reads no word of a
   parameter's name, and whether a code is owed a name is the review's, by conventions §4. This
   reverses ADR-0056, decision 5, whose five words were the parameter names of six sources, shaped
   for one domain, and caught `area_cs`, which takes no code; the answer on
   https://github.com/xippios/sdk-core/issues/478 says nothing of such a parameter and keeps it
   without an exemption. It also reverses ADR-0056, decision 6: `UNNAMED_CODES` leaves with its
   reader and its tests (https://github.com/xippios/sdk-core/issues/478, part 3).
9. **Naming a code by its own list is no mapping,** ADR-0056, decision 7, unchanged. The name is
   the one the same source's packaged list holds for the code, the list upstream serves for that
   parameter or field. Nothing is mapped onto another source's codes or names, and the code stays
   upstream's own, sent and recorded as given: reference data within one source, which ADR-0028,
   decision 1, keeps among a package's hygiene.
10. **Numbers** (https://github.com/xippios/sdk-core/issues/478, part 5). A `Decimal` whose exponent
    is zero or more, without fractional digits, serialises as a JSON integer, `16217`, and one with
    fractional digits as a JSON number with the digits upstream sent, so upstream's `16217.0`
    stays. The exponent decides and never the value, so no digit that upstream sent is dropped. A
    `Decimal` that is no finite number serialises as before, and Python keeps the `Decimal`. It
    holds in both adapters and in `dump_upstream`, and it amends ADR-0031, decision 1. A parsed
    reading stands under `<name>_number` beside upstream's text, a rule of the conventions that
    ADR-0060, decision 7, states.
11. **sdk-comtrade's ISO alpha-3,** ADR-0056, decision 8, unchanged. sdk-comtrade drops its own
    resolution of ISO alpha-3 and refuses such a value with the code it stands for, as
    sdk-usda-gats does, by a hint table keyed by the alpha-3 codes of its reporter and partner
    lists, which core's check reads before the list's type (ADR-0045, decision 3).

## Consequences

- An answer of a task without a code, a note or a whole `Decimal` dumps as before. A test that
  compares a whole dumped `meta` of a task whose records are named sees the key, and a test that
  asserts a float of a whole `Decimal` sees an integer: sdk-usda-esr's three assertions break, and
  the five of sdk-usda-gats and sdk-usda-psd hold on recordings whose numbers carry a point.
- sdk-usda-psd, sdk-usda-esr and sdk-usda-gats mark their records' country and unit codes with
  their packaged lists, and an answer for every country names each one. sdk-faostat marks its area
  code with its label field and keeps `area_cs` with no exemption.
- The family check no longer finds a task that takes a country and names nothing. The review holds
  conventions §4 there, as it held a country inside a free-form mapping before.
- A record is read wherever an answer holds it, so a source that marks its codes needs no line in
  its tasks, and an answer of records is read once more at its `Result`: about 8 ms for 1,875
  records of 125 countries with two marked fields, the size of sdk-usda-psd's largest answer, and
  under 1 ms for as many records with no mark, measured on one machine.
