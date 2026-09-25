import SwiftUI

/// 窗口范围的一点点 UI 状态，只为了让菜单命令能够到视图里的 sheet。
@MainActor
@Observable
final class UIState {
    var showSubmit = false
    /// 后端没就绪时，读者可以选择先看打进 bundle 的示例数据
    var offlineBrowsing = false
    var refreshToken = 0
    /// 要在列表页推进去的那一集（点了快捷提交的通知或记录）
    var pendingEpisodeID: String?
    var showQuickAddLog = false
    /// 菜单栏「分类」里的两项，列表页据此弹出对应的面板（004）
    var showNewCategory = false
    var showCategorize = false

    /// 打开（或带到前面）主窗口。由持有 `openWindow` 的视图填进来——
    /// 通知回调、Dock 点击这些地方拿不到 SwiftUI 的环境。
    @ObservationIgnored var openMainWindowAction: (() -> Void)?

    func requestRefresh() { refreshToken &+= 1 }

    func openMainWindow() {
        NSApp.activate(ignoringOtherApps: true)
        openMainWindowAction?()
    }

    func openEpisode(_ id: String) {
        pendingEpisodeID = id
        openMainWindow()
    }
}

/// app 级的状态都挂在这里，而不是某个窗口上。
///
/// 003 之前关窗即退出，后端跟着窗口的 `.task` 起；现在关掉主窗口 Podsum 还留在菜单栏，
/// 全局快捷键随时会送链接进来，后端与快捷提交队列就必须活得比窗口久。
///
/// 退出时收掉后端子进程也只能走这里：SwiftUI 的 Scene 没有"即将退出"的钩子，
/// 不接的话 uvicorn 会活过 app（实测确认：app 退出后端口上还留着监听进程）。
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let settings = AppSettings.shared
    let backend = BackendController()
    let ui = UIState()
    let jobs = JobsModel()
    lazy var quickAdd = QuickAddCenter(backend: backend)

    func applicationDidFinishLaunching(_ notification: Notification) {
        let notifier = QuickAddNotifier.shared
        notifier.onOpenEpisode = { [ui] id in ui.openEpisode(id) }
        notifier.onOpenLog = { [ui] in
            ui.showQuickAddLog = true
            ui.openMainWindow()
        }
        notifier.activate()

        quickAdd.onAdded = { [ui] in ui.requestRefresh() }
        GlobalHotKey.shared.onPress = { [quickAdd] in quickAdd.hotKeyPressed() }
        settings.applyQuickAddHotKey()

        Task { await backend.start() }
    }

    func applicationWillTerminate(_ notification: Notification) {
        backend.stop()
    }

    /// 关掉主窗口不退出：Podsum 留在菜单栏，快捷键照常可用（FR-016）。⌘Q 才是退出。
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// 窗口都关了再点 Dock 图标：把主窗口开回来
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { ui.openMainWindow() }
        return true
    }
}

