#!/usr/bin/env python3
"""Export, compare and explicitly restore macOS native keyboard shortcuts."""

import argparse
import copy
import json
import os
import plistlib
import re
import subprocess
import tempfile
import sys
from pathlib import Path

VERSION = 1
SYSTEM = "com.apple.symbolichotkeys"
ACCESSIBILITY = "com.apple.universalaccess"
SERVICES = "pbs"
GLOBAL = "NSGlobalDomain"

# Curated from https://gist.github.com/stephancasas/2c8e8f71e23ec7221495d7f4b9efb794
# and https://github.com/linearmouse/linearmouse/blob/main/Modules/KeyKit/Sources/KeyKit/SymbolicHotKey.swift
# The IDs remain authoritative; labels are for human review only.
SYMBOLIC_ACTIONS = {
    "15": "Accessibility: toggle zoom",
    "16": "Accessibility: toggle zoom (keypad)",
    "17": "Accessibility: zoom in",
    "18": "Accessibility: zoom in (keypad)",
    "19": "Accessibility: zoom out",
    "20": "Accessibility: zoom out (keypad)",
    "21": "Accessibility: invert colors",
    "22": "Accessibility: invert colors (keypad)",
    "23": "Accessibility: toggle zoom image smoothing",
    "24": "Accessibility: zoom pan back",
    "25": "Accessibility: increase contrast",
    "26": "Accessibility: decrease contrast",
    "33": "Mission Control: application windows",
    "35": "Mission Control: application windows (alternate)",
    "60": "Input Sources: select previous input source",
    "61": "Input Sources: select next input source",
    "64": "Spotlight: show search",
    "65": "Spotlight: show Finder search window",
    "79": "Mission Control: move left a space",
    "80": "Mission Control: move left a space (alternate)",
    "81": "Mission Control: move right a space",
    "82": "Mission Control: move right a space (alternate)",
    "118": "Mission Control: switch to Desktop 1",
    "119": "Mission Control: switch to Desktop 2",
    "164": "Accessibility: modifier key double-tap",
    "179": "Accessibility: zoom follows keyboard focus",
    "222": "Desktop & Dock: toggle Stage Manager",
    "233": "Window: minimize",
    "235": "Window: zoom",
    "237": "Window: fill",
    "238": "Window: center",
    "239": "Window: return to previous size",
    "240": "Window: tile left half",
    "241": "Window: tile right half",
    "242": "Window: tile top half",
    "243": "Window: tile bottom half",
    "257": "Window: full-screen tile left half",
    "258": "Window: full-screen tile right half",
}

ACCESSIBILITY_ACTIONS = {
    7: "Keyboard navigation: focus menu bar",
    8: "Keyboard navigation: focus Dock",
    9: "Keyboard navigation: focus active or next window",
    10: "Keyboard navigation: focus window toolbar",
    11: "Keyboard navigation: focus floating window",
}


class ShortcutError(Exception):
    """A shortcut profile is invalid or a macOS preference operation failed."""


