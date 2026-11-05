#!/usr/bin/env python3
"""Conservative path-to-CI-job dependency map.

Unknown paths fail open: run every job instead of silently losing coverage.
Keep the always-on lightweight check independent of these decisions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

JOBS = (
    "profiles",
    "fresh_home",
    "computer_use_e2e",
    "git_review_e2e",
    "pysetup_real",
    "git_review_vscode",
    "chezmoi_vscode_diff_gui",
)
ALL = frozenset(JOBS)
PROFILES = frozenset({"profiles"})
HOME = frozenset({"profiles", "fresh_home"})
REVIEW = frozenset({"git_review_e2e", "git_review_vscode"})
DIFF_GUI = frozenset({"chezmoi_vscode_diff_gui"})
COMPUTER_USE = frozenset({"computer_use_e2e"})


def jobs_for_path(path: str) -> frozenset[str]:
    """Return all jobs whose behavior can depend on this changed repository file."""
    if path == "README.md" or path.startswith("docs/"):
        return frozenset()

    # Changing the selector, shared test tooling, or CI dependencies runs everything.
    if (
        path.startswith((".github/", "src/ci/", "tests/support/", "dependencies/"))
        or path in {"AGENTS.md", ".chezmoiroot", "pyproject.toml", "poetry.lock"}
        or path == "tests/unit/test_ci_select_jobs.py"
    ):
        return ALL

    if path.startswith("home/"):
        if path in {
            "home/dot_local/bin/executable_git-review-worktree",
            "home/dot_gitconfig",
        }:
            return HOME | REVIEW
        if path == "home/dot_local/bin/executable_pysetup":
            return HOME | REVIEW | {"pysetup_real"}
        if path == "home/dot_local/bin/executable_chezmoi-code-diff":
            return HOME | DIFF_GUI
        if path.startswith("home/dot_vscode/extensions/"):
            return HOME | {"git_review_vscode"}
        if path.startswith("home/dot_hammerspoon/"):
            if path in {
                "home/dot_hammerspoon/modules/spaces.lua",
                "home/dot_hammerspoon/modules/chatgpt.lua",
            }:
                return HOME | DIFF_GUI
            return HOME
        if path in {
            "home/run_after_40-ensure-peekaboo-skill.sh.tmpl",
            "home/run_after_50-ensure-agent-browser.sh.tmpl",
        }:
            return HOME | COMPUTER_USE
        if path.startswith("home/dot_local/share/local-skills-mcp/"):
            return HOME | COMPUTER_USE
        if path.startswith((
            "home/dot_codex/",
            "home/dot_config/raycast/",
            "home/dot_config/repo-refresh/",
            "home/dot_config/pr-navigation/",
            "home/dot_config/macos-shortcuts/",
            "home/dot_config/worktrunk/",
            "home/dot_vscode/",
            "home/dot_local/share/pr-navigation/",
        )):
            return HOME
        # Other Chezmoi lifecycle hooks and unclassified managed files affect
        # the entire setup; do not assume they are independent of real E2E.
        return ALL

    if path == "src/agent-browser-runtime.sh":
        return PROFILES | COMPUTER_USE
    if path == "src/install_vscode_pr_navigation.py":
        return HOME | {"git_review_vscode"}
    if path.startswith("src/codex-guidance/") or path in {
        "src/macos_shortcuts.py",
        "src/bws_env.py",
        "src/provisioning-log.sh",
    }:
        return PROFILES
    if path.startswith("src/"):
        return ALL

    if path.startswith("tests/unit/"):
        return PROFILES
    if path == "tests/integration/test_computer_use_real.sh":
        return PROFILES | COMPUTER_USE
    if path == "tests/integration/test_pysetup_real.py":
        return PROFILES | {"pysetup_real"}
    if path == "tests/integration/test_git_review_vscode_gui.py":
        return PROFILES | {"git_review_vscode"}
    if path == "tests/integration/test_git_review_e2e.py":
        return PROFILES | {"git_review_e2e"}
    if path == "tests/integration/test_chezmoi_vscode_gui.py":
        return PROFILES | DIFF_GUI
    if path in {
        "tests/integration/test_chezmoi_code_diff.py",
    }:
        return PROFILES | DIFF_GUI
    if path in {
        "tests/integration/test_git_review.py",
        "tests/integration/test_pysetup.py",
    }:
        return PROFILES | REVIEW | {"pysetup_real"}
    if path in {
        "tests/integration/run_fresh_home.sh",
        "tests/integration/test_profiles.py",
        "tests/integration/test_chezmoi_lifecycle.py",
    }:
        return HOME
    if path == "tests/run.sh":
        return PROFILES
    if path.startswith("tests/integration/"):
        return ALL
    if path.startswith("tests/"):
        return ALL

    if path.startswith(".vscode/"):
        return frozenset()
    return ALL


def select_jobs(
    paths: list[str], *, force_full: bool = False, truncated: bool = False
) -> dict[str, bool]:
    # Empty/unknown diffs are not evidence that the full system is unaffected.
    selected = set(ALL if force_full or truncated or not paths else ())
    for path in paths:
        if not isinstance(path, str) or not path or path.startswith("/"):
            selected.update(ALL)
        else:
            selected.update(jobs_for_path(path))
    return {job: job in selected for job in JOBS}


def main() -> None:
    paths = json.loads(os.environ.get("CHANGED_FILES_JSON") or "[]")
    if not isinstance(paths, list):
        raise ValueError("Changed-file output must be a JSON array")
    force_full = os.environ.get("FORCE_FULL_CI") == "true"
    count = int(os.environ.get("CHANGED_FILES_COUNT") or "0")
    decisions = select_jobs(paths, force_full=force_full, truncated=count >= 3000)
    output = Path(os.environ["GITHUB_OUTPUT"])
    with output.open("a", encoding="utf-8") as stream:
        for job, enabled in decisions.items():
            print(f"{job}={str(enabled).lower()}", file=stream)

    print(f"Changed files: {len(paths)}; manual: {force_full}; complete: {count < 3000}")
    for job, enabled in decisions.items():
        print(f"{job}: {'run' if enabled else 'skip'}")


if __name__ == "__main__":
    main()
