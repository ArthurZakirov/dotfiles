# Use signed-in Chrome on macOS

Run `browser-use-signed-in` for an operation in regular Google Chrome. It opens
Chrome if needed and reuses the Dotfiles connection. To see which tab belongs
to the task, pass Browser Use Python on standard input.

```sh
browser-use-signed-in <<'PY'
print(list_tabs())
PY
```

Keep the task tab ID. In each invocation that edits a page, select that ID
with `switch_tab(target_id)`, check the URL and account, then perform the
action in that invocation. Open a task tab with `new_tab(url)` if needed. Read the managed CLI's helper syntax with
`~/.local/share/dotfiles/browser-use/bin/browser-use skill show`.

## Recover and finish the task

- **Command missing.** Try `~/.local/bin/browser-use-signed-in --check`.
  If the managed installation is incomplete, repair it through the Dotfiles
  installation workflow before using this command.
- **Access denied.** Use the runtime's supported approval mechanism for a
  read-only `browser-use-signed-in --check` if available. If it succeeds,
  continue through the same authorized execution context. A denied profile
  read does not tell you whether Chrome's debugging setting is enabled.
- **Browser access unavailable.** Try an already authorized browser extension
  or native computer-use tool on the visible regular Chrome window. Verify the
  intended account and tab, then complete and check the original task there.
  A fresh Chromium, a cloud browser and an in-app browser with a different
  account are unsuitable. Leave privacy settings and approval buttons to the user.
- **Approval in progress.** Keep the pending attempt alive. If the task requires
  that connection, ask the user to review the visible Chrome prompt once.
  Do not issue parallel connections or reset the shared session.
- **All authorized routes blocked.** Report the exact failed check. For a
  missing debugging endpoint, open Chrome's setup page for the user
  (`open -b com.google.Chrome 'chrome://inspect/#remote-debugging'`) and
  ask them to enable remote debugging if off. For a denied file read, request
  access only for the identified host through its supported permission flow.
  Do not infer a particular System Settings switch from the file error alone.
- **Interrupted edit.** Read back the affected record before repeating any
  write through either interface. Confirm the saved outcome in the target site.
