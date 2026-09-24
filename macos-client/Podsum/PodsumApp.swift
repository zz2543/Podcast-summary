import SwiftUI

/// 窗口范围的一点点 UI 状态，只为了让菜单命令能够到视图里的 sheet。
@MainActor
@Observable
final class UIState {
    var showSubmit = false
    /// 后端没就绪时，读者可以选择先看打进 bundle 的示例数据
    var offlineBrowsing = false
    var refreshToken = 0

    func requestRefresh() { refreshToken &+= 1 }
}

/// 退出时收掉后端子进程。
///
/// SwiftUI 的 Scene 没有"即将退出"的钩子，这件事只能走 AppDelegate——
/// 不接的话 uvicorn 会活过 app（实测确认：app 退出后端口上还留着监听进程）。
final class AppDelegate: NSObject, NSApplicationDelegate {
    @MainActor var backend: BackendController?

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { backend?.stop() }
    }

    /// 单窗口 app：关掉窗口就是退出，后端也一并停。
    /// 它取代的那个 bash 启动器也是这个语义。
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct PodsumApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var settings = AppSettings.shared
    @State private var backend = BackendController()
    @State private var ui = UIState()
    @State private var jobs = JobsModel()

    /// 读者选的字号档位，跨启动保留。
    /// macOS 没有 Dynamic Type（HIG 明说），这件事只能 app 自己做。
    @AppStorage("textScale") private var textScale: Double = TextScale.standard

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(settings)
                .environment(backend)
                .environment(ui)
                .environment(jobs)
                .environment(\.textScale, textScale)
                // 聊天在详情区域内部展开，窗口最小尺寸保持稳定。
                .frame(minWidth: 880, minHeight: 560)
                .background(alternateZoomKey)
                .task {
                    appDelegate.backend = backend
                    await backend.start()
                }
        }
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1120, height: 760)
        .commands {
            CommandGroup(after: .newItem) {
                Button("添加剧集…") { ui.showSubmit = true }
                    .keyboardShortcut("n", modifiers: .command)
                    .disabled(backend.phase.baseURL == nil)
            }

            // 放进「显示」菜单，与 Safari／邮件／图书的位置一致。
            // 每个动作只出现一次——菜单里重复项会让人以为点错了。
            CommandGroup(after: .toolbar) {
                Button("增大文字") { grow() }
                    .keyboardShortcut("+", modifiers: .command)
                    .disabled(!TextScale.canGrow(textScale))

                Button("减小文字") { shrink() }
                    .keyboardShortcut("-", modifiers: .command)
                    .disabled(!TextScale.canShrink(textScale))

                Button("实际大小（当前 \(TextScale.label(textScale))）") {
                    textScale = TextScale.standard
                }
                .keyboardShortcut("0", modifiers: .command)
                .disabled(abs(textScale - TextScale.standard) < 0.001)

                Divider()

                Button("刷新") { ui.requestRefresh() }
                    .keyboardShortcut("r", modifiers: .command)

                Divider()
            }
        }

        Settings {
            SettingsView()
                .environment(settings)
                .environment(backend)
                .environment(\.textScale, textScale)
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

    private func grow() {
        textScale = TextScale.larger(than: textScale)
    }

    private func shrink() {
        textScale = TextScale.smaller(than: textScale)
    }
}
