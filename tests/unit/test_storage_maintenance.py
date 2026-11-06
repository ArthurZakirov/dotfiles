"""Tests for safe Chrome code-sign clone cleanup."""

import importlib.util
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/dot_local/share/storage-maintenance/private_clean_chrome_clones.py"


@pytest.fixture(scope="module")
def cleaner():
    spec = importlib.util.spec_from_file_location("storage_maintenance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("age_hours", "chrome_start_minutes", "expected"),
    [(1, None, False), (72, 10, False), (72, 180, True), (72, None, True)],
    ids=["recent", "active", "old-orphan", "no-chrome"],
)
def test_eligible_respects_age_and_active_chrome(cleaner, age_hours, chrome_start_minutes, expected):
    now = 1_800_000_000
    birth = now - age_hours * 3600
    starts = [] if chrome_start_minutes is None else [birth + chrome_start_minutes * 60]

    actual = cleaner.eligible(birth, starts, now, newest_birth=now - 300)

    assert actual is expected


def test_newest_clone_is_protected_while_chrome_runs(cleaner):
    now = 1_800_000_000
    old = now - 72 * 3600

    assert cleaner.eligible(old, [], now, newest_birth=old)
    assert not cleaner.eligible(old, [now - 3600], now, newest_birth=old)


def test_cleanup_removes_only_named_clones_and_preserves_user_data(cleaner, tmp_path):
    clone = tmp_path / "code_sign_clone.123AbC"
    unrelated = tmp_path / "keep-user-data"
    clone.mkdir()
    unrelated.mkdir()
    (unrelated / "important.txt").write_text("keep")

    result = cleaner.cleanup(root=tmp_path, starts=[], now=time.time() + 72 * 3600)

    assert result["removed"] == [clone.name]
    assert not clone.exists()
    assert (unrelated / "important.txt").read_text() == "keep"


def test_dry_run_keeps_clone_on_disk(cleaner, tmp_path):
    clone = tmp_path / "code_sign_clone.123AbC"
    clone.mkdir()

    result = cleaner.cleanup(dry_run=True, root=tmp_path, starts=[], now=time.time() + 72 * 3600)

    assert result["removed"] == [clone.name]
    assert clone.exists()
