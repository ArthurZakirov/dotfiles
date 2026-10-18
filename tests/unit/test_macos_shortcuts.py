"""Portable macOS shortcut configuration, exercised at the CLI and preferences boundary."""

import copy
import json
import plistlib
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "src/macos_shortcuts.py"
loader = SourceFileLoader("macos_shortcuts", str(SCRIPT))
spec = spec_from_loader(loader.name, loader)
shortcuts = module_from_spec(spec)
loader.exec_module(shortcuts)


@pytest.fixture
def example_profile():
    return {
        "version": 1,
        "system_hotkeys": {
            "15": {"enabled": True, "value": {"type": "standard", "parameters": [56, 28, 1572864]}},
            "16": {"enabled": False},
            "164": {"enabled": True, "value": {"type": "modifier", "parameters": [262144, 18446744073709289471]}},
        },
        "app_shortcuts": {"com.openai.codex": {"New Window": "@$n"}},
        "service_shortcuts": {"service-id": "~$g"},
        "accessibility_hotkeys": [{"enabled": True, "key": 120, "modifier": 8650752, "sybmolichotkey": 7}],
    }


def test_snapshot_includes_registered_and_unregistered_apps_without_other_preferences(
    tmp_path, monkeypatch,
):
    # Arrange
    (tmp_path / "com.example.unregistered.plist").write_bytes(
        plistlib.dumps({"NSUserKeyEquivalents": {"Test": "@t"}, "PrivateToken": "do-not-export"})
    )
    prefs = {
        "com.apple.symbolichotkeys": {"AppleSymbolicHotKeys": {"15": {"enabled": False}}},
        "com.apple.universalaccess": {
            "com.apple.custommenu.apps": ["com.openai.codex"],
            "UserAssignableHotKeys": [],
        },
        "pbs": {"NSServicesStatus": {
            "service-id": {"key_equivalent": "~$g", "enabled_context_menu": 1},
            "other": {"enabled_context_menu": 1},
        }},
        "com.openai.codex": {"NSUserKeyEquivalents": {"New Window": "@$n"}},
        "com.example.unregistered": {"NSUserKeyEquivalents": {"Test": "@t"}},
    }
    monkeypatch.setattr(shortcuts, "domain_values", lambda domain: prefs.get(domain, {}))

    # Act
    result = shortcuts.snapshot(preferences=tmp_path)

    # Assert
    assert result["app_shortcuts"] == {
        "com.example.unregistered": {"Test": "@t"},
        "com.openai.codex": {"New Window": "@$n"},
    }
    assert result["system_hotkeys"] == {"15": {"enabled": False}}
    assert result["service_shortcuts"] == {"service-id": "~$g"}
    assert "PrivateToken" not in json.dumps(result)


@pytest.mark.parametrize(
    "invalid",
    [
        lambda p: p.update(version=999),
        lambda p: p["system_hotkeys"].update({"oops": {"enabled": False}}),
        lambda p: p["system_hotkeys"].update({"15": {"enabled": True, "value": {"type": "standard", "parameters": [1]}}}),
        lambda p: p["app_shortcuts"].update({"app": {"New Window": 4}}),
        lambda p: p["accessibility_hotkeys"].append({"enabled": True, "key": 99, "modifier": 0, "sybmolichotkey": 7}),
    ],
)
def test_profile_rejects_invalid_configuration(example_profile, invalid):
    # Arrange
    invalid(example_profile)

    # Act / Assert
    with pytest.raises(shortcuts.ShortcutError, match="Invalid shortcut profile"):
        shortcuts.validate(example_profile)


@pytest.mark.parametrize("enabled", [0.0, 1.0])
def test_profile_rejects_floating_point_enabled_flag(example_profile, enabled):
    # Arrange
    example_profile["system_hotkeys"]["15"]["enabled"] = enabled

    # Act / Assert
    with pytest.raises(shortcuts.ShortcutError, match="enabled flag"):
        shortcuts.validate(example_profile)


def test_managed_input_source_shortcut_has_native_preference_types():
    # Arrange
    source = SCRIPT.parent.parent / "home/dot_config/macos-shortcuts/shortcuts.json"
    profile = json.loads(source.read_text())

    # Act
    shortcuts.validate(profile)

    # Assert
    shortcut = profile["system_hotkeys"]["61"]
    assert shortcut["enabled"] is True
    assert shortcut["value"]["parameters"] == [32, 49, 786432]
    assert all(type(value) is int for value in shortcut["value"]["parameters"])


