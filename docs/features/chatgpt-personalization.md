# ChatGPT personalization instructions

[← Features](README.md) · [Local Agent Skills via MCP](chatgpt-skills-mcp.md)

DevMac manages a local copy of [ChatGPT personalization instructions](../../home/dot_config/chatgpt/personalization-instructions.md) on **personal** macOS profiles. They tell ChatGPT how to use the Mac's remote connection, `AGENTS.md`, and local skills without interrupting ordinary conversations. This file is kept in Git; ChatGPT's account settings are **not** writable through chezmoi.

## Publish changes to ChatGPT manually

1. Run `chezmoi diff` to review changes and `chezmoi apply` after approving them. Chezmoi installs the file at `~/.config/chatgpt/personalization-instructions.md`.
2. At the end of `chezmoi apply`, the [post-apply hook](../../home/run_after_90-chatgpt-personalization.sh.tmpl) prints the **absolute file path** and [ChatGPT Custom Instructions](https://chatgpt.com/settings/personalization?instructions=chatgpt).
3. Open the printed file, copy its **entire contents**, open the printed ChatGPT link, and paste the contents into the custom-instructions field. Save in ChatGPT. Repeat after future updates; `chezmoi apply` cannot publish the text to your account.

To check the current character count against ChatGPT's field limit:

```sh
wc -m "$HOME/.config/chatgpt/personalization-instructions.md"
```

The professional profile does not manage this file or print the reminder. The reminder only displays paths and instructions; it does not open a browser, change ChatGPT settings, or copy anything to the clipboard.
