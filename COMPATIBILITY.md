# Compatibility

## Campaign scope

Version 0.9.1 runs only in the single-player `main_rome` Grand Campaign. It
disables itself in multiplayer and other campaigns rather than choosing an
arbitrary human target or relying on unverified building-set coverage.

## Standalone campaign loader

Rome II uses `lua_scripts/all_scripted.lua` as its global scripted-campaign
entry point. Only one enabled file can win that exact internal path.

Rival Empires is independently versioned and distributed. Its standalone pack
preserves all seven vanilla imports and registers only Rival Empires. It does
not import, inspect, or depend on any separately versioned mod.

If another overhaul owns `all_scripted.lua`, merge this registration into that
loader and use:

```text
compatibility/@rtw2_rival_empires_balanced_module_only.pack
```

The module-only pack deliberately omits the bootstrap. Enabling it without a
merged loader leaves the Lua module dormant.

The tradeoff is explicit: Rome II allows only one enabled
`lua_scripts/all_scripted.lua` to win. To combine this pack with any other
scripted mod, maintain a deliberately merged loader and use the module-only
variant. Database-only mods do not create that loader conflict.

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
