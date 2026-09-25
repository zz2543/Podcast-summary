import AppKit
import Carbon.HIToolbox
import UserNotifications

// 快捷提交的三个外部接口：全局快捷键、浏览器当前标签页、系统通知。
// 各自只管和系统打交道，排队与提交在 `QuickAddCenter`。

// MARK: - 全局快捷键

/// 用 Carbon 的 `RegisterEventHotKey` 注册。
///
/// 选它而不是 `NSEvent.addGlobalMonitorForEvents`：后者要「辅助功能」授权，
/// 而且只能旁听、吞不掉按键；这个不需要任何授权，按键也不会再落到前台 app 里。
@MainActor
final class GlobalHotKey {
    static let shared = GlobalHotKey()

    var onPress: (() -> Void)?

    private var hotKey: EventHotKeyRef?
    private var handler: EventHandlerRef?

    /// 注册一个组合，替换掉之前的。失败（通常是被别的程序占了）返回 false。
    @discardableResult
    func register(_ combo: KeyCombo) -> Bool {
        unregister()
        installHandlerIfNeeded()
        let id = EventHotKeyID(signature: OSType(0x5044_534D), id: 1)   // 'PDSM'
        var ref: EventHotKeyRef?
        let status = RegisterEventHotKey(combo.keyCode, combo.carbonModifiers, id,
                                         GetApplicationEventTarget(), 0, &ref)
        guard status == noErr, let ref else { return false }
        hotKey = ref
        return true
    }

    func unregister() {
        if let hotKey { UnregisterEventHotKey(hotKey) }
        hotKey = nil
    }

    private func installHandlerIfNeeded() {
        guard handler == nil else { return }
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            // Carbon 在主线程上回调
            MainActor.assumeIsolated { GlobalHotKey.shared.onPress?() }
            return noErr
        }, 1, &spec, nil, &handler)
    }
}

/// 一个按键组合。存的是 Carbon 需要的原始值，外加录制时看到的键名。
struct KeyCombo: Codable, Equatable {
    var keyCode: UInt32
    var carbonModifiers: UInt32
    var keyLabel: String

    /// ⌥⌘S
    static let `default` = KeyCombo(keyCode: UInt32(kVK_ANSI_S),
                                    carbonModifiers: UInt32(cmdKey | optionKey),
                                    keyLabel: "S")

    var display: String {
        var s = ""
        if carbonModifiers & UInt32(controlKey) != 0 { s += "⌃" }
        if carbonModifiers & UInt32(optionKey) != 0 { s += "⌥" }
        if carbonModifiers & UInt32(shiftKey) != 0 { s += "⇧" }
        if carbonModifiers & UInt32(cmdKey) != 0 { s += "⌘" }
        return s + keyLabel
    }

    /// 从一次按键录出组合。只有 ⇧ 或不带修饰键的不算——那会吃掉正常打字。
    init?(event: NSEvent) {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        guard !flags.intersection([.command, .option, .control]).isEmpty else { return nil }
        var mods: UInt32 = 0
        if flags.contains(.command) { mods |= UInt32(cmdKey) }
        if flags.contains(.option)  { mods |= UInt32(optionKey) }
        if flags.contains(.control) { mods |= UInt32(controlKey) }
        if flags.contains(.shift)   { mods |= UInt32(shiftKey) }
        let label = Self.label(for: event)
        guard !label.isEmpty else { return nil }
        self.init(keyCode: UInt32(event.keyCode), carbonModifiers: mods, keyLabel: label)
    }

    init(keyCode: UInt32, carbonModifiers: UInt32, keyLabel: String) {
        self.keyCode = keyCode
        self.carbonModifiers = carbonModifiers
        self.keyLabel = keyLabel
    }

