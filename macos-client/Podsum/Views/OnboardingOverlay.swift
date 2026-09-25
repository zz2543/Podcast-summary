import SwiftUI

// MARK: - 目标上报

extension View {
    /// 把这一行登记为引导可以指向的目标：上报它在**窗口坐标**里的框，并挂上可供滚动的 id。
    ///
    /// 用窗口坐标而不是 `anchorPreference`：grouped Form 在 macOS 上由表格承载，
    /// 偏好值未必穿得过行宿主；窗口坐标不受影响，滚动时也会随之刷新。
    func onboardingTarget(_ target: OnboardingTarget) -> some View {
        modifier(OnboardingTargetReporter(target: target))
    }
}

private struct OnboardingTargetReporter: ViewModifier {
    let target: OnboardingTarget
    @Environment(OnboardingGuide.self) private var guide

    func body(content: Content) -> some View {
        content
            .id(target)
            .background(
                GeometryReader { geo in
                    Color.clear
                        .onAppear { guide.targetFrames[target] = geo.frame(in: .global) }
                        .onChange(of: geo.frame(in: .global)) { _, frame in guide.targetFrames[target] = frame }
                        .onDisappear { guide.targetFrames[target] = nil }
                }
            )
    }
}

// MARK: - 覆盖层

/// 压暗 + 聚光灯 + 气泡。挂在「设置 › 接口」那一页的表单上。
///
/// 压暗层与高亮框都不拦点击：用户直接在高亮的输入框里打字、点按钮，只有气泡本身可点。
struct OnboardingOverlay: View {
    @Environment(OnboardingGuide.self) private var guide
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme

    @State private var bubbleSize = CGSize(width: 380, height: 220)

    private let margin: CGFloat = 12
    private let gap: CGFloat = 14

    var body: some View {
        let steps = OnboardingScript.steps(settings)
        let index = guide.clampedIndex(stepCount: steps.count)
        let step = steps[index]

        GeometryReader { geo in
            let container = geo.frame(in: .global)
            let hole = step.target
                .flatMap { guide.targetFrames[$0] }
                .map { $0.offsetBy(dx: -container.minX, dy: -container.minY).insetBy(dx: -8, dy: -5) }
                .flatMap { visible($0, in: geo.size) }
            let width = hole == nil ? 420 : min(380, geo.size.width - margin * 2)
            let placement = place(hole: hole, bubble: CGSize(width: width, height: bubbleSize.height), in: geo.size)

            ZStack(alignment: .topLeading) {
                SpotlightShape(hole: hole ?? CGRect(x: geo.size.width / 2, y: geo.size.height / 2, width: 0, height: 0))
                    // 深色界面本身就暗，同样的遮罩几乎看不出来，要压得更重
                    .fill(Color.black.opacity(colorScheme == .dark ? 0.62 : 0.38), style: FillStyle(eoFill: true))
                    .allowsHitTesting(false)

                if let hole {
                    PulsingRing(rect: hole, animate: !reduceMotion)
                        .allowsHitTesting(false)
                }

                OnboardingBubble(step: step, index: index, count: steps.count,
                                 arrowEdge: placement.arrowEdge, arrowX: placement.arrowX)
                    .frame(width: width)
                    .fixedSize(horizontal: false, vertical: true)
                    .onGeometryChange(for: CGSize.self) { $0.size } action: { bubbleSize = $0 }
                    .offset(x: placement.origin.x, y: placement.origin.y)
                    .id(step.id)
                    .transition(.opacity.combined(with: .scale(scale: 0.97)))
            }
            .animation(reduceMotion ? nil : .spring(response: 0.38, dampingFraction: 0.86), value: step.id)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.2), value: hole)
        }
    }

    /// 目标完全滚出视野时不画洞（先滚过去，下一帧位置就对了）
    private func visible(_ rect: CGRect, in size: CGSize) -> CGRect? {
        rect.intersects(CGRect(origin: .zero, size: size)) ? rect : nil
    }

    private struct Placement {
        var origin: CGPoint
        var arrowEdge: Edge?
        var arrowX: CGFloat
    }

    /// 目标下方放得下就放下方，否则放上方；都放不下就贴底。水平方向对准目标中点、夹在窗内。
    private func place(hole: CGRect?, bubble: CGSize, in size: CGSize) -> Placement {
        guard let hole else {
            return Placement(origin: CGPoint(x: (size.width - bubble.width) / 2,
                                             y: max(margin, (size.height - bubble.height) / 2)),
                             arrowEdge: nil, arrowX: 0)
        }
        let x = min(max(margin, hole.midX - bubble.width / 2), size.width - bubble.width - margin)
        let arrowX = min(max(24, hole.midX - x), bubble.width - 24)
        if hole.maxY + gap + bubble.height + margin <= size.height {
            return Placement(origin: CGPoint(x: x, y: hole.maxY + gap), arrowEdge: .top, arrowX: arrowX)
        }
        if hole.minY - gap - bubble.height >= margin {
            return Placement(origin: CGPoint(x: x, y: hole.minY - gap - bubble.height), arrowEdge: .bottom, arrowX: arrowX)
        }
        return Placement(origin: CGPoint(x: x, y: max(margin, size.height - bubble.height - margin)), arrowEdge: nil, arrowX: arrowX)
    }
}

