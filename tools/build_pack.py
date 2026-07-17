#!/usr/bin/env python3
"""Build deterministic Total War: ROME II Rival Empires PFH4 Mod packs."""

from __future__ import annotations

import argparse
import math
import re
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


VERSION = "0.9.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "source"

EFFECT_BUNDLES_TABLE = "effect_bundles_tables"
EFFECT_JUNCTIONS_TABLE = "effect_bundles_to_effects_junctions_tables"
EFFECTS_TABLE = "effects_tables"
EFFECT_CATEGORIES_TABLE = "effect_categories_tables"
BUILDING_SET_JUNCTIONS_TABLE = (
    "effect_bonus_value_building_set_junctions_tables"
)

RESEARCH_EFFECT = "rom_building_research_points"
RESEARCH_SCOPE = "this_faction"
CONSTRUCTION_COST_EFFECT = "rom_building_building_cost_mod"
CONSTRUCTION_SCOPE = "in_all_your_regions"
PUBLIC_ORDER_EFFECT = "rom_faction_public_order_difficulty_level"
PUBLIC_ORDER_SCOPE = "in_all_your_provinces"
BUILD_TIME_EFFECT = "rtw2_rival_empires_build_time"
HIDDEN_EFFECT_CATEGORY = "rtw2_rival_empires_hidden"
BUILD_TIME_BONUS_VALUE = "add_build_time"
ADVANCEMENT_STAGE = "start_turn_completed"

CORE_BUILDING_SETS = (
    "rom_building_set_agriculture",
    "rom_building_set_capital",
    "rom_building_set_city_centre",
    "rom_building_set_city_major",
    "rom_building_set_city_minor",
    "rom_building_set_gold",
    "rom_building_set_industry",
    "rom_building_set_military",
    "rom_building_set_port",
    "rom_building_set_religion",
    "rom_building_set_sanitation",
)

DB_VERSION_MARKER = bytes((252, 253, 254, 255))
DB_GUID_MARKER = bytes((253, 254, 252, 255))


@dataclass(frozen=True)
class Tier:
    imperium: int
    research_percent: float
    construction_cost_percent: float
    build_turns: float
    public_order: float
    bundle_key: str


@dataclass(frozen=True)
class Settings:
    eligibility_mode: str = "independent_rivals"
    champion_count: int = 3
    minimum_champion_regions: int = 5
    minimum_established_regions: int = 3
    tiers: tuple[Tier, ...] = ()


DEFAULT_TIER_VALUES = (
    (3, 10.0, 10.0, 0.0, 0.0),
    (4, 18.0, 15.0, -1.0, 1.0),
    (5, 26.0, 22.0, -1.0, 2.0),
    (6, 34.0, 29.0, -1.0, 3.0),
    (7, 42.0, 36.0, -1.0, 4.0),
)


def _u16(value: int) -> bytes:
    return struct.pack("<H", value)


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _i32(value: int) -> bytes:
    return struct.pack("<i", value)


def _f32(value: float) -> bytes:
    return struct.pack("<f", value)


def _sized_u8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 65_535:
        raise ValueError("DB string exceeds the Rome II u16 limit")
    return _u16(len(encoded)) + encoded


def _sized_u16(value: str) -> bytes:
    encoded = value.encode("utf-16-le")
    characters = len(encoded) // 2
    if characters > 65_535:
        raise ValueError("DB UTF-16 string exceeds the Rome II u16 limit")
    return _u16(characters) + encoded


def _db_float(value: float) -> str:
    return f"{value:.4f}"


def _number(value: float | int) -> str:
    return f"{value:g}"


def make_tiers(
    values: Iterable[tuple[int, float, float, float, float]],
) -> tuple[Tier, ...]:
    ordered = sorted(values, key=lambda item: item[0])
    return tuple(
        Tier(
            imperium=imperium,
            research_percent=research,
            construction_cost_percent=construction,
            build_turns=build_turns,
            public_order=public_order,
            bundle_key=f"rtw2_rival_empires_tier_{imperium}",
        )
        for imperium, research, construction, build_turns, public_order
        in ordered
    )


def balanced_settings() -> Settings:
    return Settings(tiers=make_tiers(DEFAULT_TIER_VALUES))


