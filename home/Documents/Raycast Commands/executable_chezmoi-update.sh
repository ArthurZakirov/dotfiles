#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title chezmoi update
# @raycast.mode silent
# @raycast.packageName DevMac Workflows
# @raycast.description Update chezmoi sources and apply interactively

exec "$HOME/.config/raycast/lib/run-workflow.sh" chezmoi-update
