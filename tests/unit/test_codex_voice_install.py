"""Behavioral tests for the portable Codex Voice installer (no network or Rust build)."""

import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "home/dot_local/bin/executable_codex-voice-install"
)
TARGET = "aarch64-apple-darwin"
TAG = "voice-v0.166.0-r1"


@pytest.fixture
def installer():
    return runpy.run_path(str(SCRIPT))["install"]


def release_fixture(tmp_path: Path, *, tamper=False, traversal=False, missing=None) -> Path:
    package = tmp_path / "package"
    voice = package / "codex-resources/voice"
    (package / "bin").mkdir(parents=True)
    (voice / "bin").mkdir(parents=True)
    (voice / "lib").mkdir(parents=True)
    executable = package / "bin/codex"
    executable.write_text("#!/bin/sh\necho codex-cli 0.166.0\n")
    executable.chmod(0o755)
    helper = voice / "bin/codex-voice-host"
    helper.write_bytes(b"test helper")
    helper.chmod(0o755)
    for relative in ("bin/codex-code-mode-host", "bin/codex-exec-server", "codex-path/rg", "codex-resources/voice/bin/codex-voice-speech-helper"):
        program = package / relative
        program.parent.mkdir(parents=True, exist_ok=True)
        program.write_text("#!/bin/sh\nexit 0\n")
        program.chmod(0o755)
    lib = voice / "lib/libgstreamer-1.0.0.dylib"
    lib.write_bytes(b"test library")
    (package / "codex-package.json").write_text(json.dumps({
        "layoutVersion": 1, "target": TARGET, "entrypoint": "bin/codex",
        "version": "0.166.0",
    }))
    files = {
        path: hashlib.sha256((package / path).read_bytes()).hexdigest()
        for path in (
            "bin/codex",
            "bin/codex-code-mode-host",
            "bin/codex-exec-server",
            "codex-path/rg",
            "codex-resources/voice/bin/codex-voice-speech-helper",
            "codex-resources/voice/bin/codex-voice-host",
            "codex-resources/voice/lib/libgstreamer-1.0.0.dylib",
        )
    }
    (voice / "manifest.json").write_text(json.dumps({
        "buildCommit": "a" * 40, "appTarget": TARGET,
        "voiceTarget": TARGET, "appVersion": "0.166.0",
        "sha256": files,
    }))
    if missing:
        (package / missing).unlink()
    release = tmp_path / "release"
    release.mkdir()
    archive = release / f"codex-voice-{TARGET}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        output.add(package, arcname=".")
        if traversal:
            data = b"should not escape"
            member = tarfile.TarInfo("../escape.txt")
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    if tamper:
        checksum = "0" * 64
    (release / "SHA256SUMS").write_text(f"{checksum}  {archive.name}\n")
    return release


def test_install_places_verified_package_and_receipt(tmp_path, installer):
    # Arrange
    release = release_fixture(tmp_path)
    destination = tmp_path / "installation"

    # Act
    changed = installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    # Assert
    assert changed is True
    assert (destination / "bin/codex").is_file()
    assert (destination / "codex-resources/voice/bin/codex-voice-host").is_file()
    receipt = json.loads((destination / "codex-voice-install.json").read_text())
    assert receipt["tag"] == TAG
    assert receipt["build_commit"] == "a" * 40


def test_existing_verified_installation_is_idempotent(tmp_path, installer):
    # Arrange
    release = release_fixture(tmp_path)
    destination = tmp_path / "installation"
    installer(TAG, destination, base_url=release.as_uri(), target=TARGET)
    (release / "SHA256SUMS").unlink()

    # Act
    changed = installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    # Assert
    assert changed is False
    assert (destination / "bin/codex").exists()


@pytest.mark.parametrize("tamper,traversal,reason", [
    (True, False, "SHA-256 mismatch"),
    (False, True, "Unsafe release archive path"),
])
def test_rejected_release_does_not_replace_previous_installation(
    tmp_path, installer, tamper, traversal, reason
):
    # Arrange
    release = release_fixture(tmp_path, tamper=tamper, traversal=traversal)
    destination = tmp_path / "installation"
    destination.mkdir()
    (destination / "existing.txt").write_text("preserve")

    # Act / Assert
    with pytest.raises(ValueError, match=reason):
        installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    assert (destination / "existing.txt").read_text() == "preserve"
    assert not (tmp_path / "escape.txt").exists()
    assert not (destination / "bin/codex").exists()


@pytest.mark.parametrize("damaged_receipt", [
    "{",
    "null",
    "[]",
    '"unexpected string"',
    "42",
])
def test_damaged_install_receipt_triggers_reinstallation(
    tmp_path, installer, damaged_receipt
):
    # Arrange: keep the installed package but damage only its receipt.
    release = release_fixture(tmp_path)
    destination = tmp_path / "installation"
    installer(TAG, destination, base_url=release.as_uri(), target=TARGET)
    receipt = destination / "codex-voice-install.json"
    receipt.write_text(damaged_receipt)

    # Act: the installer must repair the installation instead of aborting.
    changed = installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    # Assert: the replacement package is valid and the old one is backed up.
    assert changed is True
    assert json.loads(receipt.read_text())["tag"] == TAG
    assert (destination / "bin/codex").is_file()
    backups = list(tmp_path.glob("installation.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "codex-voice-install.json").read_text() == damaged_receipt
    assert installer(TAG, destination, base_url=release.as_uri(), target=TARGET) is False


def test_invalid_version_is_rejected_before_download(tmp_path, installer):
    # Arrange
    destination = tmp_path / "installation"

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid release tag"):
        installer("latest", destination, target=TARGET)

    assert not destination.exists()


def test_tampered_installed_binary_is_repaired(tmp_path, installer):
    # Arrange
    release = release_fixture(tmp_path)
    destination = tmp_path / "installation"
    installer(TAG, destination, base_url=release.as_uri(), target=TARGET)
    (destination / "bin/codex").write_bytes(b"tampered")

    # Act
    changed = installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    # Assert
    assert changed is True
    assert (destination / "bin/codex").read_text().startswith("#!/bin/sh")
    assert list(tmp_path.glob("installation.backup-*"))


@pytest.mark.parametrize("relative", [
    "bin/codex-code-mode-host", "bin/codex-exec-server", "codex-path/rg",
    "codex-resources/voice/bin/codex-voice-speech-helper",
])
def test_missing_installed_tool_triggers_repair(tmp_path, installer, relative):
    release = release_fixture(tmp_path)
    destination = tmp_path / "installation"
    installer(TAG, destination, base_url=release.as_uri(), target=TARGET)
    (destination / relative).unlink()

    changed = installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    assert changed is True
    assert (destination / relative).is_file()


def test_incomplete_release_preserves_existing_installation(tmp_path, installer):
    release = release_fixture(tmp_path, missing="bin/codex-exec-server")
    destination = tmp_path / "installation"
    destination.mkdir()
    (destination / "keep.txt").write_text("old working installation")

    with pytest.raises(ValueError, match="Required release file missing"):
        installer(TAG, destination, base_url=release.as_uri(), target=TARGET)

    assert (destination / "keep.txt").read_text() == "old working installation"
    assert not (destination / "bin/codex").exists()
