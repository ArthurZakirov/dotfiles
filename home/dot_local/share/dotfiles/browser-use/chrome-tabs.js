// osascript -l JavaScript. Address running processes by PID; never launch by name.
function chromePids() {
    ObjC.import("AppKit");
    return ObjC.unwrap($.NSRunningApplication.runningApplicationsWithBundleIdentifier("com.google.Chrome"))
        .map(app => Number(app.processIdentifier));
}

// Send Chrome's native "make new tab at end of window" command to a PID.
// The destination URL is part of the create event, so no second navigation
// can land in a tab somebody else opened concurrently.
function createTab(pid, windowId, url) {
    const D = $.NSAppleEventDescriptor;
    const code = s => s.split("").reduce((n, c) => n * 256 + c.charCodeAt(0), 0);
    const record = (fields, type) => {
        const r = D.recordDescriptor;
        for (const [key, value] of Object.entries(fields)) r.setDescriptorForKeyword(value, code(key));
        return type ? r.coerceToDescriptorType(code(type)) : r;
    };
    const win = record({want: D.descriptorWithTypeCode(code("cwin")),
        form: D.descriptorWithEnumCode(code("ID  ")), seld: D.descriptorWithString(windowId),
        from: D.nullDescriptor}, "obj ");
    const event = D.appleEventWithEventClassEventIDTargetDescriptorReturnIDTransactionID(
        code("core"), code("crel"), D.descriptorWithProcessIdentifier(pid), -1, 0);
    event.setParamDescriptorForKeyword(D.descriptorWithTypeCode(code("CrTb")), code("kocl"));
    event.setParamDescriptorForKeyword(record({kobj: win, kpos: D.descriptorWithEnumCode(code("end "))}, "insl"), code("insh"));
    event.setParamDescriptorForKeyword(record({"URL ": D.descriptorWithString(url)}), code("prdt"));
    const error = Ref();
    const reply = event.sendEventWithOptionsTimeoutError($.NSAppleEventSendWaitForReply, 10, error);
    if (!reply || reply.isNil()) throw Error("Chrome tab creation unconfirmed. Inspect before retrying.");
    const failure = reply.paramDescriptorForKeyword(code("errn"));
    if (!failure.isNil() && failure.int32Value) throw Error("Chrome tab creation returned " + failure.int32Value);
}

// JXA Application(pid) can resolve back to the front process for a shared
// bundle ID. ScriptingBridge addresses its Apple Events to this specific PID.
function application(pid) {
    ObjC.import("ScriptingBridge");
    const app = $.SBApplication.applicationWithProcessIdentifier(pid);
    function property(obj, key) {
        const value = ObjC.unwrap(obj.valueForKey(key));
        if (value === undefined || value === null) throw Error("Chrome did not return " + key);
        return value;
    }
    function elements(obj, key) {
        const list = obj.valueForKey(key);
        const count = list.count;
        const error = app.lastError;
        if (!error.isNil()) throw Error("Chrome could not list " + key + ": " + ObjC.unwrap(error.localizedDescription));
        return Array.from({length: count}, (_, i) => list.objectAtIndex(i));
    }
    function wrapTab(obj) {
        return {id: () => property(obj, "id"), url: () => property(obj, "URL"),
                title: () => property(obj, "title")};
    }
    function wrapWindow(obj) {
        return {
            id: () => property(obj, "id"), mode: () => property(obj, "mode"),
            tabs: () => elements(obj, "tabs").map(wrapTab),
            focus: index => {
                obj.setValueForKey(index + 1, "activeTabIndex");
                obj.setValueForKey(1, "index");
                app.activate;
                return property(obj.valueForKey("activeTab"), "id");
            },
            openTab: url => {
                const before = elements(obj, "tabs").map(t => property(t, "id"));
                createTab(pid, property(obj, "id"), url);
                const created = elements(obj, "tabs").filter(t => !before.includes(property(t, "id")));
                if (created.length !== 1) throw Error("New tab could not be identified. Inspect before retrying.");
                return wrapTab(created[0]);
            }
        };
    }
    return {windows: () => elements(app, "windows").map(wrapWindow)};
}

function locate(pids, application, url) {
    const matches = [];
    for (const pid of pids) {
        const app = application(pid);
        for (const win of app.windows()) {
            if (win.mode() !== "normal") continue;
            for (const tab of win.tabs()) {
                if (tab.url() === url) matches.push({pid, app, windowId: win.id(), tabId: tab.id()});
            }
        }
    }
    if (matches.length !== 1) throw Error("Expected one exact tab URL match, found " + matches.length);
    return matches[0];
}

function run(args) {
    const pids = chromePids();
    if (args[0] === "--pids") return JSON.stringify(pids);
    const [command, url, destination] = args;
    if (!["--find-tab", "--focus-tab", "--new-tab-in"].includes(command) ||
        args.length !== (command === "--new-tab-in" ? 3 : 2) ||
        !/^https?:\/\//i.test(url) || (command === "--new-tab-in" && !/^https?:\/\//i.test(destination))) {
        throw Error("Use --find-tab URL, --focus-tab URL, or --new-tab-in ANCHOR_URL DESTINATION_URL (HTTP/S).");
    }
    const {pid, app, windowId, tabId} = locate(pids, application, url);
    const window = app.windows().find(w => w.id() === windowId);
    if (!window || window.mode() !== "normal") throw Error("Anchor window changed.");
    const tabs = window.tabs();
    const index = tabs.findIndex(t => t.id() === tabId);
    if (index < 0 || tabs[index].url() !== url) throw Error("Anchor changed; inspect again.");
    let resultTab = tabs[index];
    if (command === "--focus-tab" && window.focus(index) !== tabId)
        throw Error("Active tab changed; verify before acting.");
    if (command === "--new-tab-in") resultTab = window.openTab(destination);
    return JSON.stringify({pid, windowId, tabId: resultTab.id(), title: resultTab.title(), url: resultTab.url()});
}
