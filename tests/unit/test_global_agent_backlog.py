"""Contract tests for the Mac-wide Backlog.md wrapper and launchd integration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "home/dot_local/bin/executable_agent-backlog"
LAUNCH_AGENT = ROOT / "home/private_Library/private_LaunchAgents/com.arthur.agent-backlog.plist.tmpl"


def test_agent_backlog_uses_one_non_git_store_from_different_cwds(tmp_path: Path) -> None:
    # Arrange: a real shell entrypoint with a fake Backlog.md dependency.
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    fake_backlog = executable_dir / "backlog"
    fake_backlog.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"$1\" == init ]]; then\n"
        "  mkdir -p backlog\n"
        "  echo 'filesystem_only: true' > backlog/config.yml\n"
        "  echo init >> \"$TEST_CALLS\"\n"
        "else\n"
        "  printf '%s\\n' \"$PWD\"\n"
        "fi\n"
    )
    fake_backlog.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    store = home / ".local/share/agent-backlog"
    calls = tmp_path / "calls"
    env = {
        **os.environ,
        "HOME": str(home),
        "AGENT_BACKLOG_DIR": str(store),
        "TEST_CALLS": str(calls),
        "PATH": f"{executable_dir}:{os.environ['PATH']}",
    }
    cwd_a = tmp_path / "a"
    cwd_b = tmp_path / "b"
    cwd_a.mkdir()
    cwd_b.mkdir()

    # Act: use exactly the same wrapper from two unrelated working directories.
    first = subprocess.run(["bash", str(WRAPPER), "task", "list"], cwd=cwd_a, env=env, text=True, capture_output=True, check=True)
    second = subprocess.run(["bash", str(WRAPPER), "task", "list"], cwd=cwd_b, env=env, text=True, capture_output=True, check=True)

    # Assert: a single filesystem-only backlog, initialized once.
    assert first.stdout.strip() == second.stdout.strip() == str(store)
    assert calls.read_text().splitlines() == ["init"]
    assert (store / "backlog/config.yml").is_file()
    assert not (store / ".git").exists()
    assert not (cwd_a / "backlog").exists()
    assert not (cwd_b / "backlog").exists()


def test_launch_agent_uses_clean_environment_and_stable_port() -> None:
    # The provider template syntax is inside element text and remains valid XML.
    root = ET.parse(LAUNCH_AGENT).getroot()
    # Inspect the plist dictionary directly; xml.etree supports only a subset of XPath.
    entries = root.find("dict")
    assert entries is not None
    children = list(entries)
    index = next(i for i, elem in enumerate(children) if elem.tag == "key" and elem.text == "ProgramArguments")
    args = [elem.text for elem in list(children[index + 1])]
    assert args[0:2] == ["/usr/bin/env", "-i"]
    assert "browser" in args and "6420" in args and "--no-open" in args
    assert all("LANGSMITH" not in (value or "") for value in args)


def test_hammerspoon_board_pins_preferred_display_and_scopes_search_hotkey() -> None:
    # Assert the macOS WebView integration preserves the two user-facing contracts.
    source = (ROOT / "home/dot_hammerspoon/modules/agent_backlog.lua").read_text()
    assert 'PREFERRED_MONITOR = "DELL U3225QE"' in source
    assert "hs.screen.find(PREFERRED_MONITOR) or hs.screen.mainScreen()" in source
    assert "board:frame(rect)" in source
    assert "window:moveToScreen(screen, false, true, 0)" in source
    assert ":allowTextEntry(true)" in source
    assert 'hs.hotkey.new({ "cmd" }, "k", focusSearch)' in source
    assert 'action == "focusChange"' in source
    assert "searchHotkey:enable()" in source
    assert "searchHotkey:disable()" in source


def test_hammerspoon_escape_closes_only_the_focused_backlog_window() -> None:
    # Esc must be active only while the WebView has focus, not globally.
    source = (ROOT / "home/dot_hammerspoon/modules/agent_backlog.lua").read_text()
    assert 'hs.hotkey.new({}, "escape", hideBoard)' in source
    assert "closeHotkey:enable()" in source
    assert "closeHotkey:disable()" in source
    assert 'action == "focusChange"' in source
    assert "hideBoard()" in source
    assert "close = hideBoard" in source


def test_shared_workflow_columns_preserve_tasks_across_repeated_apply(tmp_path: Path) -> None:
    # Arrange: simulate an existing central Backlog.md board with a task.
    home = tmp_path / "home"
    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True)
    cli = bin_dir / "agent-backlog"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    root = home / ".local/share/agent-backlog/backlog"
    tasks = root / "tasks"
    tasks.mkdir(parents=True)
    task = tasks / "agent-1 - Existing-task.md"
    task.write_text("---\nid: AGENT-1\nstatus: In Progress\n---\n")
    config = root / "config.yml"
    config.write_text(
        'project_name: "Mac Agent Work"\n'
        'statuses: ["To Do", "In Progress", "Done"]\n'
        'labels: []\n'
        'filesystem_only: true\n'
    )
    script = ROOT / "home/run_after_55-configure-agent-backlog-statuses.sh"
    environment = {**os.environ, "HOME": str(home)}

    # Act: first application and repeat are intentionally idempotent.
    subprocess.run(["bash", str(script)], env=environment, check=True, capture_output=True, text=True)
    first = config.read_text()
    subprocess.run(["bash", str(script)], env=environment, check=True, capture_output=True, text=True)

    # Assert: names are concise and consistent, and task data is untouched.
    assert first == config.read_text()
    assert 'statuses: ["To Do", "In Progress", "Pushed", "PR", "Merged", "STG", "PRD", "Done"]' in first
    assert 'labels: ["✅ Reviewed", "✅ Behavior tested"]' in first
    assert 'filesystem_only: true' in first
    assert task.read_text() == "---\nid: AGENT-1\nstatus: In Progress\n---\n"

    # User-defined label vocabulary survives future chezmoi applies.
    config.write_text(first.replace(
        'labels: ["✅ Reviewed", "✅ Behavior tested"]',
        'labels: ["custom:important", "✅ Reviewed", "✅ Behavior tested"]',
    ))
    subprocess.run(["bash", str(script)], env=environment, check=True, capture_output=True, text=True)
    assert 'labels: ["custom:important", "✅ Reviewed", "✅ Behavior tested"]' in config.read_text()
    assert task.read_text() == "---\nid: AGENT-1\nstatus: In Progress\n---\n"

@pytest.mark.parametrize(
    "config_relative",
    ["backlog/config.yml", ".backlog/config.yml", "backlog.config.yml"],
    ids=["standard", "hidden-backlog", "root-with-custom-directory"],
)
@pytest.mark.parametrize("item_indent", ["  ", ""], ids=["indented-yaml-items", "indentless-yaml-items"])
def test_backlog_workflow_updater_resolves_active_config_without_touching_tasks(
    tmp_path: Path, config_relative: str, item_indent: str
) -> None:
    # Arrange: alternate valid project layouts and an existing task payload.
    home = tmp_path / "home"
    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True)
    cli = bin_dir / "agent-backlog"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    board = home / ".local/share/agent-backlog"
    config = board / config_relative
    config.parent.mkdir(parents=True)
    config.write_text(
        "project_name: alternate layout\n"
        "backlog_directory: custom-backlog\n"
        "statuses:\n"
        f"{item_indent}- To Do\n"
        f"{item_indent}- In Progress\n"
        f"{item_indent}- Done\n"
        "labels:\n"
        f"{item_indent}- 'custom:urgent'\n"
        f"{item_indent}- '✅ Reviewed'\n"
        "filesystem_only: true\n"
        "custom_settings:\n"
        "  nested: keep-me\n"
    )
    task = board / "custom-backlog/tasks/agent-1 - Existing.md"
    task.parent.mkdir(parents=True)
    task.write_text("---\nid: AGENT-1\nstatus: In Progress\n---\n")
    fallback = board / "backlog/config.yml"
    if config_relative == "backlog.config.yml":
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text("statuses: [not-the-active-config]\n")
    env = {**os.environ, "HOME": str(home)}
    script = ROOT / "home/run_after_55-configure-agent-backlog-statuses.sh"

    # Act: run the actual chezmoi-managed updater twice.
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True, text=True)
    first = config.read_text()
    subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True, text=True)

    # Assert: YAML remains valid; user data and unrelated config are preserved.
    parsed = yaml.safe_load(first)
    assert parsed["statuses"] == ["To Do", "In Progress", "Pushed", "PR", "Merged", "STG", "PRD", "Done"]
    assert parsed["labels"] == ["custom:urgent", "✅ Reviewed", "✅ Behavior tested"]
    assert parsed["custom_settings"] == {"nested": "keep-me"}
    assert parsed["backlog_directory"] == "custom-backlog"
    assert config.read_text() == first
    assert task.read_text() == "---\nid: AGENT-1\nstatus: In Progress\n---\n"
    if config_relative == "backlog.config.yml":
        assert fallback.read_text() == "statuses: [not-the-active-config]\n"


def test_backlog_workflow_updater_can_add_optional_missing_yaml_sequences(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True)
    cli = bin_dir / "agent-backlog"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    config = home / ".local/share/agent-backlog/backlog.config.yml"
    config.parent.mkdir(parents=True)
    config.write_text("project_name: minimal\nfilesystem_only: true\n")
    script = ROOT / "home/run_after_55-configure-agent-backlog-statuses.sh"

    subprocess.run(
        ["bash", str(script)], env={**os.environ, "HOME": str(home)},
        check=True, capture_output=True, text=True
    )

    parsed = yaml.safe_load(config.read_text())
    assert parsed["project_name"] == "minimal"
    assert len(parsed["statuses"]) == 8
    assert parsed["labels"] == ["✅ Reviewed", "✅ Behavior tested"]
