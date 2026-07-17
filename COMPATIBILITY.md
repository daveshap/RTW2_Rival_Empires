# Compatibility

## Campaign scope

Version 0.9.0 runs only in the single-player `main_rome` Grand Campaign. It
disables itself in multiplayer and other campaigns rather than choosing an
arbitrary human target or relying on unverified building-set coverage.

## Compatible campaign loader

Rome II uses `lua_scripts/all_scripted.lua` as its global scripted-campaign
entry point. Only one enabled file can win that exact internal path.

Rival Empires is independently versioned and distributed. Its standalone pack
preserves all seven vanilla imports and optionally registers Rival Empires,
Food Exports, and Grand Coalitions when those separately installed mods are
present. Its bootstrap is byte-identical to their current compatible releases,
so those packs may be enabled together in either order.

If another overhaul owns `all_scripted.lua`, merge this registration into that
loader and use:

```text
compatibility/@rtw2_rival_empires_balanced_module_only.pack
```

The module-only pack deliberately omits the bootstrap. Enabling it without a
merged loader leaves the Lua module dormant.

## Grand Coalitions

Rival Empires works without Grand Coalitions. When the loaded coalition module
offers `get_active_coalition()`, its members receive the full current tier even
during mobilization before a common war is declared. This is a read-only
integration; Rival Empires never changes diplomatic permissions, peace, war,
stance, or coalition membership.

## Food Exports and Stable Politics

Food Exports applies its construction bonus to eligible human factions, while
Rival Empires applies only to eligible AI factions, so their intended targets
do not overlap. Stable Politics is DB-only and edits unrelated politics data.

## Building mods and overhauls

Research, construction cost, and public order use faction/province scopes and
continue to apply to eligible AI factions with modded buildings.

The literal −1 construction-turn effect is mapped only to eleven verified Rome
II core building sets. A DLC or overhaul may define new building sets that do
not inherit those memberships. Such buildings receive the cost discount but
may retain their original duration.

This pack does not replace `building_levels_tables` and therefore avoids the
large conflicts created by globally rewriting every construction time. An
overhaul can extend coverage by adding its building-set keys to the project's
`effect_bonus_value_building_set_junctions_tables` source.

## Save compatibility

The pack can be added to an ongoing Grand Campaign. It does not rewrite saved
factions or buildings. Already-paid costs are not refunded, and already-queued
construction may not recalculate its duration. Removing the pack does not
delete campaign entities; one-turn bundles expire naturally after the script
stops refreshing them.
