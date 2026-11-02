#!/usr/bin/env python3
"""Navigate between existing Git worktrees and Bitbucket branches or pull requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from urllib.parse import quote, unquote, urlencode, urlsplit


class NavigationError(Exception):
    pass


def git(path, *args, optional=False):
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), *args],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode:
        if optional:
            return ""
        raise NavigationError(f"Git {args[0]} failed in {path}.")
    return result.stdout


def repository_identity(remote):
    # Remote URLs can contain authentication data. Never include them in errors.
    scp = re.fullmatch(r"(?:[^@/]+@)?bitbucket\.org:([^/]+)/([^/]+?)(?:\.git)?/?", remote)
    if scp:
        return scp.group(1).lower(), scp.group(2).lower()
    try:
        parsed = urlsplit(remote)
        if parsed.hostname != "bitbucket.org" or parsed.scheme not in ("https", "ssh"):
            return None
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2:
            return None
        return unquote(parts[0]).lower(), unquote(parts[1]).removesuffix(".git").lower()
    except ValueError:
        return None


def parse_branch_url(url):
    try:
        parsed = urlsplit(url)
        parts = parsed.path.split("/", 4)
        if (parsed.scheme != "https" or parsed.hostname != "bitbucket.org"
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or len(parts) != 5 or parts[3] != "branch"
                or not parts[1] or not parts[2] or not parts[4]):
            raise ValueError
        branch = unquote(parts[4])
        checked = subprocess.run(
            ["git", "check-ref-format", "refs/heads/" + branch],
            capture_output=True, timeout=10,
        )
        if checked.returncode or branch == "HEAD":
            raise ValueError
        return (unquote(parts[1]).lower(), unquote(parts[2]).lower()), branch
    except ValueError:
        raise NavigationError("Use an https://bitbucket.org/<workspace>/<repo>/branch/<branch> URL.") from None


def remotes(path):
    return {
        name: repository_identity(git(path, "remote", "get-url", name).strip())
        for name in git(path, "remote").splitlines()
    }


def find_worktree(root, identity, branch):
    if not root.is_dir():
        raise NavigationError(f"Repository directory does not exist: {root}")
    matches = set()
    found_repository = False
    for repo in sorted(root.iterdir()):
        if not repo.is_dir() or not (repo / ".git").exists():
            continue
        if identity not in remotes(repo).values():
            continue
        found_repository = True
        records = git(repo, "worktree", "list", "--porcelain", "-z").split("\0\0")
        for record in records:
            fields = record.split("\0")
            paths = [field[9:] for field in fields if field.startswith("worktree ")]
            if (f"branch refs/heads/{branch}" in fields and paths
                    and Path(paths[0]).is_dir()):
                matches.add(Path(paths[0]).resolve())
    if not matches:
        detail = "No existing worktree for that branch" if found_repository else "No matching repository"
        raise NavigationError(f"{detail} under {root}. Nothing was checked out or created.")
    if len(matches) > 1:
        raise NavigationError("Multiple matching worktrees; open one explicitly:\n" + "\n".join(map(str, sorted(matches))))
    return next(iter(matches))


def branch_url(path):
    branch = git(path, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True).strip()
    if not branch:
        raise NavigationError("This worktree has a detached HEAD; open a named branch first.")
    identities = remotes(path)
    preferred = (
        git(path, "config", "--get", f"branch.{branch}.pushRemote", optional=True).strip()
        or git(path, "config", "--get", "remote.pushDefault", optional=True).strip()
        or git(path, "config", "--get", f"branch.{branch}.remote", optional=True).strip()
    )
    if preferred:
        identity = identities.get(preferred)
    elif identities.get("origin"):
        identity = identities["origin"]
    else:
        available = {value for value in identities.values() if value}
        if len(available) != 1:
            raise NavigationError("Choose a Bitbucket remote with branch.<branch>.remote or remote.pushDefault.")
        identity = next(iter(available))
    if not identity:
        raise NavigationError("The selected Git remote is not a supported Bitbucket Cloud repository.")
    workspace, repo = identity
    return f"https://bitbucket.org/{quote(workspace, safe='')}/{quote(repo, safe='')}/branch/{quote(branch, safe='')}"


def hammerspoon(lua):
    result = subprocess.run(["hs", "-c", lua], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise NavigationError("Hammerspoon is unavailable. Start it before using PR navigation.")
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise NavigationError("Hammerspoon did not return a valid browser response.") from None


def lua_string(value):
    equals = "="
    while "]" + equals + "]" in value:
        equals += "="
    return "[" + equals + "[" + value + "]" + equals + "]"


def chrome(applescript):
    data = hammerspoon(
        "local ok,r=hs.osascript.applescript(" + lua_string(applescript) + "); "
        "return hs.json.encode({ok=ok,value=ok and r or nil})"
    )
    if not data.get("ok"):
        raise NavigationError("Cannot read the Bitbucket tab. Check Chrome's Allow JavaScript from Apple Events setting.")
    return data["value"]


def bitbucket_tab(fallback_url):
    return chrome('''tell application "Google Chrome"
      if (count windows) = 0 then make new window
      set w to front window
      set t to active tab of w
      if URL of t starts with "https://bitbucket.org/" then return {id of w, id of t}
      repeat with w in windows
        repeat with t in tabs of w
          if URL of t starts with "https://bitbucket.org/" then return {id of w, id of t}
        end repeat
      end repeat
      set w to front window
      set t to make new tab at end of tabs of w with properties {URL:''' + json.dumps(fallback_url) + '''}
      return {id of w, id of t}
    end tell''')


def chrome_javascript(tab, javascript):
    window_id, tab_id = (json.dumps(str(int(value))) for value in tab)
    return chrome(f'''tell application "Google Chrome"
      tell window id {window_id}
        repeat with t in tabs
          if id of t = {tab_id} then return execute t javascript {json.dumps(javascript)}
        end repeat
      end tell
      error "The selected Bitbucket tab was closed"
    end tell''')


def browser_api(tab, endpoint):
    if not endpoint.startswith("/!api/2.0/repositories/"):
        raise NavigationError("Refusing an unexpected Bitbucket API path.")
    request_id = json.dumps(uuid.uuid4().hex)
    start = '''(() => {
      if (location.origin !== 'https://bitbucket.org') return 'loading';
      const requests = window.__dotfilesBitbucketRequests ||= {};
      const key = REQUEST_ID;
      requests[key] = {state:'pending'};
      (async () => {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 12000);
        try {
          const response = await fetch(ENDPOINT, {credentials:'same-origin', signal:controller.signal});
          requests[key] = response.ok
            ? {state:'done', data:await response.json()}
            : {state:'error', status:response.status};
        } catch (_) { requests[key] = {state:'error'}; }
        finally { clearTimeout(timer); }
      })();
      return 'started';
    })()'''.replace("REQUEST_ID", request_id).replace("ENDPOINT", json.dumps(endpoint))
    poll = '''(() => {
      if (location.origin !== 'https://bitbucket.org') return JSON.stringify({state:'changed'});
      const requests = window.__dotfilesBitbucketRequests || {};
      const key = REQUEST_ID;
      const result = requests[key] || {state:'changed'};
      if (result.state !== 'pending') delete requests[key];
      return JSON.stringify(result);
    })()'''.replace("REQUEST_ID", request_id)
    # AppleScript accepts quoted JavaScript as one line; keep browser I/O asynchronous.
    start = " ".join(start.splitlines())
    poll = " ".join(poll.splitlines())
    deadline = time.monotonic() + 18
    while chrome_javascript(tab, start) == "loading":
        if time.monotonic() >= deadline:
            raise NavigationError("Bitbucket did not load in Chrome. Open it and try again.")
        time.sleep(0.2)
    while time.monotonic() < deadline:
        result = json.loads(chrome_javascript(tab, poll))
        if result["state"] == "done":
            return result["data"]
        if result["state"] == "error":
            status = result.get("status", "network error")
            raise NavigationError(f"Bitbucket lookup failed ({status}). Check access in Chrome; no separate extension login is needed.")
        if result["state"] == "changed":
            raise NavigationError("The Bitbucket tab navigated during lookup. Try again.")
        time.sleep(0.2)
    raise NavigationError("Bitbucket lookup timed out. Try again when the browser is ready.")


def pr_page(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/([\w.-]+)/([\w.-]+)/pull-requests/([1-9][0-9]*)(?:/.*)?", parsed.path)
    if (parsed.scheme != "https" or parsed.hostname != "bitbucket.org" or parsed.username
            or parsed.password or parsed.port not in (None, 443) or not match):
        raise NavigationError("Use a Bitbucket branch or pull request URL.")
    return match.groups()


def source_branch_url(url):
    workspace, repo, pr_id = pr_page(url)
    endpoint = f"/!api/2.0/repositories/{workspace}/{repo}/pullrequests/{pr_id}?fields=source.branch.name,source.repository.full_name"
    data = browser_api(bitbucket_tab(url), endpoint)
    try:
        source = data["source"]
        identity = source["repository"]["full_name"].split("/")
        if len(identity) != 2:
            raise ValueError
        branch = source["branch"]["name"]
        result = "https://bitbucket.org/" + "/".join(quote(part, safe="") for part in identity)
        result += "/branch/" + quote(branch, safe="")
        parse_branch_url(result)
        return result
    except (KeyError, TypeError, ValueError):
        raise NavigationError("The PR has no usable source repository and branch.") from None


def open_pull_requests(url):
    identity, branch = parse_branch_url(url)
    repository = "/".join(identity)
    query = "source.branch.name = " + json.dumps(branch) + " AND source.repository.full_name = " + json.dumps(repository)
    endpoint = f"/!api/2.0/repositories/{repository}/pullrequests?" + urlencode({
        "q": query, "state": "OPEN", "pagelen": 50,
        "fields": "next,values.id,values.title,values.source.branch.name,values.source.repository.full_name,values.destination.branch.name",
    })
    tab = bitbucket_tab(url)
    candidates = {}
    seen = set()
    while endpoint:
        if endpoint in seen:
            raise NavigationError("Bitbucket returned a repeated results page.")
        seen.add(endpoint)
        data = browser_api(tab, endpoint)
        for item in data["values"]:
            source = item["source"]
            if source["branch"]["name"] != branch or source["repository"]["full_name"].lower() != repository:
                continue
            number = int(item["id"])
            if number <= 0:
                raise NavigationError("Bitbucket returned an invalid PR number.")
            candidates[number] = {
                "text": f"#{number} {item['title']}",
                "subText": f"{repository}: {branch} → {item['destination']['branch']['name']}",
                "url": f"https://bitbucket.org/{repository}/pull-requests/{number}",
            }
        next_url = data.get("next")
        endpoint = ""
        if next_url:
            parsed = urlsplit(next_url)
            if parsed.scheme != "https" or parsed.hostname not in ("api.bitbucket.org", "bitbucket.org"):
                raise NavigationError("Refusing an unexpected Bitbucket pagination URL.")
            path = "/!api" + parsed.path if parsed.hostname == "api.bitbucket.org" else parsed.path
            endpoint = path + ("?" + parsed.query if parsed.query else "")
    return list(candidates.values())


def launch(command):
    result = subprocess.run(command, capture_output=True, timeout=30)
    if result.returncode:
        raise NavigationError("Application launch failed. Check that VS Code or Google Chrome is installed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("open-local", help="Open a Bitbucket branch or PR's existing worktree in VS Code")
    local.add_argument("url")
    local.add_argument("--repos-root", type=Path, default=Path.home() / "repos")
    local.add_argument("--print", action="store_true", dest="print_only", help="Print the path without opening VS Code")
    remote = commands.add_parser("open-remote", help="Open this worktree's branch in Chrome")
    remote.add_argument("--path", type=Path, default=Path.cwd())
    remote.add_argument("--print", action="store_true", dest="print_only", help="Print the URL without opening Chrome")
    pr = commands.add_parser("open-pr", help="Open this worktree's open PR, or choose between matching PRs")
    pr.add_argument("--path", type=Path, default=Path.cwd())
    pr.add_argument("--print", action="store_true", dest="print_only", help="Print matching PR URLs without opening them")
    args = parser.parse_args()
    try:
        if args.command == "open-local":
            url = source_branch_url(args.url) if "/pull-requests/" in urlsplit(args.url).path else args.url
            identity, branch = parse_branch_url(url)
            target = find_worktree(args.repos_root.expanduser(), identity, branch)
            if not args.print_only:
                code = shutil.which("code")
                if not code:
                    raise NavigationError("VS Code's 'code' command is not on PATH.")
                launch([code, "--new-window", str(target)])
        elif args.command == "open-remote":
            target = branch_url(args.path.expanduser())
            if not args.print_only:
                launch(["/usr/bin/open", "-a", "Google Chrome", target])
        else:
            candidates = open_pull_requests(branch_url(args.path.expanduser()))
            if not candidates:
                raise NavigationError("No open pull request matches this source repository and branch.")
            target = "\n".join(item["url"] for item in candidates)
            if not args.print_only:
                if len(candidates) == 1:
                    launch(["/usr/bin/open", "-a", "Google Chrome", candidates[0]["url"]])
                else:
                    payload = lua_string(json.dumps(candidates))
                    result = hammerspoon("return hs.json.encode({ok=HammerspoonConfig.chooseBitbucketPullRequest(hs.json.decode(" + payload + "))})")
                    if not result.get("ok"):
                        raise NavigationError("The Hammerspoon PR chooser is unavailable. Reload its configuration.")
        print(target)
        return 0
    except (NavigationError, OSError, subprocess.TimeoutExpired) as error:
        message = str(error) if isinstance(error, NavigationError) else "A required command failed or timed out. Check Git and application availability."
        print(f"bitbucket-branch: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
