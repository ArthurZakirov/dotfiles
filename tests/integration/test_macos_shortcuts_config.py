"""Native keyboard shortcut setup is distributed to both macOS profiles."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only chezmoi hook and script")
@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_managed_shortcuts_are_available_to_each_profile(profile, profile_factory):
    # Arrange
    rendered = profile_factory.render(profile)

    # Act
    installed = profile_factory.chezmoi(rendered.config, "managed", "--include", "files")

    # Assert
    assert ".config/macos-shortcuts/shortcuts.json" in installed
    assert "30-apply-macos-shortcuts.sh" in profile_factory.chezmoi(
        rendered.config, "managed", "--include", "scripts"
    )
    assert "hooks.diff.post" in rendered.config.read_text()
    assert "src/macos_shortcuts.py" in rendered.config.read_text()


def test_native_shortcuts_profile_matches_export_schema():
    # Arrange
    source = ROOT / "home/dot_config/macos-shortcuts/shortcuts.json"

    # Act
    profile = json.loads(source.read_text())

    # Assert
    assert profile["version"] == 1
    assert profile["system_hotkeys"]
    assert profile["app_shortcuts"]["com.openai.codex"]["New Window"] == "@$n"
    assert profile["service_shortcuts"]
    assert profile["accessibility_hotkeys"]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS defaults command")
def test_macos_defaults_import_preserves_native_hotkey_types_and_other_settings(tmp_path):
    """Real macOS defaults commands, isolated to disposable preference plists."""
    import plistlib
    import subprocess

    domain = tmp_path / "sample.plist"
    source = tmp_path / "merged.plist"
    subprocess.run(["defaults", "write", str(domain), "OtherPreference", "-int", "37"],
                   check=True, capture_output=True)
    exported = subprocess.run(["defaults", "export", str(domain), "-"],
                              check=True, capture_output=True).stdout
    prefs = plistlib.loads(exported)
    prefs["AppleSymbolicHotKeys"] = {
        "15": {"enabled": True, "value": {"type": "standard", "parameters": [56, 28, 1572864]}},
        "164": {"enabled": True, "value": {
            "type": "modifier", "parameters": [262144, 18446744073709289471]}},
    }
    source.write_bytes(plistlib.dumps(prefs))

    subprocess.run(["defaults", "import", str(domain), str(source)],
                   check=True, capture_output=True)
    restored = plistlib.loads(subprocess.run(
        ["defaults", "export", str(domain), "-"],
        check=True, capture_output=True,
    ).stdout)

    assert restored == prefs
    assert type(restored["AppleSymbolicHotKeys"]["15"]["enabled"]) is bool
    assert type(restored["AppleSymbolicHotKeys"]["15"]["value"]["parameters"][0]) is int
    assert restored["OtherPreference"] == 37


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS chezmoi configuration")
@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_chezmoi_diff_and_apply_synchronize_live_shortcuts(
    profile, profile_factory, tmp_path,
):
    """Run the actual chezmoi commands with fake preferences and a fake VS Code."""
    import os
    import plistlib
    import subprocess

    # Arrange: the source state and temporary macOS preferences disagree only on ChatGPT.
    rendered = profile_factory.render(profile)
    desired = json.loads((ROOT / "home/dot_config/macos-shortcuts/shortcuts.json").read_text())
    domain_dir = tmp_path / "domains"
    domain_dir.mkdir()
    prefs = {
        "com.apple.symbolichotkeys": {
            "AppleSymbolicHotKeys": {
                key: {field: value for field, value in entry.items() if field != "action"}
                for key, entry in desired["system_hotkeys"].items()
            }
        },
        "com.apple.universalaccess": {
            "com.apple.custommenu.apps": list(desired["app_shortcuts"]),
            "UserAssignableHotKeys": [
                {field: value for field, value in entry.items() if field != "action"}
                for entry in desired["accessibility_hotkeys"]
            ],
        },
        "pbs": {"NSServicesStatus": {
            name: {"key_equivalent": shortcut, "enabled_services_menu": 1}
            for name, shortcut in desired["service_shortcuts"].items()
        }},
    }
    for domain, shortcuts in desired["app_shortcuts"].items():
        prefs[domain] = {"NSUserKeyEquivalents": dict(shortcuts)}
    prefs["com.openai.codex"]["NSUserKeyEquivalents"]["New Window"] = "@~n"
    system_id = "64"
    prefs["com.apple.symbolichotkeys"]["AppleSymbolicHotKeys"][system_id] = {
        **desired["system_hotkeys"][system_id],
        "enabled": not desired["system_hotkeys"][system_id]["enabled"],
    }
    prefs["com.apple.symbolichotkeys"]["AppleSymbolicHotKeys"][system_id].pop("action")
    # A legacy exported preference on the source Mac stored input-source values as strings.
    prefs["com.apple.symbolichotkeys"]["AppleSymbolicHotKeys"]["61"] = {
        "enabled": "1",
        "value": {"type": "standard", "parameters": ["32", "49", "786432"]},
    }
    # The live plist also uses a Boolean where the managed shortcut expects integer 0.
    nested_id = "179"
    nested = prefs["com.apple.symbolichotkeys"]["AppleSymbolicHotKeys"][nested_id]
    assert nested["value"]["parameters"][2] == 0
    nested["value"]["parameters"][2] = False
    for name, content in prefs.items():
        (domain_dir / f"{name}.plist").write_bytes(plistlib.dumps(content))
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    fake_defaults = fake_bin / "defaults"
    fake_defaults.write_text("""#!/usr/bin/env python3
