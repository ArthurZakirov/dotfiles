"""Both macOS profiles render the same managed, credential-isolated LaunchAgent."""

import plistlib
from pathlib import Path

import pytest


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_managed_launch_agent(profile_factory, profile):
    rendered = profile_factory.render(profile)

    xml = profile_factory.chezmoi(
        rendered.config,
        "cat",
        str(Path.home() / "Library/LaunchAgents/com.arthur.storage-maintenance.plist"),
    )
    agent = plistlib.loads(xml.encode())

    assert agent["Label"] == "com.arthur.storage-maintenance"
    assert agent["StartInterval"] == 86400
    assert agent["RunAtLoad"] is True
    assert agent["ProgramArguments"] == [
        "/usr/bin/env", "-i", f"HOME={Path.home()}", "PATH=/usr/bin:/bin",
        "/usr/bin/python3",
        f"{Path.home()}/.local/share/storage-maintenance/clean_chrome_clones.py",
    ]


def test_installer_syntax():
    import subprocess

    root = Path(__file__).resolve().parents[2]
    for hook in (
        "run_before_02-snapshot-storage-maintenance.sh",
        "run_after_65-ensure-storage-maintenance.sh",
    ):
        subprocess.run(["/bin/sh", "-n", str(root / "home" / hook)], check=True)


# The installer changes a real launchd service. Exercise the hook against a
# fake macOS launchctl boundary rather than restarting any developer services.
def _setup_launchd_fixture(tmp_path, loaded=True):
    import hashlib
    import os
    import subprocess

    home = tmp_path / "home"
    binary = tmp_path / "bin"
    home.mkdir()
    binary.mkdir()
    label = "com.arthur.storage-maintenance"
    plist = home / "Library/LaunchAgents" / f"{label}.plist"
    script = home / ".local/share/storage-maintenance/clean_chrome_clones.py"
    marker = home / "Library/Caches/chezmoi" / f"{label}.sha256"
    plist.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    marker.parent.mkdir(parents=True)
    script.write_text("print('old')\n")
    plist.write_bytes(plistlib.dumps({
        "Label": label, "ProgramArguments": ["/usr/bin/python3", str(script)],
    }))
    original = (plist.read_bytes(), script.read_bytes())
    revision = hashlib.sha256(original[0] + original[1]).hexdigest()
    marker.write_text(revision + "\n")
    loaded_file = tmp_path / "service-loaded"
    if loaded:
        loaded_file.write_text(str(plist))
    fail_next = tmp_path / "bootstrap-fail-once"
    events = tmp_path / "events.log"
    (binary / "uname").write_text("#!/bin/sh\necho Darwin\n")
    (binary / "plutil").write_text(
        '#!/usr/bin/env python3\n'
        'import plistlib,sys\n'
        'with open(sys.argv[-1],"rb") as f: plistlib.load(f)\n'
    )
    (binary / "launchctl").write_text(
        '#!/usr/bin/env python3\n'
        'import os,sys,pathlib,plistlib\n'
        'loaded=pathlib.Path(os.environ["FAKE_LOADED"])\n'
        'fail=pathlib.Path(os.environ["FAKE_FAIL_NEXT"])\n'
        'events=pathlib.Path(os.environ["FAKE_EVENTS"])\n'
        'args=sys.argv[1:]\n'
        'if args[0]=="print":\n'
        '  if args[1].count("/")==1: sys.exit(0)\n'
        '  sys.exit(0 if loaded.exists() else 1)\n'
        'if args[0]=="bootout":\n'
        '  events.open("a").write("bootout\\n")\n'
        '  loaded.unlink()\n'
        '  sys.exit(0)\n'
        'if args[0]=="bootstrap":\n'
        '  target=pathlib.Path(args[2])\n'
        '  with target.open("rb") as f: agent=plistlib.load(f)\n'
        '  assert agent["Label"]=="com.arthur.storage-maintenance"\n'
        '  if fail.exists():\n'
        '    fail.unlink()\n'
        '    events.open("a").write("bootstrap-fail\\n")\n'
        '    sys.exit(5)\n'
        '  loaded.write_text(str(target))\n'
        '  events.open("a").write("bootstrap-ok\\n")\n'
        '  sys.exit(0)\n'
        'sys.exit(2)\n'
    )
    for command in ("uname", "plutil", "launchctl"):
        (binary / command).chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{binary}:{os.environ['PATH']}",
        "FAKE_LOADED": str(loaded_file),
        "FAKE_FAIL_NEXT": str(fail_next),
        "FAKE_EVENTS": str(events),
    }
    hooks = Path(__file__).resolve().parents[2] / "home"
    def invoke(name):
        return subprocess.run(
            ["/bin/sh", str(hooks / name)],
            env=env, capture_output=True, text=True, timeout=15,
        )
    def update_files():
        script.write_text("print('new')\n")
        plist.write_bytes(plistlib.dumps({
            "Label": label,
            "ProgramArguments": ["/usr/bin/python3", str(script), "--updated"],
        }))
    return {
        "invoke": invoke, "update_files": update_files, "plist": plist,
        "script": script, "marker": marker, "old_contents": original,
        "revision": revision, "loaded": loaded_file, "fail_next": fail_next,
        "events": events,
    }


