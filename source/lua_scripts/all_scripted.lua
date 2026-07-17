--[[
RTW2 Rival Empires standalone scripted-campaign bootstrap

Rome II loads lua_scripts/all_scripted.lua globally. Keep every vanilla import,
then register Rival Empires. This loader contains no knowledge of other mods.
--]]

local triggers = require "data.lua_scripts.export_triggers"
local ancillaries = require "data.lua_scripts.export_ancillaries"
local historic_characters = require "data.lua_scripts.export_historic_characters"
local missions = require "data.lua_scripts.export_missions"
local encyclopedia = require "data.lua_scripts.export_encyclopedia"
local experience = require "data.lua_scripts.export_experience"
local political = require "data.lua_scripts.export_political_triggers"

events = triggers.events

local function bootstrap_log(message)
    if type(out) == "table" and out.ting then
        out.ting("[RTW2 Bootstrap] " .. tostring(message))
    elseif type(out) == "function" then
        out("[RTW2 Bootstrap] " .. tostring(message))
    end
end

local loaded, module_or_error = pcall(
    require,
    "lua_scripts.rtw2_rival_empires"
)
if loaded and type(module_or_error) == "table" and
    module_or_error.register then
    local registered, registration_error = pcall(
        module_or_error.register,
        events
    )
    if not registered then
        bootstrap_log(
            "RTW2 Rival Empires registration failed: " ..
            tostring(registration_error)
        )
    end
elseif not loaded then
    bootstrap_log(
        "RTW2 Rival Empires load failed: " .. tostring(module_or_error)
    )
else
    bootstrap_log("RTW2 Rival Empires module has no register function")
end
