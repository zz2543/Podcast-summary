import SwiftUI

// MARK: - 设置页

struct QuickAddSettings: View {
    @Environment(AppSettings.self) private var settings
    @State private var recording = false
    @State private var monitor: Any?

    var body: some View {
        @Bindable var settings = settings

        Form {
            Section {
                Toggle(tr("启用全局快捷键", "Enable Global Hotkey"), isOn: $settings.quickAddHotKeyEnabled)
                LabeledContent(tr("快捷键", "Hotkey")) {
                    Button(recording ? tr("请按下新的组合… (Esc 取消)", "Press a new combination… (Esc to cancel)")
                                     : settings.quickAddHotKey.display) {
                        recording ? stopRecording() : startRecording()
                    }
                    .disabled(!settings.quickAddHotKeyEnabled)
                }
                if settings.quickAddHotKeyEnabled && !settings.quickAddHotKeyRegistered {
                    Label(tr("这个组合用不了，可能被别的程序占用了。换一个试试。",
                             "That combination can’t be used — another app may own it. Try a different one."),
                          systemImage: "exclamationmark.triangle")
                        .foregroundStyle(Tone.warn)
                }
                if settings.quickAddHotKey != .default {
                    Button(tr("恢复默认（\(KeyCombo.default.display)）", "Reset to Default (\(KeyCombo.default.display))")) {
                        settings.quickAddHotKey = .default
                    }
                }
            } header: {
                Text(tr("全局快捷键", "Global Hotkey"))
            } footer: {
                Text(tr("前台是 Safari、Chrome、Arc 或 Edge 时，直接读当前标签页；其他 app（比如 B 站客户端）里先复制链接再按。每个浏览器第一次用会问一次是否允许 Podsum 控制它。关掉主窗口后 Podsum 留在菜单栏，快捷键照样能用。",
                        "With Safari, Chrome, Arc, or Edge in front, the current tab is read directly; in other apps (like the Bilibili client) copy the link first. Each browser asks once whether Podsum may control it. Closing the main window keeps Podsum in the menu bar, so the hotkey keeps working."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section {
                HStack {
                    Button(tr("打开「自动化」权限设置", "Open Automation Settings")) {
                        NSWorkspace.shared.open(BrowserTab.automationSettingsURL)
                    }
                    Button(tr("打开通知设置", "Open Notification Settings")) {
                        NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension")!)
                    }
                }
            } header: {
                Text(tr("权限", "Permissions"))
            } footer: {
                Text(tr("通知关掉也不影响提交，结果都记在主窗口工具栏的「快捷提交」里。",
                        "Submissions work with notifications off — every result is kept under “Quick Add” in the main window’s toolbar."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }
        }
        .formStyle(.grouped)
        .onDisappear { stopRecording() }
    }

    private func startRecording() {
        recording = true
        GlobalHotKey.shared.unregister()   // 录制时按下旧组合，要能被录到而不是触发提交
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == 53 { stopRecording(); return nil }   // Esc
            guard let combo = KeyCombo(event: event) else { NSSound.beep(); return nil }
            settings.quickAddHotKey = combo
            stopRecording()
            return nil
        }
    }

    private func stopRecording() {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
        if recording { settings.applyQuickAddHotKey() }
        recording = false
    }
}

// MARK: - 记录

/// 工具栏「快捷提交」弹出的记录。通知是一闪而过的，这里是兜底。
struct QuickAddLog: View {
    @Environment(QuickAddCenter.self) private var center
    var onOpenEpisode: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(tr("快捷提交", "Quick Add"))
                    .font(.headline)
                Spacer()
                Button(tr("清除已完成", "Clear Finished")) { center.clearFinished() }
                    .disabled(!center.items.contains { $0.state.isTerminal })
            }
            .padding(Space.m)

            Divider()

            if center.items.isEmpty {
                Text(tr("还没有快捷提交。看视频时按 \(AppSettings.shared.quickAddHotKey.display) 就能送过来。",
                        "Nothing sent yet. Press \(AppSettings.shared.quickAddHotKey.display) while watching a video to send it here."))
                    .foregroundStyle(Tone.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(Space.l)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(center.items) { item in
                            QuickAddRow(item: item, onOpenEpisode: onOpenEpisode, onRetry: { center.retry(item.id) })
                            Divider()
                        }
                    }
                }
                .frame(maxHeight: 420)
            }
        }
        .frame(width: 420)
    }
}

private struct QuickAddRow: View {
    let item: QuickAddItem
    var onOpenEpisode: (String) -> Void
    var onRetry: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: Space.m) {
            Image(systemName: icon)
                .foregroundStyle(tint)
                .frame(width: 18)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 3) {
                Text(item.display)
                    .lineLimit(2)
                    .truncationMode(.middle)
                    .foregroundStyle(Tone.text)
                HStack(spacing: 6) {
                    Text(item.state.label).foregroundStyle(tint)
                    Text("·")
                    Text(item.source.label)
                    Text("·")
                    Text(Fmt.relative(item.receivedAt))
                }
                .font(.caption)
                .foregroundStyle(Tone.textSubtle)
                if let message = item.message {
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(Tone.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                }
            }

            Spacer(minLength: 0)

            if let episodeID = item.episodeID {
                Button(tr("打开", "Open")) { onOpenEpisode(episodeID) }
            } else if item.state == .failed {
                Button(tr("重试", "Retry"), action: onRetry)
            }
        }
        .padding(.horizontal, Space.m)
        .padding(.vertical, Space.s)
    }

    private var icon: String {
        switch item.state {
        case .queued:       return "clock"
        case .submitting:   return "arrow.up.circle"
        case .added:        return "checkmark.circle.fill"
        case .existing:     return "checkmark.circle"
        case .unrecognized: return "questionmark.circle"
        case .failed:       return "exclamationmark.triangle.fill"
        }
    }

    private var tint: Color {
        switch item.state {
        case .queued, .submitting: return Tone.info
        case .added, .existing:    return Tone.ok
        case .unrecognized:        return Tone.textSubtle
        case .failed:              return Tone.warn
        }
    }
}

// MARK: - 菜单栏

/// 主窗口关掉以后，Podsum 靠这个图标留在菜单栏里——快捷键要一直能用。
struct MenuBarContent: View {
    @Environment(QuickAddCenter.self) private var center
    @Environment(AppSettings.self) private var settings
    var openMainWindow: () -> Void
    var openEpisode: (String) -> Void

    var body: some View {
        Button(tr("打开 Podsum", "Open Podsum"), action: openMainWindow)

        Divider()

        let recent = Array(center.items.prefix(5))
        if recent.isEmpty {
            Text(settings.quickAddHotKeyEnabled
                 ? tr("按 \(settings.quickAddHotKey.display) 把当前视频送来总结", "Press \(settings.quickAddHotKey.display) to send the current video")
                 : tr("快捷键已关闭，可在设置里打开", "The hotkey is off — turn it on in Settings"))
        } else {
            Text(tr("最近的快捷提交", "Recent Quick Adds"))
            ForEach(recent) { item in
                Button("\(item.state.label) · \(item.display.prefix(40))") {
                    if let id = item.episodeID { openEpisode(id) } else { openMainWindow() }
                }
            }
        }

        Divider()

        SettingsLink { Text(tr("设置…", "Settings…")) }
            .keyboardShortcut(",", modifiers: .command)
        Button(tr("退出 Podsum", "Quit Podsum")) { NSApp.terminate(nil) }
            .keyboardShortcut("q", modifiers: .command)
    }
}