@main
struct PodsumApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    /// 放在 App 上而不是等第一次 `tr()` 才建，好尽早写好 AppleLanguages。
    @State private var localizer = Localizer.shared

    /// 读者选的字号档位，跨启动保留。
    /// macOS 没有 Dynamic Type（HIG 明说），这件事只能 app 自己做。
    @AppStorage("textScale") private var textScale: Double = TextScale.standard

    private var settings: AppSettings { appDelegate.settings }
    private var backend: BackendController { appDelegate.backend }
    private var ui: UIState { appDelegate.ui }
    private var jobs: JobsModel { appDelegate.jobs }

    var body: some Scene {
        // 单一主窗口：通知、菜单栏、Dock 反复打开它时不会多开窗口
        Window("Podsum", id: "main") {
            RootView()
                .environment(settings)
                .environment(backend)
                .environment(ui)
                .environment(jobs)
                .environment(appDelegate.quickAdd)
                .environment(\.textScale, textScale)
                .environment(\.locale, localizer.locale)
                // 聊天在详情区域内部展开，窗口最小尺寸保持稳定。
                .frame(minWidth: 880, minHeight: 560)
                .background(alternateZoomKey)
                .background(MainWindowOpener(ui: ui))
        }
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1120, height: 760)
        .commands {
            CommandGroup(after: .newItem) {
                Button(tr("添加剧集…", "Add Episodes…")) { ui.showSubmit = true }
                    .keyboardShortcut("n", modifiers: .command)
                    .disabled(backend.phase.baseURL == nil)
            }

            // 放进「显示」菜单，与 Safari／邮件／图书的位置一致。
            // 每个动作只出现一次——菜单里重复项会让人以为点错了。
            CommandMenu(tr("分类", "Categories")) {
                Group {
                    Button(tr("新建分类…", "New Category…")) { ui.showNewCategory = true }
                        .keyboardShortcut("n", modifiers: [.command, .shift])
                    Button(tr("AI 分类…", "AI Categorize…")) { ui.showCategorize = true }
                }
                .disabled(backend.phase.baseURL == nil && !ui.offlineBrowsing)
            }
            CommandGroup(after: .toolbar) {
                Button(tr("增大文字", "Bigger Text")) { grow() }
                    .keyboardShortcut("+", modifiers: .command)
                    .disabled(!TextScale.canGrow(textScale))

                Button(tr("减小文字", "Smaller Text")) { shrink() }
                    .keyboardShortcut("-", modifiers: .command)
                    .disabled(!TextScale.canShrink(textScale))

                Button(tr("实际大小（当前 \(TextScale.label(textScale))）", "Actual Size (now \(TextScale.label(textScale)))")) {
                    textScale = TextScale.standard
                }
                .keyboardShortcut("0", modifiers: .command)
                .disabled(abs(textScale - TextScale.standard) < 0.001)

                Divider()

                Button(tr("刷新", "Refresh")) { ui.requestRefresh() }
                    .keyboardShortcut("r", modifiers: .command)

                Divider()
            }
        }

        MenuBarExtra {
            MenuBarContent(openMainWindow: { ui.openMainWindow() }, openEpisode: { ui.openEpisode($0) })
                .environment(appDelegate.quickAdd)
                .environment(settings)
        } label: {
            Image(systemName: appDelegate.quickAdd.pending.isEmpty ? "waveform" : "waveform.badge.plus")
                .background(MainWindowOpener(ui: ui))
        }

        Settings {
            SettingsView()
                .environment(settings)
                .environment(backend)
                .environment(\.textScale, textScale)
                .environment(\.locale, localizer.locale)
        }
    }

    /// 放大字号的两个物理按法，都要能用。
    ///
    /// 菜单项声明的是 `"+" + .command`，它负责在菜单里显示成 ⌘+，
    /// 但**不会真的触发**：SwiftUI 要求修饰键完全吻合，而读者按 ⌘+ 时
    /// 键盘实际发出的是 cmd+shift+=，与 `.command` 单键不匹配（已实测确认）。
    ///
    /// 所以这里挂两个不可见按钮兜住真实按键：
    ///   ⌘=        不按 shift 的那个键位
    ///   ⌘⇧=       就是读者理解的 ⌘+
    /// 放在视图层而不是菜单里，菜单才不会多出重复项。
    private var alternateZoomKey: some View {
        ZStack {
            Button("", action: grow)
                .keyboardShortcut("=", modifiers: .command)
            // 注意是 "=" 而不是 "+"：物理键是 =，shift 是修饰键。
            // 写成 KeyEquivalent("+") 会失败——那个字符本身已隐含 shift，
            // 再叠加 .shift 就匹配不上了（实测过）。
            Button("", action: grow)
                .keyboardShortcut("=", modifiers: [.command, .shift])
        }
        .opacity(0)
        .frame(width: 0, height: 0)
        .accessibilityHidden(true)
    }

    /// 把 SwiftUI 的 `openWindow` 交给 `UIState`，好让通知、Dock、菜单栏也能开主窗口。
    /// 菜单栏图标与主窗口各挂一份：主窗口关掉以后，图标上那份还在。
    private struct MainWindowOpener: View {
        let ui: UIState
        @Environment(\.openWindow) private var openWindow

        var body: some View {
            Color.clear
                .frame(width: 0, height: 0)
                .onAppear { ui.openMainWindowAction = { openWindow(id: "main") } }
        }
    }

    private func grow() {
        textScale = TextScale.larger(than: textScale)
    }

    private func shrink() {
        textScale = TextScale.smaller(than: textScale)
    }
}
