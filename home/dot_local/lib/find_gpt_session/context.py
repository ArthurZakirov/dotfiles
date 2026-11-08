"""Translate the current Git editor/browser context into the shared search query."""
from __future__ import annotations

from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit

from .core import SearchRequest


class ContextError(ValueError):
    pass


def _git(path: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(path), *args],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContextError("Git context could not be read") from exc
    if completed.returncode:
        raise ContextError("Select an open Git worktree in VS Code")
    return completed.stdout.strip()


def from_workspace(path: str) -> SearchRequest:
    workspace = Path(path).expanduser()
    if not workspace.is_dir():
        raise ContextError("VS Code workspace directory does not exist")
    root = Path(_git(workspace, "rev-parse", "--show-toplevel"))
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch not in ("main", "master", "develop", "development"):
        return SearchRequest.create("branch", branch)
    # For a primary/default checkout, narrow by the repository name.
    return SearchRequest.create("repo", root.name)


def from_browser_url(raw: str) -> SearchRequest:
    try:
        url = urlsplit(raw)
    except ValueError as exc:
        raise ContextError("Could not parse browser URL") from exc
    if (url.scheme != "https" or url.hostname not in ("github.com", "bitbucket.org")
            or url.username is not None or url.password is not None
            or url.port not in (None, 443)):
        raise ContextError("Open a GitHub or Bitbucket repository/PR in Chrome")
    path = [unquote(part) for part in url.path.strip("/").split("/")]
    if len(path) < 2 or not all(path[:2]):
        raise ContextError("Open a repository, branch or pull request page")
    owner, repo = path[:2]
    if len(path) >= 4:
        if ((url.hostname == "github.com" and path[2] == "pull") or
            (url.hostname == "bitbucket.org" and path[2] == "pull-requests")):
            if path[3].isdigit():
                return SearchRequest.create(
                    "pr", f"https://{url.hostname}/{owner}/{repo}/{path[2]}/{path[3]}"
                )
        if url.hostname == "github.com" and path[2] == "commit":
            return SearchRequest.create("commit", path[3])
        if url.hostname == "bitbucket.org" and path[2] == "commits":
            return SearchRequest.create("commit", path[3])
        if url.hostname == "github.com" and path[2] == "tree":
            # A branch containing slashes cannot be distinguished reliably
            # from a file path without querying refs. Favor the repo over a
            # potentially incorrect branch.
            if len(path) == 4 and path[3] not in ("main", "master", "develop", "development"):
                return SearchRequest.create("branch", path[3])
            return SearchRequest.create("repo", repo)
        if url.hostname == "bitbucket.org" and path[2] == "branch":
            branch = "/".join(path[3:])
            return SearchRequest.create("repo", repo) if branch in ("main", "master", "develop", "development") else SearchRequest.create("branch", branch)
    return SearchRequest.create("repo", repo)