/// 整块压暗、挖掉一个圆角矩形。洞的位置可动画，换步时聚光灯会滑过去而不是闪一下。
private struct SpotlightShape: Shape {
    var hole: CGRect

    var animatableData: AnimatablePair<AnimatablePair<CGFloat, CGFloat>, AnimatablePair<CGFloat, CGFloat>> {
        get { .init(.init(hole.minX, hole.minY), .init(hole.width, hole.height)) }
        set { hole = CGRect(x: newValue.first.first, y: newValue.first.second,
                            width: newValue.second.first, height: newValue.second.second) }
    }

    func path(in rect: CGRect) -> Path {
        var p = Path(rect)
        p.addRoundedRect(in: hole, cornerSize: CGSize(width: 9, height: 9), style: .continuous)
        return p
    }
}

/// 高亮框：一道清晰的描边，外面一圈缓慢呼吸的光，提示"在这里操作"。
private struct PulsingRing: View {
    let rect: CGRect
    let animate: Bool
    @State private var breathe = false

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .stroke(Color.accentColor.opacity(breathe ? 0.15 : 0.5), lineWidth: breathe ? 9 : 3)
                .blur(radius: 3)
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .stroke(Color.accentColor, lineWidth: 2)
        }
        .frame(width: rect.width, height: rect.height)
        .offset(x: rect.minX, y: rect.minY)
        .onAppear {
            guard animate else { return }
            withAnimation(.easeInOut(duration: 1.1).repeatForever(autoreverses: true)) { breathe = true }
        }
    }
}

// MARK: - 气泡

private struct OnboardingBubble: View {
    let step: OnboardingStep
    let index: Int
    let count: Int
    let arrowEdge: Edge?
    let arrowX: CGFloat

    @Environment(OnboardingGuide.self) private var guide
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(WebGuideController.self) private var webGuide

    private var status: OnboardingStep.Status? { step.status?(settings, guide, backend) }
    private var isLast: Bool { index == count - 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            Text(step.title)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Tone.text)
            markdown(step.body)
                .font(.system(size: 13))
                .foregroundStyle(Tone.text)
                .lineSpacing(3)

