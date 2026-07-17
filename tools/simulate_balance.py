#!/usr/bin/env python3
"""Small deterministic balance model mirroring Rival Empires' Lua core."""

from __future__ import annotations

import math
from dataclasses import dataclass

import build_pack


@dataclass(frozen=True)
class Faction:
    key: str
    regions: int
    military: float = 0
    alive: bool = True
    human: bool = False
    excluded: bool = False
    allied: bool = False
    dependent: bool = False
    at_war: bool = False


def base_tier(imperium: int, settings: build_pack.Settings) -> int:
    eligible = [tier.imperium for tier in settings.tiers if imperium >= tier.imperium]
    return max(eligible, default=0)


def basic_candidate(faction: Faction) -> bool:
    return (
        faction.alive
        and not faction.human
        and not faction.excluded
        and not faction.allied
        and not faction.dependent
    )


def champion_keys(
    factions: list[Faction], settings: build_pack.Settings
) -> set[str]:
    candidates = [
        faction
        for faction in factions
        if basic_candidate(faction)
        and faction.regions >= settings.minimum_champion_regions
    ]
    candidates.sort(key=lambda faction: (
        -faction.regions,
        -faction.military,
        faction.key,
    ))
    return {faction.key for faction in candidates[:settings.champion_count]}


def assign_tiers(
    factions: list[Faction], human_imperium: int, settings: build_pack.Settings
) -> dict[str, int]:
    current = base_tier(human_imperium, settings)
    champions = champion_keys(factions, settings)
    defined = {tier.imperium for tier in settings.tiers}
    result = {}
    for faction in factions:
        assigned = 0
        if basic_candidate(faction) and current:
            full = faction.at_war or faction.key in champions
            operational_enemy = faction.at_war
            if settings.eligibility_mode == "all_ai":
                assigned = current
            elif settings.eligibility_mode == "enemies_only":
                assigned = current if operational_enemy else 0
            elif full:
                assigned = current
            elif settings.eligibility_mode == "independent_rivals":
                lower = max(
                    (tier for tier in defined if tier < current),
                    default=0,
                )
                if faction.regions >= settings.minimum_established_regions \
                        and lower:
                    assigned = lower
        result[faction.key] = assigned
    return result


def print_balance() -> None:
    settings = build_pack.balanced_settings()
    print("Imperium  Research  Build cost  Cost-limited throughput  8-turn tech")
    for imperium in range(1, 9):
        tier_number = base_tier(imperium, settings)
        tier = next(
            (item for item in settings.tiers if item.imperium == tier_number),
            None,
        )
        research = tier.research_percent if tier else 0
        cost = tier.construction_cost_percent if tier else 0
        throughput = 1 / (1 - cost / 100) if cost < 100 else math.inf
        technology = math.ceil(8 / (1 + research / 100))
        print(
            f"{imperium:>8}  +{research:>7g}%  -{cost:>8g}%  "
            f"{throughput:>22.2f}x  {technology:>11}"
        )


if __name__ == "__main__":
    print_balance()
