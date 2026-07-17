-- Runtime smoke test for RTW2 Rival Empires using mocked Rome II interfaces.

package.path = "source/?.lua;" .. package.path

local function fail(message)
    error("TEST FAILURE: " .. tostring(message), 2)
end

local function assert_true(value, message)
    if not value then
        fail(message or "expected true")
    end
end

local function assert_equal(actual, expected, message)
    if actual ~= expected then
        fail(
            (message or "values differ") ..
            ": expected=" .. tostring(expected) ..
            " actual=" .. tostring(actual)
        )
    end
end

local function list(items)
    return {
        num_items = function(self)
            return #items
        end,
        item_at = function(self, index)
            return items[index + 1]
        end
    }
end

local function set_treaty(left, right, treaty)
    left._treaties[right:name()] = left._treaties[right:name()] or {}
    table.insert(left._treaties[right:name()], treaty)
end

local function make_faction(key, human, regions, units)
    local faction = {
        _key = key,
        _human = human,
        _regions = {},
        _units = units or 0,
        _imperium = human and 7 or 2,
        _treaties = {},
        _any_war = false
    }
    function faction:name()
        return self._key
    end
    function faction:is_human()
        return self._human
    end
    function faction:region_list()
        return list(self._regions)
    end
    function faction:military_force_list()
        local units_list = {}
        for index = 1, self._units do
            units_list[index] = {
                percentage_proportion_of_full_strength = function()
                    return 100
                end
            }
        end
        return list({
            {
                unit_list = function()
                    return list(units_list)
                end
            }
        })
    end
    function faction:imperium_level()
        return self._imperium
    end
    function faction:treaty_details()
        return self._treaties
    end
    -- Deliberately aggregate, mirroring Rome II. Iberia uses true below to
    -- prove a third-party war does not become a human war.
    function faction:at_war()
        return self._any_war
    end
    for index = 1, regions do
        faction._regions[index] = {}
    end
    return faction
end

local rome = make_faction("rom_rome", true, 40, 90)
local parthia = make_faction("rom_parthia", false, 12, 32)
local carthage = make_faction("rom_carthage", false, 10, 28)
local arverni = make_faction("rom_arverni", false, 8, 22)
local egypt = make_faction("rom_ptolemaics", false, 4, 16)
local germania = make_faction("rom_suebi", false, 4, 14)
local iberia = make_faction("rom_arevaci", false, 6, 18)
local minor = make_faction("rom_minor", false, 2, 8)
local ally = make_faction("rom_ally", false, 7, 18)
local client = make_faction("rom_client", false, 7, 18)
local rebels = make_faction("rom_test_rebels", false, 14, 30)
local dead = make_faction("rom_dead", false, 0, 0)

local factions = {
    rome, parthia, carthage, arverni, egypt, germania, iberia,
    minor, ally, client, rebels, dead
}

set_treaty(egypt, rome, "current_treaty_at_war")
set_treaty(rome, egypt, "current_treaty_at_war")
ally._treaties[rome:name()] = {
    current_treaty_defensive_alliance = true
}
set_treaty(client, rome, "current_treaty_vassal_of_player")
set_treaty(rome, client, "current_treaty_client_state")

iberia._any_war = true

local model = {
    _turn = 120,
    world = function()
        return {
            faction_list = function()
                return list(factions)
            end
        }
    end,
    faction_is_local = function(self, key)
        return key == "rom_rome"
    end,
    is_multiplayer = function()
        return false
    end,
    campaign_name = function()
        return "main_rome"
    end,
    turn_number = function(self)
        return self._turn
    end
}

