"""Contracts for self-contained Codex files managed by chezmoi."""
import json
import os
import shutil
import stat
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home" / "dot_codex"
CANONICAL = ROOT / "codex-guidance"


def managed(profile_factory, profile: str) -> set[str]:
    rendered = profile_factory.render(profile)
    result = subprocess.run(
        [
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(rendered.config),
            "--destination", str(rendered.config.parent),
            "managed", "--include", "files",
        ],
        check=True, capture_output=True, text=True,
    )
    return set(result.stdout.splitlines())


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_apply_owns_only_deployed_codex_artifacts(profile_factory, profile):
    paths = managed(profile_factory, profile)
    for expected in (
        ".codex/AGENTS.md",
        ".codex/agents-md-references/codex.md",
        ".codex/agents-md-references/repositories.json",
        ".codex/.vscode/settings.json",
        ".codex/keybindings.json",
        ".codex/config-toml/realtime-voice-backend-prompt.md",
        ".codex/config-toml/sync-voice-prompt.py",
    ):
        assert expected in paths

    assert not any("guidance-source" in p for p in paths)
    assert not any(p.startswith(".codex/skills/") for p in paths)
    assert not any(p.startswith(".codex/plugins/") for p in paths)
    assert ".codex/auth.json" not in paths
    assert ".codex/config.toml" not in paths
    assert not any("config.template.toml" in p or "render-config.py" in p for p in paths)
    assert (".codex/langsmith.json" in paths) == (profile == "personal")
    assert ".codex/hooks.json" in paths
    assert ".codex/hooks-json/bedtime-device-guard/bedtime_guard.py" in paths
    assert ".codex/hooks-json/bedtime-device-guard/config.json" in paths



