#!/bin/bash
set -euo pipefail

if [[ "${RUN_COMPUTER_USE_E2E:-0}" != 1 ]]; then
  echo 'Real computer-use integration skipped (set RUN_COMPUTER_USE_E2E=1).'
  exit 0
fi
[[ "$(uname -s)" == Darwin ]] || { echo 'Real computer-use integration requires macOS.' >&2; exit 1; }
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
trial="$(mktemp -d)"
cleanup() {
  "$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e close >/dev/null 2>&1 || true
  rm -rf "$trial"
}
trap cleanup EXIT
export HOME="$trial/home"
export npm_config_prefix="$trial/npm"
export npm_config_cache="$trial/npm-cache"
mkdir -p "$HOME" "$npm_config_prefix/bin"
export PATH="$npm_config_prefix/bin:$PATH"

command -v peekaboo >/dev/null
command -v chezmoi >/dev/null
command -v npm >/dev/null
command -v npx >/dev/null

# The real browser and skills packages must exist inside the isolated prefix,
# even if another copy already happens to be available on the runner's PATH.
# Read their identities from the same manifest as normal provisioning.
while read -r command_name package verification; do
  case "$command_name" in ''|\#*) continue ;; esac
  npm install --global "$package"
done < "$repo_root/dependencies/npm/common.txt"
[[ -x "$npm_config_prefix/bin/agent-browser" ]]
"$npm_config_prefix/bin/agent-browser" --version
[[ -x "$npm_config_prefix/bin/skills" ]]
"$npm_config_prefix/bin/skills" --version
npx --no-install skills --version

# Render and exercise the exact chezmoi hooks with the disposable HOME.
for hook in run_after_40-ensure-peekaboo-skill.sh.tmpl run_after_50-ensure-agent-browser.sh.tmpl; do
  rendered="$trial/${hook%.tmpl}"
  chezmoi --source "$repo_root/home" execute-template --file "$repo_root/home/$hook" > "$rendered"
  /bin/bash "$rendered"
done

[[ -s "$HOME/.agents/skills/peekaboo/SKILL.md" ]]
[[ -s "$HOME/.agents/skills/agent-browser/SKILL.md" ]]
[[ ! -e "$HOME/.claude" ]]
"$npm_config_prefix/bin/skills" list -g --json | grep -q 'agent-browser'
[[ ! -e "$HOME/.claude" ]]
node -e '
  const lock=require(process.argv[1]);
  if(lock.skills?.["agent-browser"]?.source!=="vercel-labs/agent-browser"
    || lock.skills?.peekaboo?.source!=="openclaw/Peekaboo")process.exit(1)
' "$HOME/.agents/.skill-lock.json"
"$npm_config_prefix/bin/agent-browser" skills get core >/dev/null
"$npm_config_prefix/bin/agent-browser" skills get electron >/dev/null
peekaboo --version >/dev/null

