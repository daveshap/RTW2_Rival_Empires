-- Pure campaign-selection logic for RTW2 Rival Empires.
-- This file deliberately has no dependency on Rome II's engine interfaces so
-- its balance and eligibility rules can be tested under an ordinary Lua VM.

local core = {}

local function numeric(value, fallback)
    return tonumber(value) or fallback or 0
end

local function faction_key(faction)
    return tostring(faction.key or "")
end

local function is_basic_candidate(faction)
    return faction and faction.alive == true and
        faction.is_human ~= true and faction.excluded ~= true and
        faction.allied_human ~= true and
        faction.dependent_human ~= true
end

function core.base_tier_for_imperium(imperium, config)
    local value = math.floor(numeric(imperium, 0))
    local selected = 0
    for tier, _ in pairs(config.tiers) do
        local numeric_tier = math.floor(numeric(tier, 0))
        if value >= numeric_tier and numeric_tier > selected then
            selected = numeric_tier
        end
    end
    return selected
end

function core.bundle_key_for_tier(tier, config)
    local definition = config.tiers[math.floor(numeric(tier, 0))]
    return definition and definition.bundle_key or nil
end

local function previous_configured_tier(tier, config)
    local current = math.floor(numeric(tier, 0))
    local selected = 0
    for configured, _ in pairs(config.tiers) do
        local candidate = math.floor(numeric(configured, 0))
        if candidate < current and candidate > selected then
            selected = candidate
        end
    end
    return selected
end

function core.select_champions(factions, config)
    local candidates = {}
    for _, faction in pairs(factions or {}) do
        if is_basic_candidate(faction) and
            numeric(faction.regions, 0) >=
                numeric(config.minimum_champion_regions, 5) then
            candidates[#candidates + 1] = faction
        end
    end

    table.sort(candidates, function(left, right)
        local left_regions = numeric(left.regions, 0)
        local right_regions = numeric(right.regions, 0)
        if left_regions ~= right_regions then
            return left_regions > right_regions
        end
        local left_military = numeric(left.military, 0)
        local right_military = numeric(right.military, 0)
        if left_military ~= right_military then
            return left_military > right_military
        end
        return faction_key(left) < faction_key(right)
    end)

    local champions = {}
    local limit = math.max(
        0,
        math.floor(numeric(config.maximum_regional_champions, 3))
    )
    for index = 1, math.min(limit, #candidates) do
        champions[faction_key(candidates[index])] = true
    end
    return champions
end

function core.tier_for_faction(faction, base_tier, champions, config)
    if not is_basic_candidate(faction) or base_tier <= 0 then
        return 0, "excluded"
    end

    local mode = tostring(config.eligibility_mode or "independent_rivals")
    local operational_enemy = faction.at_war_human == true
    local full_strength = operational_enemy or
        champions[faction_key(faction)] == true

    if mode == "all_ai" then
        return base_tier, "all_ai"
    end
    if mode == "enemies_only" then
        if operational_enemy then
            return base_tier, "enemy"
        end
        return 0, "not_enemy"
    end
    if full_strength then
        if faction.at_war_human then
            return base_tier, "enemy"
        end
        return base_tier, "champion"
    end
    if numeric(faction.regions, 0) >=
        numeric(config.minimum_established_rival_regions, 3) then
        local lower_tier = previous_configured_tier(base_tier, config)
        if lower_tier > 0 then
            return lower_tier, "established_rival"
        end
    end
    return 0, "minor"
end

function core.assign_tiers(factions, human_imperium, config)
    local base_tier = core.base_tier_for_imperium(
        human_imperium,
        config
    )
    local champions = core.select_champions(factions, config)
    local assignments = {}
    local reasons = {}
    for _, faction in pairs(factions or {}) do
        local key = faction_key(faction)
        local tier, reason = core.tier_for_faction(
            faction,
            base_tier,
            champions,
            config
        )
        assignments[key] = tier
        reasons[key] = reason
    end
    return assignments, champions, reasons, base_tier
end

return core
