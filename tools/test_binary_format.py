#!/usr/bin/env python3
"""Independent PFH4 and Rome II DB regression tests for Rival Empires."""

from __future__ import annotations

import csv
import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import build_pack
import validate_pack


def post_guid_offset(payload: bytes) -> int:
    cursor = validate_pack.Cursor(payload)
    if cursor.take(4) != validate_pack.GUID_MARKER:
        raise AssertionError("missing GUID marker")
    cursor.string_u16()
    return cursor.offset


def tsv_rows(path: Path) -> list[list[str]]:
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    return rows[2:]


class IndependentBinaryFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = build_pack.balanced_settings()
        self.standalone = build_pack.build_pack(self.settings)
        self.module_only = build_pack.build_pack(
            self.settings,
            module_only=True,
        )
        self.files = validate_pack.parse_pfh4(self.standalone)

    def test_independent_pfh4_validation_for_both_variants(self) -> None:
        standalone_files = validate_pack.validate_pack_bytes(
            self.standalone,
            module_only=False,
        )
        module_files = validate_pack.validate_pack_bytes(
            self.module_only,
            module_only=True,
        )
        self.assertEqual(len(standalone_files), 9)
        self.assertEqual(len(module_files), 8)
        self.assertIn(validate_pack.BOOTSTRAP_PATH, standalone_files)
        self.assertNotIn(validate_pack.BOOTSTRAP_PATH, module_files)

    def test_version_zero_headers_omit_version_marker(self) -> None:
        expected_prefixes = {
            validate_pack.CATEGORIES_PATH: b"\x01\x01\x00\x00\x00",
            validate_pack.BUILDING_SETS_PATH: b"\x01\x0b\x00\x00\x00",
        }
        for path, expected in expected_prefixes.items():
            payload = self.files[path]
            offset = post_guid_offset(payload)
            self.assertNotEqual(
                payload[offset:offset + 4],
                validate_pack.VERSION_MARKER,
            )
            self.assertEqual(payload[offset:offset + 5], expected)

    def test_positive_version_headers_encode_exact_version(self) -> None:
        versions = {
            validate_pack.BUNDLES_PATH: 1,
            validate_pack.BUNDLE_EFFECTS_PATH: 2,
            validate_pack.EFFECTS_PATH: 3,
        }
        for path, version in versions.items():
            payload = self.files[path]
            offset = post_guid_offset(payload)
            self.assertEqual(
                payload[offset:offset + 4],
                validate_pack.VERSION_MARKER,
            )
            self.assertEqual(
                struct.unpack_from("<i", payload, offset + 4)[0],
                version,
            )

    def test_explicit_zero_version_marker_is_rejected(self) -> None:
        payload = self.files[validate_pack.CATEGORIES_PATH]
        offset = post_guid_offset(payload)
        malformed = (
            payload[:offset]
            + validate_pack.VERSION_MARKER
            + struct.pack("<i", 0)
            + payload[offset:]
        )
        with self.assertRaisesRegex(
            validate_pack.ValidationError,
            "version-zero tables must omit",
        ):
            validate_pack.decode_db_payload(
                validate_pack.CATEGORIES_PATH,
                malformed,
            )

    def test_every_db_payload_decodes_to_exact_eof(self) -> None:
        for path in validate_pack.DB_SPECS:
            rows = validate_pack.decode_db_payload(path, self.files[path])
            self.assertEqual(len(rows), validate_pack.DB_SPECS[path][2])

    def test_decoded_rows_match_checked_in_tsv_sources(self) -> None:
        db_root = ROOT / "source" / "db"
        comparisons = {
            validate_pack.BUILDING_SETS_PATH: (
                db_root
                / "effect_bonus_value_building_set_junctions_tables"
                / "rtw2_rival_empires_build_time.tsv"
            ),
            validate_pack.BUNDLES_PATH: (
                db_root
                / "effect_bundles_tables"
                / "rtw2_rival_empires_bundles.tsv"
            ),
            validate_pack.CATEGORIES_PATH: (
                db_root
                / "effect_categories_tables"
                / "rtw2_rival_empires_hidden_category.tsv"
            ),
        }
        for internal_path, source_path in comparisons.items():
            decoded = validate_pack.decode_db_payload(
                internal_path,
                self.files[internal_path],
            )
            self.assertEqual(
                [[str(value) for value in row] for row in decoded],
                tsv_rows(source_path),
            )

        junction_rows = validate_pack.decode_db_payload(
            validate_pack.BUNDLE_EFFECTS_PATH,
            self.files[validate_pack.BUNDLE_EFFECTS_PATH],
        )
        expected_junctions = tsv_rows(
            db_root
            / "effect_bundles_to_effects_junctions_tables"
            / "rtw2_rival_empires_effects.tsv"
        )
        normalized_junctions = [
            [row[0], row[1], row[2], f"{row[3]:.4f}", row[4] or ""]
            for row in junction_rows
        ]
        self.assertEqual(normalized_junctions, expected_junctions)

        effect_rows = validate_pack.decode_db_payload(
            validate_pack.EFFECTS_PATH,
            self.files[validate_pack.EFFECTS_PATH],
        )
        normalized_effects = [
            [
                row[0],
                row[1] or "",
                str(row[2]),
                row[3] or "",
                row[4],
                "true" if row[5] else "false",
            ]
            for row in effect_rows
        ]
        self.assertEqual(
            normalized_effects,
            tsv_rows(
                db_root
                / "effects_tables"
                / "rtw2_rival_empires_hidden_effect.tsv"
            ),
        )

    def test_standalone_payload_has_no_companion_mod_references(self) -> None:
        for reference in validate_pack.BANNED_CROSS_MOD_REFERENCES:
            self.assertNotIn(reference, self.standalone)
            self.assertNotIn(reference, self.module_only)


if __name__ == "__main__":
    unittest.main(verbosity=2)