def test_profiles_preserve_native_modifier_and_string_encoded_hotkeys(example_profile):
    # Arrange
    example_profile["system_hotkeys"]["61"] = {
        "enabled": "1", "value": {"type": "standard", "parameters": ["32", "49", "786432"]}
    }

    # Act
    shortcuts.validate(example_profile)

    # Assert
    assert not list(shortcuts.changes(example_profile, copy.deepcopy(example_profile)))


def test_comparison_ignores_unmanaged_shortcuts(example_profile):
    # Arrange
    current = copy.deepcopy(example_profile)
    current["system_hotkeys"]["999"] = {"enabled": True}
    current["app_shortcuts"]["another.app"] = {"New Chat": "@n"}
    current["service_shortcuts"]["another-service"] = "@g"
    current["accessibility_hotkeys"].append({"enabled": False, "key": 0, "modifier": 0, "sybmolichotkey": 8})

    # Act
    differences = list(shortcuts.changes(example_profile, current))

    # Assert
    assert differences == []


def test_comparison_reports_changed_shortcuts(example_profile):
    # Arrange
    current = copy.deepcopy(example_profile)
    current["app_shortcuts"]["com.openai.codex"]["New Window"] = "@~n"
    current["service_shortcuts"]["service-id"] = "~a"
    current["system_hotkeys"]["16"]["enabled"] = True
    current["accessibility_hotkeys"][0]["key"] = 115

    # Act
    differences = list(shortcuts.changes(example_profile, current))

    # Assert
    assert [(kind, key) for kind, key, _ in differences] == [
        ("system", "16"),
        ("app", ("com.openai.codex", "New Window")),
        ("service", "service-id"),
        ("accessibility", 7),
    ]


def test_apply_updates_only_declared_preferences_and_preserves_other_entries(
    example_profile, monkeypatch,
):
    # Arrange
    current = {"version": 1, "system_hotkeys": {}, "app_shortcuts": {},
               "service_shortcuts": {}, "accessibility_hotkeys": [
                   {"enabled": False, "key": 99, "modifier": 0, "sybmolichotkey": 8},
               ]}
    example_profile = shortcuts.with_action_labels(example_profile)
    written = []
    imported = {}
    monkeypatch.setattr(
        shortcuts, "domain_values",
        lambda domain: {
            "com.apple.universalaccess": {"com.apple.custommenu.apps": ["com.apple.finder"],
                                           "UserAssignableHotKeys": current["accessibility_hotkeys"]},
            "pbs": {"NSServicesStatus": {"service-id": {"enabled_services_menu": 1},
                                         "untouched": {"enabled_services_menu": 0}}},
            "com.apple.symbolichotkeys": {"AppleSymbolicHotKeys": {
                "999": {"enabled": False},
            }, "OtherSystemPreference": 23},
        }.get(domain, {}),
    )

    def record(*args):
        written.append(args)
        if args[0] == "import":
            imported[args[1]] = plistlib.loads(Path(args[2]).read_bytes())

    monkeypatch.setattr(shortcuts, "defaults", record)
    pending = list(shortcuts.changes(example_profile, current))

    # Act
    shortcuts.apply(example_profile, pending)

    # Assert
    assert ("write", "com.openai.codex", "NSUserKeyEquivalents",
            "-dict-add", "New Window", "@$n") in written
    assert ("write", "com.apple.universalaccess", "com.apple.custommenu.apps",
            "-array-add", "com.openai.codex") in written
    assert set(imported) == {"com.apple.symbolichotkeys", "pbs", "com.apple.universalaccess"}
    symbolic = imported["com.apple.symbolichotkeys"]
    assert symbolic["OtherSystemPreference"] == 23
    assert symbolic["AppleSymbolicHotKeys"]["999"] == {"enabled": False}
    assert symbolic["AppleSymbolicHotKeys"]["15"]["value"]["parameters"] == [56, 28, 1572864]
    assert symbolic["AppleSymbolicHotKeys"]["164"]["value"]["parameters"][-1] == 18446744073709289471
    services = imported["pbs"]["NSServicesStatus"]
    assert services["service-id"] == {"enabled_services_menu": 1, "key_equivalent": "~$g"}
    assert services["untouched"] == {"enabled_services_menu": 0}
    assert len(imported["com.apple.universalaccess"]["UserAssignableHotKeys"]) == 2


