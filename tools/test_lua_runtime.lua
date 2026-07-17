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

local factions = {
    rome, parthia, carthage, arverni, egypt, germania, iberia,
    minor, ally, client, rebels
}

set_treaty(egypt, rome, "current_treaty_at_war")
set_treaty(rome, egypt, "current_treaty_at_war")
ally._treaties[rome:name()] = {
    current_treaty_defensive_alliance = true
}
set_treaty(client, rome, "current_treaty_vassal_of_player")
set_treaty(rome, client, "current_treaty_client_state")

iberia._any_war = true

package.loaded["lua_scripts.rtw2_grand_coalitions"] = {
    get_active_coalition = function()
        return { target_key = "rom_rome", members = { "rom_suebi" } }
    end
}

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

rivals.reconcile_all(game)
local state = rivals.debug_state()
assert_equal(state.base_tier, 7, "maximum Imperium band")
for _, key in ipairs({
    "rom_parthia", "rom_carthage", "rom_arverni",
    "rom_ptolemaics", "rom_suebi"
}) do
    assert_equal(state.assignments[key], 7, key .. " full tier")
end
assert_equal(state.assignments["rom_arevaci"], 6, "established rival lower tier")
assert_equal(
    state.reasons["rom_arevaci"],
    "established_rival",
    "third-party aggregate war must not count as war with human"
)
assert_equal(state.assignments["rom_minor"], 0, "minor excluded")
assert_equal(state.assignments["rom_ally"], 0, "human ally excluded")
assert_equal(state.assignments["rom_client"], 0, "human dependent excluded")
assert_equal(state.assignments["rom_test_rebels"], 0, "rebels excluded")

local applied = {}
for _, call in ipairs(calls) do
    if call[1] == "apply" then
        applied[call[3]] = call
        assert_equal(call[4], 1, "bundle duration")
    end
end
assert_equal(applied["rom_ptolemaics"][2], "rtw2_rival_empires_tier_7")
assert_equal(applied["rom_arevaci"][2], "rtw2_rival_empires_tier_6")
assert_true(applied["rom_ally"] == nil, "ally receives no bundle")

-- The tunable enemies-only mode must not silently retain regional champions.
local previous_mode = rivals.config.eligibility_mode
rivals.config.eligibility_mode = "enemies_only"
local _, interfaces_for_mode = rivals.evaluate(game)
state = rivals.debug_state()
assert_equal(state.assignments["rom_parthia"], 0, "enemies-only champion")
assert_equal(state.assignments["rom_ptolemaics"], 7, "enemies-only war")
assert_equal(state.assignments["rom_suebi"], 7, "enemies-only coalition")
rivals.config.eligibility_mode = previous_mode

-- Early-game neutrality: the local human turn removes stale bundles and
-- applies none when Imperium is below three.
rome._imperium = 2
calls = {}
events.FactionTurnStart[1]({ faction = function() return rome end })
state = rivals.debug_state()
assert_equal(state.base_tier, 0, "Imperium two is inactive")
for _, call in ipairs(calls) do
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
local saw_egypt = false
for _, call in ipairs(calls) do
    if call[1] == "apply" and call[3] == "rom_ptolemaics" then
        saw_egypt = call[2] == "rtw2_rival_empires_tier_7"
    end
end
assert_true(saw_egypt, "post-load AI bundle application")

-- FirstTick also performs a complete reconciliation without needing a save.
calls = {}
events.FirstTickAfterWorldCreated[1]({})
assert_true(#calls > 0, "first-tick reconciliation calls")

print("RTW2 Rival Empires Lua runtime tests passed")
