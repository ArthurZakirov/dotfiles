#!/usr/bin/env python3
"""Idempotently merge portable Git PR navigation into global VS Code shortcuts.

Preserve existing unrelated tasks and bindings; VS Code JSONC is supported.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile


TASK_LABEL = "Git: Open Current Pull Request in Chrome"
BRANCH_LABEL = "Git: Open Current Branch in Chrome"
REVIEW_CLEANUP_LABEL = "Git: Unreview All"
OLD_PR_LABEL = "Bitbucket: Open Current Pull Request in Chrome"
OLD_BRANCH_LABEL = "Bitbucket: Open Current Branch in Chrome"


def strip_jsonc(source: str) -> str:
    # Preserve quoted strings while removing // and /* */ comments.
    output: list[str] = []
    i = 0
    in_string = False
    while i < len(source):
        char = source[i]
        if in_string:
            output.append(char)
            if char == "\\" and i + 1 < len(source):
                i += 1
                output.append(source[i])
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            output.append(char)
        elif source.startswith("//", i):
            end = source.find("\n", i)
            if end == -1:
                break
            output.append("\n")
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end == -1:
                raise ValueError("Unterminated JSONC comment")
            output.append("\n" * source[i:end + 2].count("\n"))
            i = end + 1
        else:
            output.append(char)
        i += 1
    # After comments are removed, trailing commas are the only JSONC extension.
    cleaned = "".join(output)
    return re.sub(r",(?=\s*[}\]])", "", cleaned)


def load(path: Path, default):
    if not path.exists():
        return default, ""
    source = path.read_text()
    try:
        return json.loads(strip_jsonc(source)), source
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot safely parse VS Code config: {path}") from exc


def structural_tokens(source: str):
    """Return bracket tokens, ignoring JSONC comments and quoted strings."""
    tokens = []
    i, quoted = 0, False
    while i < len(source):
        c = source[i]
        if quoted:
            if c == "\\":
                i += 1
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            continue
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end < 0:
                raise ValueError("Unterminated VS Code JSONC comment")
            i = end + 2
            continue
        elif c in "{}[]":
            tokens.append((i, c))
        i += 1
    return tokens


def array_entries(source: str, key: str | None):
    tokens = structural_tokens(source)
    if key is None:
        opening = next(pos for pos, token in tokens if token == "[")
    else:
        marker = re.search(r'"tasks"\s*:\s*\[', source)
        if not marker:
            raise ValueError("VS Code tasks array is missing")
        opening = marker.end() - 1
    stack, entries, start = [], [], None
    for pos, token in tokens:
        if pos < opening:
            continue
        if token in "[{":
            if token == "{" and len(stack) == 1:
                start = pos
            stack.append(token)
        else:
            if not stack or stack[-1] != {"]": "[", "}": "{"}[token]:
                raise ValueError("Malformed JSONC brackets")
            if token == "}" and len(stack) == 2 and start is not None:
                entries.append((start, pos + 1, json.loads(strip_jsonc(source[start:pos + 1]))))
                start = None
            stack.pop()
            if not stack:
                return opening, pos, entries
    raise ValueError("Unterminated VS Code JSONC array")


def merge_source(source: str, updated, is_tasks: bool) -> str:
    if not source:
        return json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
    labels = (TASK_LABEL, BRANCH_LABEL, REVIEW_CLEANUP_LABEL) if is_tasks else (TASK_LABEL,)
    for label in labels:
        key = "tasks" if is_tasks else None
        opening, closing, entries = array_entries(source, key)
        if is_tasks:
            value = next(item for item in updated["tasks"] if item["label"] == label)
            old = (OLD_PR_LABEL if label == TASK_LABEL else
                   OLD_BRANCH_LABEL if label == BRANCH_LABEL else None)
            matches = [(a, b) for a, b, item in entries
                       if item.get("label") in (label, old)]
        else:
            value = next(item for item in updated if item.get("args") == TASK_LABEL
                         and item.get("key") == "ctrl+p ctrl+r")
            matches = [(a, b) for a, b, item in entries if
                       item.get("key") == "ctrl+p ctrl+r"
                       and item.get("command") == "workbench.action.tasks.runTask"
                       and item.get("args") in (TASK_LABEL, OLD_PR_LABEL)]
        if len(matches) > 1:
            raise ValueError(f"Duplicate VS Code PR integration: {label}")
        if matches:
            start, end = matches[0]
            indent = source[source.rfind("\n", 0, start) + 1:start]
            if indent.strip():
                # Single-line JSONC array: keep the replacement on one line.
                formatted = json.dumps(value, ensure_ascii=False)
            else:
                lines = json.dumps(value, indent=2, ensure_ascii=False).splitlines()
                formatted = lines[0] + "".join("\n" + indent + line for line in lines[1:])
            source = source[:start] + formatted + source[end:]
        else:
            indent = (source[source.rfind("\n", 0, entries[0][0]) + 1:entries[0][0]]
                      if entries else "    ")
            if indent.strip():
                indent = "    "  # Inline JSON arrays do not have leading indentation.
            lines = json.dumps(value, indent=2, ensure_ascii=False).splitlines()
            formatted = "\n".join(indent + line for line in lines)
            if entries:
                last = entries[-1][1]
                if strip_jsonc(source[last:closing]).lstrip().startswith(","):
                    # Keep the existing trailing comma as the separator from
                    # the old entry; append the new one before the closing ].
                    source = source[:closing] + "\n" + formatted + source[closing:]
                else:
                    source = source[:last] + ",\n" + formatted + source[last:]
            else:
                source = source[:opening + 1] + "\n" + formatted + "\n" + source[closing:]
    if json.loads(strip_jsonc(source)) != updated:
        raise ValueError("VS Code update would modify unrelated settings")
    return source


def save(path: Path, updated, original: str) -> bool:
    # Only replace/append integration objects. Leave comments, whitespace and
    # unrelated user-owned JSONC settings untouched.
    content = merge_source(original, updated, path.name == "tasks.json")
    if original == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        file.write(content)
        temp = Path(file.name)
    temp.chmod(mode)
    os.replace(temp, path)
    return True


def task(label: str, action: str) -> dict:
    return {
        "label": label,
        "type": "process",
        "command": "${userHome}/.local/bin/git-pr",
        "args": [action, "--path", "${workspaceFolder}"],
        "problemMatcher": [],
        "presentation": {"reveal": "silent", "panel": "dedicated",
                         "showReuseMessage": False},
    }


def review_cleanup_task() -> dict:
    return {
        "label": REVIEW_CLEANUP_LABEL,
        "type": "process",
        "command": "git",
        "args": ["unreview-all"],
        "options": {"cwd": "${workspaceFolder}"},
        "problemMatcher": [],
        "presentation": {"reveal": "silent", "panel": "dedicated", "close": True},
    }


def update_tasks(existing: dict) -> bool:
    tasks = existing.setdefault("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("VS Code tasks must be a list")
    before = json.dumps(tasks, sort_keys=True)
    specs = [(TASK_LABEL, OLD_PR_LABEL, "open-pr"),
             (BRANCH_LABEL, OLD_BRANCH_LABEL, "open-remote")]
    for label, legacy, action in specs:
        candidates = [entry for entry in tasks if entry.get("label") in (label, legacy)]
        if len(candidates) > 1:
            raise ValueError(f"Duplicate VS Code tasks for {label}")
        if candidates:
            # Change only the migrated task, retain unrelated task settings.
            entry = candidates[0]
            entry.update(task(label, action))
        else:
            tasks.append(task(label, action))
    review_tasks = [entry for entry in tasks if entry.get("label") == REVIEW_CLEANUP_LABEL]
    if len(review_tasks) > 1:
        raise ValueError(f"Duplicate VS Code tasks for {REVIEW_CLEANUP_LABEL}")
    if review_tasks:
        review_tasks[0].update(review_cleanup_task())
    else:
        tasks.append(review_cleanup_task())
    existing.setdefault("version", "2.0.0")
    return before != json.dumps(tasks, sort_keys=True)


def update_bindings(existing: list) -> bool:
    before = json.dumps(existing, sort_keys=True)
    legacy = [item for item in existing if item.get("key") == "ctrl+p ctrl+r"
              and item.get("command") == "workbench.action.tasks.runTask"
              and item.get("args") in (OLD_PR_LABEL, TASK_LABEL)]
    if len(legacy) > 1:
        raise ValueError("Duplicate Ctrl+P Ctrl+R PR bindings")
    binding = {
        "key": "ctrl+p ctrl+r",
        "command": "workbench.action.tasks.runTask",
        "args": TASK_LABEL,
        "when": "workspaceFolderCount > 0",
    }
    if legacy:
        legacy[0].update(binding)
    else:
        existing.append(binding)
    return before != json.dumps(existing, sort_keys=True)


def install(user: Path) -> None:
    tasks_file = user / "tasks.json"
    keys_file = user / "keybindings.json"
    tasks, old_tasks = load(tasks_file, {"version": "2.0.0", "tasks": []})
    keys, old_keys = load(keys_file, [])
    if not isinstance(tasks, dict) or not isinstance(keys, list):
        raise ValueError("Invalid VS Code tasks/keybindings document structure")
    changed_tasks = update_tasks(tasks)
    changed_keys = update_bindings(keys)
    # Parse and validate both documents before changing either file.
    if changed_tasks:
        save(tasks_file, tasks, old_tasks)
    if changed_keys:
        save(keys_file, keys, old_keys)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", required=True)
    parser.add_argument("--user-dir", type=Path,
                        default=Path.home() / "Library/Application Support/Code/User")
    args = parser.parse_args()
    install(args.user_dir)


if __name__ == "__main__":
    main()
