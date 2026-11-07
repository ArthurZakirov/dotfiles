import AppKit
import ApplicationServices
import Foundation
import Darwin

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

func showSearch(_ root: AXUIElement, seconds: Double = 4.5) -> AXUIElement? {
    // If the search is already primed, return immediately without opening UI.
    // Otherwise wait for the *actual AX control*, not a fixed animation delay:
    // Safari may expose the ChatGPT web area before its Search button is ready.
    let deadline = Date().addingTimeInterval(seconds)
    var lastPress = Date.distantPast
    repeat {
        if let field = searchField(root) { return field }
        if Date().timeIntervalSince(lastPress) >= 1.5,
           let button = find(root, {
               (role($0) == "AXPopUpButton" || role($0) == "AXButton")
                   && title($0) == "Search"
           }) {
            lastPress = Date()
            _ = AXUIElementPerformAction(button, kAXPressAction as CFString)
        }
        if Date() >= deadline { break }
        Thread.sleep(forTimeInterval: 0.12)
    } while true
    return searchField(root)
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

func osascript(_ source: String, timeout: Double = 2.5) -> String? {
    // Safari can indefinitely block Apple Events while a background tab changes.
    // Bound the subprocess, and terminate only this AppleScript child on timeout.
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-e", source]
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = Pipe()
    let finished = DispatchSemaphore(value: 0)
    process.terminationHandler = { _ in finished.signal() }
    do { try process.run() } catch { return nil }
    if finished.wait(timeout: .now() + timeout) == .timedOut {
        if process.isRunning { process.terminate() }
        if finished.wait(timeout: .now() + 0.3) == .timedOut {
            if process.isRunning { _ = kill(process.processIdentifier, SIGKILL) }
            _ = finished.wait(timeout: .now() + 0.5)
        }
        return nil
    }
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

struct BrowserTabState {
    let url: String
    let title: String
}

func browserTabState(provider: String) -> BrowserTabState? {
    // Read URL and title in a single AppleScript roundtrip. Two independent
    // processes could observe different navigation states and consume the
    // entire 4-second timeout before ChatGPT finished updating its title.
    let script: String
    switch provider {
    case "safari":
        script = """
        tell application "Safari"
            set t to current tab of front window
            return (URL of t as string) & (ASCII character 10) & (name of t as string)
        end tell
        """
    case "chrome":
        script = """
        tell application "Google Chrome"
            set t to active tab of front window
            return (URL of t as string) & (ASCII character 10) & (title of t as string)
        end tell
        """
    default:
        return nil
    }
    guard let response = osascript(script),
          let breakIndex = response.firstIndex(of: "\n") else { return nil }
    return BrowserTabState(
        url: String(response[..<breakIndex]),
        title: String(response[response.index(after: breakIndex)...])
    )
}

func isMatchingResult(heading: String, state: BrowserTabState) -> String? {
    guard let url = canonicalUrl(state.url) else { return nil }
    let pageTitle = state.title.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !pageTitle.isEmpty, pageTitle != "ChatGPT",
          heading.lowercased().hasPrefix(pageTitle.lowercased()) else { return nil }
    return url
}

func awaitResultNavigation(
    heading: String, previousUrl: String?, seconds: Double,
    observe: () -> BrowserTabState?,
    pause: () -> Void = { Thread.sleep(forTimeInterval: 0.20) }
) -> String? {
    let deadline = Date().addingTimeInterval(seconds)
    var changedUrl: String?
    var changedSamples = 0
    repeat {
        if let state = observe() {
            // Prefer both URL and title when available, including a search
            // result that links to the already-open conversation.
            if let url = isMatchingResult(heading: heading, state: state) {
                return url
            }
            // ChatGPT sometimes updates its route *before* the Safari tab
            // title and never exposes the latter while in the background.
            // A new, stable conversation URL after an explicit AXPress is
            // sufficient navigation evidence; unlike a lone URL sample, it
            // cannot accidentally reuse the previously open conversation.
            if let previousUrl, let url = canonicalUrl(state.url), url != previousUrl {
                if changedUrl == url {
                    changedSamples += 1
                } else {
                    changedUrl = url
                    changedSamples = 1
                }
                if changedSamples >= 2 { return url }
            }
        }
        if Date() >= deadline { break }
        pause()
    } while true
    return nil
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

// Prepare the dedicated, already-authenticated Safari ChatGPT search tab
// once on Hammerspoon startup. No extra browser, cookies, login or web API.
// Safari may need a brief foreground activation to expose its AX web area.
func prepareSafariSearch() -> Bool {
    guard let root = application("safari"),
          let safari = NSRunningApplication
            .runningApplications(withBundleIdentifier: "com.apple.Safari").first else {
        return false
    }
    let priorApp = NSWorkspace.shared.frontmostApplication
    // Fast path: an existing search field is ready even while Safari is hidden.
    if searchField(root) != nil { return true }

    let shouldRestore = priorApp?.processIdentifier != safari.processIdentifier
    if shouldRestore {
        _ = safari.activate(options: [])
        let deadline = Date().addingTimeInterval(1.5)
        while NSWorkspace.shared.frontmostApplication?.processIdentifier != safari.processIdentifier
                && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.10)
        }
    }
    defer {
        if shouldRestore,
           NSWorkspace.shared.frontmostApplication?.processIdentifier == safari.processIdentifier,
           let priorApp {
            _ = priorApp.activate(options: [])
            let deadline = Date().addingTimeInterval(1.5)
            while NSWorkspace.shared.frontmostApplication?.processIdentifier != priorApp.processIdentifier
                    && Date() < deadline {
                Thread.sleep(forTimeInterval: 0.05)
            }
        }
    }
    return showSearch(root, seconds: 5.0) != nil
}

func search(provider: String, term: String, limit: Int) -> Output {
    var warnings: [String] = []
    guard let root = application(provider) else {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false, warnings: ["Browser not running"])
    }
    // Safari has no usable ChatGPT Accessibility tree when it is not the
    // foreground app on this macOS installation. The tab is open and logged
    // in, but searching in the background falsely returned zero matches.
    // Briefly bring Safari forward only for the native AX search, then
    // restore the previously active app. Do not steal focus again if the
    // user switches to a different app while this search is running.
    let priorApp = NSWorkspace.shared.frontmostApplication
    // Fast path: if the prewarmed dialog is accessible in the background,
    // set its value immediately without moving the user's window focus.
    let readyInBackground = provider == "safari" && searchField(root) != nil
    var restoreSafariFocus = provider == "safari" && !readyInBackground &&
        priorApp?.bundleIdentifier != "com.apple.Safari"
    if restoreSafariFocus {
        guard let safari = NSRunningApplication
            .runningApplications(withBundleIdentifier: "com.apple.Safari").first else {
            return Output(provider: provider, query: term, results: [],
                          completeHistory: false, warnings: ["Safari not running"])
        }
        _ = safari.activate(options: [])
        let deadline = Date().addingTimeInterval(1.5)
        while NSWorkspace.shared.frontmostApplication?.processIdentifier != safari.processIdentifier
                && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.10)
        }
        Thread.sleep(forTimeInterval: 0.30)
        trace("Safari foreground for AX search")
    }
    defer {
        // NSRunningApplication.activate is asynchronous. Wait for the focus
        // handoff before returning JSON, otherwise callers can observe Safari
        // still frontmost even though restoration was requested.
        if restoreSafariFocus,
           NSWorkspace.shared.frontmostApplication?.bundleIdentifier == "com.apple.Safari",
           let priorApp {
            _ = priorApp.activate(options: [])
            let restoreDeadline = Date().addingTimeInterval(1.5)
            while NSWorkspace.shared.frontmostApplication?.processIdentifier != priorApp.processIdentifier
                    && Date() < restoreDeadline {
                Thread.sleep(forTimeInterval: 0.05)
            }
            trace("foreground restored to previous application")
        }
    }
    let selection = provider == "chrome" ? selectChromeTab() : nil
    if provider == "chrome" && selection == nil {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false,
                      warnings: ["No ChatGPT tab in the front Chrome window"])
    }
    defer { if let selection { restoreChromeTab(selection) } }
    if selection != nil { Thread.sleep(forTimeInterval: 0.30) }

    // Keep Safari primed for the next hotkey. A result click navigates out of
    // the overlay; reopen it BEFORE the focus-restoration defer executes.
    // Do not re-prime Chrome, whose tabs belong to the user's regular work.
    defer {
        if provider == "safari" {
            let current = NSWorkspace.shared.frontmostApplication
            // Respect a user-initiated switch to a third application.
            if current?.processIdentifier == priorApp?.processIdentifier ||
               current?.bundleIdentifier == "com.apple.Safari" {
                let ready = prepareSafariSearch()
                trace("Safari search re-primed: \(ready)")
            }
        }
    }

    var searchReady = setSearchTerm(root, term)
    if !searchReady && provider == "safari" {
        // Some macOS builds expose the prewarmed field in the background but
        // refuse AXValue writes until Safari is active. Recover once.
        if let safari = NSRunningApplication
            .runningApplications(withBundleIdentifier: "com.apple.Safari").first,
           NSWorkspace.shared.frontmostApplication?.processIdentifier != safari.processIdentifier {
            _ = safari.activate(options: [])
            restoreSafariFocus = priorApp?.processIdentifier != safari.processIdentifier
            let deadline = Date().addingTimeInterval(1.5)
            while NSWorkspace.shared.frontmostApplication?.processIdentifier != safari.processIdentifier
                    && Date() < deadline {
                Thread.sleep(forTimeInterval: 0.10)
            }
        }
        searchReady = setSearchTerm(root, term)
    }
    guard searchReady else {
        return Output(provider: provider, query: term, results: [],
                      completeHistory: false,
                      warnings: ["Could not access ChatGPT Search after bringing browser forward"])
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
        let previousUrl = browserTabState(provider: provider).flatMap { canonicalUrl($0.url) }
        trace("opening index \(index) title: \(heading.prefix(65))")
        guard AXUIElementPerformAction(row, kAXPressAction as CFString) == .success else {
            warnings.append("Could not open result at position \(index + 1)")
            continue
        }
        // AXPress may return before Safari has navigated and rendered the title.
        // Poll a coherent (URL, title) pair with a bounded, generous deadline;
        // a timeout is *incomplete*, not evidence that the chat was not found.
        let resolved = awaitResultNavigation(heading: heading,
            previousUrl: previousUrl, seconds: 12) {
            browserTabState(provider: provider)
        }
        trace("after click resolved: \(resolved ?? "nil")")
        guard let url = resolved, let id = conversationId(url) else {
            warnings.append("Search result \(index + 1) was visible, but Safari did not confirm its URL and title within 12 seconds; coverage incomplete")
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
if args == ["--prepare-safari"] {
    let prepared = prepareSafariSearch()
    print(prepared ? "{\"prepared\":true}" : "{\"prepared\":false}")
    exit(prepared ? 0 : 2)
}
if args.contains("--self-test") {
    let fakeId = "11111111-2222-4333-8444-555555555555"
    let sample = "https://chatgpt.com/c/" + fakeId
    precondition(conversationId(sample) != nil)
    precondition(conversationId("https://example.org/c/" + fakeId) == nil)
    precondition(canonicalUrl(sample + "?src=history_search") == sample)
    let title = "Example Chat …git pull/67"
    let previousId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    let oldState = BrowserTabState(url: "https://chatgpt.com/c/" + previousId,
                                    title: "Different Chat")
    let newState = BrowserTabState(url: sample + "?src=history_search",
                                    title: "Example Chat")
    var pollCount = 0
    let resolved = awaitResultNavigation(heading: title, previousUrl: oldState.url,
        seconds: 1, observe: {
            pollCount += 1
            if pollCount < 3 { return oldState }
            if pollCount == 3 {
                return BrowserTabState(url: newState.url, title: "Different Chat")
            }
            return newState
        }, pause: {})
    precondition(resolved == sample && pollCount == 4)
    precondition(isMatchingResult(heading: title, state: oldState) == nil)
    var delayedTitlePoll = 0
    let changedButTitleStale = awaitResultNavigation(heading: title,
        previousUrl: oldState.url, seconds: 1, observe: {
            delayedTitlePoll += 1
            if delayedTitlePoll == 1 { return oldState }
            return BrowserTabState(url: newState.url, title: "ChatGPT")
        }, pause: {})
    precondition(changedButTitleStale == sample && delayedTitlePoll == 3)
    let oldOnly = awaitResultNavigation(heading: title, previousUrl: oldState.url,
        seconds: 0, observe: { oldState }, pause: {})
    precondition(oldOnly == nil)
    // Never let an AppleScript subprocess outlive the bounded UI search.
    precondition(osascript("delay 3", timeout: 0.1) == nil)
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
