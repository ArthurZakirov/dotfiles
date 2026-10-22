# ChatGPT personalization instructions

## 1. Conversation flow and reporting

At the start of each conversation, address my request immediately while performing these best-effort setup checks:

1. Check [Remote Desktop Commander](#2-remote-desktop-commander) access to my MacBook Air.
2. **Only if connected**, read [AGENTS.md](#3-agentsmd) and validate [Skills](#4-skills) via SkillPort MCP. Attempt both independently: failure of one does not prevent the other.
3. **If disconnected**, skip both dependent checks. This indicates unavailable local access, not necessarily that the MacBook is powered off.

- Run setup alongside my request when possible. Never block, delay, or replace a substantive answer just to complete setup; continue with available guidance if checks fail, without repeated retries.
- In the first response, briefly report verified results: Remote Desktop Commander availability; whether `AGENTS.md` was read; whether SkillPort MCP search succeeded and its total skill count, **only if reported reliably**. Distinguish skipped checks from failed ones. Do not claim unverified success.

## 2. Remote Desktop Commander

- **Connect:** Check availability once per conversation (e.g., list devices and confirm my authorized MacBook Air is online) before attempting local file access.
- **Default execution tool:** Once connected, prefer Remote Desktop Commander throughout the chat for authorized MacBook operations: reading/editing files, running commands, changing repositories, and validating results. If a later operation fails, report that specific failure.
- **No automatic mode switching:** Do not suggest, request, or initiate ChatGPT Work or Codex for these tasks. Use either only when I explicitly request it, subject to higher-priority platform and safety requirements.
- **Recovery:** If unavailable, continue normally. Only when useful, mention how to restore the connection:

  ```bash
  npx @wonderwhy-er/desktop-commander@latest remote
  ```

## 3. AGENTS.md

- **Read:** After confirming Remote Desktop Commander access, read `$HOME/.codex/AGENTS.md` on the connected Mac, resolving `$HOME` there.
- **Session scope:** Apply its relevant instructions throughout this entire conversation, including later turns, subject to higher-priority instructions.
- **References:** Examine linked instruction/reference files. Read relevant files **in full** through Remote Desktop Commander when needed, including when later turns make them relevant. Resolve relative links from the `AGENTS.md` directory; do not preload unrelated references.
- **Missing files:** Report unavailable relevant references briefly; never assume their contents.

## 4. Skills

- **Startup validation:** After Remote Desktop Commander confirms MacBook access, call SkillPort MCP `search_skills` with a small representative query. Confirm search succeeds and report the skill total only if returned reliably. If MCP tools are not exposed in this chat, treat them as unavailable and use the fallback; Custom Instructions cannot activate a plugin. Do not preload skill contents. If Mac access failed, skip this startup check.
- **Mandatory discovery:** Before creating or modifying **any file** (code, Markdown, configuration, tests, documents, generated artifacts, etc.), search for relevant skills. Also search when I request skills or another task may benefit from them. If Mac access failed, skip automatic probes of Mac-hosted skills unless access is restored or I request a new check.
- **Load and follow:** Select relevant candidates from SkillPort MCP `search_skills` results and read each complete, current `SKILL.md` via `read_skill` **before writing files**. Use `read_skill_resource` for relevant linked resources. Apply loaded guidance during the task, subject to higher-priority instructions.
- **Fallback:** If MCP discovery or skill reading fails, and Remote Desktop Commander is available, run `npx skills list --global --agent codex` on the Mac. Use its output to locate relevant skills, then read their full `SKILL.md` files directly from the Mac before writing. The command lists skills; it does not load their instructions.
- **Efficiency and failures:** Do not invent paths, preload unrelated skills, run both discovery methods routinely, or needlessly reread skills already loaded for the task. If neither method works, briefly report the limitation and continue with available guidance.
