--[[
RTW2 Rival Empires

Applies development-only mobilization bundles to eligible AI factions as the
local human's Imperium rises. The module never grants money, units, recruitment
discounts, upkeep discounts, replenishment, morale, or battle-stat bonuses.
--]]

local rival_empires = {}

local config_ok, config_or_error = pcall(
    require,
    "lua_scripts.rtw2_rival_empires_config"
)
if not config_ok or type(config_or_error) ~= "table" then
    error(
        "RTW2 Rival Empires config failed to load: " ..
        tostring(config_or_error)
    )
end
rival_empires.config = config_or_error

local core_ok, core_or_error = pcall(
    require,
    "lua_scripts.rtw2_rival_empires_core"
)
if not core_ok or type(core_or_error) ~= "table" then
    error(
        "RTW2 Rival Empires core failed to load: " ..
        tostring(core_or_error)
    )
end
rival_empires.core = core_or_error

local state = {
    dirty = true,
    evaluated_turn = -1,
    human_key = nil,
    human_imperium = 0,
    base_tier = 0,
    assignments = {},
    reasons = {},
    champions = {}
}

local function log(message)
    if not rival_empires.config.write_log then
        return
    end
    local line = "[RTW2 Rival Empires] " .. tostring(message)
    if type(out) == "table" and out.ting then
        out.ting(line)
    elseif type(out) == "function" then
        out(line)
    end
end

local function safe_value(callback, fallback)
    local ok, value = pcall(callback)
    if ok and value ~= nil then
        return value
    end
    return fallback
end

local function safe_number(callback, fallback)
    return tonumber(safe_value(callback, fallback)) or fallback or 0
end

local function campaign_game_interface()
    local episodic = rawget(_G, "EpisodicScripting")
    if type(episodic) == "table" and episodic.game_interface then
        return episodic.game_interface
    end
    episodic = rawget(_G, "scripting")
    if type(episodic) == "table" and episodic.game_interface then
        return episodic.game_interface
    end
    episodic = package.loaded["lua_scripts.EpisodicScripting"]
    if type(episodic) == "table" and episodic.game_interface then
        return episodic.game_interface
    end
    local loaded, result = pcall(
        require,
        "lua_scripts.EpisodicScripting"
    )
    if loaded and type(result) == "table" and result.game_interface then
        return result.game_interface
    end
    return nil
end

local function list_count(list)
    if not list then
        return 0
    end
    return math.max(0, math.floor(safe_number(function()
        return list:num_items()
    end, 0)))
end

local function faction_key(reference)
    if type(reference) == "string" then
        return reference
    end
    return safe_value(function()
        return reference:name()
    end, nil)
end

local function excluded_key(key)
    local lower = string.lower(tostring(key or ""))
    for _, pattern in ipairs(
        rival_empires.config.excluded_faction_patterns
    ) do
        if string.find(
            lower,
            string.lower(tostring(pattern)),
            1,
            true
        ) then
            return true
        end
    end
    return false
end

local function normalize_treaty(value)
    return string.lower(tostring(value or ""))
end

local function treaty_map_for(faction)
    local result = {}
    local details = safe_value(function()
        return faction:treaty_details()
    end, nil)
    if type(details) ~= "table" then
        return result
    end

    for other_reference, treaty_list in pairs(details) do
        local other_key = faction_key(other_reference)
        if other_key and type(treaty_list) == "table" then
            result[other_key] = result[other_key] or {}
            for treaty_key, treaty_value in pairs(treaty_list) do
                -- Engine builds normally expose an array of treaty strings.
                -- Some mocks/wrappers expose a set keyed by treaty instead;
                -- accept both without turning boolean values into names.
                local treaty = treaty_value
                if type(treaty_key) == "string" and
                    treaty_value == true then
                    treaty = treaty_key
                end
                local normalized = normalize_treaty(treaty)
                if normalized ~= "" then
                    result[other_key][normalized] = true
                end
            end
        end
    end
    return result
end

local function treaty_names_between(left_map, right_map, left_key, right_key)
    local merged = {}
    local left = left_map[right_key] or {}
    local right = right_map[left_key] or {}
    for name, present in pairs(left) do
        if present then
            merged[name] = true
        end
    end
    for name, present in pairs(right) do
        if present then
            merged[name] = true
        end
    end
    return merged
end

local function treaties_contain(treaties, fragment)
    local needle = string.lower(tostring(fragment or ""))
    for treaty, present in pairs(treaties or {}) do
        if present and string.find(treaty, needle, 1, true) then
            return true
        end
    end
    return false
