"""Exercise the managed launcher with an isolated Codex session catalog."""

import importlib.machinery
import importlib.util
import shlex
import sys
from pathlib import Path

import pytest

LAUNCHER = (
    Path(__file__).resolve().parents[2]
    / "home/dot_hammerspoon/bin/executable_warp-codex-chats"
)
THREAD = "11111111-2222-4333-8444-555555555555"


SIBLING = "22222222-3333-4444-8555-666666666666"
TREE = "33333333-4444-4555-8666-777777777777"


@pytest.mark.parametrize("fork", [False, True])
def test_same_cli_lists_resumes_and_starts_chats(tmp_path, monkeypatch, fork):
    loader = importlib.machinery.SourceFileLoader("warp_codex_chats", str(LAUNCHER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    launcher = importlib.util.module_from_spec(spec)
    loader.exec_module(launcher)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    bin_dir = tmp_path / ".local/bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / ("codex-voice" if fork else "codex")
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "assert sys.argv[-1] == 'app-server'\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if request.get('id') == 2:\n"
        "        assert request['params']['sortKey'] == 'updated_at'\n"
        f"        chats = [dict(id=thread, sessionId={TREE!r}, cwd=os.getcwd(), name='A chat') for thread in [{THREAD!r}, {SIBLING!r}]]\n"
        "        print(json.dumps(dict(id=2, result=dict(data=chats))), flush=True)\n"
    )
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + str(Path(sys.executable).parent))
    command = [str(executable)]
    if fork:
        config = tmp_path / ".config/warp-codex/command"
        config.parent.mkdir(parents=True)
        config.write_text('codex-voice --profile "Local Voice"\n')
        command.extend(["--profile", "Local Voice"])

    interactive = [
        *command, "-c", "check_for_update_on_startup=false",
        "-c", 'tui.terminal_title=["thread-name"]',
    ]
    opened = []
    monkeypatch.setattr(launcher, "open_tab", lambda *a, **kw: opened.append((a, kw)))
    monkeypatch.setattr(sys, "argv", [str(LAUNCHER)])
    launcher.main()
    assert opened == [
        (("A chat", str(tmp_path), shlex.join([*interactive, "resume", THREAD])),
         {"new_window": True}),
        (("A chat", str(tmp_path), shlex.join([*interactive, "resume", SIBLING])),
         {"new_window": False}),
    ]

    monkeypatch.setattr(sys, "argv", [str(LAUNCHER), "--new"])
    monkeypatch.chdir(bin_dir)
    launcher.main()
    assert opened[-1] == (("Codex", str(tmp_path), shlex.join(interactive)), {})