def test_export_and_apply_require_explicit_user_confirmation(
    example_profile, monkeypatch, tmp_path, capsys,
):
    # Arrange
    profile = tmp_path / "shortcuts.json"
    current = copy.deepcopy(example_profile)
    monkeypatch.setattr(shortcuts, "snapshot", lambda: copy.deepcopy(current))
    calls = []
    monkeypatch.setattr(shortcuts, "apply", lambda *args: calls.append(args))

    # Act
    assert shortcuts.main(["export", str(profile)]) == 0
    current["app_shortcuts"]["com.openai.codex"]["New Window"] = "@~n"
    assert shortcuts.main(["diff", str(profile)]) == 0
    assert shortcuts.main(["apply", str(profile)]) == 2

    # Assert
    assert calls == []
    assert profile.exists()
    assert "app: ('com.openai.codex', 'New Window')" in capsys.readouterr().out

    # Act
    assert shortcuts.main(["apply", str(profile), "--yes"]) == 0

    # Assert
    assert len(calls) == 1


def test_native_plist_export_is_type_preserving(example_profile):
    # Arrange
    original = {"AppleSymbolicHotKeys": example_profile["system_hotkeys"]}

    # Act
    restored = plistlib.loads(plistlib.dumps(original))

    # Assert
    assert restored == original



def test_export_accepts_a_quoted_home_path(example_profile, monkeypatch, tmp_path):
    # Arrange: the shell passes a literal tilde within a quoted argument.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(shortcuts.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(shortcuts, "snapshot", lambda: example_profile)

    # Act
    exit_code = shortcuts.main(["export", "~/mac_shortcuts.json"])

    # Assert
    assert exit_code == 0
    assert json.loads((tmp_path / "mac_shortcuts.json").read_text()) == shortcuts.with_action_labels(example_profile)


def test_chezmoi_review_opens_live_vs_managed_in_vscode_only_for_drift(
    example_profile, monkeypatch,
):
    # Arrange
    desired = copy.deepcopy(example_profile)
    current = copy.deepcopy(example_profile)
    current["app_shortcuts"]["com.openai.codex"]["New Window"] = "@~n"
    current["app_shortcuts"]["com.example.other"] = {"Other": "@a"}
    observed = []

    def capture_editor(args, check):
        # Capture the actual editor's input before the temporary files are removed.
        observed.append((
            args,
            json.loads(Path(args[-2]).read_text()),
            json.loads(Path(args[-1]).read_text()),
        ))

    monkeypatch.setattr(shortcuts.subprocess, "run", capture_editor)

    # Act
    assert shortcuts.review(desired, current) == 0

    # Assert
    assert len(observed) == 1
    command, left, right = observed[0]
    assert command[:3] == ["code", "--wait", "--diff"]
    assert left["app_shortcuts"] == {"com.openai.codex": {"New Window": "@~n"}}
    assert right == desired

    # Act: the same desired values on the Mac.
    assert shortcuts.review(desired, desired) == 0

    # Assert
    assert len(observed) == 1


@pytest.mark.parametrize("editor_failure", [FileNotFoundError, subprocess.CalledProcessError])
def test_chezmoi_review_falls_back_to_text_diff_without_editor(
    example_profile, monkeypatch, capsys, editor_failure,
):
    # Arrange
    desired = copy.deepcopy(example_profile)
    current = copy.deepcopy(example_profile)
    current["app_shortcuts"]["com.openai.codex"]["New Window"] = "@~n"

    def unavailable_editor(*args, **kwargs):
        if editor_failure is subprocess.CalledProcessError:
            raise subprocess.CalledProcessError(127, args[0])
        raise FileNotFoundError("code is unavailable")

    monkeypatch.setattr(shortcuts.subprocess, "run", unavailable_editor)

    # Act
    result = shortcuts.review(desired, current)

    # Assert
    stdout, stderr = capsys.readouterr()
    assert result == 0
    assert "--- macOS shortcuts (current)" in stdout
    assert "+++ macOS shortcuts (managed)" in stdout
    assert '"New Window": "@~n"' in stdout
    assert '"New Window": "@$n"' in stdout
    assert "showing text diff" in stderr


def test_chezmoi_review_targets_login_users_home(
    example_profile, monkeypatch, tmp_path,
):
    # Arrange
    profile = tmp_path / "shortcut-config.json"
    profile.write_text(json.dumps(example_profile))
    monkeypatch.setenv("CHEZMOI_DEST_DIR", str(tmp_path / "isolated-home"))
    monkeypatch.setenv("CHEZMOI_HOME_DIR", str(tmp_path / "isolated-home"))
    monkeypatch.delenv("MACOS_SHORTCUTS_TEST_LOGIN_HOME", raising=False)
    monkeypatch.setattr(
        shortcuts.pwd, "getpwuid", lambda _: type("Account", (), {"pw_dir": str(tmp_path / "actual-home")})(),
    )
    monkeypatch.setattr(
        shortcuts, "snapshot",
        lambda: pytest.fail("Preferences read for an unrelated chezmoi destination"),
    )

    # Act
    result = shortcuts.main(["review", str(profile)])

    # Assert
    assert result == 0