def defaults(*args):
    result = subprocess.run(["defaults", *args], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        if args[0] == "export" and "does not exist" in detail:
            return None
        raise ShortcutError(f"defaults {' '.join(args[:2])}: {detail}")
    return result.stdout


def domain_values(domain):
    data = defaults("export", domain, "-")
    if data is None:
        return {}
    try:
        values = plistlib.loads(data)
    except (ValueError, plistlib.InvalidFileException) as exc:
        raise ShortcutError(f"Invalid preferences for {domain}: {exc}") from exc
    if not isinstance(values, dict):
        raise ShortcutError(f"Unexpected preferences for {domain}")
    return values


def app_domains(preferences, accessibility):
    """Discover both registered apps and overrides on disk (including unregistered ones)."""
    domains = {GLOBAL}
    for domain in accessibility.get("com.apple.custommenu.apps", []):
        if isinstance(domain, str) and domain not in ("NSGlobalDomain",):
            domains.add(domain)
    if preferences.is_dir():
        for path in preferences.glob("*.plist"):
            if path.is_symlink():
                continue
            try:
                content = plistlib.loads(path.read_bytes())
            except (OSError, ValueError, plistlib.InvalidFileException):
                continue
            if isinstance(content, dict) and isinstance(content.get("NSUserKeyEquivalents"), dict):
                domains.add(GLOBAL if path.stem == ".GlobalPreferences" else path.stem)
    return domains


def snapshot(preferences=None):
    preferences = preferences or Path.home() / "Library/Preferences"
    system = domain_values(SYSTEM)
    accessibility = domain_values(ACCESSIBILITY)
    services = domain_values(SERVICES)
    apps = {}
    for domain in sorted(app_domains(preferences, accessibility)):
        overrides = domain_values(domain).get("NSUserKeyEquivalents", {})
        if overrides:
            apps[domain] = overrides
    return {
        "version": VERSION,
        "system_hotkeys": system.get("AppleSymbolicHotKeys", {}),
        "app_shortcuts": apps,
        "service_shortcuts": {
            name: item["key_equivalent"]
            for name, item in services.get("NSServicesStatus", {}).items()
            if isinstance(item, dict) and isinstance(item.get("key_equivalent"), str)
        },
        "accessibility_hotkeys": accessibility.get("UserAssignableHotKeys", []),
    }



def without_action(entry):
    """Use only native preference fields to compare or restore a shortcut."""
    return {name: value for name, value in entry.items() if name != "action"}


def with_action_labels(profile):
    """Provide readable names in exported JSON and VS Code's review documents."""
    annotated = copy.deepcopy(profile)
    for key, entry in annotated["system_hotkeys"].items():
        if action := SYMBOLIC_ACTIONS.get(key):
            entry["action"] = action
    for entry in annotated["accessibility_hotkeys"]:
        if action := ACCESSIBILITY_ACTIONS.get(entry["sybmolichotkey"]):
            entry["action"] = action
    return annotated


def require(condition, description):
    if not condition:
        raise ShortcutError(f"Invalid shortcut profile: {description}")


def validate(profile):
    require(isinstance(profile, dict), "expected a JSON object")
    require(set(profile) == {"version", "system_hotkeys", "app_shortcuts",
                             "service_shortcuts", "accessibility_hotkeys"}, "unknown or missing sections")
    require(type(profile["version"]) is int and profile["version"] == VERSION, "unsupported version")
    for name in ("system_hotkeys", "app_shortcuts", "service_shortcuts"):
        require(isinstance(profile[name], dict), f"{name} must be an object")
    for key, entry in profile["system_hotkeys"].items():
        require(isinstance(key, str) and re.fullmatch(r"[0-9]+", key) is not None,
                "system hotkey IDs must be numeric")
        require(isinstance(entry, dict) and entry.get("enabled") in (True, False, 0, 1, "0", "1"),
                f"system hotkey {key} needs an enabled flag")
        require(set(entry) <= {"enabled", "value", "action"}, f"unsupported fields in hotkey {key}")
        if "action" in entry:
            require(entry["action"] == SYMBOLIC_ACTIONS.get(key),
                    f"system hotkey {key} has an incorrect action label")
        if "value" in entry:
            value = entry["value"]
            require(isinstance(value, dict) and value.get("type") in ("standard", "modifier")
                    and set(value) == {"type", "parameters"}
                    and isinstance(value.get("parameters"), list)
                    and len(value["parameters"]) == (3 if value["type"] == "standard" else 2)
                    and all((type(n) is int or
                             (isinstance(n, str) and n.isdecimal())) for n in value["parameters"]),
                    f"invalid parameters for hotkey {key}")
    for domain, shortcuts in profile["app_shortcuts"].items():
        require(isinstance(domain, str) and domain and not any(c.isspace() for c in domain),
                "invalid application domain")
        require(isinstance(shortcuts, dict), f"app {domain} must be an object")
        for title, key in shortcuts.items():
            require(isinstance(title, str) and title and isinstance(key, str),
                    f"app {domain}: shortcut titles and equivalents must be strings")
    for service, shortcut in profile["service_shortcuts"].items():
        require(isinstance(service, str) and service and isinstance(shortcut, str),
                "invalid service shortcut")
    accessibility = profile["accessibility_hotkeys"]
    require(isinstance(accessibility, list), "accessibility_hotkeys must be a list")
    seen = set()
    for entry in accessibility:
        require(isinstance(entry, dict) and
                set(entry) in ({"enabled", "key", "modifier", "sybmolichotkey"},
                               {"enabled", "key", "modifier", "sybmolichotkey", "action"})
                and type(entry["enabled"]) is bool
                and all(type(entry[field]) is int for field in ("key", "modifier", "sybmolichotkey")),
                "invalid accessibility hotkey")
        if "action" in entry:
            require(entry["action"] == ACCESSIBILITY_ACTIONS.get(entry["sybmolichotkey"]),
                    "incorrect accessibility action label")
        require(entry["sybmolichotkey"] not in seen, "duplicate accessibility hotkey")
        seen.add(entry["sybmolichotkey"])


def load_profile(path):
    try:
        profile = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ShortcutError(f"Cannot load {path}: {exc}") from exc
    validate(profile)
    return profile


def changes(desired, current):
    """Yield only differences for explicitly declared keys; never delete extra entries."""
    for key, value in desired["system_hotkeys"].items():
        if current["system_hotkeys"].get(key) != without_action(value):
            yield ("system", key, without_action(value))
    for domain, shortcuts in desired["app_shortcuts"].items():
        actual = current["app_shortcuts"].get(domain, {})
        for title, shortcut in shortcuts.items():
            if actual.get(title) != shortcut:
                yield ("app", (domain, title), shortcut)
    for name, shortcut in desired["service_shortcuts"].items():
        if current["service_shortcuts"].get(name) != shortcut:
            yield ("service", name, shortcut)
    actual = {x["sybmolichotkey"]: x for x in current["accessibility_hotkeys"]}
    for entry in desired["accessibility_hotkeys"]:
        native = without_action(entry)
        if actual.get(entry["sybmolichotkey"]) != native:
            yield ("accessibility", entry["sybmolichotkey"], native)


def import_merged_domain(domain, data):
    """Import a fresh, merged plist so nested numbers remain correctly typed."""
    with tempfile.TemporaryDirectory(prefix="macos-shortcuts-") as directory:
        source = Path(directory) / "preferences.plist"
        source.write_bytes(plistlib.dumps(data))
        defaults("import", domain, str(source))


def apply(desired, pending):
    """Preserve unrelated preferences while replacing only declared shortcuts."""
    groups = {}
    registry = set(domain_values(ACCESSIBILITY).get("com.apple.custommenu.apps", []))
    app_writes = []

    # Preflight all merged preference data before the first write.
    for kind, key, value in pending:
        if kind == "app":
            app_writes.append((key[0], key[1], value))
            continue
        domain = {"system": SYSTEM, "service": SERVICES,
                  "accessibility": ACCESSIBILITY}[kind]
        if domain not in groups:
            groups[domain] = domain_values(domain)
        prefs = groups[domain]
        if kind == "system":
            entries = dict(prefs.get("AppleSymbolicHotKeys", {}))
            entries[key] = value
            prefs["AppleSymbolicHotKeys"] = entries
        elif kind == "service":
            entries = dict(prefs.get("NSServicesStatus", {}))
            original = entries.get(key, {})
            require(isinstance(original, dict), f"service {key} has invalid existing preferences")
            entries[key] = {**original, "key_equivalent": value}
            prefs["NSServicesStatus"] = entries
        elif kind == "accessibility":
            entries = {x["sybmolichotkey"]: x for x in prefs.get("UserAssignableHotKeys", [])}
            entries[value["sybmolichotkey"]] = value
            prefs["UserAssignableHotKeys"] = [entries[k] for k in sorted(entries)]

    # Importing a domain changes its top-level preferences; fresh exports above
    # retain every unrelated key, including keys not managed by this utility.
    for domain, prefs in groups.items():
        import_merged_domain(domain, prefs)

    # App menu equivalents are scalar strings: dict-add updates only their key.
    for domain, title, value in app_writes:
        defaults("write", domain, "NSUserKeyEquivalents", "-dict-add", title, value)
        if domain != GLOBAL and domain not in registry:
            defaults("write", ACCESSIBILITY, "com.apple.custommenu.apps", "-array-add", domain)
            registry.add(domain)


def projected_live_profile(desired, current):
    """Render the live values for managed entries in the normal profile schema."""
    apps = {}
    for domain, entries in desired["app_shortcuts"].items():
        local = current["app_shortcuts"].get(domain, {})
        values = {title: local[title] for title in entries if title in local}
        if values:
            apps[domain] = values
    accessibility = {x["sybmolichotkey"]: x for x in current["accessibility_hotkeys"]}
    return {
        "version": VERSION,
        "system_hotkeys": {key: current["system_hotkeys"][key]
                           for key in desired["system_hotkeys"]
                           if key in current["system_hotkeys"]},
        "app_shortcuts": apps,
        "service_shortcuts": {key: current["service_shortcuts"][key]
                              for key in desired["service_shortcuts"]
                              if key in current["service_shortcuts"]},
        "accessibility_hotkeys": [
            accessibility[entry["sybmolichotkey"]]
            for entry in desired["accessibility_hotkeys"]
            if entry["sybmolichotkey"] in accessibility
        ],
    }


def review(desired, current):
    """Open the source-of-truth VS Code diff only when managed shortcuts drift."""
    if not list(changes(desired, current)):
        return 0
    with tempfile.TemporaryDirectory(prefix="chezmoi-shortcuts-diff-") as tmp:
        actual = Path(tmp) / "macOS shortcuts (current).json"
        expected = Path(tmp) / "macOS shortcuts (managed).json"
        actual.write_text(json.dumps(with_action_labels(projected_live_profile(desired, current)), indent=2,
                                     sort_keys=True) + "\n")
        expected.write_text(json.dumps(desired, indent=2, sort_keys=True) + "\n")
        try:
            subprocess.run(["code", "--wait", "--diff", str(actual), str(expected)], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ShortcutError(f"Cannot open VS Code shortcut diff: {exc}") from exc
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Write a portable JSON shortcut snapshot")
    export.add_argument("path", type=Path)
    diff = commands.add_parser("diff", help="Compare managed shortcuts with this Mac")
    diff.add_argument("path", type=Path)
    restore = commands.add_parser("apply", help="Restore only declared shortcuts")
    restore.add_argument("path", type=Path)
    restore.add_argument("--yes", action="store_true", help="Confirm actual preference writes")
    gui = commands.add_parser("review", help="Open differences in VS Code (chezmoi hook)")
    gui.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    args.path = args.path.expanduser()

    if args.command == "export":
        profile = with_action_labels(snapshot())
        validate(profile)
        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")
        print(f"Exported shortcuts to {args.path.resolve()}")
        return 0

    if args.command == "review" and os.environ.get("CHEZMOI_DEST_DIR") != os.environ.get("CHEZMOI_HOME_DIR"):
        return 0
    desired = load_profile(args.path)
    current = snapshot()
    pending = list(changes(desired, current))
    if args.command == "review":
        return review(desired, current)
    if args.command == "apply":
        if not pending:
            return 0
        if not args.yes:
            print("No changes made; pass --yes to write preferences.")
            return 2
        apply(desired, pending)
        print(f"Applied {len(pending)} macOS shortcut settings.")
        return 0
    for kind, key, value in pending:
        action = (SYMBOLIC_ACTIONS.get(key) if kind == "system" else
                  ACCESSIBILITY_ACTIONS.get(key) if kind == "accessibility" else None)
        title = f"{key} ({action})" if action else str(key)
        print(f"{kind}: {title}: {json.dumps(value, sort_keys=True)}")
    print(f"{len(pending)} shortcut differences")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ShortcutError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