local calls = {}
local game = {
    model = function()
        return model
    end,
    remove_effect_bundle = function(self, bundle, faction_key)
        calls[#calls + 1] = { "remove", bundle, faction_key }
    end,
    apply_effect_bundle = function(self, bundle, faction_key, duration)
        calls[#calls + 1] = {
            "apply", bundle, faction_key, duration
        }
    end
}

package.loaded["lua_scripts.EpisodicScripting"] = {
    game_interface = game
}
_G.EpisodicScripting = package.loaded["lua_scripts.EpisodicScripting"]
_G.out = function(message) end

local rivals = require "lua_scripts.rtw2_rival_empires"

local events = {
    FactionTurnStart = {},
    LoadingGame = {},
    FirstTickAfterWorldCreated = {}
}
assert_true(rivals.register(events), "event registration")
assert_equal(#events.FactionTurnStart, 1, "turn handler count")
assert_equal(#events.LoadingGame, 1, "load handler count")
assert_equal(#events.FirstTickAfterWorldCreated, 1, "first-tick handler count")

rivals.prepare_round(game)
local state = rivals.debug_state()
assert_equal(#calls, 0, "round preparation must not mutate native state")
assert_equal(state.base_tier, 7, "maximum Imperium band")
for _, key in ipairs({
    "rom_parthia", "rom_carthage", "rom_arverni",
    "rom_ptolemaics"
}) do
    assert_equal(state.assignments[key], 7, key .. " full tier")
end
assert_equal(state.assignments["rom_arevaci"], 6, "established rival lower tier")
assert_equal(state.assignments["rom_suebi"], 6, "standalone established rival")
assert_equal(
    state.reasons["rom_arevaci"],
    "established_rival",
    "third-party aggregate war must not count as war with human"
)
assert_equal(state.assignments["rom_minor"], 0, "minor excluded")
assert_equal(state.assignments["rom_ally"], 0, "human ally excluded")
assert_equal(state.assignments["rom_client"], 0, "human dependent excluded")
assert_equal(state.assignments["rom_test_rebels"], 0, "rebels excluded")
assert_equal(state.assignments["rom_dead"], 0, "dead faction excluded")

-- Applying a tier is bounded to the active AI faction; no world-wide native
-- mutation occurs during round preparation or another faction's turn.
calls = {}
events.FactionTurnStart[1]({ faction = function() return egypt end })
local saw_egypt = false
for _, call in ipairs(calls) do
    assert_equal(call[3], "rom_ptolemaics", "per-faction mutation target")
    if call[1] == "apply" then
        saw_egypt = call[2] == "rtw2_rival_empires_tier_7"
        assert_equal(call[4], 1, "bundle duration")
    end
end
assert_true(saw_egypt, "enemy receives full-tier bundle")

calls = {}
events.FactionTurnStart[1]({ faction = function() return iberia end })
local saw_iberia = false
for _, call in ipairs(calls) do
    assert_equal(call[3], "rom_arevaci", "established-rival target")
    if call[1] == "apply" then
        saw_iberia = call[2] == "rtw2_rival_empires_tier_6"
    end
end
assert_true(saw_iberia, "established rival receives lower-tier bundle")

-- The tunable enemies-only mode must not silently retain regional champions.
local previous_mode = rivals.config.eligibility_mode
rivals.config.eligibility_mode = "enemies_only"
rivals.evaluate(game)
state = rivals.debug_state()
assert_equal(state.assignments["rom_parthia"], 0, "enemies-only champion")
assert_equal(state.assignments["rom_ptolemaics"], 7, "enemies-only war")
assert_equal(state.assignments["rom_suebi"], 0, "enemies-only neutral")
rivals.config.eligibility_mode = previous_mode

-- Early-game neutrality: the local human turn only evaluates assignments.
rome._imperium = 2
calls = {}
events.FactionTurnStart[1]({ faction = function() return rome end })
state = rivals.debug_state()
assert_equal(state.base_tier, 0, "Imperium two is inactive")
assert_equal(#calls, 0, "human turn performs no native bundle mutation")

-- The current AI clears its own stale bundles and receives no early-game
-- application. Every native call remains scoped to that one faction.
calls = {}
events.FactionTurnStart[1]({ faction = function() return egypt end })
for _, call in ipairs(calls) do
    assert_equal(call[3], "rom_ptolemaics", "early-game cleanup target")
    assert_true(call[1] ~= "apply", "no early-game application")
end

-- Loading marks assignments dirty; the next AI start evaluates the current
-- maximum Imperium and reapplies that faction's one-turn bundle.
events.LoadingGame[1]({})
rome._imperium = 7
calls = {}
events.FactionTurnStart[1]({ faction = function() return egypt end })
state = rivals.debug_state()
assert_equal(state.base_tier, 7, "post-load evaluation")
saw_egypt = false
for _, call in ipairs(calls) do
    if call[1] == "apply" and call[3] == "rom_ptolemaics" then
        saw_egypt = call[2] == "rtw2_rival_empires_tier_7"
    end
end
assert_true(saw_egypt, "post-load AI bundle application")

-- FirstTick is deliberately mutation-free. The next active AI evaluates and
-- refreshes only itself.
calls = {}
events.FirstTickAfterWorldCreated[1]({})
state = rivals.debug_state()
assert_true(state.dirty, "first tick marks assignments dirty")
assert_equal(#calls, 0, "first tick performs no native mutation")
events.FactionTurnStart[1]({ faction = function() return egypt end })
assert_true(#calls > 0, "next AI turn refreshes its own bundle")
for _, call in ipairs(calls) do
    assert_equal(call[3], "rom_ptolemaics", "post-first-tick target")
end

-- Excluded and dead placeholders never receive native bundle calls.
calls = {}
events.FactionTurnStart[1]({ faction = function() return rebels end })
events.FactionTurnStart[1]({ faction = function() return dead end })
assert_equal(#calls, 0, "excluded/dead factions are never mutated")

-- Disabling the mod drains only the currently active AI faction.
rivals.config.enabled = false
calls = {}
events.FactionTurnStart[1]({ faction = function() return egypt end })
assert_true(#calls > 0, "disabled mod clears current AI bundles")
for _, call in ipairs(calls) do
    assert_equal(call[1], "remove", "disabled cleanup only removes")
    assert_equal(call[3], "rom_ptolemaics", "disabled cleanup target")
end
rivals.config.enabled = true

-- Tuned builds may intentionally skip Imperium bands. Established rivals use
-- the previous configured tier, not a hard-coded numeric decrement.
local saved_tiers = rivals.config.tiers
rivals.config.tiers = {
    [3] = { bundle_key = "tier_3" },
    [5] = { bundle_key = "tier_5" },
    [7] = { bundle_key = "tier_7" }
}
local tuned_assignments = rivals.core.assign_tiers({
    established = {
        key = "established",
        alive = true,
        is_human = false,
        excluded = false,
        allied_human = false,
        dependent_human = false,
        at_war_human = false,
        regions = 3,
        military = 1
    }
}, 7, rivals.config)
assert_equal(tuned_assignments.established, 5, "previous configured tier")
rivals.config.tiers = saved_tiers

print("RTW2 Rival Empires Lua runtime tests passed")
