import SwiftUI

struct EpisodeDetailView: View {
    let episodeID: String
    /// 删除成功后让列表页重新拉一次
    var onDeleted: (() async -> Void)?

    @Environment(\.episodeRepository) private var repository
    @Environment(\.dismiss) private var dismiss

    @State private var episode: EpisodeDetail?
    @State private var failure: String?
    @State private var player = AudioPlayerModel()
    @State private var showChat = false
    @State private var pendingDelete = false
    @State private var actionNote: String?
    @State private var actionError: String?
    @State private var working = false

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
        .onDisappear { player.pause() }
        .inspector(isPresented: $showChat) {
            if let e = episode {
                ChatPanel(episodeID: e.id, episodeTitle: e.title ?? "未命名剧集")
                    .inspectorColumnWidth(min: 300, ideal: 380, max: 520)
            }
        }
        .toolbar { toolbarContent }
        .alert("删除这一集？", isPresented: $pendingDelete) {
            Button("删除", role: .destructive) { Task { await deleteEpisode() } }
            Button("取消", role: .cancel) { }
        } message: {
            Text("音频、文稿与摘要都会从磁盘上一并删掉，且无法撤销。")
        }
        .alert("操作失败", isPresented: Binding(
            get: { actionError != nil }, set: { if !$0 { actionError = nil } }
        )) {
            Button("好") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
    }

