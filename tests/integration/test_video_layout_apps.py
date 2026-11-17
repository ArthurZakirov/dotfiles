"""Exercise app identity selection without manipulating the live desktop."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('chat_running', [True, False])
def test_edit_layout_never_selects_codex_for_chatgpt(tmp_path, chat_running):
    lua = shutil.which('luajit')
    if not lua:
        pytest.skip('LuaJIT required')
    text = (ROOT / 'home/dot_hammerspoon/modules/video_layouts.lua.tmpl').read_text()
    module = tmp_path / 'module.lua'
    module.write_text(text.split('{{ else -}}')[0].split('\n', 1)[1])
    scenario = tmp_path / 'scenario.lua'
    scenario.write_text('''
local activated, opened = {}, {}
local win = {isStandard=function() return true end, id=function() return 1 end,
 isFullScreen=function() return false end, isMinimized=function() return false end,
 setFrame=function() end, raise=function() end}
local function app(name)
 return {name=function() return name end, bundleID=function() return "com.openai.codex" end,
 allWindows=function() return {win} end, mainWindow=function() return win end,
 unhide=function() end, activate=function() activated[name]=true end}
end
local codex, chat = app("Codex"), app("ChatGPT")
local apps={codex}
if arg[2]=="yes" then table.insert(apps,chat) end
hs={application={runningApplications=function() return apps end,
 get=function(bundle) if bundle=="com.openai.codex" then return codex end end, open=function(path) opened[path]=true end,
 launchOrFocusByBundleID=function() end},
 screen={find=function() return {frame=function() return {} end} end},
 timer={doAfter=function() end}, alert={show=function() end},
 hotkey={disableAll=function() end,bind=function() end}}
local m=dofile(arg[1]); assert(m.apply("editing"))
assert(not activated.Codex, "Codex must never stand in for ChatGPT")
if arg[2]=="yes" then assert(activated.ChatGPT) else assert(opened["/Applications/ChatGPT.app"]) end
''')
    result = subprocess.run([lua, str(scenario), str(module), 'yes' if chat_running else 'no'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
