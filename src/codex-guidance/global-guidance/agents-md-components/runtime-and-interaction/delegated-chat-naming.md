<a id="delegated-chat-naming"></a>
# 🏷️ Delegated chat naming

| When | Then |
| --- | --- |
| An orchestrator creates a separate user-visible chat to perform delegated worker work. | Set its title at creation time to `[DELEGIERT] <topic or outcome>`. Keep the text after the prefix concise and specific. |
| A chat is the user-facing orchestrator, an ordinary standalone chat, or a native internal subagent thread rather than a separate user-visible delegated chat. | Do not add the delegated prefix; retain the normal topic- or outcome-based title. |
| The user explicitly requests a different exact title for a delegated chat. | Follow the user's exact title instead of imposing the default prefix. |