            if !step.tips.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(step.tips.enumerated()), id: \.offset) { _, tip in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Circle().fill(Color.accentColor.opacity(0.7)).frame(width: 4, height: 4)
                                .alignmentGuide(.firstTextBaseline) { $0[.bottom] + 1 }
                            markdown(tip)
                                .font(.system(size: 12))
                                .foregroundStyle(Tone.textMuted)
                                .lineSpacing(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }

            if let example = step.example {
                HStack(spacing: 6) {
                    Text(tr("长这样", "Looks like"))
                        .font(.system(size: 11))
                        .foregroundStyle(Tone.textSubtle)
                    Text(example)
                        .font(.system(size: 11.5, design: .monospaced))
                        .foregroundStyle(Tone.text)
                        .padding(.horizontal, 7).padding(.vertical, 2)
                        .background(Tone.surfaceElev, in: Capsule())
                        .textSelection(.enabled)
                }
            }

            if !step.presets.isEmpty {
                HStack(spacing: 6) {
                    ForEach(Array(step.presets.enumerated()), id: \.offset) { _, preset in
                        Button(preset.title) { preset.apply(settings) }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .focusable(false)
                    }
                }
            }

            if let walkthrough = step.walkthrough, !(status?.isDone ?? false) {
                Button {
                    webGuide.open(walkthrough)
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "safari")
                        VStack(alignment: .leading, spacing: 1) {
                            Text(tr("带我去网站创建", "Walk me through the website"))
                                .font(.system(size: 13, weight: .semibold))
                            Text(tr("打开官网，屏幕右侧一步步指着点哪；点了「复制」自动填回这里",
                                    "Opens the site; a side panel shows where to click, and copied keys fill in here"))
                                .font(.system(size: 11))
                                .opacity(0.85)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 0)
                        Image(systemName: "arrow.up.forward")
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .focusable(false)
            }

            if !step.links.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(step.links.enumerated()), id: \.offset) { _, link in
                        Button {
                            NSWorkspace.shared.open(link.url)
                        } label: {
                            Label(link.title, systemImage: "arrow.up.forward.square")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .buttonStyle(.link)
                        .focusable(false)
                        .help(link.url.absoluteString)
                    }
                }
            }

            if let status {
                StatusLine(status: status)
            }

            Divider().padding(.vertical, 2)
            footer
        }
        .padding(16)
        .background(
            BubbleShape(arrowEdge: arrowEdge, arrowX: arrowX)
                .fill(Tone.surface)
                .shadow(color: .black.opacity(0.28), radius: 18, y: 8)
        )
        .overlay(
            BubbleShape(arrowEdge: arrowEdge, arrowX: arrowX)
                .stroke(Tone.border.opacity(0.6), lineWidth: 0.5)
        )
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image(systemName: step.symbol)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 24, height: 24)
                .background(Color.accentColor, in: Circle())
            Text(tr("第 \(index + 1) 步，共 \(count) 步", "Step \(index + 1) of \(count)"))
                .font(.system(size: 11))
                .foregroundStyle(Tone.textSubtle)
                .monospacedDigit()
            Spacer()
            ProgressDots(index: index, count: count)
        }
    }

    private var footer: some View {
        HStack(spacing: 8) {
            if !isLast {
                Button(tr("跳过引导", "Skip Guide")) { guide.finish() }
                    .buttonStyle(.plain)
                    .focusable(false)
                    .font(.system(size: 12))
                    .foregroundStyle(Tone.textSubtle)
            }
            Spacer()
            if index > 0 {
                Button(tr("上一步", "Back")) { withAnimation { guide.back() } }
                    .controlSize(.regular)
                    .focusable(false)
            }
            primaryButton
        }
    }

    /// 没完成时仍然可以往下走，只是按钮换成「先跳过」、不再是强调色——
    /// 不把人卡死在一格上，但看得出这一格还空着。
    ///
    /// 气泡里的按钮一律不接键盘：用户此刻多半正在高亮的输入框里打字，空格（中文输入法选词）
    /// 或回车一旦落到按钮上，就会一下一下把引导往前推——实测踩过。所以不接焦点，
    /// 主按钮也不用系统的 `.borderedProminent`（它在 macOS 上会被当成窗口的默认按钮、响应回车）。
    private var primaryButton: some View {
        let done = status?.isDone ?? true
        let title = isLast ? tr("完成", "Done")
            : index == 0 ? tr("开始", "Start")
            : done ? tr("下一步", "Next") : tr("先跳过", "Skip for Now")
        return Button(title) { advance() }
            .buttonStyle(GuideButtonStyle(prominent: done))
            .focusable(false)
    }

    private func advance() {
        withAnimation { guide.next(stepCount: count) }
    }

    private func markdown(_ text: String) -> Text {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        return Text((try? AttributedString(markdown: text, options: options)) ?? AttributedString(text))
    }
}

