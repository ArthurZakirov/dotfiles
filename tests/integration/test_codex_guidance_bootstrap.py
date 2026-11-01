"""User-visible contracts for the versioned Codex guidance bootstrap."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "src/codex-guidance/scripts/bootstrap-agents-md.py"
BASE_MANIFEST = ROOT / "src/codex-guidance/global-guidance/agents-md-manifest.yaml"


def bootstrap(tmp_path: Path, *options: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(BOOTSTRAP),
            *options,
            "--codex-home", str(tmp_path / ".codex"),
            "--claude-home", str(tmp_path / ".claude"),
            "--opencode-home", str(tmp_path / "opencode"),
        ],
        capture_output=True, text=True,
    )


def manifest_at(root: Path, *, layer_id: str | None = None) -> Path:
    root.mkdir(parents=True)
    (root / "component.md").write_text("# External guidance\n\nUnique guidance.\n")
    manifest = root / "manifest.yaml"
    manifest.write_text(
        (f"layer_id: {layer_id}\n" if layer_id is not None else "")
        + "components:\n  - component.md\n"
    )
    return manifest


def test_manual_json_reference_requires_explicit_replacement(tmp_path):
    manifest = manifest_at(tmp_path / "sources")
    source_refs = manifest.parent / "agents-md-references"
    source_refs.mkdir()
    (source_refs / "repositories.json").write_text('{"managed": true}\n')

    destination = tmp_path / ".codex/agents-md-references/repositories.json"
    destination.parent.mkdir(parents=True)
    previous = '{"handwritten": true}\n'
    destination.write_text(previous)

    refused = bootstrap(tmp_path, "--manifest", str(manifest))

    assert refused.returncode != 0
    assert "ownership differs" in refused.stderr
    assert destination.read_text() == previous
    assert not (tmp_path / ".codex/AGENTS.md").exists()

    installed = bootstrap(tmp_path, "--manifest", str(manifest), "--replace-existing")

    assert installed.returncode == 0, installed.stderr
    assert destination.read_text() == '{"managed": true}\n'
    saved = list((tmp_path / ".codex/guidance-backups").glob("*/agents-md-references/repositories.json"))
    assert len(saved) == 1
    assert saved[0].read_text() == previous


@pytest.mark.parametrize("with_overlay", [False, True])
def test_guidance_from_external_manifest_paths_is_rendered(tmp_path, with_overlay):
    manifest = manifest_at(tmp_path / "external")
    arguments = ["--manifest", str(BASE_MANIFEST if with_overlay else manifest)]
    if with_overlay:
        (manifest.parent / "component.md").write_text("# Distinct external overlay\n\nExtra guidance.\n")
        manifest.write_text("layer_id: external-overlay\ncomponents:\n  - component.md\n")
        arguments += ["--overlay-manifest", str(manifest)]

    installed = bootstrap(tmp_path, *arguments)

    assert installed.returncode == 0, installed.stderr
    guidance = (tmp_path / ".codex/AGENTS.md").read_text()
    assert f"`{manifest.as_posix()}`" in guidance
    assert "Resolved order:" not in guidance
    assert "Resolved component order:" not in guidance
    assert (manifest.parent / "component.md").as_posix() not in guidance
    assert "# Distinct external overlay" in guidance if with_overlay else "# External guidance" in guidance


def test_dangling_symlink_can_be_reconciled_and_backed_up(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Shared guidance\n")
    home = tmp_path / ".codex"
    home.mkdir()
    dangling = home / "AGENTS.md"
    old_target = tmp_path / "deleted-checkout" / "AGENTS.md"
    dangling.symlink_to(old_target)

    installed = bootstrap(tmp_path, "--source", str(source), "--replace-existing")

    assert installed.returncode == 0, installed.stderr
    assert dangling.is_symlink()
    assert dangling.resolve() == source.resolve()
    saved = list((home / "guidance-backups").glob("*/AGENTS.md"))
    assert len(saved) == 1
    assert saved[0].read_text() == f"symlink -> {old_target}\n"


def test_canonical_document_staging_guidance_is_consistent():
    references = ROOT / "src/codex-guidance/global-guidance/agents-md-references"
    routing = (references / "repository-routing-and-data-boundaries.md").read_text()
    documents = (references / "personal-document-workflow.md").read_text()

    assert "self-source/.local-workspace/documents/" in routing
    assert ".local-workspace/documents/" in documents
    assert "outside Git repositories" not in routing


def test_information_representation_guidance_is_always_rendered(tmp_path):
    """Every agent reply and human-readable artifact must receive the four-stage guidance."""
    installed = bootstrap(tmp_path, "--manifest", str(BASE_MANIFEST))

    assert installed.returncode == 0, installed.stderr
    guidance = (tmp_path / ".codex/AGENTS.md").read_text()

    assert guidance.count('<a id="information-representation-design"></a>') == 1
    assert "**every user-facing chat reply or message**" in guidance
    assert "**any other human-readable text**" in guidance
    assert "**Apply all four stages below**" in guidance
    assert "Within each stage, apply the rules relevant to the content and medium." in guidance
    assert "do not skip the process for short replies" not in guidance
    assert "including intermediate work-in-progress updates, partial answers, and final replies" in guidance
    assert "including intermediate work-in-progress updates, partial findings" in guidance
    assert "Before sending each message" in guidance
    assert "The rules apply to the **accumulating sequence of messages**" in guidance
    assert "**short, descriptive bold title or heading**" in guidance
    assert "even one sentence long" in guidance
    assert "do **not** inflate a short update into a table" in guidance
    assert "Report meaningful milestones, findings, blockers, or next steps" in guidance
    assert "Brief progress updates need not contain headings, lists, or tables" not in guidance
    assert "[🧩 Information representation design](#information-representation-design)" in guidance
    for index in range(1, 5):
        assert guidance.count(f'<a id="stage-{index}"></a>') == 1
        assert f"](#stage-{index})" in guidance

    # The full source is embedded, not gated behind choosing a separate skill.
    assert "#### T2 — Group scannable items by semantic type" in guidance
    assert "###### Negative example — Unframed" in guidance
    assert "When available, use the information-representation-design skill" not in guidance