end

local function subject_relationship(treaties)
    for _, pattern in ipairs(rival_empires.config.subject_treaty_patterns) do
        if treaties_contain(treaties, pattern) then
            return true
        end
    end
    return false
end

local function collect_military(faction)
    local forces = safe_value(function()
        return faction:military_force_list()
    end, nil)
    local total = 0
    for force_index = 0, list_count(forces) - 1 do
        local force = safe_value(function()
            return forces:item_at(force_index)
        end, nil)
        local units = force and safe_value(function()
            return force:unit_list()
        end, nil) or nil
        for unit_index = 0, list_count(units) - 1 do
            local unit = safe_value(function()
                return units:item_at(unit_index)
            end, nil)
            if unit then
                local strength = safe_number(function()
                    return unit:percentage_proportion_of_full_strength()
                end, 100) / 100
                if strength < 0 then
                    strength = 0
                elseif strength > 1 then
                    strength = 1
                end
                total = total + (0.5 + 0.5 * strength)
            end
        end
    end
    return total
end

local function local_human(model, faction_interfaces)
    local fallback = nil
    for key, faction in pairs(faction_interfaces) do
        if safe_value(function()
            return faction:is_human()
        end, false) then
            fallback = fallback or faction
            if safe_value(function()
                return model:faction_is_local(key)
            end, false) then
                return faction
            end
        end
    end
    return fallback
end

local function collect_world(game)
    local model = game:model()
    local faction_list = model:world():faction_list()
    local snapshots = {}
    local interfaces = {}
    local treaty_maps = {}
    for index = 0, list_count(faction_list) - 1 do
        local faction = faction_list:item_at(index)
        local key = faction_key(faction)
        if key then
            local regions = list_count(safe_value(function()
                return faction:region_list()
            end, nil))
            snapshots[key] = {
                key = key,
                alive = regions > 0,
                is_human = safe_value(function()
                    return faction:is_human()
                end, false),
                excluded = excluded_key(key),
                regions = regions,
                military = collect_military(faction),
                at_war_human = false,
                allied_human = false,
                dependent_human = false
            }
            interfaces[key] = faction
            treaty_maps[key] = treaty_map_for(faction)
        end
    end

    local human = local_human(model, interfaces)
    local human_key = faction_key(human)
    if not human or not human_key then
        return snapshots, interfaces, nil, nil
    end
    local human_map = treaty_maps[human_key] or {}

    for key, snapshot in pairs(snapshots) do
        if key ~= human_key then
            local faction = interfaces[key]
            local treaties = treaty_names_between(
                treaty_maps[key] or {},
                human_map,
                key,
                human_key
            )
            -- Rome II's faction:at_war() query is an aggregate boolean, not a
            -- reliable bilateral query. Treaty details name the counterparty,
            -- so use only the merged directional treaty record here.
            snapshot.at_war_human =
                treaties.current_treaty_at_war == true
            snapshot.allied_human =
                treaties.current_treaty_military_alliance == true or
                treaties.current_treaty_defensive_alliance == true
            snapshot.dependent_human = subject_relationship(treaties)
        end
    end
    return snapshots, interfaces, human, human_key
end

local function campaign_is_supported(game)
    local model = game:model()
    if safe_value(function()
        return model:is_multiplayer()
    end, false) then
        return false, "multiplayer"
    end
    if rival_empires.config.grand_campaign_only then
        local campaign = tostring(safe_value(function()
            return model:campaign_name()
        end, ""))
        if campaign ~= "main_rome" then
            return false, "campaign=" .. campaign
        end
    end
    return true, ""
end

local function current_turn(game)
    return math.floor(safe_number(function()
        return game:model():turn_number()
    end, 0))
end

local function remove_known_bundles(game, key)
    for tier, definition in pairs(rival_empires.config.tiers) do
        if tonumber(tier) and definition.bundle_key then
            game:remove_effect_bundle(definition.bundle_key, key)
        end
    end
end

local function runtime_target(faction)
    local key = faction_key(faction)
    if not key or excluded_key(key) then
        return false
    end
    if safe_value(function()
        return faction:is_human()
    end, false) then
        return false
    end
    return list_count(safe_value(function()
        return faction:region_list()
    end, nil)) > 0
end

local function apply_assignment(game, faction, tier)
    local key = faction_key(faction)
    if not key or not runtime_target(faction) then
        return false
    end
    local bundle = rival_empires.core.bundle_key_for_tier(
        tier,
        rival_empires.config
    )
    for _, definition in pairs(rival_empires.config.tiers) do
        if definition.bundle_key and definition.bundle_key ~= bundle then
            game:remove_effect_bundle(definition.bundle_key, key)
        end
    end
    if bundle then
        game:apply_effect_bundle(
            bundle,
            key,
            rival_empires.config.effect_bundle_duration
        )
    end
    return true