def test_update_failure_restores_previous_loaded_job(tmp_path):
    """A rejected new plist cannot leave a formerly running service disabled."""
    ctx = _setup_launchd_fixture(tmp_path)

    before = ctx["invoke"]("run_before_02-snapshot-storage-maintenance.sh")
    assert before.returncode == 0, before.stderr
    ctx["update_files"]()
    ctx["fail_next"].touch()

    result = ctx["invoke"]("run_after_65-ensure-storage-maintenance.sh")

    assert result.returncode != 0
    assert "previous job restored" in result.stderr
    assert ctx["events"].read_text().splitlines() == [
        "bootout", "bootstrap-fail", "bootstrap-ok",
    ]
    assert ctx["loaded"].exists()
    assert ctx["plist"].read_bytes() == ctx["old_contents"][0]
    assert ctx["script"].read_bytes() == ctx["old_contents"][1]
    assert ctx["marker"].read_text().strip() == ctx["revision"]


def test_update_without_verified_backup_leaves_active_job_untouched(tmp_path):
    ctx = _setup_launchd_fixture(tmp_path)
    ctx["update_files"]()

    result = ctx["invoke"]("run_after_65-ensure-storage-maintenance.sh")

    assert result.returncode != 0
    assert "no recovery snapshot" in result.stderr
    assert ctx["loaded"].exists()
    assert not ctx["events"].exists()


def test_successful_update_reloads_only_once(tmp_path):
    ctx = _setup_launchd_fixture(tmp_path)
    assert ctx["invoke"]("run_before_02-snapshot-storage-maintenance.sh").returncode == 0
    ctx["update_files"]()

    initial = ctx["invoke"]("run_after_65-ensure-storage-maintenance.sh")
    repeated = ctx["invoke"]("run_after_65-ensure-storage-maintenance.sh")

    assert initial.returncode == 0, initial.stderr
    assert repeated.returncode == 0, repeated.stderr
    assert ctx["loaded"].exists()
    assert ctx["events"].read_text().splitlines() == ["bootout", "bootstrap-ok"]


def test_fresh_install_needs_no_previous_backup(tmp_path):
    ctx = _setup_launchd_fixture(tmp_path, loaded=False)
    ctx["update_files"]()

    result = ctx["invoke"]("run_after_65-ensure-storage-maintenance.sh")

    assert result.returncode == 0, result.stderr
    assert ctx["loaded"].exists()
    assert ctx["events"].read_text().splitlines() == ["bootstrap-ok"]
