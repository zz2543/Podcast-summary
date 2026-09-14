import SwiftUI

struct EpisodeDetailView: View {
    let episodeID: String
    @Environment(\.episodeRepository) private var repository

    @State private var episode: EpisodeDetail?
    @State private var failure: String?

    var body: some View {
        Group {
            if let e = episode {
                loaded(e)
            } else if let failure {
                ContentUnavailableView {
                    Label("打不开这一集", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(failure)
                } actions: {
                    Button("重试") { Task { await load() } }
                }
            } else {
                ProgressView("读取详情…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Tone.bg)
        .task(id: episodeID) { await load() }
    }

    @ViewBuilder
    private func loaded(_ e: EpisodeDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.section) {
                hero(e)
                UsefulnessCard(usefulness: e.usefulness,
                               stage: e.stageStatus.usefulness,
                               promptVersion: e.promptVersions.usefulnessScore)
                threeAct(e)
                chapters(e)
                entities(e)
                provenance(e)
            }
            .padding(Space.xxl)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .navigationTitle(e.title ?? "未命名剧集")
    }

    // MARK: 头部

    @ViewBuilder
    private func hero(_ e: EpisodeDetail) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            HStack(spacing: Space.s) {
                if let name = e.podcastName, !name.isEmpty {
                    Text(name).font(Typo.secondary.weight(.semibold)).foregroundStyle(Tone.text)
                    Text("·").foregroundStyle(Tone.border)
                }
                Text(Fmt.duration(e.durationSeconds)).monospacedDigit()
                Text("·").foregroundStyle(Tone.border)
                Text(e.language?.rawValue.uppercased() ?? "—")
                Text("·").foregroundStyle(Tone.border)
                StatusDot(status: e.status)
            }
            .font(Typo.secondary)
            .foregroundStyle(Tone.textMuted)

            Text(e.title ?? "未命名剧集")
                .font(Typo.pageTitle)
                .foregroundStyle(Tone.text)
                .fixedSize(horizontal: false, vertical: true)

            if let hook = e.hook, !hook.isEmpty {
                Text("“\(hook)”")
                    .font(Typo.hook)
                    .foregroundStyle(Tone.text)
                    .readable()
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(Space.xl)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: Radius.large))
            }
        }
    }

    // MARK: 三幕

    @ViewBuilder
    private func threeAct(_ e: EpisodeDetail) -> some View {
        if let ta = e.threeAct {
            section("三幕摘要") {
                HStack(alignment: .top, spacing: Space.m) {
                    actCard("背景", ta.background)
                    actCard("核心论点", ta.coreArgument)
                    actCard("结论", ta.conclusion)
                }
            }
        }
    }

    private func actCard(_ label: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: Space.s) {
            Text(label)
                .font(Typo.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)
            Text(body)
                .font(Typo.body)
                .foregroundStyle(Tone.text)
                .readable()
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Space.l)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(RoundedRectangle(cornerRadius: Radius.medium).strokeBorder(Tone.border.opacity(0.5)))
    }

    // MARK: 章节

    @ViewBuilder
    private func chapters(_ e: EpisodeDetail) -> some View {
        if !e.chapters.isEmpty {
            section("章节 · \(e.chapters.count)") {
                VStack(spacing: Space.m) {
                    ForEach(e.chapters) { ChapterRow(chapter: $0) }
                }
            }
        }
    }

    // MARK: 实体

    @ViewBuilder
    private func entities(_ e: EpisodeDetail) -> some View {
        if e.entities.isEmpty {
            section("提及") {
                Text("这一集没有抽取到人物、书籍或产品。")
                    .font(Typo.body).foregroundStyle(Tone.textSubtle)
            }
        } else {
            section("提及 · \(e.entities.count)") {
                FlowRow(spacing: Space.s) {
                    ForEach(e.entities) { entity in
                        HStack(spacing: 5) {
                            Image(systemName: icon(entity.kind))
                                .font(.system(size: 11))
                                .foregroundStyle(Tone.textSubtle)
                            Text(entity.name).font(Typo.secondary)
                            Text("\(entity.count)")
                                .font(Typo.meta).monospacedDigit()
                                .foregroundStyle(Tone.textSubtle)
                        }
                        .padding(.horizontal, 11).padding(.vertical, 6)
                        .background(Tone.surface, in: Capsule())
                        .overlay(Capsule().strokeBorder(Tone.border.opacity(0.6)))
                    }
                }
            }
        }
    }

    private func icon(_ kind: Fallback<EntityKind>) -> String {
        switch kind.value {
        case .person:  return "person"
        case .book:    return "book"
        case .product: return "shippingbox"
        case nil:      return "tag"
        }
    }

    // MARK: 溯源

    @ViewBuilder
    private func provenance(_ e: EpisodeDetail) -> some View {
        section("溯源") {
            VStack(alignment: .leading, spacing: Space.s) {
                row("来源", e.sourceRef)
                row("提示词版本", "one_liner \(e.promptVersions.oneLiner) · three_act \(e.promptVersions.threeAct) · chapters \(e.promptVersions.chapterOutline) · entities \(e.promptVersions.entityExtraction)")
                if let s = e.summaryStyle {
                    row("摘要风格", "\(s.preset.rawValue)\(s.detail.map { " · \($0.rawValue)" } ?? "")")
                }
                row("更新于", e.updatedAt.formatted(date: .abbreviated, time: .shortened))
            }
        }
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(label)
                .font(Typo.micro).foregroundStyle(Tone.textSubtle)
                .frame(width: 82, alignment: .leading)
            Text(value)
                .font(Typo.micro).foregroundStyle(Tone.textMuted)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: 脚手架

    private func section<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Text(title)
                .font(Typo.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)
                .tracking(0.8)
            content()
        }
    }

    private func load() async {
        episode = nil
        failure = nil
        do { episode = try await repository.detail(id: episodeID) }
        catch { failure = error.localizedDescription }
    }
}

/// 会换行的横向排布，用于实体标签
struct FlowRow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x + size.width > maxWidth, x > 0 {
                x = 0; y += rowHeight + spacing; rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX, x > bounds.minX {
                x = bounds.minX; y += rowHeight + spacing; rowHeight = 0
            }
            s.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

#Preview("详情页") {
    NavigationStack {
        EpisodeDetailView(episodeID: "01M2FKVC8GT40083QZHH6VRSMW")
    }
    .frame(width: 940, height: 800)
}
