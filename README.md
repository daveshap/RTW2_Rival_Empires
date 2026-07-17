# RTW2 Rival Empires

RTW2 Rival Empires gives established AI powers a measured development response
to the local human's growing Imperium. It is intended to produce healthier
mid- and late-game rivals: factions that research, rebuild damaged provinces,
and maintain infrastructure instead of surviving as hollow collections of
ruined settlements.

The balanced release grants no money, units, recruitment discounts, upkeep
discounts, replenishment, morale, battle statistics, or autoresolve bonuses.
The AI must still use its own settlements, economy, build choices, and armies.

Version 0.9.1 is a single-player Grand Campaign playtest release and replaces
the withdrawn, boot-broken 0.9.0 build.

## Release archive

The versioned release is one ZIP file:

```text
rtw2_rival_empires_v0.9.1.zip
```

For normal installation, extract and use:

```text
@rtw2_rival_empires_balanced.pack
```

That same ZIP contains the module-only compatibility variant at
`compatibility/@rtw2_rival_empires_balanced_module_only.pack`, together with
the documentation, source, builders, and tests. The module-only pack is for
people who maintain a manually merged `lua_scripts/all_scripted.lua`; it is not
a standalone alternative.

## What it does

The local human's Imperium determines the available response tier:

| Human Imperium | Research | Building cost | Core build time | Public order |
|---:|---:|---:|---:|---:|
| 1–2 | None | None | None | None |
| 3 | +10% | −10% | None | None |
| 4 | +18% | −15% | −1 turn | +1 |
| 5 | +26% | −22% | −1 turn | +2 |
| 6 | +34% | −29% | −1 turn | +3 |
| 7 or higher | +42% | −36% | −1 turn | +4 |

Full current-tier support goes to:

- AI factions currently at war with the local human; and
- the three largest eligible regional powers with at least five regions.

Other independent AI factions with at least three regions receive one tier
lower. One- and two-region factions receive nothing unless they are actually at
war with the human. This concentrates assistance on plausible rival empires
instead of indefinitely preserving every minor tribe.

The following never receive a bundle:

- any human faction;
- the human's military or defensive allies;
- the human's clients, vassals, satrapies, subjects, or tributaries;
- dead factions; and
- slave, rebel, separatist, or civil-war factions.

All relationships are resolved bilaterally through `treaty_details()`. The
script does not mistake an AI faction's unrelated third-party war for a war
against the human.

## Installation

1. Extract `rtw2_rival_empires_v0.9.1.zip`.
2. Close Rome II.
3. Copy `@rtw2_rival_empires_balanced.pack` into the game's `data` directory.
4. Open the Rome II launcher and Mod Manager.
5. Enable **Run user script mods**.
6. Enable the Rival Empires pack.
7. Load the Grand Campaign save and advance to the next faction turns.

It is designed to be added to an existing save. At maximum Imperium, eligible
AI factions receive the maximum appropriate tier at their next faction turn.
Construction costs already paid are not refunded, and an already-queued
building may retain the duration captured when it was ordered.

## How selection works

At the start of the local human turn, the script scans the living factions and
creates a deterministic assignment for that campaign round. Regional champions
are ranked by:

1. regions owned;
2. current military unit strength; and
3. faction key as a stable tie-break.

The script evaluates assignments at the local human turn. Each AI faction then
refreshes only its own one-turn bundle at its faction-turn start. Loading and
the first world tick mark the assignments for reevaluation but deliberately
perform no world-wide native bundle mutation.

The default eligibility mode is `independent_rivals`. Builders may select
`enemies_only` or `all_ai`; see [BALANCE.md](BALANCE.md).

## Core construction-time coverage

Rome II does not expose a Lua command for advancing an individual construction
queue. Rival Empires therefore defines a hidden database effect connected to
the engine's `add_build_time` bonus and these verified core building sets:

```text
rom_building_set_agriculture
rom_building_set_capital
rom_building_set_city_centre
rom_building_set_city_major
rom_building_set_city_minor
rom_building_set_gold
rom_building_set_industry
rom_building_set_military
rom_building_set_port
rom_building_set_religion
rom_building_set_sanitation
```

This covers the principal Grand Campaign building families. DLC-specific or
overhaul-defined building sets are not assumed to be members of those sets.
Their research, building-cost, and public-order effects still work, but their
literal construction duration may not. See [COMPATIBILITY.md](COMPATIBILITY.md).

## Standalone and scripted-mod compatibility

Rival Empires is independent, with its own version history, release archive,
configuration, source, and Rival-only bootstrap. The standalone loader
preserves Rome II's seven vanilla imports and registers only Rival Empires.

Rome II permits only one enabled `lua_scripts/all_scripted.lua` to win that
internal path. Combining Rival Empires with another scripted mod therefore
requires a consciously merged loader and the included module-only pack. Rival
Empires contains no automatic imports or runtime integration with other mods.

## Tuning and building

Python 3.10 or later is sufficient; the builder uses only the standard library.

```text
python tools/build_pack.py \
  --output build/@rtw2_rival_empires_balanced.pack \
  --emit-source source
```

Example enemies-only build:

```text
python tools/build_pack.py \
  --eligibility-mode enemies_only \
  --output build/@rtw2_rival_empires_enemies_only.pack
```

Every tier is replaceable with repeated arguments in this format:

```text
--tier IMPERIUM:RESEARCH:COST_DISCOUNT:BUILD_TURNS:PUBLIC_ORDER
```

For example, the maximum balanced row is `7:42:36:-1:4`. The builder rejects
duplicate tiers, discounts above 75%, positive build-time adjustments, invalid
eligibility modes, and a changed or duplicated core building-set list.

## Verification

The release is covered by:

- pure Python selection and balance tests;
- deterministic PFH4 construction plus an independent container parser;
- a full-row independent DB decoder with strict schema-version-zero checks;
- exact DB effect, scope, field-order, building-set, and TSV-source tests;
- Lua 5.1 parsing;
- a mocked campaign runtime covering maximum Imperium, current enemies,
  champions, lower-tier rivals, minors, allies, subjects, rebels, dead
  placeholders, third-party wars, loading, mutation-free first tick, and
  bounded per-faction refresh; and
- a reproducible SHA-256 manifest.

The game executable is not present in the build environment. The remaining
manual checks are in [TEST_CHECKLIST.md](TEST_CHECKLIST.md).

## Technical records

The pack uses these vanilla effects:

- `rom_building_research_points`, scope `this_faction`;
- `rom_building_building_cost_mod`, scope `in_all_your_regions`; and
- `rom_faction_public_order_difficulty_level`, scope
  `in_all_your_provinces`.

Literal core construction time uses the project-owned hidden effect
`rtw2_rival_empires_build_time`, mapped to `add_build_time` for the eleven sets
listed above. A project-owned hidden effect category avoids a dangling database
reference. The effect's priority is zero, so it does not add a blank UI line.

Primary technical references:

- [Rome II campaign API dump](https://github.com/bukowa/ConsulScriptum/blob/master/docs/reference/rome2-api.md)
- [Rome II global script-loader pattern](https://github.com/bukowa/ConsulScriptum/blob/master/src/lua_scripts/all_scripted_rome2.lua)
- [Current Rome II RPFM schema](https://github.com/Frodo45127/rpfm-schemas/blob/master/schema_rom2.ron)

No third-party source code or game assets are included.