import os, plistlib, pathlib, sys
domain = pathlib.Path(os.environ["FAKE_PREF_DIR"]) / (sys.argv[2] + ".plist")
action = sys.argv[1]
if action == "export":
    if not domain.exists():
        print("The domain/default pair does not exist", file=sys.stderr)
        sys.exit(1)
    sys.stdout.buffer.write(plistlib.dumps(plistlib.loads(domain.read_bytes())))
elif action == "import":
    domain.write_bytes(pathlib.Path(sys.argv[3]).read_bytes())
elif action == "write":
    data = plistlib.loads(domain.read_bytes()) if domain.exists() else {}
    field, mode = sys.argv[3:5]
    if mode == "-dict-add":
        data.setdefault(field, {})[sys.argv[5]] = sys.argv[6]
    elif mode == "-array-add":
        data.setdefault(field, []).append(sys.argv[5])
    else:
        sys.exit("Unsupported mock operation " + str(sys.argv))
    domain.write_bytes(plistlib.dumps(data))
else:
    sys.exit("Unsupported mock operation " + str(sys.argv))
""")
    fake_defaults.chmod(0o755)

    log = tmp_path / "code-calls.jsonl"
    fake_code = fake_bin / "code"
    fake_code.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
result = {"args": args}
if "--diff" in args:
    result["original"] = pathlib.Path(args[-2]).read_text()
    result["target"] = pathlib.Path(args[-1]).read_text()
with open(os.environ["FAKE_CODE_LOG"], "a") as stream:
    stream.write(json.dumps(result) + "\\n")
""")
    fake_code.chmod(0o755)
    logging_code = fake_code.read_text()
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_PREF_DIR": str(domain_dir),
        "FAKE_CODE_LOG": str(log),
        "MACOS_SHORTCUTS_TEST_LOGIN_HOME": str(home),
        "DOTFILES_SKIP_OPTIONAL_APPS": "1",
    }

    def chezmoi(*args):
        return subprocess.run([
            "chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
            "--destination", str(home), *args,
        ], check=True, capture_output=True, text=True, env=env, timeout=50)

    # Establish an up-to-date file tree: native preference drift is the only difference.
    chezmoi("apply", "--exclude", "scripts", "--force")

    # Act: stock chezmoi diff invokes its post-hook with no file changes to show.
    chezmoi("diff")

    # Assert: VS Code receives one diff of live vs desired Shortcut JSON.
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == 1
    assert calls[0]["args"][:2] == ["--wait", "--diff"]
    assert json.loads(calls[0]["original"])["app_shortcuts"]["com.openai.codex"]["New Window"] == "@~n"
    assert json.loads(calls[0]["target"])["app_shortcuts"]["com.openai.codex"]["New Window"] == "@$n"
    left_system = json.loads(calls[0]["original"])["system_hotkeys"]
    right_system = json.loads(calls[0]["target"])["system_hotkeys"]
    assert left_system[system_id]["action"] == "Spotlight: show search"
    assert right_system[system_id]["action"] == "Spotlight: show search"
    assert left_system[system_id]["enabled"] != right_system[system_id]["enabled"]

    # Act: a failed VS Code CLI still permits the builtin, non-GUI chezmoi diff.
    fake_code.write_text("#!/bin/sh\nexit 127\n")
    fallback = chezmoi("--use-builtin-diff", "diff", "--exclude", "scripts")
    assert '--- macOS shortcuts (current)' in fallback.stdout
    assert '+++ macOS shortcuts (managed)' in fallback.stdout
    assert '"New Window": "@~n"' in fallback.stdout
    assert '"New Window": "@$n"' in fallback.stdout
    assert 'showing text diff' in fallback.stderr

    # Act: chezmoi dry-run leaves the preferences intact; ordinary apply executes the run_after script.
    source_hook = ROOT / "home/run_after_30-apply-macos-shortcuts.sh.tmpl"
    chezmoi("apply", "--dry-run", "--source-path", str(source_hook))
    assert plistlib.loads((domain_dir / "com.openai.codex.plist").read_bytes())[
        "NSUserKeyEquivalents"]["New Window"] == "@~n"
    chezmoi("apply", "--source-path", str(source_hook))

    # Assert: the preferences match the desired state, with no VS Code diff on the next run.
    actual = plistlib.loads((domain_dir / "com.openai.codex.plist").read_bytes())
    assert actual["NSUserKeyEquivalents"]["New Window"] == "@$n"
    actual_system = plistlib.loads(
        (domain_dir / "com.apple.symbolichotkeys.plist").read_bytes()
    )["AppleSymbolicHotKeys"][system_id]
    assert actual_system["enabled"] == desired["system_hotkeys"][system_id]["enabled"]
    assert "action" not in actual_system
    input_source = plistlib.loads(
        (domain_dir / "com.apple.symbolichotkeys.plist").read_bytes()
    )["AppleSymbolicHotKeys"]["61"]
    assert input_source["enabled"] is True
    assert input_source["value"]["parameters"] == [32, 49, 786432]
    assert all(type(n) is int for n in input_source["value"]["parameters"])
    nested_after = plistlib.loads(
        (domain_dir / "com.apple.symbolichotkeys.plist").read_bytes()
    )["AppleSymbolicHotKeys"][nested_id]["value"]["parameters"][2]
    assert type(nested_after) is int and nested_after == 0
    # The final diff must use the logging editor again, so a leftover drift
    # cannot silently fall back to text while the log stays unchanged.
    fake_code.write_text(logging_code)
    chezmoi("diff")
    assert len(log.read_text().splitlines()) == 1
