--[[
RTW2 compatible scripted-campaign bootstrap

Rome II loads lua_scripts/all_scripted.lua globally. Keep every vanilla import,
then register whichever compatible optional RTW2 modules are present. Missing
optional modules are harmless; every mod remains independently packaged.
--]]

local triggers = require "data.lua_scripts.export_triggers"
local ancillaries = require "data.lua_scripts.export_ancillaries"
local historic_characters = require "data.lua_scripts.export_historic_characters"
local missions = require "data.lua_scripts.export_missions"
local encyclopedia = require "data.lua_scripts.export_encyclopedia"
local experience = require "data.lua_scripts.export_experience"
local political = require "data.lua_scripts.export_political_triggers"

events = triggers.events

local optional_modules = {
    {
        path = "lua_scripts.rtw2_food_exports",
        label = "RTW2 Food Exports"
    },
    {
        path = "lua_scripts.rtw2_grand_coalitions",
        label = "RTW2 Grand Coalitions"
    },
    {
        path = "lua_scripts.rtw2_rival_empires",
        label = "RTW2 Rival Empires"
    }
}

local function bootstrap_log(message)
    if type(out) == "table" and out.ting then
        out.ting("[RTW2 Bootstrap] " .. tostring(message))
    elseif type(out) == "function" then
        out("[RTW2 Bootstrap] " .. tostring(message))
    end
end

for _, definition in ipairs(optional_modules) do
    local loaded, module_or_error = pcall(require, definition.path)
    if loaded and type(module_or_error) == "table" and
        module_or_error.register then
        local registered, registration_error = pcall(
            module_or_error.register,
            events
        )
        if not registered then
            bootstrap_log(
                definition.label .. " registration failed: " ..
                tostring(registration_error)
            )
        end
    elseif not loaded then
        -- Missing optional modules are expected when only one compatible mod
        -- is installed. Report real module errors while ignoring "not found".
        local error_text = tostring(module_or_error)
        if not string.find(error_text, "not found", 1, true) then
            bootstrap_log(
                definition.label .. " load failed: " .. error_text
            )
        end
    end
end
