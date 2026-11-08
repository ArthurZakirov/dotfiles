"""Behavioral contract of the Hammerspoon find-gpt-session shortcut feedback."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "home/dot_hammerspoon/modules/gpt_sessions.lua"
LUAJIT = shutil.which("luajit")


def lua_run(source: str) -> str:
    assert LUAJIT
    setup = (
        "HammerspoonConfig = {hyper = {'ctrl', 'alt', 'cmd'}}\n"
        "hs = {hotkey = {bind = function() end}}\n"
        f"dofile({json.dumps(str(MODULE))})\n"
    )
    completed = subprocess.run(
        [LUAJIT, "-e", setup + source],
        capture_output=True,
        text=True,
        timeout=8,
        check=True,
    )
    return completed.stdout.strip()


@pytest.mark.skipif(LUAJIT is None, reason="LuaJIT unavailable on this runner")
@pytest.mark.parametrize(
    ("payload", "exit_code", "expected_count", "expected_status", "expected_message"),
    [
        pytest.param(
            {"total": 0, "incomplete_providers": ["safari"]},
            2, 0, "provider-incomplete", "ChatGPT-Suche derzeit nicht verfügbar",
            id="pr-65-no-codex-and-safari-unavailable",
        ),
        pytest.param(
            {"total": 0, "incomplete_providers": []},
            1, 0, "no-matches", "Keine passende Session gefunden",
            id="verified-no-matches",
        ),
        pytest.param(
            {"total": 1, "incomplete_providers": ["safari"]},
            2, 0, "unopenable", "Treffer gefunden",
            id="found-but-no-verifiable-url",
        ),
        pytest.param(
            {"total": 2, "opening": {"dispatched": [{}, {}]}, "incomplete_providers": []},
            0, 2, "opened", "2 Sessions geöffnet",
            id="opened-two-sessions",
        ),
        pytest.param(
            {"total": 2, "opening": {"dispatched": [{}]}, "incomplete_providers": ["safari"]},
            2, 1, "partial-open", "1 Session geöffnet; weitere Treffer nicht verfügbar",
            id="opened-one-with-partial-failure",
        ),
        pytest.param(
            {"total": 0, "incomplete_providers": ["codex", "safari"]},
            2, 0, "provider-incomplete", "Codex- und ChatGPT-Suche derzeit nicht verfügbar",
            id="providers-unavailable",
        ),
        pytest.param(
            {"total": 1, "opening": {"dispatched": [{}]}, "incomplete_providers": ["safari"]},
            0, 1, "opened", "1 Session geöffnet.",
            id="opened-codex-with-safari-unavailable",
        ),
    ],
)
def test_shortcut_feedback_is_specific_and_not_a_false_hotkey_error(
    payload: dict,
    exit_code: int,
    expected_count: int,
    expected_status: str,
    expected_message: str,
):
    # LuaJIT does not parse JSON as a Lua table: construct the relevant shape
    # explicitly, preserving fields and the public status contract.
    providers = payload.get("incomplete_providers", [])
    table = "{" + (
        f"total={payload['total']},"
        f"incomplete_providers={{{','.join(json.dumps(s) for s in providers)}}},"
        f"opening={{dispatched={{{','.join('{}' for _ in payload.get('opening', {}).get('dispatched', []))}}}}}"
    ) + "}"
    output = lua_run(
        f"local m,n,s = HammerspoonConfig.relatedSessionFeedback({table}, {exit_code});"
        "print(tostring(n)..'|'..s..'|'..m)"
    )
    count, status, message = output.split("|", 2)
    assert int(count) == expected_count
    assert status == expected_status
    assert expected_message in message
    assert "inspect find-gpt-session logs" not in message


@pytest.mark.skipif(LUAJIT is None, reason="LuaJIT unavailable on this runner")
def test_hotkey_invokes_json_cli_and_displays_precise_message():
    output = lua_run(
        """
        local alerts = {}
        local invokedArgs
        local callback
        hs.alert = {show = function(msg) table.insert(alerts, msg) end}
        hs.json = {decode = function()
            return {total=0, incomplete_providers={'safari'}}
        end}
        hs.task = {new = function(helper, fn, args)
            callback = fn
            invokedArgs = args
            local task = {}
            function task:environment() return {} end
            function task:setEnvironment(_) end
            function task:start()
                callback(2, '{}', '')
                return true
            end
            return task
        end}
        HammerspoonConfig.gitBrowserUrl = function(_)
            return 'https://github.com/example/demo/pull/65'
        end
        HammerspoonConfig.openRelatedSessionsFromApp({
            bundleID = function() return 'com.google.Chrome' end
        })
        print(table.concat(invokedArgs, ','))
        print(alerts[#alerts])
        print(HammerspoonConfig.lastRelatedSessionOpen.status)
        """
    )
    args, message, status = output.splitlines()
    assert args.startswith("--json,--open,--context-url,")
    assert "ChatGPT-Suche derzeit nicht verfügbar" in message
    assert status == "provider-incomplete"

@pytest.mark.skipif(LUAJIT is None, reason="LuaJIT unavailable on this runner")
def test_browser_hotkey_invokes_search_without_modifier_release_polling():
    """The real hotkey callback must not defer Chrome until modifier release."""
    output = lua_run(
        """
        local alerts = {}
        local callback
        HammerspoonConfig.afterModsReleased = function()
            error('Chrome must not wait for modifier release')
        end
        hs.alert = {show=function(msg) table.insert(alerts, msg) end}
        hs.application = {frontmostApplication=function()
            return {bundleID=function() return 'com.google.Chrome' end}
        end}
        hs.task = {new=function(_,fn,args)
            callback = fn
            local task={}
            function task:environment() return {} end
            function task:setEnvironment(_) end
            function task:start() return true end
            return task
        end}
        HammerspoonConfig.gitBrowserUrl=function(_)
            return 'https://github.com/example/demo/pull/65'
        end
        HammerspoonConfig.openRelatedSessionsFromHotkey()
        print(HammerspoonConfig.lastRelatedSessionOpen.phase)
        print(alerts[1])
        """
    )
    phase, message = output.splitlines()
    assert phase == "starting"
    assert "Session-Suche gestartet" in message


@pytest.mark.skipif(LUAJIT is None, reason="LuaJIT unavailable on this runner")
def test_vscode_hotkey_waits_before_injecting_task_shortcut():
    output = lua_run(
        """
        local alerts = {}
        local deferred
        HammerspoonConfig.afterModsReleased = function(fn) deferred=fn end
        hs.alert = {show=function(msg) table.insert(alerts,msg) end}
        hs.application={frontmostApplication=function()
            return {bundleID=function() return 'com.microsoft.VSCode' end}
        end}
        local count=0
        hs.eventtap={keyStroke=function(...)count=count+1 end}
        HammerspoonConfig.openRelatedSessionsFromHotkey()
        print(HammerspoonConfig.lastRelatedSessionOpen.phase)
        print(tostring(deferred ~= nil))
        print(tostring(count))
        deferred()
        print(tostring(count))
        """
    )
    assert output.splitlines() == ["hotkey-received", "true", "0", "1"]
