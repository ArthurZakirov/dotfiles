#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Open AWS config
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open the local AWS profiles file in VS Code

exec "$HOME/.config/raycast/lib/open-target.sh" file "$HOME/.aws/config"