@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_hook_outputs_keep_executable_and_private_modes(profile_factory, profile, tmp_path):
    rendered = profile_factory.render(profile)
    paths = (
        tmp_path / ".codex/hooks-json/bedtime-device-guard/bedtime_guard.py",
        tmp_path / ".codex/hooks-json/bedtime-device-guard/config.json",
    )
    paths[0].parent.mkdir(parents=True)
    result = subprocess.run(
        [
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(rendered.config), "--destination", str(tmp_path),
            "apply", "--exclude", "scripts", *map(str, paths),
        ],
        text=True, capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(paths[0].stat().st_mode) == 0o755
    assert stat.S_IMODE(paths[1].stat().st_mode) == 0o600



def test_canonical_guidance_is_only_in_the_repository():
    assert (CANONICAL / "global-guidance/agents-md-manifest.yaml").is_file()
    assert (CANONICAL / "scripts/bootstrap-agents-md.py").is_file()
    assert (CANONICAL / "render.py").is_file()
    assert not (SOURCE / "guidance-source").exists()
    guidance = (SOURCE / "AGENTS.md").read_text(encoding="utf-8")
    assert "codex-guidance/global-guidance/agents-md-manifest.yaml" in guidance
    assert "guidance-source/" not in guidance
    assert (SOURCE / "agents-md-references/codex.md").is_file()
    assert "sync-agents-md" not in (ROOT / "home/dot_zshrc.tmpl").read_text()


def test_generated_guidance_is_reproducible_without_any_other_repository():
    subprocess.run(
        [sys.executable, str(CANONICAL / "render.py"), "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def run_prompt_sync(config: Path, prompt: Path) -> subprocess.CompletedProcess[str]:
    # uv uses the pinned PEP 723 dependency; no global pip installation.
    return subprocess.run(
        [
            "uv", "run", "--no-project", "--script",
            str(SOURCE / "config-toml/sync-voice-prompt.py"),
            "--config", str(config), "--prompt", str(prompt),
        ],
        text=True, capture_output=True,
    )


@pytest.mark.parametrize("existing_prompt", ["single-line", "multiline", "missing"])
def test_voice_prompt_sync_preserves_local_codex_preferences(tmp_path, existing_prompt):
    config = tmp_path / "config.toml"
    prompt_path = tmp_path / "prompt.md"
    prompt = 'First line\nQuoted """ text and \\ backslashes\nUnicode: 🐈\n'
    prompt_path.write_text(prompt, encoding="utf-8")
    value = {
        "single-line": 'experimental_realtime_ws_backend_prompt = "old voice prompt"\n',
        "multiline": 'experimental_realtime_ws_backend_prompt = """\nold prompt\nwith many lines\n"""\n',
        "missing": "",
    }[existing_prompt]
    existing = (
        '# Codex still owns these settings.\n'
        'model = "gpt-6" # chosen in Desktop\n'
        + value
        + '\n[plugins."github@openai-curated"]\n'
        'enabled = true\n'
        '\n[projects."/tmp/my project"]\n'
        'trust_level = "trusted"\n'
        '\n[mcp_servers.work]\n'
        'command = "work-mcp"\n'
        '\n[desktop]\n'
        'show-context-window-usage = true\n'
    )
    config.write_text(existing, encoding="utf-8")
    config.chmod(0o600)
    before = tomllib.loads(existing)

    result = run_prompt_sync(config, prompt_path)

    assert result.returncode == 0, result.stderr
    updated = config.read_text(encoding="utf-8")
    assert tomllib.loads(updated) == {**before, "experimental_realtime_ws_backend_prompt": prompt}
    for unrelated_line in (
        '# Codex still owns these settings.',
        'model = "gpt-6" # chosen in Desktop',
        '[projects."/tmp/my project"]',
        'trust_level = "trusted"',
        '[mcp_servers.work]',
        'command = "work-mcp"',
        '[desktop]',
        'show-context-window-usage = true',
    ):
        assert unrelated_line in updated
    assert stat.S_IMODE(config.stat().st_mode) == 0o600

    # Unchanged syncs must not rewrite a live file.
    previous = config.stat().st_mtime_ns
    repeated = run_prompt_sync(config, prompt_path)
    assert repeated.returncode == 0, repeated.stderr
    assert config.stat().st_mtime_ns == previous
    assert config.read_text(encoding="utf-8") == updated


def test_voice_prompt_sync_creates_only_prompt_in_new_home(tmp_path):
    config = tmp_path / "config.toml"
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Versioned prompt\n", encoding="utf-8")

    result = run_prompt_sync(config, prompt_path)

    assert result.returncode == 0, result.stderr
    assert tomllib.loads(config.read_text()) == {
        "experimental_realtime_ws_backend_prompt": "Versioned prompt\n"
    }
    assert stat.S_IMODE(config.stat().st_mode) == 0o600


def test_voice_prompt_sync_rejects_invalid_config_without_modifying_it(tmp_path):
    config = tmp_path / "config.toml"
    prompt_path = tmp_path / "prompt.md"
    content = '[projects."broken"\ntrust_level = "trusted"\n'
    config.write_text(content, encoding="utf-8")
    prompt_path.write_text("Versioned prompt\n", encoding="utf-8")

    result = run_prompt_sync(config, prompt_path)

    assert result.returncode != 0
    assert config.read_text(encoding="utf-8") == content
    assert not list(tmp_path.glob(".config.toml-*"))




@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_chezmoi_hook_updates_config_in_isolated_home(profile_factory, profile, tmp_path):
    rendered = profile_factory.render(profile)
    codex_home = tmp_path / ".codex"
    config = codex_home / "config.toml"
    source_files = SOURCE / "config-toml"
    installed = codex_home / "config-toml"
    installed.mkdir(parents=True)
    for name in ("sync-voice-prompt.py", "realtime-voice-backend-prompt.md"):
        shutil.copy2(source_files / name, installed / name)
    config.write_text(
        'model = "machine-local"\n[projects."/tmp/only-this-mac"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    hook_source = (ROOT / "home/run_after_85-sync-codex-voice-prompt.sh.tmpl").read_text()
    # A fresh machine has no running Codex. Stub just the process probe
    # so this isolated fixture does not depend on the host's open applications.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pgrep = fake_bin / "pgrep"
    pgrep.write_text("#!/bin/sh\nexit 1\n")
    pgrep.chmod(0o755)
    env = {**os.environ, "HOME": str(tmp_path),
           "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    render = subprocess.run(
        [
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(rendered.config), "--destination", str(tmp_path),
            "execute-template",
        ],
        input=hook_source, env=env, text=True, capture_output=True,
    )
    assert render.returncode == 0, render.stderr
    assert f'{tmp_path}/.codex' in render.stdout

    applied = subprocess.run(["bash"], input=render.stdout, env=env, text=True, capture_output=True)

    assert applied.returncode == 0, applied.stderr
    result = tomllib.loads(config.read_text())
    assert result["experimental_realtime_ws_backend_prompt"] == (
        source_files / "realtime-voice-backend-prompt.md"
    ).read_text()
    assert result["model"] == "machine-local"
    assert result["projects"]["/tmp/only-this-mac"]["trust_level"] == "trusted"


@pytest.mark.parametrize("running", [True, False])
def test_voice_prompt_sync_defers_while_codex_is_running(tmp_path, running):
    config = tmp_path / "config.toml"
    prompt = tmp_path / "prompt.md"
    old = 'model = "existing"\n'
    config.write_text(old)
    prompt.write_text("New prompt\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    probe = fake_bin / "pgrep"
    probe.write_text("#!/bin/sh\nexit " + ("0" if running else "1") + "\n")
    probe.chmod(0o755)

    result = subprocess.run(
        [
            "uv", "run", "--no-project", "--script",
            str(SOURCE / "config-toml/sync-voice-prompt.py"),
            "--defer-while-active", "--config", str(config), "--prompt", str(prompt),
        ],
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True, capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    if running:
        assert "Deferred" in result.stdout
        assert config.read_text() == old
    else:
        assert "Updated" in result.stdout
        assert tomllib.loads(config.read_text())["experimental_realtime_ws_backend_prompt"] == "New prompt\n"


def test_voice_prompt_sync_defers_when_codex_starts_during_update(tmp_path):
    config = tmp_path / "config.toml"
    prompt = tmp_path / "prompt.md"
    old = 'model = "existing"\n'
    config.write_text(old)
    prompt.write_text("New prompt\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    counter = tmp_path / "probe-count"
    probe = fake_bin / "pgrep"
    probe.write_text(
        '#!/bin/sh\n'
        'count=$(cat "$PGREP_COUNT_FILE" 2>/dev/null || echo 0)\n'
        'count=$((count + 1))\n'
        'echo "$count" > "$PGREP_COUNT_FILE"\n'
        '[ "$count" -eq 3 ]\n'
    )
    probe.chmod(0o755)

    result = subprocess.run(
        [
            "uv", "run", "--no-project", "--script",
            str(SOURCE / "config-toml/sync-voice-prompt.py"),
            "--defer-while-active", "--config", str(config), "--prompt", str(prompt),
        ],
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
             "PGREP_COUNT_FILE": str(counter)},
        text=True, capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Deferred" in result.stdout
    assert config.read_text() == old
    assert not list(tmp_path.glob(".config.toml-*"))


def test_voice_prompt_sync_preserves_symlinked_config(tmp_path):
    config = tmp_path / "config.toml"
    real_config = tmp_path / "original.toml"
    real_config.write_text('model = "local"\n')
    config.symlink_to(real_config)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Versioned prompt\n")

    result = run_prompt_sync(config, prompt)

    assert result.returncode != 0
    assert config.is_symlink()
    assert real_config.read_text() == 'model = "local"\n'




def test_versioned_voice_prompt_distinguishes_live_and_backend():
    upstream = (ROOT / "codex-guidance/upstream/realtime/backend_prompt.md").read_text()
    custom = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()

    assert "The user's name is {{ user_first_name }}" in upstream
    assert "Treat the system as one unified assistant" in upstream
    assert "do not mention \"backend\"" in upstream
    assert "distinct conversational agent" in custom
    assert "no backend consulted" in custom
    assert "handed to the backend" in custom
    assert "information actually received from the backend" in custom
    assert "do not mention \"backend\"" not in custom.lower()
    assert "Do not disclose the concept or existence of backend" not in custom



def test_live_voice_waits_for_explicit_spoken_turn_completion():
    prompt = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()
    assert prompt.index("## Voice turn-taking") < prompt.index("## Backend use and steering")

    turn_taking = prompt.split("## Voice turn-taking", 1)[1].split(
        "## Backend use and steering", 1
    )[0]
    assert 'explicitly says "go"' in turn_taking
    assert 'not when it appears naturally within a sentence' in turn_taking
    assert 'do not speak, acknowledge, summarize, ask questions, call tools, or delegate' in turn_taking
    assert "including the user's corrections" in turn_taking
    assert 'not typed messages, backend updates' in turn_taking
    assert 'takes precedence over instructions to respond promptly or to delegate immediately' in turn_taking


def test_hooks_template_preserves_expected_events():
    source = (SOURCE / "hooks.json.tmpl").read_text(encoding="utf-8")
    data = json.loads(source.replace("{{ .chezmoi.homeDir }}", "/tmp/codex-fixture"))
    assert set(data["hooks"]) == {"UserPromptSubmit"}
    commands = [
        hook["command"]
        for entry in data["hooks"]["UserPromptSubmit"]
        for hook in entry["hooks"]
    ]
    assert len(commands) == 1
    assert "bedtime-device-guard/bedtime_guard.py" in commands[0]
