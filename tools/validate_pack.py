#!/usr/bin/env python3
"""Independently validate Rival Empires PFH4 and Rome II DB payloads."""

from __future__ import annotations

import argparse
import math
import struct
import uuid
from pathlib import Path
from typing import Callable


GUID_MARKER = bytes((253, 254, 252, 255))
VERSION_MARKER = bytes((252, 253, 254, 255))

BUILDING_SETS_PATH = (
    "db\\effect_bonus_value_building_set_junctions_tables\\"
    "rtw2_rival_empires_build_time"
)
BUNDLES_PATH = "db\\effect_bundles_tables\\rtw2_rival_empires_bundles"
BUNDLE_EFFECTS_PATH = (
    "db\\effect_bundles_to_effects_junctions_tables\\"
    "rtw2_rival_empires_effects"
)
CATEGORIES_PATH = (
    "db\\effect_categories_tables\\rtw2_rival_empires_hidden_category"
)
EFFECTS_PATH = "db\\effects_tables\\rtw2_rival_empires_hidden_effect"

DB_SPECS = {
    BUILDING_SETS_PATH: (0, ("string_u8",) * 3, 11),
    BUNDLES_PATH: (1, ("string_u8",) * 5, 5),
    BUNDLE_EFFECTS_PATH: (
        2,
        (
            "string_u8",
            "string_u8",
            "string_u8",
            "f32",
            "optional_string_u8",
        ),
        18,
    ),
    CATEGORIES_PATH: (0, ("string_u8",), 1),
    EFFECTS_PATH: (
        3,
        (
            "string_u8",
            "optional_string_u8",
            "i32",
            "optional_string_u8",
            "string_u8",
            "bool",
        ),
        1,
    ),
}

COMMON_PATHS = set(DB_SPECS) | {
    "lua_scripts\\rtw2_rival_empires.lua",
    "lua_scripts\\rtw2_rival_empires_config.lua",
    "lua_scripts\\rtw2_rival_empires_core.lua",
}
BOOTSTRAP_PATH = "lua_scripts\\all_scripted.lua"
BANNED_CROSS_MOD_REFERENCES = (
    b"rtw2_food_exports",
    b"rtw2_grand_coalitions",
)


class ValidationError(ValueError):
    """Raised when a release pack violates the independently fixed format."""


class Cursor:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise ValidationError("payload ended before the declared field")
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def f32(self) -> float:
        value = struct.unpack("<f", self.take(4))[0]
        if not math.isfinite(value):
            raise ValidationError("DB contains a non-finite float")
        return value

    def string_u8(self) -> str:
        try:
            return self.take(self.u16()).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError("invalid UTF-8 DB string") from error

    def string_u16(self) -> str:
        try:
            return self.take(self.u16() * 2).decode("utf-16-le")
        except UnicodeDecodeError as error:
            raise ValidationError("invalid UTF-16 DB string") from error

    def boolean(self) -> bool:
        value = self.u8()
        if value not in (0, 1):
            raise ValidationError(f"invalid DB boolean {value}")
        return value == 1

    def optional_string_u8(self) -> str | None:
        return self.string_u8() if self.boolean() else None


FIELD_READERS: dict[str, Callable[[Cursor], object]] = {
    "string_u8": Cursor.string_u8,
    "optional_string_u8": Cursor.optional_string_u8,
    "i32": Cursor.i32,
    "f32": Cursor.f32,
    "bool": Cursor.boolean,
}


