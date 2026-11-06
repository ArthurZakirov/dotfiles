import AppKit
import ApplicationServices
import Foundation

// Browser-specific infrastructure. Outputs only verified conversation URLs.
// The shared query semantics, scoring and JSON schema belong to the Python core.
struct Hit: Codable {
    let title: String
    let url: String
    let sessionId: String
    let evidence: String
}

struct Output: Codable {
    let provider: String
    let query: String
    let results: [Hit]
    let completeHistory: Bool
    let warnings: [String]
}

func ax(_ element: AXUIElement, _ key: String) -> CFTypeRef? {
    var result: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, key as CFString, &result) == .success ? result : nil
}

func role(_ element: AXUIElement) -> String {
    ax(element, kAXRoleAttribute as String) as? String ?? ""
}
func title(_ element: AXUIElement) -> String {
    ax(element, kAXTitleAttribute as String) as? String ?? ""
}
func value(_ element: AXUIElement) -> String {
    ax(element, kAXValueAttribute as String) as? String ?? ""
}
func children(_ element: AXUIElement) -> [AXUIElement] {
    ax(element, kAXChildrenAttribute as String) as? [AXUIElement] ?? []
}

func find(_ element: AXUIElement, _ match: (AXUIElement) -> Bool, depth: Int = 0) -> AXUIElement? {
    guard depth < 42 else { return nil }
    if match(element) { return element }
    for child in children(element) {
        if let result = find(child, match, depth: depth + 1) { return result }
    }
    return nil
}

func conversationId(_ address: String) -> String? {
    guard let url = URL(string: address), url.scheme == "https",
          url.host?.lowercased() == "chatgpt.com" else { return nil }
    let parts = url.pathComponents.filter { $0 != "/" }
    let raw: String
    if parts.count == 2, parts[0] == "c" {
        raw = parts[1]
    } else if parts.count == 4, parts[0] == "g", parts[2] == "c" {
        raw = parts[3]
    } else {
        return nil
    }
    return UUID(uuidString: raw)?.uuidString.lowercased()
}

func canonicalUrl(_ address: String) -> String? {
    guard let parsed = URL(string: address), conversationId(address) != nil else { return nil }
    return "https://chatgpt.com" + parsed.path
}

func application(_ name: String) -> AXUIElement? {
    let bundle = name == "safari" ? "com.apple.Safari" : "com.google.Chrome"
    guard let process = NSRunningApplication.runningApplications(withBundleIdentifier: bundle).first else {
        return nil
    }
    return AXUIElementCreateApplication(process.processIdentifier)
}

func currentChatUrl(_ root: AXUIElement) -> String? {
    let area = find(root) { element in
        guard role(element) == "AXWebArea",
              let address = ax(element, "AXURL") else { return false }
        let text = (address as? URL)?.absoluteString ?? (address as? String) ?? ""
        return text.contains("chatgpt.com/")
    }
    if let area, let raw = ax(area, "AXURL") {
        return (raw as? URL)?.absoluteString ?? (raw as? String)
    }
    return nil
}

func searchField(_ root: AXUIElement) -> AXUIElement? {
    find(root) { role($0) == "AXComboBox" && title($0) == "Search" }
}

func waitForField(_ root: AXUIElement, seconds: Double = 2.5) -> AXUIElement? {
    let deadline = Date().addingTimeInterval(seconds)
    repeat {
        if let field = searchField(root) { return field }
        Thread.sleep(forTimeInterval: 0.10)
    } while Date() < deadline
    return nil
}

func showSearch(_ root: AXUIElement) -> AXUIElement? {
    if let field = searchField(root) { return field }
    guard let button = find(root, {
        (role($0) == "AXPopUpButton" || role($0) == "AXButton")
            && title($0) == "Search"
    }) else { return nil }
    guard AXUIElementPerformAction(button, kAXPressAction as CFString) == .success else {
        return nil
    }
    return waitForField(root)
}

