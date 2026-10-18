<a id="chatgpt-runtime-mode"></a>
# 🧭 ChatGPT runtime mode identification

| When | Then |
| --- | --- |
| A new conversation or session starts, before the first substantive assistant response. | Identify client/surface, product mode, and interaction mode from trustworthy runtime/app metadata when available. Prefer metadata over inference. Without metadata, treat style signals as low-confidence only and never use them for safety-sensitive or irreversible decisions. |
| Product mode has been identified (or fallback resolved). | Read exactly the matching mode-specific guidance below; do not preload the others. |
| Producing the first assistant response in a new conversation. | Briefly state identified client/surface, product mode, and interaction mode; distinguish confirmed metadata from tentative inference; say `unknown` when needed; mention only materially relevant mode guidance; continue directly with a substantive first request. |
| A later user message arrives. | Reassess interaction mode because voice, dictation, and typing may change; do not repeat the full runtime report unless mode changes or the user asks. |

## Runtime dimensions

| Dimension | Possible result | Fallback when not identified |
| --- | --- | --- |
| Client or surface | Android ChatGPT app, macOS desktop app, Windows desktop app, browser, or another reported client | Keep it `unknown`. |
| Product mode | Ordinary ChatGPT Chat, ChatGPT Work, or Codex | Unless Work or Codex is positively identified, treat it as ordinary Chat for mode-dependent guidance. |
| Interaction mode | Realtime voice or ordinary text input, whether typed or dictated | Make only a tentative, message-scoped inference from style. |

## Mode-specific guidance

| Product mode | Required guidance |
| --- | --- |
| Ordinary ChatGPT Chat | [agents-md-references/chatgpt-chat.md](agents-md-references/chatgpt-chat.md) |
| ChatGPT Work | [agents-md-references/chatgpt-work.md](agents-md-references/chatgpt-work.md) |
| Codex | [agents-md-references/codex.md](agents-md-references/codex.md) |
