import SwiftUI

/// 贴在屏幕右侧的置顶面板：用户在浏览器里操作厂商控制台，这里一步一步写着点哪。
///
/// 当前一步展开、其余折叠成一行；做过的打勾。拿 key 的那一步底部有剪贴板检测条：
/// 用户在网页上点「复制」，这里就冒出「检测到 sk-…，填入？」。
struct WebGuidePanel: View {
    let controller: WebGuideController
    let settings: AppSettings

    var body: some View {
        if let w = controller.walkthrough {
            VStack(alignment: .leading, spacing: 0) {
                header(w)
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(w.steps.enumerated()), id: \.element.id) { i, step in
                            StepRow(step: step, number: i + 1, state: state(of: i, step: step),
                                    open: { controller.openCurrentPage() },
                                    select: { controller.go(to: i) })
                        }
                    }
                    .padding(14)
                }
                if let c = controller.candidate {
                    CaptureBar(candidate: c, accept: controller.accept, dismiss: controller.dismissCandidate)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                } else if let capture = controller.step?.capture, capture.field.value(in: settings).isBlank {
                    // 已经填上的就不再等了
                    WatchingBar()
                }
                footer(w)
            }
            .frame(minWidth: 320)
            .background(Tone.bg)
            .animation(.spring(response: 0.35, dampingFraction: 0.85), value: controller.index)
            .animation(.easeOut(duration: 0.2), value: controller.candidate)
        }
    }

    private func header(_ w: WebWalkthrough) -> some View {
        HStack(spacing: 10) {
            Image(systemName: w.symbol)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 30, height: 30)
                .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text(w.vendor).font(.system(size: 14, weight: .semibold))
                Text(tr("照着左边浏览器里的页面一步步来", "Follow along in your browser"))
                    .font(.system(size: 11)).foregroundStyle(Tone.textSubtle)
            }
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.top, 30)   // 让出透明标题栏
        .padding(.bottom, 10)
    }

    private func footer(_ w: WebWalkthrough) -> some View {
        HStack(spacing: 8) {
            Button(tr("上一步", "Back")) { controller.back() }
                .disabled(controller.index == 0)
            Spacer()
            if controller.isFinished {
                Button(tr("回到懂听继续", "Back to GotIt")) { controller.returnToApp() }
                    .buttonStyle(.borderedProminent)
            } else if controller.index + 1 < w.steps.count {
                Button(tr("下一步", "Next")) { controller.next() }
                    .buttonStyle(.borderedProminent)
            } else {
                Button(tr("回到懂听", "Back to GotIt")) { controller.returnToApp() }
            }
        }
        .controlSize(.regular)
        .padding(12)
        .background(.bar)
    }

    private func state(of i: Int, step: WebWalkthrough.Step) -> StepRow.State {
        if let c = step.capture, !c.field.value(in: settings).isBlank, i != controller.index { return .done }
        if controller.filled.contains(step.id) { return .done }
        if i < controller.index { return .done }
        return i == controller.index ? .current : .upcoming
    }
}

private struct StepRow: View {
    enum State { case done, current, upcoming }

    let step: WebWalkthrough.Step
    let number: Int
    let state: State
    let open: () -> Void
    let select: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            badge
            VStack(alignment: .leading, spacing: 8) {
                Text(step.title)
                    .font(.system(size: state == .current ? 14 : 12.5, weight: state == .current ? .semibold : .regular))
                    .foregroundStyle(state == .upcoming ? Tone.textSubtle : Tone.text)
                    .fixedSize(horizontal: false, vertical: true)

                if state == .current {
                    ForEach(Array(step.details.enumerated()), id: \.offset) { _, line in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text("·").foregroundStyle(Color.accentColor)
                            markdown(line)
                                .font(.system(size: 12.5))
                                .foregroundStyle(Tone.textMuted)
                                .lineSpacing(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    if step.url != nil {
                        Button(action: open) {
                            Label(tr("在浏览器里打开这一页", "Open this page in the browser"), systemImage: "safari")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(state == .current ? 12 : 8)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(state == .current ? Tone.surface : Color.clear)
                .shadow(color: .black.opacity(state == .current ? 0.12 : 0), radius: 6, y: 2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(state == .current ? Color.accentColor.opacity(0.5) : Color.clear, lineWidth: 1)
        )
        .contentShape(Rectangle())
        .onTapGesture { if state != .current { select() } }
    }

    @ViewBuilder private var badge: some View {
        ZStack {
            Circle().fill(state == .done ? Tone.ok : state == .current ? Color.accentColor : Tone.surfaceElev)
            if state == .done {
                Image(systemName: "checkmark").font(.system(size: 10, weight: .bold)).foregroundStyle(.white)
            } else {
                Text("\(number)").font(.system(size: 11, weight: .semibold)).monospacedDigit()
                    .foregroundStyle(state == .current ? .white : Tone.textSubtle)
            }
        }
        .frame(width: 22, height: 22)
    }

    private func markdown(_ text: String) -> Text {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        return Text((try? AttributedString(markdown: text, options: options)) ?? AttributedString(text))
    }
}

/// 等用户在网页上点「复制」
private struct WatchingBar: View {
    @State private var pulse = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "doc.on.clipboard")
                .foregroundStyle(Color.accentColor)
                .opacity(pulse ? 0.4 : 1)
                .onAppear {
                    guard !reduceMotion else { return }
                    withAnimation(.easeInOut(duration: 0.9).repeatForever()) { pulse = true }
                }
            VStack(alignment: .leading, spacing: 2) {
                Text(tr("正在等你在网页上点「复制」", "Waiting for you to click “Copy” on the page"))
                    .font(.system(size: 12, weight: .medium))
                Text(tr("macOS 第一次可能会问是否允许懂听读取剪贴板，选「允许」。复制的内容不会离开这台 Mac。",
                        "macOS may ask once whether GotIt can read the clipboard — choose Allow. Nothing leaves this Mac."))
                    .font(.system(size: 11))
                    .foregroundStyle(Tone.textSubtle)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surfaceElev)
    }
}

/// 认出来了：给人看一眼（打码），确认再填
private struct CaptureBar: View {
    let candidate: WebGuideController.Candidate
    let accept: () -> Void
    let dismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "checkmark.seal.fill").foregroundStyle(Tone.ok)
                Text(tr("检测到你刚复制的 \(candidate.field.label)", "Found the \(candidate.field.label) you just copied"))
                    .font(.system(size: 12.5, weight: .semibold))
            }
            Text(candidate.masked)
                .font(.system(size: 12, design: .monospaced))
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(Tone.surface, in: Capsule())
            HStack {
                Button(tr("填入懂听", "Fill into GotIt"), action: accept)
                    .buttonStyle(.borderedProminent)
                Button(tr("不是这个", "Not this one"), action: dismiss)
            }
            .controlSize(.regular)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.ok.opacity(0.12))
    }
}