def parse_pfh4(data: bytes) -> dict[str, bytes]:
    if len(data) < 28 or data[:4] != b"PFH4":
        raise ValidationError("pack is not PFH4")
    pack_type, dependency_count, dependency_size, file_count, index_size = (
        struct.unpack_from("<IIIII", data, 4)
    )
    if pack_type != 3:
        raise ValidationError("pack is not Mod type 3")
    if dependency_count != 0 or dependency_size != 0:
        raise ValidationError("release pack unexpectedly declares dependencies")

    index_end = 28 + index_size
    if index_end > len(data):
        raise ValidationError("PFH4 index extends beyond the pack")
    cursor = 28
    index: list[tuple[str, int]] = []
    for _ in range(file_count):
        if cursor + 4 > index_end:
            raise ValidationError("PFH4 index ended before a file size")
        size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        terminator = data.find(b"\0", cursor, index_end)
        if terminator < 0:
            raise ValidationError("PFH4 path is not NUL terminated")
        try:
            path = data[cursor:terminator].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError("PFH4 path is not UTF-8") from error
        if not path:
            raise ValidationError("PFH4 contains an empty path")
        cursor = terminator + 1
        index.append((path, size))
    if cursor != index_end:
        raise ValidationError("PFH4 index size does not match its entries")

    paths = [path for path, _ in index]
    if paths != sorted(paths):
        raise ValidationError("PFH4 paths are not deterministically sorted")
    if len(paths) != len(set(paths)):
        raise ValidationError("PFH4 contains duplicate paths")

    files = {}
    payload_cursor = index_end
    for path, size in index:
        payload_end = payload_cursor + size
        if payload_end > len(data):
            raise ValidationError(f"PFH4 payload overruns the pack: {path}")
        files[path] = data[payload_cursor:payload_end]
        payload_cursor = payload_end
    if payload_cursor != len(data):
        raise ValidationError("PFH4 contains unindexed trailing bytes")
    return files


def decode_db_payload(path: str, payload: bytes) -> list[tuple[object, ...]]:
    try:
        version, fields, expected_rows = DB_SPECS[path]
    except KeyError as error:
        raise ValidationError(f"no independent DB specification for {path}") from error

    cursor = Cursor(payload)
    if cursor.take(4) != GUID_MARKER:
        raise ValidationError(f"{path}: missing GUID marker")
    guid_text = cursor.string_u16()
    try:
        uuid.UUID(guid_text)
    except ValueError as error:
        raise ValidationError(f"{path}: malformed GUID") from error

    marker = payload[cursor.offset:cursor.offset + 4]
    if version == 0:
        if marker == VERSION_MARKER:
            raise ValidationError(
                f"{path}: version-zero tables must omit the version marker"
            )
    else:
        if cursor.take(4) != VERSION_MARKER:
            raise ValidationError(f"{path}: missing version marker")
        encoded_version = cursor.i32()
        if encoded_version != version:
            raise ValidationError(
                f"{path}: expected version {version}, got {encoded_version}"
            )

    if cursor.u8() != 1:
        raise ValidationError(f"{path}: unexpected DB header flag")
    row_count = cursor.u32()
    if row_count != expected_rows:
        raise ValidationError(
            f"{path}: expected {expected_rows} rows, got {row_count}"
        )

    rows = []
    for _ in range(row_count):
        rows.append(tuple(FIELD_READERS[field](cursor) for field in fields))
    if cursor.offset != len(payload):
        raise ValidationError(f"{path}: DB row decode did not finish at EOF")
    return rows


def validate_pack_bytes(
    data: bytes,
    *,
    module_only: bool | None = None,
) -> dict[str, bytes]:
    files = parse_pfh4(data)
    inferred_module_only = BOOTSTRAP_PATH not in files
    if module_only is not None and module_only != inferred_module_only:
        raise ValidationError("pack variant does not match the requested kind")
    expected_paths = set(COMMON_PATHS)
    if not inferred_module_only:
        expected_paths.add(BOOTSTRAP_PATH)
    if set(files) != expected_paths:
        missing = sorted(expected_paths - set(files))
        extra = sorted(set(files) - expected_paths)
        raise ValidationError(
            f"unexpected PFH4 contents; missing={missing}, extra={extra}"
        )
    for path in DB_SPECS:
        decode_db_payload(path, files[path])
    for reference in BANNED_CROSS_MOD_REFERENCES:
        if any(reference in payload for payload in files.values()):
            raise ValidationError(
                f"standalone boundary violation: {reference.decode()}"
            )
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="+", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in args.packs:
        files = validate_pack_bytes(path.read_bytes())
        kind = "module-only" if BOOTSTRAP_PATH not in files else "standalone"
        print(f"validated {path} ({kind}, {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