def validate_settings(settings: Settings) -> None:
    if settings.eligibility_mode not in {
        "enemies_only", "independent_rivals", "all_ai"
    }:
        raise ValueError("unsupported eligibility mode")
    if settings.champion_count < 0:
        raise ValueError("champion count cannot be negative")
    if settings.minimum_champion_regions < 1:
        raise ValueError("minimum champion regions must be positive")
    if settings.minimum_established_regions < 1:
        raise ValueError("minimum established regions must be positive")
    if not settings.tiers:
        raise ValueError("at least one Imperium tier is required")

    imperium_levels = [tier.imperium for tier in settings.tiers]
    if imperium_levels != sorted(set(imperium_levels)):
        raise ValueError("Imperium tiers must be sorted and unique")
    if imperium_levels[0] < 3:
        raise ValueError("tiers below Imperium 3 would alter the early game")
    for tier in settings.tiers:
        values = (
            tier.research_percent,
            tier.construction_cost_percent,
            tier.build_turns,
            tier.public_order,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("tier values must be finite")
        if tier.research_percent < 0 or tier.research_percent > 100:
            raise ValueError("research bonus must be between 0 and 100")
        if tier.construction_cost_percent < 0 or \
                tier.construction_cost_percent > 75:
            raise ValueError("construction discount must be between 0 and 75")
        if tier.build_turns > 0 or tier.build_turns < -10:
            raise ValueError("build-turn adjustment must be between -10 and 0")
        if tier.public_order < 0 or tier.public_order > 20:
            raise ValueError("public-order support must be between 0 and 20")

    if len(CORE_BUILDING_SETS) != 11 or \
            len(set(CORE_BUILDING_SETS)) != 11:
        raise ValueError("the verified core building-set list changed")
    building_rows = building_set_junction_rows()
    if len(building_rows) != 11 or len(set(building_rows)) != 11:
        raise ValueError("building-set junctions must contain 11 unique rows")


def render_config(settings: Settings) -> str:
    template = (
        SOURCE_ROOT / "lua_scripts" / "rtw2_rival_empires_config.lua.in"
    ).read_text(encoding="utf-8")
    tier_rows = []
    for tier in settings.tiers:
        tier_rows.append(
            f"        [{tier.imperium}] = {{ "
            f'research_percent = {_number(tier.research_percent)}, '
            f'construction_cost_percent = '
            f'{_number(tier.construction_cost_percent)}, '
            f'build_turns = {_number(tier.build_turns)}, '
            f'public_order = {_number(tier.public_order)}, '
            f'bundle_key = "{tier.bundle_key}" }},'
        )
    replacements = {
        "@VERSION@": VERSION,
        "@CHAMPION_COUNT@": str(settings.champion_count),
        "@MINIMUM_CHAMPION_REGIONS@": str(
            settings.minimum_champion_regions
        ),
        "@MINIMUM_ESTABLISHED_REGIONS@": str(
            settings.minimum_established_regions
        ),
        "@TIER_ROWS@": "\n".join(tier_rows),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    template = template.replace(
        'eligibility_mode = "independent_rivals"',
        f'eligibility_mode = "{settings.eligibility_mode}"',
    )
    unresolved = re.findall(r"@[A-Z][A-Z_]+@", template)
    if unresolved:
        raise ValueError(f"unresolved config tokens: {unresolved}")
    return template


def bundle_rows(settings: Settings) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for tier in settings.tiers:
        effects = [
            f"research +{_number(tier.research_percent)}%",
            f"construction cost -{_number(tier.construction_cost_percent)}%",
        ]
        if tier.build_turns:
            effects.append(
                f"core-building construction {_number(tier.build_turns)} turn"
            )
        if tier.public_order:
            effects.append(
                f"provincial public order +{_number(tier.public_order)}"
            )
        rows.append(
            (
                tier.bundle_key,
                "Rival development mobilization: " + ", ".join(effects) + ".",
                f"Rival Mobilization {tier.imperium}",
                "",
                "faction",
            )
        )
    return rows


def effect_junction_rows(
    settings: Settings,
) -> list[tuple[str, str, str, float, str]]:
    rows = []
    for tier in settings.tiers:
        rows.extend(
            (
                (
                    tier.bundle_key,
                    RESEARCH_EFFECT,
                    RESEARCH_SCOPE,
                    tier.research_percent,
                    ADVANCEMENT_STAGE,
                ),
                (
                    tier.bundle_key,
                    CONSTRUCTION_COST_EFFECT,
                    CONSTRUCTION_SCOPE,
                    -tier.construction_cost_percent,
                    ADVANCEMENT_STAGE,
                ),
            )
        )
        if tier.build_turns:
            rows.append(
                (
                    tier.bundle_key,
                    BUILD_TIME_EFFECT,
                    CONSTRUCTION_SCOPE,
                    tier.build_turns,
                    ADVANCEMENT_STAGE,
                )
            )
        if tier.public_order:
            rows.append(
                (
                    tier.bundle_key,
                    PUBLIC_ORDER_EFFECT,
                    PUBLIC_ORDER_SCOPE,
                    tier.public_order,
                    ADVANCEMENT_STAGE,
                )
            )
    return rows


def effect_category_rows() -> list[tuple[str]]:
    return [(HIDDEN_EFFECT_CATEGORY,)]


def effects_rows() -> list[tuple[str, None, int, None, str, bool]]:
    # Priority zero hides the plumbing effect. A project-owned category avoids
    # a dangling reference without guessing at a vanilla UI category.
    return [(
        BUILD_TIME_EFFECT,
        None,
        0,
        None,
        HIDDEN_EFFECT_CATEGORY,
        False,
    )]


def building_set_junction_rows() -> list[tuple[str, str, str]]:
    return [
        (BUILD_TIME_BONUS_VALUE, building_set, BUILD_TIME_EFFECT)
        for building_set in CORE_BUILDING_SETS
    ]


def _db_header(table: str, version: int, rows: Sequence[object]) -> bytearray:
    guid = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"rtw2-rival-empires:{VERSION}:{table}:{rows!r}",
        )
    )
    data = bytearray(DB_GUID_MARKER)
    data += _sized_u16(guid)
    data += DB_VERSION_MARKER
    data += _i32(version)
    data += b"\x01"
    data += _u32(len(rows))
    return data


