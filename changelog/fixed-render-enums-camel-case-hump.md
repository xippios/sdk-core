- `render_enums` keeps a camelCase hump in a default class name, after a lower-case letter
  or a digit, `attributeId` giving `AttributeId` where it gave `Attributeid` and
  `partner2Code` `Partner2Code`, and a key without a hump keeps its name, `state_alpha`
  and `STATE_ALPHA` `StateAlpha`. The default gives every class name that sdk-comtrade,
  sdk-usda-esr, sdk-usda-gats, sdk-usda-nass and sdk-usda-psd commit, but sdk-usda-nass's
  `ProgressStage` and `ConditionCategory`, which stay in its `class_names`, so no class a
  source commits changes its name and a re-render under conventions §15 item 6 writes the
  same module.
  (ADR-0008, https://github.com/xippios/sdk-core/issues/95)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-usda-esr, sdk-usda-gats,
    sdk-usda-psd) — the line `class_names[id_field] = id_field[:1].upper() +
    id_field[1:]` (esr line 125, gats line 148, psd line 142), the `class_names` dict
    (lines 113, 139 and 130) and its argument to `render_enums` (lines 126, 149 and 143)
    → dropped: the default gives `UnitId`, `UnitOfMeasureId`, and `UnitId` and
    `AttributeId` — the default gives the line's name for an id field in camelCase with no
    upper-case run and no separator, as each of these is. For another id field the line
    stays: it keeps `countryISO` as `CountryISO` and `unit_id` as `Unit_id`, where the
    default gives `CountryIso` and `UnitId`.
    `scripts/refresh_reference.py` (sdk-cashctrl, sdk-faostat, sdk-google-mail, sdk-x) —
    the same line (line 110 in sdk-cashctrl, sdk-google-mail and sdk-x, 181 in
    sdk-faostat), its dict (98, 169) and its argument (111, 182) → dropped, since none of
    the four renders a list yet, as long as each id list it takes up later has such an id
    field — as above.
    `scripts/refresh_reference.py` (sdk-comtrade) — `class_names=class_names` in the
    `render_enums` call (line 483) → dropped, the dict of line 478 kept for the order of
    line 479: the default gives the ten names it sets, each key in camelCase with no
    upper-case run — as above.
