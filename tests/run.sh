#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$repo_root/src/homebrew.sh" "$repo_root/src/shell-setup.sh"
bash "$repo_root/tests/test_shell_setup_module.sh"
python3 "$repo_root/scripts/verify.py"
git -C "$repo_root" diff --check
