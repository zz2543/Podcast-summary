import SwiftUI

struct EpisodeCard: View {
    let episode: EpisodeSummary
    @State private var hovering = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                Image(systemName: "waveform")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Tone.textMuted)
                    .frame(width: 34, height: 34)
                    .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: 10))

                Spacer(minLength: 8)

                ScoreBadge(usefulness: episode.usefulness)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(episode.displayTitle)
                    .font(.system(.body, weight: .semibold))
                    .foregroundStyle(Tone.text)
                    .lineLimit(2, reservesSpace: true)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                if let name = episode.podcastName, !name.isEmpty {
                    Text(name)
                        .font(.caption)
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
            .font(.caption)
            .foregroundStyle(Tone.textMuted)

            StatusDot(status: episode.status)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 176, alignment: .topLeading)
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
