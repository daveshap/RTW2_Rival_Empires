# Balance model

Rival Empires is a development catch-up system, not a combat difficulty mod.
Its purpose is to help the campaign generate a few functioning late-game
powers that can exploit the diplomacy and coalition systems with real regional
economies.

## Balanced tiers

| Human Imperium | Full research | Full cost discount | Approx. cost-limited throughput | Eight-turn technology | Core build time | PO |
|---:|---:|---:|---:|---:|---:|---:|
| 1–2 | — | — | 1.00× | 8 turns | — | — |
| 3 | +10% | −10% | 1.11× | about 8 turns | — | — |
| 4 | +18% | −15% | 1.18× | about 7 turns | −1 | +1 |
| 5 | +26% | −22% | 1.28× | about 7 turns | −1 | +2 |
| 6 | +34% | −29% | 1.41× | about 6 turns | −1 | +3 |
| 7+ | +42% | −36% | 1.56× | about 6 turns | −1 | +4 |

The throughput column is `1 / (1 - discount)`. It describes the maximum number
of buildings the same construction budget could purchase, not a guarantee that
the AI will spend perfectly. Research turns are illustrative because the game
rounds progress and technologies have different costs.

The top tier is intentionally below a 50% construction discount. Very Hard and
Legendary already give the AI other advantages, and stacking a 50% discount
would double budget-limited infrastructure throughput before those systems are
counted.

## Full tier versus support tier

At human Imperium 7, current enemies, coalition members, and the top three
regional champions receive tier 7. Other established independent rivals
receive tier 6. At Imperium 3, that one-tier-lower rule resolves to no bundle,
so the first response remains focused on actual enemies and significant powers.

This creates deliberate concentration:

- successful Egypt, Persia, Carthage, a major tribal federation, or another
  emergent power can become a regional champion without faction hard-coding;
- a current opponent remains supported even after being reduced below five
  regions; and
- neutral one-region factions do not become immortal speed-builders.

## Public order

The +1 to +4 provincial support is small. It is intended to reduce the AI's
tendency to lock itself into a ruin/rebellion/reconquest loop while still
requiring it to construct food, sanitation, culture, and public-order
infrastructure. It is not a battle-morale effect.

## Eligibility modes

`independent_rivals` is recommended.

- `enemies_only`: only factions at war with the human and active Grand
  Coalition members receive the full tier. Regional champions do not qualify
  merely by size.
- `independent_rivals`: enemies, coalition members, and champions receive the
  full tier; other established rivals receive one tier lower.
- `all_ai`: every otherwise eligible AI faction receives the full tier. Human
  allies, dependents, insurgents, and dead factions remain excluded.

## Tunable parameters

The generated config contains:

```text
eligibility_mode
maximum_regional_champions
minimum_champion_regions
minimum_established_rival_regions
effect_bundle_duration
tiers
excluded_faction_patterns
subject_treaty_patterns
```

The builder exposes the selection thresholds and repeated custom tier rows on
the command line. A tier edit changes both the Lua tuning file and the database
effect bundles, keeping displayed source and executable pack synchronized.

## What is deliberately absent

- direct treasury payments;
- free armies or units;
- recruitment and upkeep discounts;
- replenishment bonuses;
- battle morale, attack, defence, armour, or weapon bonuses;
- autoresolve modification; and
- automatic territory transfer.

If the AI still selects destructive province builds after its affordability
problem is reduced, the next intervention should be a separately testable CAI
building-priority mod, not more raw bonuses in this pack.
