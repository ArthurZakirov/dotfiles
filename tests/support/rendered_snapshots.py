"""Stable snapshots of complete chezmoi-rendered profile outputs."""

from difflib import unified_diff
from pathlib import Path

from tests.support.chezmoi_profile import RenderedProfile


SNAPSHOT_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "rendered"


def rendered_outputs(rendered: RenderedProfile, repository: Path) -> dict[str, str]:
    # Remove machine-specific absolute paths without changing shell structure.
    # Replace repository first because it may live inside HOME.
    replacements = (
        (str(repository), "<DOTFILES_REPO>"),
        (str(Path.home()), "<HOME>"),
    )
    outputs = {
        "chezmoi.toml": rendered.config.read_text(),
        "zshrc": rendered.zshrc.read_text(),
    }
    for name, content in outputs.items():
        for original, replacement in replacements:
            content = content.replace(original, replacement)
        outputs[name] = content
    return outputs


def assert_snapshots_match(rendered: RenderedProfile, repository: Path) -> None:
    for name, actual in rendered_outputs(rendered, repository).items():
        expected_path = SNAPSHOT_ROOT / rendered.name / name
        expected = expected_path.read_text()
        if actual != expected:
            diff = "".join(unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(expected_path),
                tofile=f"rendered/{rendered.name}/{name}",
            ))
            raise AssertionError(
                f"Rendered chezmoi output differs from {expected_path}. "
                "Review the diff and explicitly regenerate snapshots if intended:\n"
                "python3 -m tests.support.update_rendered_snapshots\n" + diff
            )