    private static func label(for event: NSEvent) -> String {
        switch Int(event.keyCode) {
        case kVK_Space:  return "Space"
        case kVK_Return: return "↩"
        case kVK_Tab:    return "⇥"
        default: break
        }
        if let fn = functionKeyNames[Int(event.keyCode)] { return fn }
        // ⌥ 会把字母变成特殊字符（⌥S → ß），键名要取不带修饰键的那个
        return (event.charactersIgnoringModifiers ?? "").uppercased()
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static let functionKeyNames: [Int: String] = [
        kVK_F1: "F1", kVK_F2: "F2", kVK_F3: "F3", kVK_F4: "F4", kVK_F5: "F5", kVK_F6: "F6",
        kVK_F7: "F7", kVK_F8: "F8", kVK_F9: "F9", kVK_F10: "F10", kVK_F11: "F11", kVK_F12: "F12",
    ]
}

// MARK: - 浏览器当前标签页

/// 用 AppleScript 问前台浏览器要当前标签页的地址。
///
/// 每个浏览器第一次被问时，系统会弹「Podsum 想要控制 …」；
/// 拒绝后再问会立刻得到 -1743，这时退回剪贴板。
enum BrowserTab {
    enum Outcome: Equatable {
        case url(String)
        /// 用户没授权（或授权被撤回）
        case notAuthorized
        /// 没有窗口、脚本出错等
        case unavailable
    }

    /// bundle id → 浏览器名。Chromium 系的字典与 Chrome 相同。
    static let supported: [String: String] = [
        "com.apple.Safari": "Safari",
        "com.apple.SafariTechnologyPreview": "Safari Technology Preview",
        "com.google.Chrome": "Google Chrome",
        "company.thebrowser.Browser": "Arc",
        "com.microsoft.edgemac": "Microsoft Edge",
    ]

    static func isSupported(_ bundleID: String?) -> Bool {
        guard let bundleID else { return false }
        return supported[bundleID] != nil
    }

    static func read(_ bundleID: String) async -> Outcome {
        let source: String
        if bundleID.hasPrefix("com.apple.Safari") {
            source = "tell application id \"\(bundleID)\" to return URL of front document"
        } else {
            source = "tell application id \"\(bundleID)\" to return URL of active tab of front window"
        }
        // 首次授权时这一步会一直等到用户点完系统弹窗，所以不在主线程上跑。
        return await withCheckedContinuation { continuation in
            queue.async {
                var error: NSDictionary?
                let result = NSAppleScript(source: source)?.executeAndReturnError(&error)
                if let url = result?.stringValue, !url.isEmpty {
                    continuation.resume(returning: .url(url))
                } else if (error?[NSAppleScript.errorNumber] as? Int) == -1743 {
                    continuation.resume(returning: .notAuthorized)
                } else {
                    continuation.resume(returning: .unavailable)
                }
            }
        }
    }

    /// NSAppleScript 不是线程安全的，固定在一条串行队列上用。
    private static let queue = DispatchQueue(label: "local.podsum.browser-tab")

    /// 系统设置 › 隐私与安全性 › 自动化
    static let automationSettingsURL = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation")!
}

// MARK: - 系统通知

/// 一条快捷提交对应一条通知：先发「已收到」，出结果后用同一个 identifier 覆盖，
/// 通知中心里不会攒出一串过期的中间状态。
@MainActor
final class QuickAddNotifier: NSObject, UNUserNotificationCenterDelegate {
    static let shared = QuickAddNotifier()

    /// 点了带剧集的通知
    var onOpenEpisode: ((String) -> Void)?
    /// 点了不带剧集的通知（失败、无法识别）
    var onOpenLog: (() -> Void)?

    private(set) var authorization: UNAuthorizationStatus = .notDetermined
    private var asked = false

    private var center: UNUserNotificationCenter { .current() }

    func activate() {
        center.delegate = self
        Task { await refreshAuthorization() }
    }

    func refreshAuthorization() async {
        authorization = await center.notificationSettings().authorizationStatus
    }

    func post(id: String, title: String, body: String, episodeID: String? = nil) {
        Task {
            if !asked {
                asked = true
                _ = try? await center.requestAuthorization(options: [.alert])
                await refreshAuthorization()
            }
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.threadIdentifier = "quick-add"
            if let episodeID { content.userInfo = ["episodeID": episodeID] }
            try? await center.add(UNNotificationRequest(identifier: id, content: content, trigger: nil))
        }
    }

    // Podsum 在前台时系统默认不弹横幅；快捷提交的结果照样要看得见。
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list]
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            didReceive response: UNNotificationResponse) async {
        let episodeID = response.notification.request.content.userInfo["episodeID"] as? String
        await MainActor.run {
            if let episodeID { onOpenEpisode?(episodeID) } else { onOpenLog?() }
        }
    }
}
