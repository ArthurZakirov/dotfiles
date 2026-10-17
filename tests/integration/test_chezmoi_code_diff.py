"""Exercise the VS Code diff adapter without opening real GUI windows."""

import os
from pathlib import Path
import subprocess
import time

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_chezmoi-code-diff"


@pytest.fixture
def code_stub(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    code = bin_dir / "code"
    code.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$CODE_ARGS"\n'
        'test -f "$3" && test -f "$4" && test -d "$5"\n'
    )
    code.chmod(0o755)
    return {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "CODE_ARGS": str(tmp_path / "arguments"),
        "CHEZMOI_CODE_DIFF_CACHE": str(tmp_path / "snapshot-cache"),
        "CHEZMOI_CODE_DIFF_WORKSPACE": str(tmp_path),
        "CHEZMOI_CODE_DIFF_SETTLE_SECONDS": "0",
    }


def recorded_args(env: dict[str, str]) -> list[str]:
    output = Path(env["CODE_ARGS"])
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if output.exists() and output.stat().st_size:
            return output.read_text().splitlines()
        time.sleep(0.025)
    raise AssertionError(f"Editor CLI not invoked: {output}")


def diff_args(env: dict[str, str]) -> list[Path]:
    args = recorded_args(env)
    assert args[:2] == ["--reuse-window", "--diff"]
    assert Path(args[4]) == Path(env["CHEZMOI_CODE_DIFF_WORKSPACE"])
    return [Path(path) for path in args[2:4]]


def test_added_file_remains_readable_after_diff_process_exits(tmp_path, code_stub):
    target = tmp_path / "new-file"
    target.write_text("managed\n")

    subprocess.run(
        ["/bin/bash", str(SCRIPT), "/dev/null", str(target)],
        env=code_stub, check=True,
    )
    original, managed = diff_args(code_stub)

    assert original.is_file() and original.read_text() == ""
    assert managed.is_file() and managed.read_text() == "managed\n"
    assert original.parent.parent == managed.parent.parent
    assert original.parent.parent.parent == Path(code_stub["CHEZMOI_CODE_DIFF_CACHE"])


def test_default_workspace_is_repository_root_not_nested_chezmoi_source(
    tmp_path, code_stub,
):
    repo = tmp_path / "dotfiles"
    source = repo / "home"
    source.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    fake_chezmoi = Path(code_stub["PATH"].split(os.pathsep)[0]) / "chezmoi"
    fake_chezmoi.write_text(
        '#!/bin/sh\n'
        'test "$1" = source-path || exit 2\n'
        f'printf "%s\\n" "{source}"\n'
    )
    fake_chezmoi.chmod(0o755)
    env = dict(code_stub)
    del env["CHEZMOI_CODE_DIFF_WORKSPACE"]
    new_file = tmp_path / "new-file"
    new_file.write_text("managed content")

    subprocess.run(
        ["/bin/bash", str(SCRIPT), "/dev/null", str(new_file)],
        env=env, check=True,
    )

    args = recorded_args(env)
    assert args[:2] == ["--reuse-window", "--diff"]
    assert Path(args[4]) == repo
    assert Path(args[4]) != source


def test_explicit_workspace_works_in_arbitrary_non_git_checkout(tmp_path, code_stub):
    """The generated config, not an unrelated default checkout, owns the tab."""
    workspace = tmp_path / "clones and worktrees" / "portable chezmoi checkout"
    workspace.mkdir(parents=True)
    source = tmp_path / "managed"
    source.write_text("expected\n")
    env = dict(code_stub)
    del env["CHEZMOI_CODE_DIFF_WORKSPACE"]
    subprocess.run(
        ["/bin/bash", str(SCRIPT), str(workspace), "/dev/null", str(source)],
        env=env, check=True,
    )
    args = recorded_args(env)
    assert args[-1] == str(workspace)
    assert Path(args[-2]).read_text() == "expected\n"


