# In-game test checklist

Automated tests cover formulas, selection, pack bytes, DB records, Lua parsing,
and mocked campaign calls. These checks require the actual Rome II executable.

## Clean activation

1. Back up the save.
2. Disable every other user-script mod and enable only the balanced Rival
   Empires standalone pack.
3. Confirm **Run user script mods** is enabled.
4. Launch Rome II and confirm that the main menu appears. Failure to reach the
   main menu is release-blocking.
5. Load a single-player Grand Campaign.
6. End or advance the current turn.
7. Check `scripting.lua.log` for `RTW2 Rival Empires` registration and an
   assignment line containing the human Imperium and base tier.

Expected: no startup crash, Lua error, freeze, or campaign event failure.

## Maximum-Imperium save

1. Load a save where the local human has maximum Imperium.
2. Advance to several AI faction turns.
3. Inspect a current enemy's newly offered building costs where observable.
4. Queue or observe a new core building through a transferable test save or
   campaign inspection tool if available.

Expected full tier: +42% research, −36% construction cost, −1 turn on covered
core building sets, and +4 provincial public order. Already-queued buildings
need not change duration and already-paid costs are not refunded.

## Regional champion selection

1. Identify the three largest non-friendly, non-dependent AI factions with at
   least five regions.
2. Confirm the evaluation log reports three champions when three exist.
3. Compare against a fourth independent faction with at least three regions.

Expected: the top three receive the full tier; the fourth receives one tier
lower. Ties resolve by military unit strength and then faction key.

## Relationship exclusions

Check one of each if present:

- human military or defensive ally;
- human client, vassal, satrapy, subject, or tributary;
- slave, rebel, separatist, or civil-war faction;
- neutral one- or two-region minor; and
- AI faction at war with someone other than the human.

Expected: none is classified as a current human enemy or receives a bundle,
except that an actual war with the human always receives the full current tier.
A third-party war alone must not trigger the full tier.

## Construction coverage

Test new agriculture, capital/city, industry, military, port, religion, and
sanitation construction orders.

Expected at Imperium 4+: a one-turn reduction where the original duration is
above the engine minimum. Test DLC/overhaul buildings separately; unlisted
building sets may retain their original duration while still getting the cost
discount.

## Save/load and removal

1. Save while the maximum tier is active.
2. Reload and advance to the next AI faction turn.
3. Confirm an assignment line appears and effects persist as each AI faction
   begins its turn.
4. On a disposable copy, disable the pack and advance one full round.

Expected: load refreshes bundles. After removal, the one-turn bundles expire;
no faction, unit, building, or region is deleted.

## Report with

- campaign and turn;
- local human Imperium;
- affected faction key and region count;
- diplomatic relationship to the human;
- building key/set if construction duration is involved;
- complete `RTW2 Rival Empires` log lines; and
- active mod list and load order.
