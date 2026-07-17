#!/usr/bin/env python3
"""Release synchronization and reproducibility tests for Rival Empires."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import build_pack
import package_release
import validate_pack


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = build_pack.balanced_settings()

    def test_checked_in_packs_equal_clean_build(self) -> None:
        standalone = build_pack.build_pack(self.settings)
        module_only = build_pack.build_pack(
            self.settings,
            module_only=True,
        )
        self.assertEqual(
            (ROOT / "@rtw2_rival_empires_balanced.pack").read_bytes(),
            standalone,
        )
        self.assertEqual(
            (
                ROOT
                / "compatibility"
                / "@rtw2_rival_empires_balanced_module_only.pack"
            ).read_bytes(),
            module_only,
        )
        self.assertEqual(
            (ROOT / "build" / "@rtw2_rival_empires_balanced.pack").read_bytes(),
            standalone,
        )
        validate_pack.validate_pack_bytes(standalone, module_only=False)
        validate_pack.validate_pack_bytes(module_only, module_only=True)

    def test_generated_sources_match_renderers(self) -> None:
        source = ROOT / "source"
        expected = {
            source / "lua_scripts" / "rtw2_rival_empires_config.lua":
                build_pack.render_config(self.settings),
            source / "db" / build_pack.EFFECT_BUNDLES_TABLE /
                "rtw2_rival_empires_bundles.tsv":
                build_pack.render_bundles_tsv(self.settings),
            source / "db" / build_pack.EFFECT_JUNCTIONS_TABLE /
                "rtw2_rival_empires_effects.tsv":
                build_pack.render_effect_junctions_tsv(self.settings),
            source / "db" / build_pack.EFFECTS_TABLE /
                "rtw2_rival_empires_hidden_effect.tsv":
                build_pack.render_effects_tsv(),
            source / "db" / build_pack.EFFECT_CATEGORIES_TABLE /
                "rtw2_rival_empires_hidden_category.tsv":
                build_pack.render_effect_categories_tsv(),
            source / "db" / build_pack.BUILDING_SET_JUNCTIONS_TABLE /
                "rtw2_rival_empires_build_time.tsv":
                build_pack.render_building_set_junctions_tsv(),
        }
        for path, rendered in expected.items():
            self.assertEqual(path.read_text(encoding="utf-8"), rendered)

    def test_sha256_manifest_is_exact(self) -> None:
        checksum_path = ROOT / "SHA256SUMS.txt"
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
        expected_paths = [
            "@rtw2_rival_empires_balanced.pack",
            "compatibility/@rtw2_rival_empires_balanced_module_only.pack",
        ]
        self.assertEqual(len(lines), 2)
        actual_paths = []
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            self.assertIsNotNone(match)
            digest, relative = match.groups()
            actual_paths.append(relative)
            self.assertEqual(
                digest,
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            )
        self.assertEqual(actual_paths, expected_paths)

    def test_release_metadata_uses_one_version(self) -> None:
        version = build_pack.VERSION
        manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], version)
        self.assertEqual(
            manifest["release_archive"],
            f"rtw2_rival_empires_v{version}.zip",
        )
        self.assertEqual(
            package_release.OUTPUT.name,
            f"rtw2_rival_empires_v{version}.zip",
        )
        self.assertEqual(
            package_release.PREFIX,
            f"rtw2_rival_empires_v{version}",
        )
        config = (
            ROOT / "source" / "lua_scripts" / "rtw2_rival_empires_config.lua"
        ).read_text(encoding="utf-8")
        self.assertIn(f'version = "{version}"', config)
        self.assertIn(
            f"## {version} —",
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        )
        for name in ("README.md", "QUICK_INSTALL.txt", "COMPATIBILITY.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(version, text, name)

    def test_release_zip_is_deterministic_and_curated(self) -> None:
        self.assertTrue(package_release.OUTPUT.is_file())
        files = package_release.included_files()
        package_release.verify_archive(files)
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory) / package_release.OUTPUT.name
            package_release.build_archive(other)
            self.assertEqual(
                other.read_bytes(),
                package_release.OUTPUT.read_bytes(),
            )

    def test_release_zip_packs_pass_independent_validation(self) -> None:
        prefix = package_release.PREFIX
        with zipfile.ZipFile(package_release.OUTPUT, "r") as archive:
            standalone = archive.read(
                f"{prefix}/@rtw2_rival_empires_balanced.pack"
            )
            module_only = archive.read(
                f"{prefix}/compatibility/"
                "@rtw2_rival_empires_balanced_module_only.pack"
            )
        validate_pack.validate_pack_bytes(standalone, module_only=False)
        validate_pack.validate_pack_bytes(module_only, module_only=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
