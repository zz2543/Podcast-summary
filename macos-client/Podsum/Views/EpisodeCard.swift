import SwiftUI

struct EpisodeCard: View {
    let episode: EpisodeSummary
    @State private var hovering = false
    @Environment(\.textScale) private var scale

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                Image(systemName: "waveform")
                    .font(.system(size: 15 * scale, weight: .medium))
                    .foregroundStyle(Tone.textMuted)
                    .frame(width: 34 * scale, height: 34 * scale)
                    .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: 10))

                Spacer(minLength: 8)

                // "未评分"只对有摘要的剧集有意义；失败或还在跑的，谈不上评没评分
                if episode.usefulness != nil || [.done, .partial].contains(episode.status.value) {
                    ScoreBadge(usefulness: episode.usefulness)
                }
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(episode.displayTitle)
                    .podsumFont(.cardTitle)
                    .foregroundStyle(Tone.text)
                    .lineLimit(2, reservesSpace: true)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                if let name = episode.podcastName, !name.isEmpty {
                    Text(name)
                        .podsumFont(.meta)
                        .foregroundStyle(Tone.textSubtle)
                        .lineLimit(1)
                }
            }

            Spacer(minLength: 0)

            HStack(spacing: 6) {
                Text(Fmt.duration(episode.durationSeconds))
                    .monospacedDigit()
                Text("·").foregroundStyle(Tone.border)
                // language 已知不可靠（见 api-shapes.md 第 6 条），仅作展示
                Text(episode.language?.rawValue.uppercased() ?? "—")
                Text("·").foregroundStyle(Tone.border)
                Text(Fmt.relative(episode.updatedAt))
                    .lineLimit(1)
            }
            .podsumFont(.meta)
            .foregroundStyle(Tone.textMuted)
            .lineLimit(1)

            HStack(spacing: 6) {
                StatusDot(status: episode.status)
                // 失败时说清卡在哪一步，免得每个红点都得点进去看
                if episode.status.value == .failed, let failure = episode.lastFailure {
                    Text("· 卡在\(FailureCopy.stage(failure.stage))")
                        .podsumFont(.meta)
                        .foregroundStyle(Tone.textSubtle)
                        .lineLimit(1)
                }
            }
        }
        .padding(18)
        // minHeight 只是栅格等高的下限，不随字号放大——
        // 放大后内容本就超过它，再乘 scale 只会在卡片里留出大片空白。
        .frame(maxWidth: .infinity, minHeight: 194, alignment: .topLeading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(hovering ? Tone.info.opacity(0.45) : Tone.border.opacity(0.55))
        )
        .shadow(
            color: .black.opacity(hovering ? 0.10 : 0.05),
            radius: hovering ? 12 : 5, y: hovering ? 5 : 2
        )
        .scaleEffect(hovering ? 1.012 : 1)
        .animation(.easeOut(duration: 0.16), value: hovering)
        .onHover { hovering = $0 }
        .contentShape(RoundedRectangle(cornerRadius: 16))
    }
}

#Preview("卡片：真实数据的几种形态") {
    ScrollView {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 16)], spacing: 16) {
            ForEach(PreviewFixtures.episodes) { EpisodeCard(episode: $0) }
        }
        .padding(20)
    }
    .background(Tone.bg)
    .frame(width: 900, height: 560)
}
