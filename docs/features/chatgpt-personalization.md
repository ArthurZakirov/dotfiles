# ChatGPT personalization instructions

[← Features](README.md) · [Local Agent Skills via MCP](chatgpt-skills-mcp.md)

The [ChatGPT personalization instructions](../../src/chatgpt/personalization-instructions.md) live **once** in the DevMac Git repository. They tell ChatGPT how to use the Mac's remote connection, `AGENTS.md`, and local skills without interrupting ordinary conversations. Chezmoi never installs a duplicate under `$HOME`, and it cannot write to ChatGPT's account settings.

## Publish changes to ChatGPT manually

**Open ChatGPT Custom Instructions directly:** [https://chatgpt.com/settings/personalization?instructions=chatgpt](https://chatgpt.com/settings/personalization?instructions=chatgpt)

1. Edit the linked Markdown file in the Dotfiles checkout and review it with Git (`git diff -- src/chatgpt/personalization-instructions.md`). Since it is repository documentation rather than a managed destination file, `chezmoi diff` does not show its changes.
2. On a **personal** profile, run `chezmoi apply`. The [after-apply hook](../../home/run_after_90-chatgpt-personalization.sh.tmpl) prints the **absolute path to that same file in the checkout** and the ChatGPT settings URL.
3. Open the printed file, copy its **entire contents**, paste them into the custom-instructions field, and save in ChatGPT. Repeat when the instructions change; `chezmoi apply` cannot publish them to your account.

To check the character limit on the source file:

```sh
repo="$(git -C "$(chezmoi source-path)" rev-parse --show-toplevel)"
wc -m "$repo/src/chatgpt/personalization-instructions.md"
```

The professional profile does not print this reminder. The hook does not copy the file, open a browser, modify ChatGPT settings, or touch the clipboard.
