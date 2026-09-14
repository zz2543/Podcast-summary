import SwiftUI

struct StatusDot: View {
    let status: Fallback<EpisodeStatus>
    var showLabel = true

    @State private var pulsing = false

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(status.tint)
                .frame(width: 8, height: 8)
                .opacity(status.isAnimating && pulsing ? 0.35 : 1)
                .animation(
                    status.isAnimating
                        ? .easeInOut(duration: 0.9).repeatForever(autoreverses: true)
                        : .default,
                    value: pulsing
                )
                .onAppear { if status.isAnimating { pulsing = true } }

            if showLabel {
                Text(status.label)
                    .font(Typo.meta)
                    .foregroundStyle(Tone.textMuted)
            }
        }
        // 颜色从不是唯一信号：文字标签始终同行
        .accessibilityElement(children: .combine)
        .accessibilityLabel("状态：\(status.label)")
    }
}

#Preview("各状态") {
    VStack(alignment: .leading, spacing: 12) {
        StatusDot(status: .known(.done))
        StatusDot(status: .known(.processing))
        StatusDot(status: .known(.partial))
        StatusDot(status: .known(.failed))
        StatusDot(status: .known(.pending))
        StatusDot(status: .unknown("transcoding"))   // 后端将来新增的取值
    }
    .padding(24)
}