func resultElements(_ root: AXUIElement) -> [AXUIElement] {
    guard let overlay = find(root, { role($0) == "AXGroup" && title($0) == "Global search" }) else {
        return []
    }
    for group in children(overlay) where role(group) == "AXGroup" &&
        ["All", "Chats"].contains(title(group)) {
        if let list = find(group, { role($0) == "AXList" }) {
            return children(list).filter { role($0) == "AXStaticText" && !title($0).isEmpty }
        }
    }
    return []
}

func availableResults(_ root: AXUIElement, seconds: Double = 4) -> [AXUIElement] {
    let deadline = Date().addingTimeInterval(seconds)
    repeat {
        let elements = resultElements(root)
        if !elements.isEmpty { return elements }
        Thread.sleep(forTimeInterval: 0.15)
    } while Date() < deadline
    return []
}

func setSearchTerm(_ root: AXUIElement, _ term: String) -> Bool {
    guard let field = showSearch(root) else { return false }
    if value(field) == term { return true }
    return AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString,
                                        term as CFString) == .success
}

func observedTitle(_ root: AXUIElement, fallback: String) -> String {
    let window = find(root, { role($0) == "AXWindow" && !title($0).isEmpty })
    let name = window.map(title) ?? ""
    if !name.isEmpty && name != "ChatGPT" && name != "Google Chrome" &&
       !name.hasPrefix("ChatGPT:") {
        return name.replacingOccurrences(of: " - Google Chrome", with: "")
    }
    // Search results begin with the chat title followed by the match excerpt.
    if let range = fallback.range(of: " …") {
        return String(fallback[..<range.lowerBound])
    }
    if let range = fallback.range(of: " **") {
        return String(fallback[..<range.lowerBound])
    }
    return String(fallback.prefix(120))
}

