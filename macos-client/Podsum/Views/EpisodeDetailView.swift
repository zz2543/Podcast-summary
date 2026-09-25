import SwiftUI

struct EpisodeDetailView: View {
    let episodeID: String
    /// 删除成功后让列表页重新拉一次
    var onDeleted: (() async -> Void)?
    /// 在这里改了分类，列表页那张卡跟着改（004）
    var onCategoryChanged: ((CategoryAssignment) -> Void)?

    @Environment(\.episodeRepository) private var repository
    /// 列表页注入；预览等场合没有时，分类那一行不显示
    @Environment(CategoryStore.self) private var categoryStore: CategoryStore?
    @Environment(\.dismiss) private var dismiss

    @State private var showChat = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @State private var episode: EpisodeDetail?
    @State private var failure: String?
    @State private var player = AudioPlayerModel()
    @State private var pendingDelete = false
    @State private var actionNote: String?
    @State private var actionError: String?
    @State private var working = false

    var body: some View {
        GeometryReader { geometry in
            let panelWidth = min(320.0, geometry.size.width * 0.42)
            let revealedWidth = showChat ? panelWidth : 0
            HStack(spacing: 0) {
                detailContent
                    .frame(width: max(0, geometry.size.width - revealedWidth))
                    .clipped()
                if let episode {
                    ChatPanel(episodeID: episodeID, episodeTitle: episode.title ?? tr("未命名剧集", "Untitled Episode"))
                        .id(episodeID)
                        .frame(width: panelWidth)
                        .overlay(alignment: .leading) { Divider() }
                        .frame(width: revealedWidth, alignment: .leading)
                        .clipped()
                        .allowsHitTesting(showChat)
                        .disabled(!showChat)
                        .accessibilityHidden(!showChat)
                }
            }
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.24), value: showChat)
        }
        .background(Tone.bg)
        .task(id: episodeID) { await load() }
        .onDisappear {
            player.pause()
            showChat = false
        }
        .toolbar { toolbarContent }
        .alert(tr("删除这一集？", "Delete This Episode?"), isPresented: $pendingDelete) {
            Button(tr("删除", "Delete"), role: .destructive) { Task { await deleteEpisode() } }
            Button(tr("取消", "Cancel"), role: .cancel) { }
        } message: {
            Text(tr("音频、文稿与摘要都会从磁盘上一并删掉，且无法撤销。",
                    "The audio, transcript, and summary will all be deleted from disk. This can’t be undone."))
        }
        .alert(tr("操作失败", "Action Failed"), isPresented: Binding(
            get: { actionError != nil }, set: { if !$0 { actionError = nil } }
        )) {
            Button(tr("好", "OK")) { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
    }

    @ViewBuilder
    private var detailContent: some View {
        Group {
            if let e = episode {
                loaded(e)
            } else if let failure {
                ContentUnavailableView {
                    Label(tr("打不开这一集", "Couldn’t Open This Episode"), systemImage: "exclamationmark.triangle")
                } description: {
                    Text(failure)
                } actions: {
                    Button(tr("重试", "Retry")) { Task { await load() } }
                }
            } else {
                ProgressView(tr("读取详情…", "Loading details…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }

    // MARK: 工具栏

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Button { showChat.toggle() } label: {
                Label(tr("对话", "Chat"), systemImage: "bubble.left.and.bubble.right")
            }
            .keyboardShortcut("i", modifiers: [.command, .option])
            .help(tr("基于本集文稿提问（⌥⌘I）", "Ask about this episode’s transcript (⌥⌘I)"))
            .disabled(episode == nil)
        }
        ToolbarItem(placement: .primaryAction) {
            Menu {
                Button(tr("生成音频摘要", "Generate Audio Summary")) { Task { await requestDigest() } }
                    .disabled(episode?.stageStatus.tts.value == .present)
                Button(tr("重新处理", "Reprocess")) { Task { await retry() } }
                if let ref = episode?.sourceRef, let url = URL(string: ref) {
                    Divider()
                    Button(tr("打开来源链接", "Open Source Link")) { NSWorkspace.shared.open(url) }
                }
                Divider()
                Button(tr("删除…", "Delete…"), role: .destructive) { pendingDelete = true }
            } label: {
                Label(tr("更多", "More"), systemImage: "ellipsis.circle")
            }
            .disabled(episode == nil || working)
        }
    }

    @ViewBuilder
    private func loaded(_ e: EpisodeDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.section) {
                hero(e)
                if let failure = e.lastFailure, e.status.value != .processing {
                    FailureNotice(failure: failure, hasSummary: hasSummary(e), working: working) {
                        Task { await retry() }
                    }
                }
                playback(e)
                if let note = actionNote {
                    Label(note, systemImage: "info.circle")
                        .podsumFont(.meta)
                        .foregroundStyle(Tone.info)
                }
                // 没有摘要时，"未评分""没有抽取到提及"这类卡片只会误导——
                // 它们说的是"这一项是空的"，而实情是"根本还没走到这一步"。
                if hasSummary(e) {
                    UsefulnessCard(usefulness: e.usefulness,
                                   stage: e.stageStatus.usefulness,
                                   promptVersion: e.promptVersions.usefulnessScore)
                    threeAct(e)
                    chapters(e)
                    entities(e)
                } else if e.status.value == .processing || e.status.value == .pending {
                    Label(tr("摘要还在生成，进度见列表页顶部。", "The summary is still being generated — progress is shown at the top of the list."), systemImage: "hourglass")
                        .podsumFont(.secondary)
                        .foregroundStyle(Tone.textMuted)
                }
                provenance(e)
            }
            .padding(Space.xxl)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .navigationTitle(e.title ?? tr("未命名剧集", "Untitled Episode"))
    }

    /// 一句话、三幕、章节，有任何一样就算有东西可读
    private func hasSummary(_ e: EpisodeDetail) -> Bool {
        e.hook?.isEmpty == false || e.threeAct != nil || !e.chapters.isEmpty
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
        case .pending, .processing: return tr("音频还在抓取或转写中，处理完就能播。", "The audio is still being fetched or transcribed. It’ll be playable once processing finishes.")
        case .failed:               return tr("这一集处理失败了，磁盘上没有可播的音频。", "Processing failed for this episode; there’s no playable audio on disk.")
        default:                    return tr("找不到这一集的音频文件。", "Can’t find this episode’s audio file.")
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

            Text(e.title ?? tr("未命名剧集", "Untitled Episode"))
                .podsumFont(.pageTitle)
                .foregroundStyle(Tone.text)
                .fixedSize(horizontal: false, vertical: true)

            if let categoryStore { categoryRow(e, categoryStore) }

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

    // MARK: 分类（004）

    /// 当前分类 + 来源。在这里改就是手动归类（FR-004 / FR-012）。
    private func categoryRow(_ e: EpisodeDetail, _ store: CategoryStore) -> some View {
        HStack(spacing: Space.s) {
            Menu {
                Button {
                    Task { await setCategory(nil, store) }
                } label: {
                    if e.category == nil { Label(tr("未分类", "Uncategorized"), systemImage: "checkmark") }
                    else { Text(tr("未分类", "Uncategorized")) }
                }
                if !store.items.isEmpty { Divider() }
                ForEach(store.items) { category in
                    Button {
                        Task { await setCategory(category.id, store) }
                    } label: {
                        if e.category?.id == category.id { Label(category.name, systemImage: "checkmark") }
                        else { Text(category.name) }
                    }
                }
            } label: {
                Label(e.category?.name ?? tr("未分类", "Uncategorized"),
                      systemImage: e.category == nil ? "tray" : "folder")
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
            .disabled(working)

            switch (e.categoryOrigin?.value, e.category == nil) {
            case (.manual, false):
                Text(tr("你放的", "Filed by you")).foregroundStyle(Tone.textSubtle)
            case (.manual, true):
                // Taken out by hand: AI skips it until it is handed back.
                Text(tr("你移出的 · AI 不会再分它", "Taken out by you · AI won’t file it"))
                    .foregroundStyle(Tone.textSubtle)
                Button(tr("交给 AI 分类", "Let AI Categorize")) { Task { await releaseCategory() } }
                    .buttonStyle(.link)
                    .help(tr("交还后，下次 AI 分类会处理它", "The next AI categorization will file it"))
            case (.auto, _):
                Label(tr("AI 放的", "Filed by AI"), systemImage: "sparkles")
                    .foregroundStyle(Tone.textSubtle)
            default:
                EmptyView()
            }
        }
        .podsumFont(.meta)
        .foregroundStyle(Tone.textMuted)
    }

    private func setCategory(_ categoryID: String?, _ store: CategoryStore) async {
        do {
            let assignment = try await store.assign(episodeID, to: categoryID, repository)
            applyCategory(assignment)
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func releaseCategory() async {
        do {
            let assignment = try await repository.releaseCategory(episodeID: episodeID)
            applyCategory(assignment)
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func applyCategory(_ assignment: CategoryAssignment) {
        episode?.category = assignment.category
        episode?.categoryOrigin = assignment.categoryOrigin
        onCategoryChanged?(assignment)
    }

    // MARK: 三幕

    @ViewBuilder
    private func threeAct(_ e: EpisodeDetail) -> some View {
        if let ta = e.threeAct {
            section(tr("三幕摘要", "Three-Act Summary")) {
                HStack(alignment: .top, spacing: Space.m) {
                    ActCard(label: tr("背景", "Background"), text: ta.background)
                    ActCard(label: tr("核心论点", "Core Argument"), text: ta.coreArgument)
                    ActCard(label: tr("结论", "Conclusion"), text: ta.conclusion)
                }
                // 换集时收起，不把上一集的展开状态带过来
                .id(e.id)
            }
        }
    }

    // MARK: 章节

    @ViewBuilder
    private func chapters(_ e: EpisodeDetail) -> some View {
        if !e.chapters.isEmpty {
            section(tr("章节 · \(e.chapters.count)", "Chapters · \(e.chapters.count)")) {
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
            section(tr("提及", "Mentions")) {
                Text(tr("这一集没有抽取到人物、书籍或产品。", "No people, books, or products were found in this episode."))
                    .podsumFont(.body).foregroundStyle(Tone.textSubtle)
            }
        } else {
            section(tr("提及 · \(e.entities.count)", "Mentions · \(e.entities.count)")) {
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
        section(tr("溯源", "Provenance")) {
            VStack(alignment: .leading, spacing: Space.s) {
                row(tr("来源", "Source"), e.sourceRef)
                row(tr("提示词版本", "Prompts"), "one_liner \(e.promptVersions.oneLiner) · three_act \(e.promptVersions.threeAct) · chapters \(e.promptVersions.chapterOutline) · entities \(e.promptVersions.entityExtraction)")
                if let s = e.summaryStyle {
                    row(tr("摘要风格", "Style"), "\(s.preset.rawValue)\(s.detail.map { " · \($0.rawValue)" } ?? "")")
                }
                row(tr("更新于", "Updated"), e.updatedAt.formatted(
                    Date.FormatStyle(date: .abbreviated, time: .shortened).locale(Localizer.shared.locale)))
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
            actionNote = tr("已排队重新处理，进度在列表页顶部。", "Queued for reprocessing — progress is at the top of the list.")
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
                actionNote = tr("音频摘要已经有了。", "The audio summary already exists.")
                await load()
            case .queued:
                actionNote = tr("已排队合成音频摘要，完成后会出现在播放器的「音频摘要」里。",
                               "Audio summary queued. When it’s done, it’ll appear under “Audio Summary” in the player.")
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

/// 三幕里的一幕。长文默认只露出前几行，超出时给一个展开按钮。
/// 是否超出靠量出来：背景里放两份隐藏的同款文字，一份截断、一份完整，
/// 高度不同才说明真被截了——按字数估会被栏宽和字号调节骗到。
private struct ActCard: View {
    let label: String
    let text: String

    static let collapsedLines = 8

    @State private var expanded = false
    @State private var clippedHeight: CGFloat = 0
    @State private var fullHeight: CGFloat = 0

    private var isTruncated: Bool { fullHeight > clippedHeight + 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            Text(label)
                .podsumFont(.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)
            bodyText(lines: expanded ? nil : Self.collapsedLines)
                .background(alignment: .topLeading) {
                    ZStack(alignment: .topLeading) {
                        bodyText(lines: Self.collapsedLines).measure { clippedHeight = $0 }
                        bodyText(lines: nil).measure { fullHeight = $0 }
                    }
                    .hidden()
                }
            if isTruncated {
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
                } label: {
                    Label(expanded ? tr("收起", "Show Less") : tr("展开全部", "Show All"),
                          systemImage: expanded ? "chevron.up" : "chevron.down")
                }
                .buttonStyle(.link)
                .controlSize(.small)
            }
        }
        .padding(Space.l)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(RoundedRectangle(cornerRadius: Radius.medium).strokeBorder(Tone.border.opacity(0.5)))
    }

    private func bodyText(lines: Int?) -> some View {
        Text(text)
            .podsumFont(.body)
            .foregroundStyle(Tone.text)
            .readable()
            .lineLimit(lines)
            .fixedSize(horizontal: false, vertical: true)
    }
}

private extension View {
    /// 把自身高度报出来（首次出现和之后每次变化）
    func measure(_ report: @escaping (CGFloat) -> Void) -> some View {
        background(GeometryReader { geo in
            Color.clear
                .onAppear { report(geo.size.height) }
                .onChange(of: geo.size.height) { _, h in report(h) }
        })
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
