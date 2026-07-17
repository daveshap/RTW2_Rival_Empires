# Changelog

## 0.9.1 — 2026-07-17

- Fixed the startup-crash defect in the custom construction-time database
  layer: schema-version-0 tables now omit the on-disk version marker required
  only by positive table versions.
- Added an independent PFH4 and full-row DB decoder that rejects the exact
  malformed version-zero header emitted by 0.9.0.
- Replaced the shared companion-aware bootstrap with a Rival-only standalone
  loader and removed runtime knowledge of other mods.
- Replaced world-wide first-tick and human-turn bundle mutation with bounded
  per-AI-faction refreshes at that faction's turn start.
- Prevented native bundle calls against dead, regionless, rebel, separatist,
  civil-war, and other explicitly excluded faction placeholders.
- Made established-rival support select the previous configured tier even when
  a custom build uses non-contiguous Imperium tiers.
- Made the release command rebuild packs and generated sources, refresh
  checksums, run Python and Lua tests, build the deterministic ZIP, and verify
  the finished archive.
- Added release/source/checksum/version synchronization tests and made clean
  main-menu activation an explicit manual release gate.
- Withdrawn 0.9.0 as a boot-broken release; its archive remains unchanged for
  version history and diagnosis.

## 0.9.0 — 2026-07-17

- Added AI-only development response tiers keyed to local-human Imperium.
- Added faction research and building-cost support from Imperium 3 onward.
- Added a one-turn construction reduction for eleven verified core building
  sets from Imperium 4 onward.
- Added +1 to +4 provincial public-order stabilization from Imperium 4 onward.
- Added deterministic regional champions and a one-tier-lower established-rival
  band.
- Excluded human allies, dependents, insurgents, dead factions, and humans.
- Added bilateral treaty parsing so unrelated AI wars do not trigger support.
- Added optional read-only Grand Coalitions membership integration.
- Added save-load/first-tick reconciliation and one-turn faction bundles.
- Added a compatible Rome II bootstrap and a module-only compatibility build
  for independently installed scripted mods.
- Packaged the standalone and module-only variants, documentation, source,
  builders, and tests in one deterministic versioned release ZIP.
- Added deterministic PFH4/DB builders, balance simulation, Python tests, Lua
  5.1 parsing, and mocked campaign runtime tests.