func osascript(_ source: String) -> String? {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-e", source]
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = Pipe()
    do { try process.run() } catch { return nil }
    process.waitUntilExit()
    guard process.terminationStatus == 0 else { return nil }
    return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

func selectChromeTab() -> (window: String, original: String, selected: String)? {
    let script = """
    tell application "Google Chrome"
        if (count of windows) is 0 then return "none"
        set w to front window
        set originalIndex to active tab index of w
        repeat with i from 1 to (count of tabs of w)
            if URL of tab i of w starts with "https://chatgpt.com/" then
                set active tab index of w to i
                return (id of w as string) & "|" & originalIndex & "|" & i
            end if
        end repeat
        return "none"
    end tell
    """
    guard let response = osascript(script) else { return nil }
    let parts = response.split(separator: "|").map(String.init)
    guard parts.count == 3, parts.allSatisfy({ Int($0) != nil }) else { return nil }
    return (parts[0], parts[1], parts[2])
}

func verifiedTabTitle(provider: String) -> String? {
    if provider == "safari" {
        return osascript("tell application \"Safari\" to return name of current tab of front window")
    }
    if provider == "chrome" {
        return osascript("tell application \"Google Chrome\" to return title of active tab of front window")
    }
    return nil
}

func verifiedTabUrl(provider: String, root: AXUIElement) -> String? {
    // Safari does not always expose AXWebArea while in the background;
    // AppleScript reads the tab address without focusing or navigating the browser.
    if provider == "safari" {
        return osascript("tell application \"Safari\" to return URL of current tab of front window")
    }
    if provider == "chrome" {
        return osascript("tell application \"Google Chrome\" to return URL of active tab of front window")
    }
    return currentChatUrl(root)
}

func restoreChromeTab(_ selection: (window: String, original: String, selected: String)) {
    let script = """
    tell application "Google Chrome"
        repeat with w in windows
            if (id of w as string) is "\(selection.window)" then
                if active tab index of w is \(selection.selected) then
                    set active tab index of w to \(selection.original)
                end if
                exit repeat
            end if
        end repeat
    end tell
    """
    _ = osascript(script)
}

func trace(_ text: String) {
    if ProcessInfo.processInfo.environment["DEBUG_FIND_GPT"] != nil {
        fputs("ui-ax: " + text + "\n", stderr)
    }
}

func search(provider: String, term: String, limit: Int) -> Output {
    var warnings: [String] = []
    guard let root = application(provider) else {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false, warnings: ["Browser not running"])
    }
    let selection = provider == "chrome" ? selectChromeTab() : nil
    if provider == "chrome" && selection == nil {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false,
                      warnings: ["No ChatGPT tab in the front Chrome window"])
    }
    defer { if let selection { restoreChromeTab(selection) } }
    if selection != nil { Thread.sleep(forTimeInterval: 0.30) }

    guard setSearchTerm(root, term) else {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false, warnings: ["Could not open or set ChatGPT Search"])
    }
    let initial = availableResults(root)
    trace("initial results count: \(initial.count)")
    if initial.isEmpty {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false, warnings: ["No visible search suggestions (could be no matches)"])
    }
    var results: [Hit] = []
    var seen = Set<String>()
    // The result list is recreated after opening each chat. Re-query by position,
    // not by remembered AX references, which become invalid after navigation.
    for index in 0..<min(limit, initial.count) {
        guard setSearchTerm(root, term) else {
            warnings.append("Search overlay no longer available")
            break
        }
        var rows = availableResults(root, seconds: 3)
        if rows.count <= index {
            warnings.append("Search result list changed while navigating")
            break
        }
        let row = rows[index]
        let heading = title(row)
        trace("opening index \(index) title: \(heading.prefix(65))")
        guard AXUIElementPerformAction(row, kAXPressAction as CFString) == .success else {
            warnings.append("Could not open result at position \(index + 1)")
            continue
        }
        let deadline = Date().addingTimeInterval(4.0)
        var resolved: String?
        repeat {
            if let raw = verifiedTabUrl(provider: provider, root: root), let url = canonicalUrl(raw) {
                let pageTitle = verifiedTabTitle(provider: provider) ?? ""
                // Never treat the previous tab URL as the newly opened result.
                // A live search row starts with the exact chat title; only use
                // a URL whose current page title identifies that row.
                if !pageTitle.isEmpty && heading.lowercased().hasPrefix(pageTitle.lowercased()) {
                    resolved = url
                    break
                }
            }
            Thread.sleep(forTimeInterval: 0.12)
        } while Date() < deadline
        trace("after click resolved: \(resolved ?? "nil")")
        guard let url = resolved, let id = conversationId(url) else {
            warnings.append("No verified chat URL for result \(index + 1)")
            continue
        }
        if seen.insert(id).inserted {
            results.append(Hit(title: observedTitle(root, fallback: heading),
                               url: url, sessionId: id,
                               evidence: "ChatGPT visible full-text search result"))
        }
        rows.removeAll()
        // macOS may detach Safari's background AX tree after navigation.
        // Avoid waiting and returning unrelated/stale URLs for subsequent rows.
        if provider == "safari" &&
           NSWorkspace.shared.frontmostApplication?.bundleIdentifier != "com.apple.Safari" &&
           index + 1 < initial.count {
            warnings.append("Background Safari exposes only the first navigated result reliably")
            break
        }
    }
    return Output(provider: provider, query: term, results: results,
                  completeHistory: false, warnings: warnings)
}

let args = Array(CommandLine.arguments.dropFirst())
if args.contains("--self-test") {
    let fakeId = "11111111-2222-4333-8444-555555555555"
    let sample = "https://chatgpt.com/c/" + fakeId
    precondition(conversationId(sample) != nil)
    precondition(conversationId("https://example.org/c/" + fakeId) == nil)
    precondition(canonicalUrl(sample + "?src=history_search") == sample)
    print("{\"self_test\":true}")
    exit(0)
}
guard args.count == 3, ["safari", "chrome"].contains(args[0]),
      let limit = Int(args[2]), limit > 0 else {
    fputs("Usage: ui-ax safari|chrome SEARCH_QUERY LIMIT\n", stderr)
    exit(2)
}
let output = search(provider: args[0], term: args[1], limit: limit)
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
guard let data = try? encoder.encode(output) else { exit(2) }
print(String(decoding: data, as: UTF8.self))
