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
CANONICAL = ROOT / "src/codex-guidance"


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
        ".codex/agents-md-references/repositories.json",
        ".codex/.vscode/settings.json",
        ".codex/keybindings.json",
        ".codex/config-toml/realtime-voice-backend-prompt.md",
        ".codex/config-toml/sync-voice-prompt.py",
        ".codex/config.toml",
    ):
        assert expected in paths

    assert not any("guidance-source" in p for p in paths)
    assert not any(p.startswith(".codex/skills/") for p in paths)
    assert not any(p.startswith(".codex/plugins/") for p in paths)
    assert ".codex/auth.json" not in paths
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
    assert "src/codex-guidance/global-guidance/agents-md-manifest.yaml" in guidance
    assert "Resolved order:" not in guidance
    assert "agents-md-components/" not in guidance
    assert "guidance-source/" not in guidance
    for removed in ("chatgpt-chat.md", "chatgpt-work.md", "codex.md"):
        assert not (SOURCE / "agents-md-references" / removed).exists()
    assert "sync-agents-md" not in (ROOT / "home/dot_zshrc.tmpl").read_text()


def test_generated_guidance_is_reproducible_without_any_other_repository():
    subprocess.run(
        [sys.executable, str(CANONICAL / "render.py"), "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def render_prompt(config: str, prompt: Path, **env: str) -> subprocess.CompletedProcess[str]:
    # The same pinned renderer is called by the native chezmoi modify script.
    return subprocess.run(
        [
            "uv", "run", "--no-project", "--script",
            str(SOURCE / "config-toml/sync-voice-prompt.py"),
            "--prompt", str(prompt),
        ],
        input=config, text=True, capture_output=True, env={**os.environ, **env},
    )


@pytest.mark.parametrize("existing_prompt", ["single-line", "multiline", "missing"])
def test_voice_prompt_render_preserves_local_codex_preferences(tmp_path, existing_prompt):
    prompt_path = tmp_path / "prompt.md"
    prompt = 'First line\nQuoted """ text and \\ backslashes\nUnicode: 🐈\n'
    prompt_path.write_text(prompt, encoding="utf-8")
    value = {
        "single-line": 'experimental_realtime_ws_backend_prompt = "old voice prompt"\n',
        "multiline": 'experimental_realtime_ws_backend_prompt = """\nold prompt\nwith many lines\n"""\n',
        "missing": "",
    }[existing_prompt]
    original = (
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
    before = tomllib.loads(original)

    result = render_prompt(original, prompt_path)

    assert result.returncode == 0, result.stderr
    updated = result.stdout
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
    if existing_prompt != "missing":
        # The renderer does not touch the rest of the file, even at text level.
        prefix = original.split('experimental_realtime_ws_backend_prompt')[0]
        assert updated.startswith(prefix)
        suffix = original[original.index('\n[plugins.'):]
        assert updated.endswith(suffix)

    repeated = render_prompt(updated, prompt_path)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout == updated


def test_voice_prompt_render_handles_missing_and_invalid_config(tmp_path):
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Versioned prompt\n", encoding="utf-8")

    new = render_prompt("", prompt_path)
    assert new.returncode == 0, new.stderr
    assert tomllib.loads(new.stdout) == {
        "experimental_realtime_ws_backend_prompt": "Versioned prompt\n"
    }

    invalid = render_prompt('[projects."broken"\ntrust_level = "trusted"\n', prompt_path)
    assert invalid.returncode != 0
    assert invalid.stdout == ""

    prompt_path.write_text("")
    empty_prompt = render_prompt('model = "local"\n', prompt_path)
    assert empty_prompt.returncode != 0
    assert empty_prompt.stdout == ""


def chezmoi_codex_command(profile_factory, profile: str, dest: Path, *args: str,
                         env: dict | None = None) -> subprocess.CompletedProcess[str]:
    rendered = profile_factory.render(profile)
    return subprocess.run(
        [
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(rendered.config), "--destination", str(dest),
            *args,
        ],
        env={**os.environ, **(env or {})}, text=True, capture_output=True,
    )


def prepare_codex_home(tmp_path: Path) -> Path:
    config = tmp_path / ".codex/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        '# Local UI preferences stay intact.\n'
        'experimental_realtime_ws_backend_prompt = "original voice prompt"\n'
        '[desktop]\nshow-context-window-usage = true\n'
        '[projects."/tmp/private repository"]\ntrust_level = "trusted"\n'
        '[mcp_servers.private]\ncommand = "private-command"\n',
        encoding="utf-8",
    )
    config.chmod(0o600)
    return config


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_normal_chezmoi_diff_and_apply_include_active_voice_prompt(profile_factory, profile, tmp_path):
    config = prepare_codex_home(tmp_path)
    initial = config.read_text()
    prompt = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()
    # The installed Markdown can be current even though Codex's active TOML
    # was later edited through its UI; this is the original visibility gap.
    installed_prompt = config.parent / "config-toml/realtime-voice-backend-prompt.md"
    installed_prompt.parent.mkdir(parents=True)
    installed_prompt.write_text(prompt)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "pgrep").write_text("#!/bin/sh\nexit 1\n")
    (fake_bin / "pgrep").chmod(0o755)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    diff = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )

    assert diff.returncode == 0, diff.stderr
    assert "diff --git a/.codex/config.toml b/.codex/config.toml" in diff.stdout
    assert "-experimental_realtime_ws_backend_prompt" in diff.stdout
    assert "+experimental_realtime_ws_backend_prompt" in diff.stdout
    assert config.read_text() == initial

    apply = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "apply", "--exclude", "scripts",
        str(config), env=env,
    )

    assert apply.returncode == 0, apply.stderr
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    after = tomllib.loads(config.read_text())
    before = tomllib.loads(initial)
    assert after == {**before, "experimental_realtime_ws_backend_prompt": prompt}

    repeat_diff = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert repeat_diff.returncode == 0, repeat_diff.stderr
    assert repeat_diff.stdout == ""

    # Codex's own UI can subsequently add a plugin without registering any
    # version-controlled change; re-applying must leave it untouched.
    new_gui_setting = '\n[plugins."installed-in-UI"]\nenabled = true\n'
    config.write_text(config.read_text() + new_gui_setting)
    machine_local_state = config.read_bytes()
    unchanged_diff = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert unchanged_diff.returncode == 0, unchanged_diff.stderr
    assert unchanged_diff.stdout == ""
    unchanged_apply = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "apply", "--exclude", "scripts",
        str(config), env=env,
    )
    assert unchanged_apply.returncode == 0, unchanged_apply.stderr
    assert config.read_bytes() == machine_local_state


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_first_apply_bootstraps_voice_config_without_uv(profile_factory, profile, tmp_path):
    # The official chezmoi installer precedes Homebrew/uv on a fresh Mac.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "chezmoi").symlink_to(shutil.which("chezmoi"))
    env = {"PATH": f"{fake_bin}:/usr/bin:/bin"}
    config = tmp_path / ".codex/config.toml"
    config.parent.mkdir(parents=True)
    prompt = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()

    preview = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert preview.returncode == 0, preview.stderr
    assert "diff --git a/.codex/config.toml" in preview.stdout
    assert not config.exists()

    apply = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "apply", "--exclude", "scripts",
        str(config), env=env,
    )

    assert apply.returncode == 0, apply.stderr
    assert tomllib.loads(config.read_text()) == {
        "experimental_realtime_ws_backend_prompt": prompt
    }
    assert stat.S_IMODE(config.stat().st_mode) == 0o600

    # Without the parser dependency, existing settings must never be rewritten.
    current = config.read_bytes()
    rejected = chezmoi_codex_command(
        profile_factory, profile, tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert rejected.returncode != 0
    assert "needs uv" in rejected.stderr
    assert config.read_bytes() == current


@pytest.mark.parametrize("active_process", ["ChatGPT", "Codex", "codex"])
def test_codex_modify_diff_remains_visible_while_app_running_and_apply_defers(
    profile_factory, tmp_path, active_process
):
    config = prepare_codex_home(tmp_path)
    initial = config.read_bytes()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pgrep = fake_bin / "pgrep"
    pgrep.write_text(f'#!/bin/sh\n[ "$2" = "{active_process}" ]\n')
    pgrep.chmod(0o755)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    diff = chezmoi_codex_command(
        profile_factory, "personal", tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert diff.returncode == 0, diff.stderr
    assert "diff --git a/.codex/config.toml" in diff.stdout

    apply = chezmoi_codex_command(
        profile_factory, "personal", tmp_path, "apply", "--exclude", "scripts",
        str(config), env=env,
    )
    assert apply.returncode == 0, apply.stderr
    assert "Deferred Codex Live Voice prompt sync" in apply.stderr
    assert config.read_bytes() == initial

    still_pending = chezmoi_codex_command(
        profile_factory, "personal", tmp_path, "--use-builtin-diff", "--no-pager",
        "diff", str(config), env=env,
    )
    assert "diff --git a/.codex/config.toml" in still_pending.stdout


def test_chezmoi_gui_diff_shows_only_the_readable_voice_prompt(profile_factory, tmp_path):
    config = prepare_codex_home(tmp_path)
    script_bin = tmp_path / "bin"
    script_bin.mkdir()
    code_log = tmp_path / "code_args.txt"
    fake_code = script_bin / "code"
    fake_code.write_text('#!/bin/sh\nprintf "%s\n" "$@" > "$CODE_ARGS_LOG"\n')
    fake_code.chmod(0o755)
    cache = tmp_path / "diff-cache"
    env = {
        "PATH": f"{script_bin}:{os.environ['PATH']}",
        "CODE_ARGS_LOG": str(code_log),
        "CHEZMOI_CODE_DIFF_CACHE": str(cache),
        "CHEZMOI_CODE_DIFF_SETTLE_SECONDS": "0",
    }

    result = chezmoi_codex_command(profile_factory, "personal", tmp_path, "diff",
                                   str(config), env=env)

    assert result.returncode == 0, result.stderr
    args = code_log.read_text().splitlines()
    assert args[:2] == ["--reuse-window", "--diff"]
    before, after = Path(args[2]), Path(args[3])
    assert before.name == after.name == "realtime-voice-backend-prompt.md"
    assert before.read_text() == "original voice prompt"
    assert after.read_text() == (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()
    assert "private-command" not in before.read_text() + after.read_text()
    assert config.read_text().startswith('# Local UI preferences stay intact.')



def test_versioned_voice_prompt_distinguishes_live_and_backend():
    upstream = (ROOT / "src/codex-guidance/upstream/realtime/backend_prompt.md").read_text()
    custom = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()

    assert "The user's name is {{ user_first_name }}" in upstream
    assert "Treat the system as one unified assistant" in upstream
    assert "do not mention \"backend\"" in upstream
    assert "distinct conversational agent" in custom
    assert "* **Disclose the source of every reply**" in custom
    assert "the backend was not consulted" in custom
    assert "the result is not yet known" in custom
    assert "Attribute received findings to the backend" in custom
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


def test_mode_specific_guidance_is_removed_from_global_agents_md():
    global_guidance = (SOURCE / "AGENTS.md").read_text()
    canonical = CANONICAL / "global-guidance"
    manifest = (canonical / "agents-md-manifest.yaml").read_text()

    assert "Delegated chat naming" in global_guidance
    for obsolete in ("ChatGPT runtime mode identification", "Interaction mode behavior",
                     "Mode-specific guidance"):
        assert obsolete not in global_guidance
    for obsolete in ("chatgpt-runtime-mode-identification.md", "interaction-mode-behavior.md"):
        assert obsolete not in manifest
        assert not (canonical / "agents-md-components/runtime-and-interaction" / obsolete).exists()
    for obsolete in ("chatgpt-chat.md", "chatgpt-work.md", "codex.md"):
        assert not (canonical / "agents-md-references" / obsolete).exists()
        assert not (SOURCE / "agents-md-references" / obsolete).exists()


def test_voice_frontend_requires_backend_and_grounded_code_navigation():
    prompt = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()
    backend = prompt.split("## Backend use and steering", 1)[1].split(
        "## Backend outputs and user inputs", 1
    )[0]
    walkthrough = prompt.split("### Code walkthroughs", 1)[1].split(
        "### Application and UI walkthroughs", 1
    )[0]

    assert "* Delegate **every question about real code or repository behavior**" in backend
    assert "Never answer from memory" in backend
    assert "* Ask the backend to verify the repository, branch/worktree" in backend
    assert "**return a navigation-only first result**" in backend
    assert "visible output must not spoil the explanation" in backend
    assert "* **Every actual code question**" in walkthrough
    assert "Never deliver the full answer before the user can inspect its evidence" in walkthrough
    assert "* Begin with the first missing visual anchor" in walkthrough
    for step in range(1, 6):
        assert f"{step}. " in walkthrough


def test_voice_frontend_discloses_provenance_in_existing_bullet_sections():
    prompt = (SOURCE / "config-toml/realtime-voice-backend-prompt.md").read_text()
    policies = prompt.split("### Policies", 1)[1].split(
        "## Voice turn-taking", 1
    )[0]
    communication = prompt.split("## Communication style", 1)[1].split(
        "## Delegated execution context", 1
    )[0]
    pacing = prompt.split("### General pacing", 1)[1].split(
        "### Code walkthroughs", 1
    )[0]

    assert "* **Disclose the source of every reply**" in policies
    assert "including brief answers and acknowledgements" in policies
    assert "* For a direct voice-frontend answer, explicitly say" in policies
    assert "Direct from me, without consulting the backend:" in policies
    assert "* For a backend handoff, identify the delegated work" in policies
    assert "* Before invisible or noticeably slow backend work" in communication
    assert "* After each step, stop and yield" in pacing
    assert "Silence is the checkpoint" in pacing
    assert "change representation rather than repeat jargon" in pacing
    assert "## Spoken progress and explanation checkpoints" not in prompt

    # All new instruction rules belong to existing bullet sections.
    for section in (policies, communication, pacing):
        assert all(line.startswith("* ") for line in section.splitlines() if line.strip())


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