def test_configured_chezmoi_diff_targets_its_own_checkout(tmp_path, code_stub):
    """A full chezmoi diff uses its configured workspace even outside git."""
    checkout = tmp_path / "unrelated clone with spaces"
    source = checkout / "home"
    source.mkdir(parents=True)
    (source / "dot_example").write_text("expected new content\n")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / ".example").write_text("previous local content\n")
    config = tmp_path / "config.toml"
    config.write_text('[diff]\ncommand = "/bin/bash"\n'
                      f'args = ["{SCRIPT}", "{checkout}"]\n')
    env = dict(code_stub)
    del env["CHEZMOI_CODE_DIFF_WORKSPACE"]
    result = subprocess.run([
        "chezmoi", "--source", str(source), "--destination", str(destination),
        "--working-tree", str(checkout), "--config", str(config), "diff",
    ], env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    args = recorded_args(env)
    assert args[-1] == str(checkout)
    assert Path(args[3]).read_text() == "expected new content\n"
    assert (destination / ".example").read_text() == "previous local content\n"


def test_missing_code_cli_shows_readable_text_diff_without_gui(tmp_path):
    """A fresh Mac can preview dotfiles before VS Code is installed."""
    before = tmp_path / "old"
    after = tmp_path / "new"
    before.write_text("existing\n")
    after.write_text("managed\n")
    env = {**os.environ,
           "HOME": str(tmp_path),
           "PATH": "/usr/bin:/bin",
           "CHEZMOI_CODE_DIFF_CACHE": str(tmp_path / "cache")}
    result = subprocess.run(
        ["/bin/bash", str(SCRIPT), str(tmp_path), str(before), str(after)],
        env=env, capture_output=True, text=True, timeout=12,
    )
    assert result.returncode == 0, result.stderr
    assert "-existing" in result.stdout
    assert "+managed" in result.stdout
    assert "VS Code CLI missing" in result.stderr


def test_existing_files_are_snapshotted_before_launching_editor(tmp_path, code_stub):
    source = tmp_path / "before"
    target = tmp_path / "after"
    source.write_text("old\n")
    target.write_text("new\n")

    subprocess.run(
        ["/bin/bash", str(SCRIPT), str(source), str(target)],
        env=code_stub, check=True,
    )
    original, managed = diff_args(code_stub)
    source.unlink()
    target.unlink()

    assert original.read_text() == "old\n"
    assert managed.read_text() == "new\n"


@pytest.mark.parametrize("broken", [False, True], ids=["valid-link", "dangling-link"])
def test_existing_hammerspoon_symlink_is_rendered_as_a_document(tmp_path, code_stub, broken):
    old_root = tmp_path / "old-config"
    old_root.mkdir()
    bin_target = old_root / "bin"
    if not broken:
        bin_target.mkdir()
        (bin_target / "mic_level").write_text("old")
    install = tmp_path / ".hammerspoon"
    install.mkdir()
    link = install / "bin"
    link.symlink_to(bin_target, target_is_directory=True)

    subprocess.run(
        ["/bin/bash", str(SCRIPT), str(link), "/dev/null"],
        env=code_stub, check=True,
    )
    original, empty = diff_args(code_stub)
    link.unlink()

    assert original.read_text() == f"Symbolic link -> {bin_target}\n"
    assert empty.read_text() == ""


def test_directory_difference_is_not_opened_in_file_editor(tmp_path, code_stub):
    directory = tmp_path / "generated"
    directory.mkdir()
    (directory / "child").write_text("content")

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT), "/dev/null", str(directory)],
        env=code_stub, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "content" in result.stdout
    assert not Path(code_stub["CODE_ARGS"]).exists()



