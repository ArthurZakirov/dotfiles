#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title chezmoi diff
# @raycast.mode silent
# @raycast.packageName DevMac Workflows
# @raycast.description Preview changes managed by chezmoi in a terminal

exec "$HOME/.config/raycast/lib/run-workflow.sh" chezmoi-diff
