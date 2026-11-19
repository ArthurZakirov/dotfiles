"""External commands in the profile harness must fail within a caller's bound."""
import subprocess

import pytest

from tests.support.chezmoi_profile import ChezmoiProfileFixture


@pytest.mark.parametrize("capture_bytes", [False, True], ids=["text", "bytes"])
def test_profile_commands_time_out_when_external_process_does_not_finish(
    tmp_path, monkeypatch, capture_bytes,
):
    executable = tmp_path / "chezmoi"
    executable.write_text("#!/bin/sh\nexec /bin/sleep 1\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    fixture = ChezmoiProfileFixture(tmp_path, tmp_path)

    with pytest.raises(subprocess.TimeoutExpired):
        if capture_bytes:
            fixture.chezmoi_bytes(tmp_path / "config.toml", "managed", timeout=0.05)
        else:
            fixture.run(str(executable), timeout=0.05)
