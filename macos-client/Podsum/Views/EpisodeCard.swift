import SwiftUI

/// 剧集卡片：封面铺满整张卡，文字放在压在封面上的玻璃里。
///
/// 相比纯文字卡片，这里刻意少放了几样：
/// - 语言：本就不可靠（见 api-shapes.md 第 6 条）
/// - 相对时间：列表已按时间排序，位置本身就说明了新旧
/// - 「已完成」：绝大多数剧集的常态，只在不是完成时才出状态标记
/// - 「未评分」：同理是常态，封面上不再占一块
struct EpisodeCard: View {
    let episode: EpisodeSummary
    /// 在某个分类里浏览时，每张卡都写同一个分类名是噪音
    var showsCategory = true
    @State private var hovering = false
    @Environment(\.textScale) private var scale
    @Environment(\.episodeRepository) private var repository

    private let shape = RoundedRectangle(cornerRadius: 16, style: .continuous)

    var body: some View {
        // 4:3 比 16:9 高一些：底部玻璃占掉一截后，封面主体仍露得出来
        Color.clear
            .aspectRatio(4 / 3, contentMode: .fit)
            .overlay {
                CoverArt(url: repository.coverURL(for: episode), seed: episode.id)
                    .scaleEffect(hovering ? 1.04 : 1)
            }
            .overlay {
                // 底部压暗，玻璃边缘外的封面也不会和文字抢
                LinearGradient(
                    stops: [.init(color: .clear, location: 0.45), .init(color: .black.opacity(0.35), location: 1)],
                    startPoint: .top, endPoint: .bottom
                )
            }
            .overlay { content }
            .clipShape(shape)
            .overlay(
                shape.strokeBorder(hovering ? Tone.info.opacity(0.6) : Color.black.opacity(0.08))
            )
            .shadow(
                color: .black.opacity(hovering ? 0.18 : 0.08),
                radius: hovering ? 14 : 6, y: hovering ? 6 : 2
            )
            .scaleEffect(hovering ? 1.012 : 1)
            .animation(.easeOut(duration: 0.18), value: hovering)
            .onHover { hovering = $0 }
            .contentShape(shape)
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 8) {
                if showsStatus { statusChip }
                Spacer(minLength: 0)
                if let usefulness = episode.usefulness { scoreChip(usefulness) }
            }
            Spacer(minLength: 8)
            infoPanel
        }
        .padding(10)
        .environment(\.colorScheme, .dark)
    }

    private var infoPanel: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(episode.displayTitle)
                .podsumFont(.secondary, weight: .semibold)
                .foregroundStyle(.white)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 6) {
                if showsCategory, let category = episode.category {
                    categoryTag(category)
                    Text("·")
                }
                if let name = episode.podcastName, !name.isEmpty {
                    Text(name)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    Text("·")
                }
                Text(Fmt.duration(episode.durationSeconds))
                    .monospacedDigit()
                    .layoutPriority(1)
            }
            .podsumFont(.micro)
            .foregroundStyle(.white.opacity(0.78))
            .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .coverGlass(in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .shadow(color: .black.opacity(0.18), radius: 8, y: 2)
    }

    /// AI 管理的用 sparkles，手动放的用文件夹（FR-012）
    private func categoryTag(_ category: CategoryRef) -> some View {
        let byAI = episode.categoryOrigin?.value == .auto
        return Label(category.name, systemImage: byAI ? "sparkles" : "folder")
            .labelStyle(.titleAndIcon)
            .lineLimit(1)
            .layoutPriority(2)
            .help(byAI ? tr("AI 分到「\(category.name)」", "Filed in “\(category.name)” by AI")
                       : tr("你放在「\(category.name)」", "You filed this in “\(category.name)”"))
    }

    private var showsStatus: Bool {
        episode.status.value != .done
    }

    private var statusChip: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(episode.status.tint)
                .frame(width: 7, height: 7)
            Text(statusText)
                .lineLimit(1)
        }
        .podsumFont(.micro, weight: .medium)
        .foregroundStyle(.white)
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .coverGlass(in: Capsule())
        .accessibilityElement(children: .combine)
        .accessibilityLabel(tr("状态：\(statusText)", "Status: \(statusText)"))
    }

    /// 失败时说清卡在哪一步，免得每张失败的卡都得点进去看
    private var statusText: String {
        if episode.status.value == .failed, let failure = episode.lastFailure {
            return tr("\(episode.status.label) · 卡在\(FailureCopy.stage(failure.stage))",
                      "\(episode.status.label) · stuck at \(FailureCopy.stage(failure.stage))")
        }
        return episode.status.label
    }

    private func scoreChip(_ u: Usefulness) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text("\(u.score)")
                .podsumFont(.scoreSmall)
                .monospacedDigit()
                .foregroundStyle(u.band.tint)
            Text(u.band.label)
                .podsumFont(.bandSmall)
                .foregroundStyle(.white.opacity(0.9))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .coverGlass(in: Capsule())
        .help(u.rationale)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(tr("有用性 \(u.score) 分，\(u.band.label)", "Usefulness \(u.score), \(u.band.label)"))
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
