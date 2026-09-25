import SwiftUI

/// 沿容器边缘的一圈炫彩光，表示「这里交给 AI」。
///
/// 做法：一张缓慢旋转的角向渐变，用三层粗细、模糊各异的描边当遮罩——
/// 最细那层是清晰的边线，另两层是向外晕开的光。形状内部整块挖掉，
/// 光只落在轮廓外侧，不压到内容上。
///
/// 光向外铺开需要地方：本视图比形状每边大出 `spread`，调用方要在
/// 形状四周留出同样的透明边距（见 `aiGlowBorder`）。
///
/// 节奏：出现时亮起，随后收敛成若隐若现的一圈；`isActive` 为真（比如
/// 正在提交）时重新亮起。旋转只改变换、不重画渐变，开销很小；
/// 「减弱动态效果」打开时不转，只保留静止的光。
struct AIGlowBorder<S: Shape>: View {
    var shape: S
    var isActive = false
    /// 光向外铺开的距离
    var spread: CGFloat = AIGlowMetrics.spread

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme
    @State private var intensity = 0.0
    @State private var spin = false

    /// 收敛后的亮度。浅色背景上光更难看出来，给高一点。
    private var restLevel: Double { colorScheme == .dark ? 0.55 : 0.7 }

    var body: some View {
        GeometryReader { geo in
            // 旋转的是一张边长等于对角线的方形，转到任何角度都铺满整个区域
            let side = hypot(geo.size.width, geo.size.height)
            AngularGradient(colors: AIPalette.loop, center: .center)
                .frame(width: side, height: side)
                .rotationEffect(.degrees(spin ? 360 : 0))
                .position(x: geo.size.width / 2, y: geo.size.height / 2)
        }
        .mask {
            ZStack {
                shape.stroke(lineWidth: 22).blur(radius: 11).opacity(0.65)
                shape.stroke(lineWidth: 10).blur(radius: 4).opacity(0.9)
                shape.stroke(lineWidth: 2.5)
            }
            .padding(spread)
        }
        // 挖掉形状内部，只留外圈
        .mask {
            Rectangle()
                .overlay { shape.padding(spread).blendMode(.destinationOut) }
                .compositingGroup()
        }
        .opacity(intensity)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .task {
            if !reduceMotion {
                withAnimation(.linear(duration: 7).repeatForever(autoreverses: false)) { spin = true }
            }
            withAnimation(.easeOut(duration: 0.5)) { intensity = 1 }
            try? await Task.sleep(for: .seconds(1.6))
            guard !isActive else { return }
            withAnimation(.easeInOut(duration: 1.4)) { intensity = restLevel }
        }
        .onChange(of: isActive) { _, active in
            withAnimation(.easeInOut(duration: active ? 0.4 : 1.2)) {
                intensity = active ? 1 : restLevel
            }
        }
    }
}

/// AI 相关元素共用的一组颜色
enum AIPalette {
    static let colors: [Color] = [
        Color(red: 0.74, green: 0.51, blue: 0.95),  // 紫
        Color(red: 0.96, green: 0.73, blue: 0.92),  // 粉
        Color(red: 1.00, green: 0.40, blue: 0.47),  // 珊瑚红
        Color(red: 1.00, green: 0.73, blue: 0.44),  // 橙
        Color(red: 0.55, green: 0.62, blue: 1.00),  // 蓝
        Color(red: 0.40, green: 0.80, blue: 1.00),  // 青
    ]

    /// 首尾同色，旋转时接缝处不会出现硬边
    static var loop: [Color] { colors + [colors[0]] }
}

enum AIGlowMetrics {
    /// 要容得下最外层光的模糊半径，否则光会被窗口边缘切出一道直线
    static let spread: CGFloat = 44
}

extension View {
    /// 在视图外围亮一圈 AI 炫彩光，`shape` 是视图自身的外轮廓。
    ///
    /// 会在视图四周加 `AIGlowMetrics.spread` 的透明边距给光留地方，
    /// 所以容器本身得是透明的（比如 `presentationBackground(.clear)` 的 sheet）。
    func aiGlowBorder(in shape: some Shape, isActive: Bool = false) -> some View {
        background {
            AIGlowBorder(shape: shape, isActive: isActive)
                .padding(-AIGlowMetrics.spread)
        }
        .padding(AIGlowMetrics.spread)
    }
}

// MARK: - 透明的宿主窗口
//
// 光在外围，就得画在玻璃外面；可系统 sheet 窗口自带一层材质底板
// （theme frame 里的 NSVisualEffectView）、一圈边框和窗口阴影，
// `presentationBackground(.clear)` 管不到它们（macOS 26/27 实测）。
// 这里把宿主窗口整个变透明：藏起那层底板、清掉背景、关掉窗口阴影，
// 外观全交给 SwiftUI——玻璃、阴影、光圈都由视图自己画。

extension View {
    /// 让承载本视图的窗口完全透明。视图得自己画出底板和阴影。
    func transparentHostWindow() -> some View {
        background(TransparentWindowConfigurator())
    }
}

private struct TransparentWindowConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { Probe() }
    func updateNSView(_ nsView: NSView, context: Context) {}

    private final class Probe: NSView {
        private var updateToken: NSObjectProtocol?

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if let updateToken { NotificationCenter.default.removeObserver(updateToken) }
            updateToken = nil
            guard let window else { return }
            configure()
            // 改了窗口背景色，系统会拆掉材质底板、在 sheet 上屏前一刻再装一块新的
            // （实测在私有的 _NSWindowWillBecomeVisible 时装上）。等下一轮 runloop
            // 再藏就晚了：滑入动画跑在私有 runloop 模式里，那几帧老底板会闪一下。
            // didUpdate 紧跟着那一步同步发出，此时窗口还没上屏，在这里藏正好；
            // 之后每轮事件循环也都会发，系统再换底板也跟得上。
            updateToken = NotificationCenter.default.addObserver(
                forName: NSWindow.didUpdateNotification, object: window, queue: nil
            ) { [weak self] _ in
                MainActor.assumeIsolated { self?.configure() }
            }
        }

        deinit {
            if let updateToken { NotificationCenter.default.removeObserver(updateToken) }
        }

        private func configure() {
            guard let window else { return }
            if window.isOpaque { window.isOpaque = false }
            if window.backgroundColor != .clear { window.backgroundColor = .clear }
            if window.hasShadow { window.hasShadow = false }
            // 系统的材质底板是 theme frame 的直接子视图
            for view in window.contentView?.superview?.subviews ?? []
            where view is NSVisualEffectView && !view.isHidden {
                view.isHidden = true
            }
        }
    }
}
