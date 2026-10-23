#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title config.toml
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open the local Codex configuration in VS Code

exec "$HOME/.config/raycast/lib/open-target.sh" file "$HOME/.codex/config.toml"