end

function rival_empires.evaluate(game)
    local snapshots, interfaces, human, human_key = collect_world(game)
    if not human then
        error("local human faction could not be resolved")
    end
    local imperium = math.floor(safe_number(function()
        return human:imperium_level()
    end, 0))
    local assignments, champions, reasons, base_tier =
        rival_empires.core.assign_tiers(
            snapshots,
            imperium,
            rival_empires.config
        )

    state.dirty = false
    state.evaluated_turn = current_turn(game)
    state.human_key = human_key
    state.human_imperium = imperium
    state.base_tier = base_tier
    state.assignments = assignments
    state.reasons = reasons
    state.champions = champions
    return snapshots, interfaces
end

local function log_assignments()
    local boosted = 0
    for _, tier in pairs(state.assignments) do
        if tier > 0 then
            boosted = boosted + 1
        end
    end
    local champion_count = 0
    for _, present in pairs(state.champions) do
        if present then
            champion_count = champion_count + 1
        end
    end
    log(
        "evaluated turn=" .. tostring(state.evaluated_turn) ..
        " human=" .. tostring(state.human_key) ..
        " imperium=" .. tostring(state.human_imperium) ..
        " base_tier=" .. tostring(state.base_tier) ..
        " champions=" .. tostring(champion_count) ..
        " boosted=" .. tostring(boosted)
    )
end

function rival_empires.prepare_round(game)
    local snapshots, interfaces = rival_empires.evaluate(game)
    log_assignments()
    return snapshots, interfaces
end

function rival_empires.on_faction_turn_start(context)
    local game = campaign_game_interface()
    if not game then
        if not rival_empires.config.enabled then
            return
        end
        error("campaign game_interface is unavailable")
    end
    local supported, reason = campaign_is_supported(game)
    if not supported then
        log("inactive: " .. reason)
        return
    end
    local faction = context:faction()
    local key = faction_key(faction)
    local is_local_human = safe_value(function()
        return faction:is_human() and
            game:model():faction_is_local(key)
    end, false)

    if not rival_empires.config.enabled then
        if runtime_target(faction) then
            remove_known_bundles(game, key)
        end
        return
    end

    if is_local_human then
        state.dirty = true
        rival_empires.prepare_round(game)
        return
    end
    if safe_value(function()
        return faction:is_human()
    end, false) then
        return
    end

    local turn = current_turn(game)
    if state.dirty or state.evaluated_turn ~= turn then
        rival_empires.prepare_round(game)
    end
    apply_assignment(game, faction, state.assignments[key] or 0)
end

function rival_empires.on_loading_game(context)
    state.dirty = true
    state.evaluated_turn = -1
end

function rival_empires.on_first_tick_after_world_created(context)
    -- FirstTick is deliberately mutation-free. The next faction-turn event
    -- evaluates the world and refreshes only that active AI faction's bundle.
    state.dirty = true
    state.evaluated_turn = -1
end

local function safe_handler(name, callback, context)
    local ok, error_message = pcall(callback, context)
    if not ok then
        log(name .. " failed: " .. tostring(error_message))
    end
end

function rival_empires.register(event_table)
    if rawget(_G, "__rtw2_rival_empires_registered") then
        return true
    end
    if type(event_table) ~= "table" or
        type(event_table.FactionTurnStart) ~= "table" or
        type(event_table.LoadingGame) ~= "table" then
        error("required Rome II campaign events are unavailable")
    end

    table.insert(event_table.FactionTurnStart, function(context)
        safe_handler(
            "FactionTurnStart",
            rival_empires.on_faction_turn_start,
            context
        )
    end)
    table.insert(event_table.LoadingGame, function(context)
        safe_handler("LoadingGame", rival_empires.on_loading_game, context)
    end)
    if type(event_table.FirstTickAfterWorldCreated) == "table" then
        table.insert(event_table.FirstTickAfterWorldCreated, function(context)
            safe_handler(
                "FirstTickAfterWorldCreated",
                rival_empires.on_first_tick_after_world_created,
                context
            )
        end)
    end

    rawset(_G, "__rtw2_rival_empires_registered", true)
    log("registered preset=" .. tostring(rival_empires.config.preset))
    return true
end

function rival_empires.debug_state()
    return state
end

return rival_empires