    // MARK: 工具栏

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Button { showChat.toggle() } label: {
                Label("对话", systemImage: "bubble.left.and.bubble.right")
            }
            .help("基于本集文稿提问")
            .disabled(episode == nil)
        }
        ToolbarItem(placement: .primaryAction) {
            Menu {
                Button("生成音频摘要") { Task { await requestDigest() } }
                    .disabled(episode?.stageStatus.tts.value == .present)
                Button("重新处理") { Task { await retry() } }
                if let ref = episode?.sourceRef, let url = URL(string: ref) {
                    Divider()
                    Button("打开来源链接") { NSWorkspace.shared.open(url) }
                }
                Divider()
                Button("删除…", role: .destructive) { pendingDelete = true }
            } label: {
                Label("更多", systemImage: "ellipsis.circle")
            }
            .disabled(episode == nil || working)
        }
    }

    @ViewBuilder
    private func loaded(_ e: EpisodeDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.section) {
                hero(e)
                playback(e)
                if let note = actionNote {
                    Label(note, systemImage: "info.circle")
                        .podsumFont(.meta)
                        .foregroundStyle(Tone.info)
                }
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

    // MARK: 播放

    @ViewBuilder
    private func playback(_ e: EpisodeDetail) -> some View {
        if player.hasAudio {
            AudioPlayerBar(player: player, chapters: e.chapters)
        } else {
            AudioUnavailableNote(reason: playbackUnavailableReason(e))
        }
    }

    private func playbackUnavailableReason(_ e: EpisodeDetail) -> String {
        switch e.status.value {
        case .pending, .processing: return "音频还在抓取或转写中，处理完就能播。"
        case .failed:               return "这一集处理失败了，磁盘上没有可播的音频。"
        default:                    return "找不到这一集的音频文件。"
        }
    }

    /// 有音频才把时间戳变成可点的按钮
    private var seekAction: ((Int) -> Void)? {
        player.hasAudio ? { player.seek(toMs: $0) } : nil
    }

    // MARK: 头部

    @ViewBuilder
    private func hero(_ e: EpisodeDetail) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            HStack(spacing: Space.s) {
                if let name = e.podcastName, !name.isEmpty {
                    Text(name).podsumFont(.secondary, weight: .semibold).foregroundStyle(Tone.text)
                    Text("·").foregroundStyle(Tone.border)
                }
                Text(Fmt.duration(e.durationSeconds)).monospacedDigit()
                Text("·").foregroundStyle(Tone.border)
                Text(e.language?.rawValue.uppercased() ?? "—")
                Text("·").foregroundStyle(Tone.border)
                StatusDot(status: e.status)
            }
            .podsumFont(.secondary)
            .foregroundStyle(Tone.textMuted)

            Text(e.title ?? "未命名剧集")
                .podsumFont(.pageTitle)
                .foregroundStyle(Tone.text)
                .fixedSize(horizontal: false, vertical: true)

            if let hook = e.hook, !hook.isEmpty {
                Text("“\(hook)”")
                    .podsumFont(.hook)
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
                .podsumFont(.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)
            Text(body)
                .podsumFont(.body)
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
                    ForEach(e.chapters) { chapter in
                        ChapterRow(
                            chapter: chapter,
                            onSeek: seekAction,
                            isCurrent: isCurrent(chapter, in: e)
                        )
                    }
                }
            }
        }
    }

    /// 播放头落在本章内。只有在播原声时才有意义——
    /// 摘要音频是另一条时间轴，和章节时间戳对不上。
    private func isCurrent(_ chapter: Chapter, in e: EpisodeDetail) -> Bool {
        guard player.hasAudio, player.isPlaying, player.track == .original else { return false }
        return chapter.startMs <= player.currentMs && player.currentMs < chapter.endMs
    }

    // MARK: 实体

    @ViewBuilder
    private func entities(_ e: EpisodeDetail) -> some View {
        if e.entities.isEmpty {
            section("提及") {
                Text("这一集没有抽取到人物、书籍或产品。")
                    .podsumFont(.body).foregroundStyle(Tone.textSubtle)
            }
        } else {
            section("提及 · \(e.entities.count)") {
                FlowRow(spacing: Space.s) {
                    ForEach(e.entities) { entity in
                        entityChip(entity)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func entityChip(_ entity: Entity) -> some View {
        let chip = HStack(spacing: 5) {
            Image(systemName: icon(entity.kind))
                .font(.system(size: 11))
                .foregroundStyle(Tone.textSubtle)
            Text(entity.name).podsumFont(.secondary)
            Text("\(entity.count)")
                .podsumFont(.meta).monospacedDigit()
                .foregroundStyle(Tone.textSubtle)
        }
        .padding(.horizontal, 11).padding(.vertical, 6)
        .background(Tone.surface, in: Capsule())
        .overlay(Capsule().strokeBorder(Tone.border.opacity(0.6)))

        // sample_timestamps_ms 最多 5 个，有音频时做成"跳到它被提到的地方"
        if let stamps = entity.sampleTimestampsMs, !stamps.isEmpty, let seek = seekAction {
            Menu {
                ForEach(stamps, id: \.self) { ms in
                    Button(Fmt.timestamp(ms)) { seek(ms) }
                }
            } label: {
                chip
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()
        } else {
            chip
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
                .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
                .frame(width: 82, alignment: .leading)
            Text(value)
                .podsumFont(.micro).foregroundStyle(Tone.textMuted)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: 脚手架

    private func section<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Text(title)
                .podsumFont(.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)
                .tracking(0.8)
            content()
        }
    }

    // MARK: 动作

    private func load() async {
        episode = nil
        failure = nil
        do {
            let detail = try await repository.detail(id: episodeID)
            episode = detail
            player.configure(
                original: repository.audioURL(for: detail),
                digest: repository.digestURL(for: detail),
                fallbackDurationSeconds: detail.durationSeconds
            )
        } catch {
            failure = error.localizedDescription
        }
    }

    private func retry() async {
        working = true
        defer { working = false }
        do {
            _ = try await repository.retry(id: episodeID)
            actionNote = "已排队重新处理，进度在列表页顶部。"
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func requestDigest() async {
        working = true
        defer { working = false }
        do {
            switch try await repository.requestDigest(id: episodeID) {
            case .alreadyPresent:
                actionNote = "音频摘要已经有了。"
                await load()
            case .queued:
                actionNote = "已排队合成音频摘要，完成后会出现在播放器的「音频摘要」里。"
            }
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func deleteEpisode() async {
        working = true
        defer { working = false }
        do {
            try await repository.delete(id: episodeID)
            await onDeleted?()
            dismiss()
        } catch {
            actionError = error.localizedDescription
        }
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
