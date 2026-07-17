#!/usr/bin/env python3
"""Builder, DB-record, deterministic-pack, and balance-core tests."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_pack
import simulate_balance


class BalanceCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = build_pack.balanced_settings()

    def test_imperium_mapping(self) -> None:
        expected = {1: 0, 2: 0, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 7}
        self.assertEqual(
            {
                level: simulate_balance.base_tier(level, self.settings)
                for level in range(1, 9)
            },
            expected,
        )

    def test_champions_enemy_coalition_and_established_rival(self) -> None:
        factions = [
            simulate_balance.Faction("rome", 40, human=True),
            simulate_balance.Faction("parthia", 12, 30),
            simulate_balance.Faction("carthage", 10, 27),
            simulate_balance.Faction("arverni", 8, 22),
            simulate_balance.Faction("egypt", 4, at_war=True),
            simulate_balance.Faction("germania", 4, coalition=True),
            simulate_balance.Faction("iberia", 6),
            simulate_balance.Faction("minor", 2),
        ]
        assigned = simulate_balance.assign_tiers(factions, 7, self.settings)
        for key in ("parthia", "carthage", "arverni", "egypt", "germania"):
            self.assertEqual(assigned[key], 7)
        self.assertEqual(assigned["iberia"], 6)
        self.assertEqual(assigned["minor"], 0)

    def test_friends_dependents_and_insurgents_are_excluded(self) -> None:
        factions = [
            simulate_balance.Faction("ally", 12, allied=True),
            simulate_balance.Faction("client", 12, dependent=True),
            simulate_balance.Faction("rebels", 12, excluded=True),
            simulate_balance.Faction("dead", 12, alive=False),
        ]
        assigned = simulate_balance.assign_tiers(factions, 7, self.settings)
        self.assertEqual(set(assigned.values()), {0})

    def test_enemies_only_does_not_include_regional_champions(self) -> None:
        settings = build_pack.Settings(
            eligibility_mode="enemies_only",
            tiers=build_pack.make_tiers(build_pack.DEFAULT_TIER_VALUES),
        )
        factions = [
            simulate_balance.Faction("champion", 12, 30),
            simulate_balance.Faction("enemy", 2, at_war=True),
            simulate_balance.Faction("coalition", 2, coalition=True),
        ]
        assigned = simulate_balance.assign_tiers(factions, 7, settings)
        self.assertEqual(assigned["champion"], 0)
        self.assertEqual(assigned["enemy"], 7)
        self.assertEqual(assigned["coalition"], 7)


class BuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = build_pack.balanced_settings()

    def test_config_and_exact_default_tiers(self) -> None:
        config = build_pack.render_config(self.settings)
        self.assertNotRegex(config, r"@[A-Z][A-Z_]+@")
        self.assertIn('eligibility_mode = "independent_rivals"', config)
        self.assertIn("maximum_regional_champions = 3", config)
        self.assertIn("research_percent = 42", config)
        self.assertIn("construction_cost_percent = 36", config)
        self.assertIn("build_turns = -1", config)
        self.assertIn("public_order = 4", config)

    def test_effect_rows_use_verified_effects_and_scopes(self) -> None:
        rows = build_pack.effect_junction_rows(self.settings)
        self.assertIn(
            (
                "rtw2_rival_empires_tier_7",
                build_pack.RESEARCH_EFFECT,
                build_pack.RESEARCH_SCOPE,
                42.0,
                build_pack.ADVANCEMENT_STAGE,
            ),
            rows,
        )
        self.assertIn(
            (
                "rtw2_rival_empires_tier_7",
                build_pack.CONSTRUCTION_COST_EFFECT,
                build_pack.CONSTRUCTION_SCOPE,
                -36.0,
                build_pack.ADVANCEMENT_STAGE,
            ),
            rows,
        )
        self.assertIn(
            (
                "rtw2_rival_empires_tier_7",
                build_pack.PUBLIC_ORDER_EFFECT,
                build_pack.PUBLIC_ORDER_SCOPE,
                4.0,
                build_pack.ADVANCEMENT_STAGE,
            ),
            rows,
        )

    def test_build_time_plumbing_is_complete_and_ordered(self) -> None:
        self.assertEqual(len(build_pack.CORE_BUILDING_SETS), 11)
        rows = build_pack.building_set_junction_rows()
        self.assertEqual(len(rows), 11)
        self.assertEqual(len(set(rows)), 11)
        self.assertEqual(
            rows[0],
            (
                "add_build_time",
                "rom_building_set_agriculture",
                build_pack.BUILD_TIME_EFFECT,
            ),
        )
        self.assertTrue(all(row[0] == "add_build_time" for row in rows))
        effect = build_pack.effects_rows()[0]
        self.assertEqual(effect[2], 0)
        self.assertEqual(effect[4], build_pack.HIDDEN_EFFECT_CATEGORY)
        self.assertEqual(
            build_pack.effect_category_rows(),
            [(build_pack.HIDDEN_EFFECT_CATEGORY,)],
        )
        self.assertNotEqual(effect[4], "")

    def test_binary_tables_contain_expected_schema_records(self) -> None:
        self.assertIn(
            build_pack.BUILD_TIME_EFFECT.encode(),
            build_pack.build_effects_db(),
        )
        building_sets = build_pack.build_building_set_junctions_db()
        self.assertIn(b"add_build_time", building_sets)
        for key in build_pack.CORE_BUILDING_SETS:
            self.assertIn(key.encode(), building_sets)
        self.assertIn(
            build_pack.HIDDEN_EFFECT_CATEGORY.encode(),
            build_pack.build_effect_categories_db(),
        )

    def test_standalone_and_module_only_structure(self) -> None:
        standalone = build_pack.build_pack(self.settings)
        build_pack.verify_pack(standalone, self.settings)
        self.assertEqual(standalone[:4], b"PFH4")
        self.assertEqual(struct.unpack_from("<I", standalone, 4)[0], 3)
        self.assertEqual(struct.unpack_from("<I", standalone, 16)[0], 9)
        self.assertIn(b"lua_scripts\\all_scripted.lua", standalone)

        module = build_pack.build_pack(self.settings, module_only=True)
        build_pack.verify_pack(module, self.settings, module_only=True)
        self.assertEqual(struct.unpack_from("<I", module, 16)[0], 8)
        self.assertNotIn(b"lua_scripts\\all_scripted.lua", module)

    def test_pack_build_is_deterministic(self) -> None:
        first = build_pack.build_pack(self.settings)
        second = build_pack.build_pack(self.settings)
        self.assertEqual(first, second)

    def test_bootstrap_registers_compatible_mods_in_order(self) -> None:
        files = dict(build_pack.pack_files(self.settings))
        bootstrap = files["lua_scripts\\all_scripted.lua"]
        food = bootstrap.index(b"lua_scripts.rtw2_food_exports")
        coalitions = bootstrap.index(b"lua_scripts.rtw2_grand_coalitions")
        rivals = bootstrap.index(b"lua_scripts.rtw2_rival_empires")
        self.assertLess(food, coalitions)
        self.assertLess(coalitions, rivals)
        self.assertIn(b"events = triggers.events", bootstrap)

    def test_invalid_tuning_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_pack.validate_settings(
                build_pack.Settings(
                    champion_count=-1,
                    tiers=build_pack.make_tiers(build_pack.DEFAULT_TIER_VALUES),
                )
            )
        values = list(build_pack.DEFAULT_TIER_VALUES)
        values[-1] = (7, 42, 80, -1, 4)
        with self.assertRaises(ValueError):
            build_pack.validate_settings(
                build_pack.Settings(tiers=build_pack.make_tiers(values))
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
