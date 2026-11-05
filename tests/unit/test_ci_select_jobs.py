"""Regression coverage for selective, fail-open GitHub Actions execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.ci.select_jobs import JOBS, select_jobs

ROOT = Path(__file__).resolve().parents[2]
ALL = set(JOBS)


def enabled(paths: list[str], **options: bool) -> set[str]:
    return {job for job, run in select_jobs(paths, **options).items() if run}


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/development.md",
        "docs/features/hammerspoon.md",
        ".vscode/settings.json",
    ],
)
def test_documentation_or_editor_metadata_never_runs_expensive_jobs(path: str) -> None:
    assert enabled([path]) == set()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            "home/dot_local/bin/executable_git-review-worktree",
            {"profiles", "fresh_home", "git_review_e2e", "git_review_vscode"},
        ),
        (
            "home/dot_local/bin/executable_pysetup",
            {"profiles", "fresh_home", "pysetup_real", "git_review_e2e", "git_review_vscode"},
        ),
        (
            "home/dot_local/bin/executable_chezmoi-code-diff",
            {"profiles", "fresh_home", "chezmoi_vscode_diff_gui"},
        ),
        (
            "home/dot_vscode/extensions/agentdesk.git-review-ui-0.1.0/extension.js",
            {"profiles", "fresh_home", "git_review_vscode"},
        ),
        (
            "home/dot_codex/config-toml/config.toml",
            {"profiles", "fresh_home"},
        ),
        (
            "home/dot_hammerspoon/modules/chatgpt.lua",
            {"profiles", "fresh_home", "chezmoi_vscode_diff_gui"},
        ),
        (
            "home/run_after_50-ensure-agent-browser.sh.tmpl",
            {"profiles", "fresh_home", "computer_use_e2e"},
        ),
        (
            "src/agent-browser-runtime.sh",
            {"profiles", "computer_use_e2e"},
        ),
        (
            "tests/integration/test_pysetup_real.py",
            {"profiles", "pysetup_real"},
        ),
        (
            "tests/integration/test_git_review_e2e.py",
            {"profiles", "git_review_e2e"},
        ),
        (
            "tests/integration/test_chezmoi_vscode_gui.py",
            {"profiles", "chezmoi_vscode_diff_gui"},
        ),
    ],
)
def test_known_component_only_runs_dependent_jobs(path: str, expected: set[str]) -> None:
    assert enabled([path]) == expected


def test_mixed_changes_union_dependencies_without_running_everything() -> None:
    assert enabled([
        "README.md",
        "home/dot_local/bin/executable_pysetup",
        "src/agent-browser-runtime.sh",
    ]) == {
        "profiles",
        "fresh_home",
        "computer_use_e2e",
        "git_review_e2e",
        "git_review_vscode",
        "pysetup_real",
    }


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/shell.yml",
        "src/ci/select_jobs.py",
        "tests/unit/test_ci_select_jobs.py",
        "dependencies/npm/common.txt",
        "home/run_after_90-new-installer.sh",
        "home/dot_local/bin/executable_brand_new_tool",
        "src/new_critical_installer.sh",
        "new-root-config.yaml",
        "../outside-repository",
    ],
)
def test_shared_or_unclassified_changes_trigger_every_job(path: str) -> None:
    assert enabled([path]) == ALL


def test_empty_or_truncated_diff_and_manual_dispatch_trigger_every_job() -> None:
    assert enabled([]) == ALL
    assert enabled(["README.md"], force_full=True) == ALL
    assert enabled(["README.md"], truncated=True) == ALL


def test_output_is_machine_readable_and_matches_changed_file_inputs(tmp_path: Path) -> None:
    result_file = tmp_path / "github-output"
    env = os.environ | {
        "GITHUB_OUTPUT": str(result_file),
        "CHANGED_FILES_JSON": json.dumps(["README.md", "src/agent-browser-runtime.sh"]),
        "CHANGED_FILES_COUNT": "2",
        "FORCE_FULL_CI": "false",
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "src/ci/select_jobs.py")],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    output = dict(line.split("=", 1) for line in result_file.read_text().splitlines())
    assert set(output) == ALL
    assert output["computer_use_e2e"] == "true"
    assert output["git_review_e2e"] == "false"
    assert output["profiles"] == "true"

def test_workflow_gate_outputs_match_classifier_contract() -> None:
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/shell.yml").read_text())
    changes = workflow["jobs"]["changes"]
    outputs = changes["outputs"]
    assert set(outputs) == ALL
    assert set(workflow["jobs"]) == {
        "changes",
        "ci-sanity",
        "profiles",
        "fresh-home",
        "computer-use-e2e",
        "git-review-e2e",
        "pysetup-real",
        "git-review-vscode",
        "chezmoi-vscode-diff-gui",
    }
    for job_id, selector in {
        "profiles": "profiles",
        "fresh-home": "fresh_home",
        "computer-use-e2e": "computer_use_e2e",
        "git-review-e2e": "git_review_e2e",
        "pysetup-real": "pysetup_real",
        "git-review-vscode": "git_review_vscode",
        "chezmoi-vscode-diff-gui": "chezmoi_vscode_diff_gui",
    }.items():
        job = workflow["jobs"][job_id]
        assert job["needs"] == "changes"
        assert job["if"] == "${{ needs.changes.outputs." + selector + " == 'true' }}"