def build_effect_bundles_db(settings: Settings) -> bytes:
    rows = bundle_rows(settings)
    data = _db_header(EFFECT_BUNDLES_TABLE, 1, rows)
    for row in rows:
        for value in row:
            data += _sized_u8(value)
    return bytes(data)


def build_effect_junctions_db(settings: Settings) -> bytes:
    rows = effect_junction_rows(settings)
    data = _db_header(EFFECT_JUNCTIONS_TABLE, 2, rows)
    for bundle, effect, scope, value, stage in rows:
        data += _sized_u8(bundle)
        data += _sized_u8(effect)
        data += _sized_u8(scope)
        data += _f32(value)
        data += b"\x01" + _sized_u8(stage)
    return bytes(data)


def build_effects_db() -> bytes:
    rows = effects_rows()
    data = _db_header(EFFECTS_TABLE, 3, rows)
    for effect, icon, priority, icon_negative, category, positive_good in rows:
        data += _sized_u8(effect)
        data += b"\x00" if icon is None else b"\x01" + _sized_u8(icon)
        data += _i32(priority)
        data += (
            b"\x00" if icon_negative is None
            else b"\x01" + _sized_u8(icon_negative)
        )
        data += _sized_u8(category)
        data += b"\x01" if positive_good else b"\x00"
    return bytes(data)


def build_effect_categories_db() -> bytes:
    rows = effect_category_rows()
    data = _db_header(EFFECT_CATEGORIES_TABLE, 0, rows)
    for (key,) in rows:
        data += _sized_u8(key)
    return bytes(data)


def build_building_set_junctions_db() -> bytes:
    rows = building_set_junction_rows()
    data = _db_header(BUILDING_SET_JUNCTIONS_TABLE, 0, rows)
    for bonus_value, building_set, effect in rows:
        data += _sized_u8(bonus_value)
        data += _sized_u8(building_set)
        data += _sized_u8(effect)
    return bytes(data)


def render_bundles_tsv(settings: Settings) -> str:
    lines = [
        "key\tlocalised_description\tlocalised_title\tui_icon\tbundle_target",
        "#effect_bundles_tables;1;db/effect_bundles_tables/"
        "rtw2_rival_empires_bundles\t\t\t\t",
    ]
    lines.extend("\t".join(row) for row in bundle_rows(settings))
    return "\n".join(lines) + "\n"