# Direct reads must work before any browser has been started. Use the actual
# wrapper/CLI against loopback HTTP, with isolated daemon sockets and HOME.
python3 - "$repo_root/home/dot_local/bin/executable_agent-chrome" <<'PYTHON'
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"# Fixture\n\nbrowserless-local-check\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
cli = shutil.which("agent-browser")
with tempfile.TemporaryDirectory(prefix="chrome-read-") as trial:
    env = {"HOME": trial, "PATH": os.environ["PATH"],
           "AGENT_BROWSER_SOCKET_DIR": trial + "/run", "TMPDIR": trial}
    url = f"http://127.0.0.1:{server.server_port}/fixture"
    scenarios = [
        (["read", url], None),
        (["batch", f"read {url}", f"read {url}"], None),
        (["batch"], '[["read", "' + url + '"]]'),
    ]
    home_config = Path(trial) / ".agent-browser/config.json"
    try:
        for args, stdin in scenarios:
            result = subprocess.run([sys.argv[1], *args], env=env, input=stdin,
                                    text=True, capture_output=True, timeout=30, cwd=trial)
            assert result.returncode == 0, (args, result.stdout, result.stderr)
            assert "browserless-local-check" in result.stdout, result.stdout
        # Rejected launch modes must reach the real CLI diagnostic without
        # asking Launch Services to open Chrome. OS commands stay isolated.
        mode_bin = Path(trial) / "bin"
        mode_bin.mkdir()
        for name, body in {
            "pgrep": "#!/bin/sh\nexit 1\n",
            "open": '#!/bin/sh\n: > "$CHROME_MODE_LAUNCH_MARKER"\nexit 99\n',
        }.items():
            command = mode_bin / name
            command.write_text(body)
            command.chmod(0o755)
        marker = Path(trial) / "unexpected-launch"
        env.update(PATH=str(mode_bin) + os.pathsep + env["PATH"],
                   CHROME_MODE_LAUNCH_MARKER=str(marker))
        for args in (["--webgpu", "snapshot"], ["snapshot", "--cdp", "9222"],
                     ["snapshot", "--provider", "example"],
                     ["snapshot", "--ca-cert", "example.pem"]):
            result = subprocess.run([sys.argv[1], *args], env=env,
                                    text=True, capture_output=True, timeout=15, cwd=trial)
            assert result.returncode == 1, (args, result.stdout, result.stderr)
            assert "--auto-connect" in result.stderr, result.stderr
            assert not marker.exists(), args
        # Effective settings are resolved by the real CLI, including private
        # config origins; only synthetic fixtures are created in this test.
        project = Path(trial) / "project"
        project.mkdir()
        (project / "agent-browser.json").write_text('{"webgpu": true}')
        explicit = Path(trial) / "explicit.json"
        explicit.write_text('{"webgpu": true}')
        configured_cases = [
            (["snapshot"], dict(env, AGENT_BROWSER_WEBGPU="1"), trial),
            (["snapshot"], env, str(project)),
            (["--config", str(explicit), "snapshot"], env, trial),
        ]
        for args, case_env, cwd in configured_cases:
            result = subprocess.run([sys.argv[1], *args], env=case_env, cwd=cwd,
                                    text=True, capture_output=True, timeout=15)
            assert result.returncode == 1, (args, result.stdout, result.stderr)
            assert "--auto-connect" in result.stderr, result.stderr
            assert not marker.exists(), args
        result = subprocess.run([sys.argv[1], "--json", "snapshot"],
                                env=dict(env, AGENT_BROWSER_WEBGPU="1"), cwd=trial,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 1, (result.stdout, result.stderr)
        error = json.loads(result.stdout)
        assert error["success"] is False and "--auto-connect" in error["error"]
        assert not marker.exists()
        home_config.parent.mkdir(parents=True, exist_ok=True)
        home_config.write_text('{"webgpu": true}')
        result = subprocess.run([sys.argv[1], "snapshot"], env=env, cwd=trial,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert "--auto-connect" in result.stderr, result.stderr
        assert not marker.exists()
    finally:
        home_config.unlink(missing_ok=True)
        subprocess.run([cli, "--session", "dotfiles-chrome", "close"], env=env,
                       text=True, capture_output=True, timeout=15, cwd=trial)
        server.shutdown()
print("Real wrapper: browserless fetches and rejected launch modes passed without Chrome.")
PYTHON

# Real browser runtime and UI action, with no network services or personal profile.
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e open 'data:text/html,<button onclick="this.textContent=%27clicked%27">click me</button>'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e snapshot | grep -q 'click me'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e click 'button'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e snapshot | grep -q 'clicked'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e close

# Repeated apply must not duplicate skills or damage the browser runtime.
/bin/bash "$trial/run_after_40-ensure-peekaboo-skill.sh"
/bin/bash "$trial/run_after_50-ensure-agent-browser.sh"
echo 'Real macOS computer-use E2E passed: CLIs, skills, Chromium, click, snapshot, repeated apply.'
