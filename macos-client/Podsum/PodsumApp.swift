import SwiftUI

@main
struct PodsumApp: App {
    /// 阶段 1 注入 Mock；阶段 3 换成 LiveRepository，视图一行不改。
    @State private var repository: any EpisodeRepository = MockRepository()

    /// 读者选的字号档位，跨启动保留。
    /// macOS 没有 Dynamic Type（HIG 明说），这件事只能 app 自己做。
    @AppStorage("textScale") private var textScale: Double = TextScale.standard

    var body: some Scene {
        WindowGroup {
            EpisodeListView()
                .environment(\.episodeRepository, repository)
                .environment(\.textScale, textScale)
                .frame(minWidth: 880, minHeight: 560)
                .background(alternateZoomKey)
        }
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1120, height: 760)
        .commands {
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
            }
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
