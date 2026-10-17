"""Exercise the VS Code diff adapter without opening real GUI windows."""

import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_chezmoi-code-diff"


@pytest.fixture
def code_stub(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    code = bin_dir / "code"
    code.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$CODE_ARGS"\n'
        'test -f "$3" && test -f "$4"\n'
    )
    code.chmod(0o755)
    return {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "CODE_ARGS": str(tmp_path / "arguments"),
        "CHEZMOI_CODE_DIFF_CACHE": str(tmp_path / "snapshot-cache"),
    }


def diff_args(env: dict[str, str]) -> list[Path]:
    args = Path(env["CODE_ARGS"]).read_text().splitlines()
    assert args[:2] == ["--wait", "--diff"]
    return [Path(path) for path in args[2:]]


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
        '#!/bin/sh\nprintf "%s\\t%s\\n" "$3" "$4" >> "$CODE_ARGS"\n'
        'test -f "$3" && test -f "$4"\n'
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
    recorded = Path(code_stub["CODE_ARGS"]).read_text().splitlines()
    pairs = [tuple(map(Path, line.split("\t"))) for line in recorded]
    assert len(pairs) >= 2
    assert all(before.is_file() and after.is_file() for before, after in pairs)
    assert any(
        before.read_text() == f"Symbolic link -> {old_bin}\n"
        and after.read_text() == ""
        for before, after in pairs
    )
    assert any(after.name == "mic_level" for _, after in pairs)
    assert (existing / "bin").is_symlink()
    assert (old_bin / "mic_level").read_text() == "old bin content"
