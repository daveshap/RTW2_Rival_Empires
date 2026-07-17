-- RTW2 Rival Empires - generated balanced configuration

return {
    version = "0.9.0",
    preset = "balanced",
    enabled = true,
    write_log = true,

    -- Version 0.9 is intentionally scoped to the single-player Grand
    -- Campaign. Multiple local humans need a different target-selection rule.
    grand_campaign_only = true,
    eligibility_mode = "independent_rivals",

    maximum_regional_champions = 3,
    minimum_champion_regions = 5,
    minimum_established_rival_regions = 3,
    effect_bundle_duration = 1,

    -- A faction at war with the local human, a Grand Coalition member, or a
    -- regional champion receives the current full tier. Other established
    -- independent rivals receive one tier lower. Human friends/dependents and
    -- campaign insurgents are always excluded.
    tiers = {
        [3] = { research_percent = 10, construction_cost_percent = 10, build_turns = 0, public_order = 0, bundle_key = "rtw2_rival_empires_tier_3" },
        [4] = { research_percent = 18, construction_cost_percent = 15, build_turns = -1, public_order = 1, bundle_key = "rtw2_rival_empires_tier_4" },
        [5] = { research_percent = 26, construction_cost_percent = 22, build_turns = -1, public_order = 2, bundle_key = "rtw2_rival_empires_tier_5" },
        [6] = { research_percent = 34, construction_cost_percent = 29, build_turns = -1, public_order = 3, bundle_key = "rtw2_rival_empires_tier_6" },
        [7] = { research_percent = 42, construction_cost_percent = 36, build_turns = -1, public_order = 4, bundle_key = "rtw2_rival_empires_tier_7" },
    },

    excluded_faction_patterns = {
        "slave",
        "rebel",
        "separatist",
        "civil_war",
        "civilwar"
    },

    subject_treaty_patterns = {
        "client_state",
        "client_of_player",
        "vassal",
        "satrap",
        "subject",
        "tributary"
    }
}