def render_effect_junctions_tsv(settings: Settings) -> str:
    lines = [
        "effect_bundle_key\teffect_key\teffect_scope\tvalue\tadvancement_stage",
        "#effect_bundles_to_effects_junctions_tables;2;"
        "db/effect_bundles_to_effects_junctions_tables/"
        "rtw2_rival_empires_effects\t\t\t\t",
    ]
    lines.extend(
        "\t".join((bundle, effect, scope, _db_float(value), stage))
        for bundle, effect, scope, value, stage
        in effect_junction_rows(settings)
    )
    return "\n".join(lines) + "\n"


def render_effects_tsv() -> str:
    lines = [
        "effect\ticon\tpriority\ticon_negative\tcategory\t"
        "is_positive_value_good",
        "#effects_tables;3;db/effects_tables/"
        "rtw2_rival_empires_hidden_effect\t\t\t\t\t",
        f"{BUILD_TIME_EFFECT}\t\t0\t\t{HIDDEN_EFFECT_CATEGORY}\tfalse",
    ]
    return "\n".join(lines) + "\n"


def render_effect_categories_tsv() -> str:
    return (
        "key\n"
        "#effect_categories_tables;0;db/effect_categories_tables/"
        "rtw2_rival_empires_hidden_category\n"
        f"{HIDDEN_EFFECT_CATEGORY}\n"
    )


def render_building_set_junctions_tsv() -> str:
    lines = [
        "bonus_value_id\tbuilding_set\teffect",
        "#effect_bonus_value_building_set_junctions_tables;0;"
        "db/effect_bonus_value_building_set_junctions_tables/"
        "rtw2_rival_empires_build_time\t\t",
    ]
    lines.extend("\t".join(row) for row in building_set_junction_rows())
    return "\n".join(lines) + "\n"


def pack_files(
    settings: Settings,
    module_only: bool = False,
) -> list[tuple[str, bytes]]:
    files = [
        (
            "db\\effect_categories_tables\\"
            "rtw2_rival_empires_hidden_category",
            build_effect_categories_db(),
        ),
        (
            "db\\effect_bonus_value_building_set_junctions_tables\\"
            "rtw2_rival_empires_build_time",
            build_building_set_junctions_db(),
        ),
        (
            "db\\effect_bundles_tables\\rtw2_rival_empires_bundles",
            build_effect_bundles_db(settings),
        ),
        (
            "db\\effect_bundles_to_effects_junctions_tables\\"
            "rtw2_rival_empires_effects",
            build_effect_junctions_db(settings),
        ),
        (
            "db\\effects_tables\\rtw2_rival_empires_hidden_effect",
            build_effects_db(),
        ),
        (
            "lua_scripts\\rtw2_rival_empires.lua",
            (
                SOURCE_ROOT / "lua_scripts" / "rtw2_rival_empires.lua"
            ).read_bytes(),
        ),
        (
            "lua_scripts\\rtw2_rival_empires_config.lua",
            render_config(settings).encode("utf-8"),
        ),
        (
            "lua_scripts\\rtw2_rival_empires_core.lua",
            (
                SOURCE_ROOT / "lua_scripts" / "rtw2_rival_empires_core.lua"
            ).read_bytes(),
        ),
    ]
    if not module_only:
        files.append(
            (
                "lua_scripts\\all_scripted.lua",
                (SOURCE_ROOT / "lua_scripts" / "all_scripted.lua").read_bytes(),
            )
        )
    return sorted(files, key=lambda item: item[0])


def build_pack(settings: Settings, module_only: bool = False) -> bytes:
    files = pack_files(settings, module_only)
    index = bytearray()
    payload = bytearray()
    for internal_path, contents in files:
        index += _u32(len(contents))
        index += internal_path.encode("utf-8") + b"\x00"
        payload += contents
    header = bytearray(b"PFH4")
    header += _u32(3)
    header += _u32(0)
    header += _u32(0)
    header += _u32(len(files))
    header += _u32(len(index))
    header += _u32(0)
    return bytes(header + index + payload)


