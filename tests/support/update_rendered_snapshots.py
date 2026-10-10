"""Regenerate the committed snapshots. Does not apply configuration."""
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.support.chezmoi_profile import ChezmoiProfileFixture
from tests.support.rendered_snapshots import SNAPSHOT_ROOT, rendered_outputs


def main():
    repository = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="chezmoi-snapshot-") as scratch:
        factory = ChezmoiProfileFixture(repository, Path(scratch))
        for profile in ("personal", "professional"):
            rendered = factory.render(profile)
            destination = SNAPSHOT_ROOT / profile
            destination.mkdir(parents=True, exist_ok=True)
            for name, content in rendered_outputs(rendered, repository).items():
                (destination / name).write_text(content)
                print(f"Updated {destination / name}")


if __name__ == "__main__":
    main()