def test_action_names_are_present_for_current_mac_shortcut_ids():
    # Arrange
    source = Path(__file__).resolve().parents[2] / "home/dot_config/macos-shortcuts/shortcuts.json"
    profile = json.loads(source.read_text())

    # Act
    shortcuts.validate(profile)

    # Assert: every stored system/accessibility action is described by the curated mapping.
    assert all(
        entry["action"] == shortcuts.SYMBOLIC_ACTIONS[key]
        for key, entry in profile["system_hotkeys"].items()
    )
    assert all(
        entry["action"] == shortcuts.ACCESSIBILITY_ACTIONS[entry["sybmolichotkey"]]
        for entry in profile["accessibility_hotkeys"]
    )
    assert profile["system_hotkeys"]["64"]["action"] == "Spotlight: show search"
    assert profile["system_hotkeys"]["240"]["action"] == "Window: tile left half"


def test_action_descriptions_do_not_trigger_preference_changes(example_profile):
    # Arrange: the native records match, including the enabled state and key bindings.
    labelled = shortcuts.with_action_labels(example_profile)

    # Act
    pending = list(shortcuts.changes(labelled, example_profile))

    # Assert
    assert pending == []


def test_exported_action_descriptions_are_not_written_to_macos_preferences(example_profile):
    # Arrange
    labelled = shortcuts.with_action_labels(example_profile)
    native = {
        "version": 1, "system_hotkeys": {}, "app_shortcuts": {},
        "service_shortcuts": {}, "accessibility_hotkeys": [],
    }

    # Act
    pending = list(shortcuts.changes(labelled, native))

    # Assert: the apply boundary receives only preference-compatible fields.
    assert pending
    assert all("action" not in value for kind, _, value in pending
               if kind in ("system", "accessibility"))


@pytest.mark.parametrize(("id_", "wrong_name"), [
    ("64", "Window: tile left half"),
    ("240", "Spotlight: show search"),
])
def test_rejects_mislabeled_system_action(example_profile, id_, wrong_name):
    # Arrange
    labelled = shortcuts.with_action_labels(example_profile)
    labelled["system_hotkeys"][id_] = {
        "enabled": True, "action": wrong_name
    }

    # Act and Assert
    with pytest.raises(shortcuts.ShortcutError, match="incorrect action label"):
        shortcuts.validate(labelled)



def test_chezmoi_review_accepts_the_real_account_home(monkeypatch, tmp_path):
    # Arrange: the destination is the account home despite a different HOME variable.
    monkeypatch.setenv("CHEZMOI_DEST_DIR", str(tmp_path))
    monkeypatch.setenv("CHEZMOI_HOME_DIR", str(tmp_path / "different-env-home"))
    monkeypatch.delenv("MACOS_SHORTCUTS_TEST_LOGIN_HOME", raising=False)
    monkeypatch.setattr(shortcuts.pwd, "getpwuid",
                        lambda _: type("Account", (), {"pw_dir": str(tmp_path)})())

    # Act / Assert
    assert shortcuts.is_login_home_destination()


def test_chezmoi_review_is_skipped_if_destination_is_missing(monkeypatch):
    # Arrange
    monkeypatch.delenv("CHEZMOI_DEST_DIR", raising=False)
    monkeypatch.delenv("MACOS_SHORTCUTS_TEST_LOGIN_HOME", raising=False)

    # Act / Assert
    assert not shortcuts.is_login_home_destination()



def test_chezmoi_apply_does_not_touch_preferences_in_an_isolated_home(
    example_profile, monkeypatch, tmp_path,
):
    # Arrange: a disposable chezmoi HOME is distinct from the login account home.
    source = tmp_path / "shortcuts.json"
    source.write_text(json.dumps(shortcuts.with_action_labels(example_profile)))
    monkeypatch.setenv("CHEZMOI_DEST_DIR", str(tmp_path / "temporary-home"))
    monkeypatch.setenv("CHEZMOI_HOME_DIR", str(tmp_path / "temporary-home"))
    monkeypatch.delenv("MACOS_SHORTCUTS_TEST_LOGIN_HOME", raising=False)
    monkeypatch.setattr(
        shortcuts.pwd, "getpwuid",
        lambda _: type("Account", (), {"pw_dir": str(tmp_path / "login-home")})(),
    )
    monkeypatch.setattr(
        shortcuts, "snapshot",
        lambda: pytest.fail("Preferences read for a disposable chezmoi home"),
    )

    # Act
    result = shortcuts.main(["apply", str(source), "--yes"])

    # Assert
    assert result == 0
