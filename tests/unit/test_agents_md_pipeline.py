"""Read-only local guidance pipeline; each boundary reports its own evidence."""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/dot_codex/hooks-json/agents-md-freshness/pipeline.py"
loader = importlib.machinery.SourceFileLoader("agents_md_pipeline", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

SESSION = "01a1935b-e50c-7d52-a754-3f81fdffcaee"
SHA_LOCAL = "a" * 40
SHA_REMOTE = "b" * 40


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    repo = tmp_path / "dotfiles"
    source = repo / "home/dot_codex/AGENTS.md.tmpl"
    source.parent.mkdir(parents=True)
    source.write_text("source guidance\n")
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "AGENTS.md").write_text("rendered guidance\n")
    checker = codex_home / "hooks-json/agents-md-freshness/check.py"
    checker.parent.mkdir(parents=True)
    checker.write_text("")

    state = {
        "remote": SHA_LOCAL,
        "local": SHA_LOCAL,
        "committed": "source guidance\n",
        "applied": "rendered guidance\n",
        "session_status": "current",
    }

    def fake_run(argv, **kwargs):
        if "ls-remote" in argv:
            if state["remote"] is None:
                raise subprocess.TimeoutExpired(argv, 4)
            return subprocess.CompletedProcess(argv, 0, state["remote"] + "\trefs/heads/main\n", "")
        if "--show-toplevel" in argv:
            return subprocess.CompletedProcess(argv, 0, str(repo) + "\n", "")
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, state["local"] + "\n", "")
        if "show" in argv:
            return subprocess.CompletedProcess(argv, 0, state["committed"], "")
        if "chezmoi" in argv:
            return subprocess.CompletedProcess(argv, 0, state["applied"], "")
        if "--session-id" in argv:
            import json
            payload = {"session_id": SESSION, "status": state["session_status"]}
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run", fake_run)
    return repo, codex_home, checker, state


def statuses(pipeline, session_id=SESSION):
    repo, codex_home, checker, _ = pipeline
    repository, stages = module.check(repo, codex_home, session_id, checker)
    return {r["key"]: r["status"] for r in [repository, *stages]}


def test_repository_and_guidance_current(pipeline):
    assert statuses(pipeline) == dict.fromkeys(
        ("github", "local", "deployed", "session"), "current"
    )


@pytest.mark.parametrize(
    ("case", "change", "expected_stage", "expected_status"),
    [
        ("main-behind", {"remote": SHA_REMOTE}, "github", "outdated"),
        ("uncommitted-guidance", {"committed": "different\n"}, "local", "outdated"),
        ("chezmoi-stale", {"applied": "new guidance\n"}, "deployed", "outdated"),
        ("session-stale", {"session_status": "outdated"}, "session", "outdated"),
        ("github-unreachable", {"remote": None}, "github", "unknown"),
    ],
)
def test_each_boundary_identifies_its_failure(
    pipeline, case, change, expected_stage, expected_status
):
    pipeline[3].update(change)
    result = statuses(pipeline)
    assert result[expected_stage] == expected_status
    if case == "github-unreachable":
        assert result["local"] == "unknown"


def test_missing_session_does_not_hide_other_layer_results(pipeline):
    result = statuses(pipeline, session_id=None)
    assert result["session"] == "unknown"
    assert all(result[key] == "current" for key in ("github", "local", "deployed"))


def test_invalid_repository_has_no_false_green(tmp_path):
    repo = tmp_path / "not-a-repository"
    repo.mkdir()
    repository, stages = module.check(repo, tmp_path / ".codex", None, tmp_path / "checker")
    assert len(stages) == 3
    assert repository["status"] == "unknown"
    assert all(stage["status"] == "unknown" for stage in stages)