def test_real_chezmoi_diff_keeps_hammerspoon_upgrade_documents_available(
    tmp_path, code_stub,
):
    """Real chezmoi diff must leave editor-readable snapshots after exiting."""
    import shutil

    root = SCRIPT.parents[3]
    # Record every editor invocation: chezmoi diff compares multiple files.
    code = Path(code_stub["PATH"].split(os.pathsep)[0]) / "code"
    code.write_text(
        '#!/bin/sh\ntest "$1" = --reuse-window && test "$2" = --diff || exit 2\n'
        'printf "%s\\t%s\\n" "$3" "$4" >> "$CODE_ARGS"\n'
        'test -f "$3" && test -f "$4" && test -d "$5"\n'
    )
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(root / "home/dot_hammerspoon", source / "dot_hammerspoon")
    home = tmp_path / "home"
    home.mkdir()
    existing = home / ".hammerspoon"
    existing.mkdir()
    old_setup = tmp_path / "other-hammerspoon-configuration"
    old_setup.mkdir()
    old_bin = old_setup / "bin"
    old_bin.mkdir()
    (old_bin / "mic_level").write_text("old bin content")
    (existing / "bin").symlink_to(old_bin, target_is_directory=True)
    old_modules = old_setup / "modules"
    old_modules.mkdir()
    (old_modules / "spaces.lua").write_text("-- previous space behavior\n")
    (old_modules / "chatgpt.lua").write_text("-- previous chatgpt behavior\n")
    (existing / "modules").symlink_to(old_modules, target_is_directory=True)
    config = tmp_path / "chezmoi.toml"
    config.write_text(
        '[diff]\ncommand = "/bin/bash"\n'
        f'args = ["{SCRIPT}"]\n'
    )

    command = [
        "chezmoi", "--source", str(source), "--destination", str(home),
        "--config", str(config), "diff", "--recursive", str(existing),
    ]
    result = subprocess.run(
        command, env=code_stub, capture_output=True, text=True, timeout=35,
    )

    assert result.returncode == 0, result.stderr
    recorded = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        recorded = Path(code_stub["CODE_ARGS"]).read_text().splitlines() if Path(code_stub["CODE_ARGS"]).exists() else []
        if any("window_picker.lua" in line for line in recorded):
            break
        time.sleep(0.05)
    pairs = [tuple(map(Path, line.split("\t"))) for line in recorded]
    assert len(pairs) >= 2
    assert all(before.is_file() and after.is_file() for before, after in pairs)
    assert any(
        before.read_text() == f"Symbolic link -> {old_bin}\n"
        and after.read_text() == ""
        for before, after in pairs
    )
    assert any(after.name == "mic_level" for _, after in pairs)
    for name, previous in (
        ("spaces.lua", "-- previous space behavior\n"),
        ("chatgpt.lua", "-- previous chatgpt behavior\n"),
    ):
        assert any(
            before.read_text() == previous
            and after.read_text() == (root / "home/dot_hammerspoon/modules" / name).read_text()
            for before, after in pairs
        )
    assert (existing / "bin").is_symlink()
    assert (existing / "modules").is_symlink()
    assert (old_bin / "mic_level").read_text() == "old bin content"


def test_editor_dispatch_finishes_before_adapter_returns_and_errors_propagate(
    tmp_path, code_stub,
):
    """A backgrounded CLI silently loses tabs and hides launch failures."""
    code = Path(code_stub["PATH"].split(os.pathsep)[0]) / "code"
    target = tmp_path / "modified.lua"
    target.write_text("changed\n")
    code.write_text(
        '#!/bin/sh\nsleep 0.2\nprintf "done\\n" > "$CODE_ARGS"\n'
    )
    code.chmod(0o755)

    started = time.monotonic()
    subprocess.run(
        ["/bin/bash", str(SCRIPT), "/dev/null", str(target)],
        env=code_stub, check=True,
    )
    assert time.monotonic() - started >= 0.18
    assert Path(code_stub["CODE_ARGS"]).read_text() == "done\n"

    code.write_text("#!/bin/sh\nexit 47\n")
    failed = subprocess.run(
        ["/bin/bash", str(SCRIPT), "/dev/null", str(target)],
        env=code_stub, capture_output=True, text=True,
    )
    assert failed.returncode == 47