def verify_pack(
    pack: bytes,
    settings: Settings,
    module_only: bool = False,
) -> None:
    expected = pack_files(settings, module_only)
    if pack[:4] != b"PFH4":
        raise ValueError("pack preamble is not PFH4")
    if struct.unpack_from("<I", pack, 4)[0] != 3:
        raise ValueError("pack is not Mod type")
    file_count = struct.unpack_from("<I", pack, 16)[0]
    index_size = struct.unpack_from("<I", pack, 20)[0]
    if file_count != len(expected):
        raise ValueError("PFH4 file count does not match expected content")

    cursor = 28
    actual_index = []
    for _ in range(file_count):
        size = struct.unpack_from("<I", pack, cursor)[0]
        cursor += 4
        end = pack.index(b"\x00", cursor)
        path = pack[cursor:end].decode("utf-8")
        cursor = end + 1
        actual_index.append((path, size))
    if cursor != 28 + index_size:
        raise ValueError("PFH4 file index size is incorrect")

    payload_cursor = cursor
    for (path, size), (expected_path, expected_data) in zip(
        actual_index,
        expected,
    ):
        if path != expected_path or size != len(expected_data):
            raise ValueError(f"incorrect PFH entry {path!r}")
        if pack[payload_cursor:payload_cursor + size] != expected_data:
            raise ValueError(f"payload mismatch for {path}")
        payload_cursor += size
    if payload_cursor != len(pack):
        raise ValueError("pack contains unindexed trailing bytes")


def emit_source(settings: Settings, destination: Path) -> None:
    lua = destination / "lua_scripts"
    bundles = destination / "db" / EFFECT_BUNDLES_TABLE
    junctions = destination / "db" / EFFECT_JUNCTIONS_TABLE
    effects = destination / "db" / EFFECTS_TABLE
    categories = destination / "db" / EFFECT_CATEGORIES_TABLE
    building_sets = destination / "db" / BUILDING_SET_JUNCTIONS_TABLE
    for directory in (
        lua, bundles, junctions, effects, categories, building_sets
    ):
        directory.mkdir(parents=True, exist_ok=True)
    (lua / "rtw2_rival_empires_config.lua").write_text(
        render_config(settings), encoding="utf-8", newline=""
    )
    (bundles / "rtw2_rival_empires_bundles.tsv").write_text(
        render_bundles_tsv(settings), encoding="utf-8", newline=""
    )
    (junctions / "rtw2_rival_empires_effects.tsv").write_text(
        render_effect_junctions_tsv(settings), encoding="utf-8", newline=""
    )
    (effects / "rtw2_rival_empires_hidden_effect.tsv").write_text(
        render_effects_tsv(), encoding="utf-8", newline=""
    )
    (categories / "rtw2_rival_empires_hidden_category.tsv").write_text(
        render_effect_categories_tsv(), encoding="utf-8", newline=""
    )
    (building_sets / "rtw2_rival_empires_build_time.tsv").write_text(
        render_building_set_junctions_tsv(), encoding="utf-8", newline=""
    )


def parse_tier(value: str) -> tuple[int, float, float, float, float]:
    try:
        parts = value.split(":")
        if len(parts) != 5:
            raise ValueError
        return (
            int(parts[0]),
            float(parts[1]),
            float(parts[2]),
            float(parts[3]),
            float(parts[4]),
        )
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "tier must be IMPERIUM:RESEARCH:COST_DISCOUNT:BUILD_TURNS:PO"
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a tunable Rome II Rival Empires PFH4 Mod pack."
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path("@rtw2_rival_empires_balanced.pack"),
    )
    parser.add_argument(
        "--eligibility-mode",
        choices=("enemies_only", "independent_rivals", "all_ai"),
        default="independent_rivals",
    )
    parser.add_argument("--champion-count", type=int, default=3)
    parser.add_argument("--minimum-champion-regions", type=int, default=5)
    parser.add_argument("--minimum-established-regions", type=int, default=3)
    parser.add_argument(
        "--tier", action="append", type=parse_tier,
        help="IMPERIUM:RESEARCH:COST_DISCOUNT:BUILD_TURNS:PO; repeat",
    )
    parser.add_argument("--module-only", action="store_true")
    parser.add_argument("--emit-source", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings(
        eligibility_mode=args.eligibility_mode,
        champion_count=args.champion_count,
        minimum_champion_regions=args.minimum_champion_regions,
        minimum_established_regions=args.minimum_established_regions,
        tiers=make_tiers(args.tier or DEFAULT_TIER_VALUES),
    )
    validate_settings(settings)
    pack = build_pack(settings, args.module_only)
    verify_pack(pack, settings, args.module_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pack)
    if args.emit_source:
        emit_source(settings, args.emit_source)
    kind = "module-only" if args.module_only else "standalone"
    print(f"built {args.output} ({kind}, {len(pack)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
