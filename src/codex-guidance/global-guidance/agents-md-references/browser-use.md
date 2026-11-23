# Use the signed-in browser

Use the Browser Use CLI installed by Dotfiles. In the shell that runs a browser
command, put its directory first so an independently installed version cannot
change the workflow.

```sh
export PATH="$HOME/.local/share/dotfiles/browser-use/bin:$PATH"
```

Open regular Chrome on macOS with
`open -a 'Google Chrome'` if it is closed. Keep the default session across
commands. Leave it running when the task ends.

Before visiting a private site, check which browser the command reached.
Browser Use can start a separate Chromium when regular Chrome is unavailable.
Run this check in the same invocation as the first browser action.

```sh
browser-use <<'PY'
from browser_harness.admin import daemon_browser_kind
if daemon_browser_kind(NAME) != "local":
    raise SystemExit("Regular Chrome is unavailable")
print(list_tabs())
PY
```

Use the intended tab or open one task tab with `new_tab(url)`. Verify the URL
and signed-in account before changing anything. For more command examples,
read `browser-use skill show`. Use the local browser for this workflow. A
fresh profile, a cloud browser or a new login does not satisfy a request to
use the existing account.

If Chrome asks for approval, leave the original command running and let the
user review the dialog. If it fails, use `browser-use --doctor` and report
the actual result. Before repeating an interrupted write, check whether it
already took effect.
