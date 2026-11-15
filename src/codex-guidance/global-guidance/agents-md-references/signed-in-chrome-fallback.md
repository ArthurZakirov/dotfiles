# Signed-in Chrome fallback

## Attach and select a tab

Run `agent-chrome` with ordinary Agent Browser commands. If your shell lacks
`~/.local/bin` in `PATH`, use `~/.local/bin/agent-chrome`. Use
the installed Agent Browser skill for command syntax. The wrapper
attaches to running Chrome with a fixed daemon session and strict tab pinning.
Omit session, connection, and state persistence options. Keep the
daemon running when your task ends.

The daemon shares its selected tab and snapshot references with other callers.
Use a dedicated task tab, verify the selected tab, and take a fresh snapshot
before acting. If you observe that another task is using the session,
coordinate access with the user before proceeding.

For your current task, replace `example-task-01` with a unique task tab
label and `https://example.com` with the intended URL. The label identifies
the tab within the wrapper's fixed daemon session. Follow these steps in order
and inspect each command's result before continuing.

1. **Open and select the task tab.** Open a dedicated tab with your label and
   URL.

   ```sh
   agent-chrome tab new --label example-task-01 https://example.com
   ```

   Select the tab by its label.

   ```sh
   agent-chrome tab example-task-01
   ```

2. **Verify the URL.** Read the URL of the selected tab.

   ```sh
   agent-chrome get url
   ```

   If the URL differs from the intended page, stop before taking a snapshot
   or acting. Confirm the task tab's label, reselect it using step 1's
   selection command, and repeat the URL check. Continue to step 3 only
   when the URL matches.

3. **Take a fresh snapshot.** Inspect the selected page before acting.

   ```sh
   agent-chrome snapshot
   ```

   If the snapshot differs from the intended page, stop before acting.
   Confirm the label, reselect the tab, and repeat steps 2 and 3. Continue
   only when both checks match the intended page.

   If the title helps with the current task, read it after verifying the
   page.

   ```sh
   agent-chrome get title
   ```

## Close the task tab

When the task is done, close only the task tab you opened.

```sh
agent-chrome tab close example-task-01
```

## Recover from command results

Use the current command's output and running or exited state to choose the next action.

- **Chrome unavailable.** If the command reports that it found no running
  debuggable Chrome, share that result and ask the user to open regular Chrome
  and enable remote debugging at `chrome://inspect/#remote-debugging`. After
  the user confirms setup and the previous attempt has ended, check the
  connection with `agent-chrome tab list`.
- **Approval pending.** Ask the user to review the Chrome prompt and click
  **Allow** if they approve. The user handles Chrome settings and approval.
  If the command is still waiting, let that same invocation finish after the
  user clicks **Allow** and inspect its result. If the attempt ended while
  waiting for approval, retry with the read-only `agent-chrome tab list`
  after the user confirms approval.
- **Connection interrupted.** After Chrome or the daemon recovers and the
  previous command has ended, check the connection with
  `agent-chrome tab list`. If a write may have run before the
  interruption, verify its outcome before deciding whether to repeat it.
- **Pinned tab gone.** If the command reports `tab_gone`, run
  `agent-chrome tab new <url>` to bind a fresh task tab, then take
  a new snapshot.
