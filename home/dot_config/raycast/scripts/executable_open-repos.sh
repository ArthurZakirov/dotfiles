#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title repos
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open the repositories folder in VS Code

root="$("$HOME/.config/raycast/lib/resolve-repos-dir.sh")" || exit 1
exec "$HOME/.config/raycast/lib/open-target.sh" directory "$root"
