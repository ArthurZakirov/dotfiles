#!/bin/bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp"
export PATH='/usr/bin:/bin'
export DOTFILES_ROOT="$repo_root" DOTFILES_PROFILE=professional
mkdir -p "$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin"
cat > "$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" <<'SCRIPT'
#!/bin/sh
[ "$1" = '--version' ] && { echo 'test-version'; exit 0; }
exit 1
SCRIPT
chmod +x "$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
source "$repo_root/src/shell-setup.sh"
configure_vscode_cli
[[ -L "$HOME/.local/bin/code" ]]
[[ "$("$HOME/.local/bin/code" --version)" == test-version ]]
configure_vscode_cli
[[ "$("$HOME/.local/bin/code" --version)" == test-version ]]
echo 'VS Code CLI integration: executable symlink verified in isolated HOME'