/// 状态行：实时反映这一步的完成条件。
private struct StatusLine: View {
    let status: OnboardingStep.Status
    @State private var blink = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            switch status {
            case .waiting(let text):
                Circle().fill(Tone.warn).frame(width: 7, height: 7)
                    .opacity(blink ? 0.35 : 1)
                    .onAppear {
                        guard !reduceMotion else { return }
                        withAnimation(.easeInOut(duration: 0.8).repeatForever()) { blink = true }
                    }
                Text(text).foregroundStyle(Tone.textMuted)
            case .working(let text):
                ProgressView().controlSize(.mini)
                Text(text).foregroundStyle(Tone.textMuted)
            case .done(let text):
                Image(systemName: "checkmark.circle.fill").foregroundStyle(Tone.ok)
                Text(text).foregroundStyle(Tone.ok)
            case .problem(let text):
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Tone.warn)
                Text(text).foregroundStyle(Tone.text)
                    .textSelection(.enabled)
            }
        }
        .font(.system(size: 12, weight: .medium))
        .fixedSize(horizontal: false, vertical: true)
        .padding(.horizontal, 10).padding(.vertical, 7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .animation(.easeOut(duration: 0.2), value: status)
    }
}

private struct ProgressDots: View {
    let index: Int
    let count: Int

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<count, id: \.self) { i in
                Capsule()
                    .fill(i <= index ? Color.accentColor : Tone.border)
                    .frame(width: i == index ? 12 : 5, height: 5)
            }
        }
        .animation(.easeOut(duration: 0.2), value: index)
    }
}

/// 圆角气泡，带一个指向目标的小三角。
private struct BubbleShape: Shape {
    let arrowEdge: Edge?
    let arrowX: CGFloat
    private let radius: CGFloat = 14
    private let arrow = CGSize(width: 18, height: 8)

    func path(in rect: CGRect) -> Path {
        var p = Path(roundedRect: rect, cornerRadius: radius, style: .continuous)
        guard let arrowEdge else { return p }
        let x = min(max(rect.minX + radius + arrow.width / 2, rect.minX + arrowX), rect.maxX - radius - arrow.width / 2)
        var tri = Path()
        switch arrowEdge {
        case .top:
            tri.move(to: CGPoint(x: x - arrow.width / 2, y: rect.minY + 0.5))
            tri.addLine(to: CGPoint(x: x, y: rect.minY - arrow.height))
            tri.addLine(to: CGPoint(x: x + arrow.width / 2, y: rect.minY + 0.5))
        case .bottom:
            tri.move(to: CGPoint(x: x - arrow.width / 2, y: rect.maxY - 0.5))
            tri.addLine(to: CGPoint(x: x, y: rect.maxY + arrow.height))
            tri.addLine(to: CGPoint(x: x + arrow.width / 2, y: rect.maxY - 0.5))
        default:
            return p
        }
        tri.closeSubpath()
        p.addPath(tri)
        return p
    }
}

/// 引导进行中、用户却切到了别的设置页：给一条回去的路
struct OnboardingReturnBanner: View {
    @Environment(OnboardingGuide.self) private var guide

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "hand.point.up.left.fill").foregroundStyle(Color.accentColor)
            Text(tr("新手引导还在进行", "The setup guide is still running"))
                .font(.system(size: 12, weight: .medium))
            Spacer()
            Button(tr("回到「接口」继续", "Back to Providers")) { guide.settingsTab = .providers }
                .buttonStyle(.borderedProminent).controlSize(.small)
            Button(tr("结束引导", "End Guide")) { guide.finish() }
                .controlSize(.small)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(.regularMaterial)
    }
}

/// 气泡的主按钮：外观接近系统强调按钮，但不带默认按钮的回车语义
private struct GuideButtonStyle: ButtonStyle {
    let prominent: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .medium))
            .foregroundStyle(prominent ? Color.white : Tone.text)
            .padding(.horizontal, 14)
            .padding(.vertical, 5)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(prominent ? Color.accentColor : Tone.surfaceElev)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .stroke(prominent ? Color.clear : Tone.border, lineWidth: 0.5)
            )
            .opacity(configuration.isPressed ? 0.75 : 1)
            .contentShape(Rectangle())
    }
}
