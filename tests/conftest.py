"""Shared pytest fixtures for rendered, non-destructive chezmoi profiles."""

from pathlib import Path

import pytest

from tests.support.chezmoi_profile import ChezmoiProfileFixture, RenderedProfile


@pytest.fixture(scope="session")
def profile_factory(tmp_path_factory: pytest.TempPathFactory) -> ChezmoiProfileFixture:
    repository = Path(__file__).resolve().parents[1]
    scratch = tmp_path_factory.mktemp("chezmoi-profiles")
    return ChezmoiProfileFixture(repository, scratch)


@pytest.fixture(scope="session", params=["personal", "professional"])
def rendered_profile(
    request: pytest.FixtureRequest, profile_factory: ChezmoiProfileFixture
) -> RenderedProfile:
    return profile_factory.render(request.param)
