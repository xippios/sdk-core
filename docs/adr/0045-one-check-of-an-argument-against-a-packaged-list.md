# ADR-0045: One check of an argument against a packaged list

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/361 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/440

## Context

Conventions §5 refuse a code the packaged list lacks with core's `UnknownCode`, naming the
list, its fetch date and the closest known codes (ADR-0041, decision 8). Core gives the error,
`closest` and `nearest`, and no check: nine sources each keep a copy of the same frame
(https://github.com/xippios/sdk-core/issues/313), sdk-usda-esr, sdk-usda-psd, sdk-usda-nass and
sdk-usda-gats in `params.py`, sdk-comtrade in `params.py`, sdk-faostat, sdk-eurostat,
sdk-usda-wasde and sdk-usda-esmis in `tasks.py`. Each copy caches a lookup of the list's codes
to their names, compares a value and words the refusal with a `reason` and its source's slug,
and they differ in four places.

- The code field, the name field and whether case is folded are constant per list in every
  copy. sdk-usda-nass folds case on every list, sdk-comtrade on `flowCode` and `customsCode`,
  and the others compare exactly.
- Three copies hint only where no code is close (sdk-usda-nass, sdk-usda-gats, sdk-usda-wasde),
  and sdk-usda-psd keeps a table of values that are no codes with a text for each (`"all"`,
  `"00"`).
- Four copies find the closest codes by a strategy of their own: sdk-usda-esr by number and by
  digits, sdk-usda-gats by ISO and GENC codes first, sdk-comtrade by the same area in the other
  table, sdk-usda-wasde by a description of its own.
- sdk-usda-esr refuses a text given for its integer codes and names the integer to pass, while
  sdk-comtrade, sdk-usda-psd and sdk-usda-gats compare an integer code by its text.

The live comparison of a packaged list (https://github.com/xippios/sdk-core/issues/319) and the
name of a code in `meta` (https://github.com/xippios/sdk-core/issues/316) read the same facts of
a list.

## Decision

1. **A list's facts are declared once, and the check hangs off that declaration.**
   `PackagedList.codes(code, name=None, *, fold_case=False, list_name=None, source=None)`
   returns a `PackagedCodes`, exported from `xippios.core`: the list's codes under the field
   `code`, each with its name under the field `name`, upstream's record as it stands, or with
   its own text where the list has no name field or a record no name. The declaration builds
   its index of the codes once, and a source keeps it for the process, in a constant of its
   module or behind `functools.cache`. `fold_case=True` compares without case, for a list that
   upstream compares so. `list_name`, `param` unless given, is the list as a refusal names it,
   such as sdk-faostat's `element_QCL`, and `source` is the source's slug, which every refusal
   carries. A record without the code field or the name field, a code that is neither text nor
   an integer, a list of both, folding over integer codes, and two codes that differ in case
   alone in a folded list are refused at the declaration with `ValueError`, naming the field
   and the record's position, never the record.
2. **The check returns the value as given or raises `UnknownCode`.** `check(param, value, *,
   hints=None, otherwise=None, closest=None, reason=None)` returns `value` itself, an enum
   member included, so a task sends it, and records it in `meta.request`, as the caller gave
   it (conventions §5): under folding the caller's spelling, which upstream compares without
   case. A value the list lacks raises `UnknownCode` with the list's name, its fetch date, the
   closest codes, the `reason` and the source. An enum member is compared, and named in a
   refusal, by its value.
3. **Hints are a table, and one text for when no code is close.** `hints` maps a value that is
   no code to its text, read with the value's text stripped and without case, and a value it
   holds is refused with that text in place of the closest codes. The table is read before the
   list's type, since a text given for integer codes is a value that is no code: `"all"` for
   integer codes reads its hint, and so does `0` for text codes by its text `"0"`, while a value
   that is neither text nor an integer reads none. `otherwise` is the text of a
   refusal that names no code. `closest` takes a strategy of the source's own, a function of
   the value and the list's codes to their names that returns `(code, name)` pairs, best first;
   by default core's `closest` serves text codes and `nearest` integer codes. A strategy, core's
   or the source's, reads each name with its runs of white space collapsed, as a refusal shows
   it, so ESR's padded names read `CANADA`.
4. **The list's type decides.** A list's codes are text or integers, as its records hold them.
   A value of the other type that the hint table does not hold is refused with
   `InvalidRequestError`, never compared by its text:
   a text of digits given for integer codes names the integer to pass (`Pass it as the integer
   104.`), another text the codes whose name holds it or comes close to it (`By name: 104
   (Wheat - White).`), and an integer given for text codes its text (`Pass it as the text
   '757'.`) or the codes close to that text. Each task keeps its declared type, and
   sdk-comtrade converts its area codes to integers before the check.
5. **What the declaration reads.** `code`, `name`, `fold_case`, `list_name`, `source`,
   `integer` and `packaged`, the list it was declared from, and `names`, each code to its name
   in upstream order and read-only, the first record's name for a code listed twice;
   `name_of(value)` gives the name of a value compared as the check compares it, `None` for
   one the list lacks, and `value in codes` asks the same. The live comparison and the names in
   `meta` read these, and build their own on them.

## Consequences

- A source's check of an argument is one call, `COMMODITIES.check("commodity_code", value,
  reason=REASON)`, and each source deletes its copy in its own patch: the copies the
  changelog's Hand-apply note lists.
- The declaration loads its file where the source makes it, at import for a constant of a
  module, about 0.2 s for sdk-eurostat's 40,409 product codes, so a large list is declared
  behind `functools.cache`.
- A text given for integer codes is now refused where sdk-usda-psd and sdk-usda-gats compared
  it by its text, and an integer given for text codes where sdk-usda-nass compared its text,
  once each source takes the check.
- The check does not settle a list filter that answers an empty list for a value the list
  lacks. The three such filters are the sources' own rows, each of which refuses the value
  through this check in its patch: `list_countries(region_id=...)` in
  https://github.com/xippios/sdk-usda-esr/issues/27, `list_countries(region_code=...)` in
  https://github.com/xippios/sdk-usda-psd/issues/30, and `list_countries(region_code=...)`
  and `list_commodities(product_type=...)` in https://github.com/xippios/sdk-usda-gats/issues/31.
  The conventions state no rule for a list filter, and these rows do not ask for one.

## Amendment 2026-11-22

https://github.com/xippios/sdk-core/issues/440 amends decisions 3 and 4, from two misfits that
the trial of core 0.4.1 met in sdk-comtrade (https://github.com/xippios/sdk-core/issues/410,
https://github.com/xippios/sdk-core/issues/418 and https://github.com/xippios/sdk-core/issues/430).

(a) **A refusal of a value of the hint table ends with its hint and its reason** (decision 3). A
value the table holds is no code, so its refusal names the table's text in place of the closest
codes, then the `reason`, and leaves out that the packaged list is out of date, by
`UnknownCode(..., outdated=False)` (ADR-0041, decision 8, as amended on the same day). No refresh
of the list makes sdk-comtrade's ISO alpha-3 `"CHE"` a code of its integer reporters. It holds
for every value of a table: sdk-eurostat's hint for a product that another dataset lists, and
that upstream could still add to this list, loses the sentence too, and its hint says where the
product is. A source marks no value of its table as one that could become a code. A refusal with
`otherwise` names no code and keeps the sentence, since its value may be a code upstream added.

(b) **The source's strategy first for a text given for integer codes** (decisions 3 and 4). A
text that is no number, given for integer codes, is asked of the source's `closest` strategy
first, and the codes it names are named as closest codes are, `Did you mean 842 (USA)?`. The codes
whose name holds the text or comes close to it, `By name: 104 (Wheat - White).`, are named where
the strategy names none or the source passed none, and a text of digits still names the integer
to pass and asks no strategy. A strategy is a function of the value as the caller gave it, so a
strategy of integer codes takes a text as well and returns no pair for one it does not read; one
written for integers alone raises from the source's own function. sdk-comtrade's `"US"` for a
partner names 842 by its strategy, where the codes by name were 36 (Australia), 40 (Austria) and
112 (Belarus), whose names hold the two letters.

Decisions 1, 2 and 5 stand as written, as does the rest of decisions 3 and 4.
