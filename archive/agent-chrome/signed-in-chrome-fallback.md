# Signed-in Chrome fallback

## Attach and select a tab

Start with a read-only check in the same shell context you will use for the task.

```sh
agent-chrome tab list
```

Continue when the command lists tabs. The wrapper handles Chrome startup,
connection reuse and recovery. Omit session, connection and state persistence
flags. Use the installed Agent Browser skill for subcommand syntax. If
`agent-chrome` is missing from `PATH`, use `~/.local/bin/agent-chrome`.

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

When the task is done, close only the task tab you opened. Leave the shared session running.

```sh
agent-chrome tab close example-task-01
```

## Recover from command results

Use the current command's output and running or exited state to choose the next action.

- **Tabs listed or recovery succeeded.** Continue through `agent-chrome`.
  If the wrapper says the original action was not repeated, inspect the page
  before deciding whether that action is still needed.
- **Chrome is waiting for approval.** Ask the user to review Chrome’s prompt.
  While the command is running, wait for that same command to finish.
- **Previous connection awaiting confirmation.** Stop browser attempts.
  After the user confirms the previous dialog is resolved and authorizes
  another attempt, run this read-only check once.

  ```sh
  AGENT_CHROME_RETRY_AFTER_APPROVAL=1 agent-chrome tab list
  ```

- **Access denied before connecting.** If the runtime reports that process,
  listener or localhost inspection was denied, use the runtime’s supported
  permission flow for one read-only `agent-chrome tab list`. A Chrome timeout
  or pending approval is handled by the preceding rule.
- **Chrome unavailable.** The wrapper opens ordinary Chrome when it confirms
  the app is closed. Report its specific failure if it cannot launch or
  identify Chrome. Ask the user to enable `chrome://inspect/#remote-debugging`
  only when there is evidence debugging is disabled. The user handles this
  setting and Chrome’s approval. Avoid manual port guesses, alternate tools
  and further attachment attempts after a failed connection.
- **Interrupted action.** Once access is restored, verify the result in the
  task tab before repeating any operation that could already have taken effect.
- **Pinned tab gone.** If the command reports `tab_gone`, run
  `agent-chrome tab new <url>` to bind a fresh task tab, then take
  a new snapshot.
