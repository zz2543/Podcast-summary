import SwiftUI

struct EpisodeListView: View {
    /// 离线模式的横幅。接了后端就不显示。
    var offlineNotice = false

    @Environment(\.episodeRepository) private var repository
    @Environment(\.textScale) private var scale
    @Environment(UIState.self) private var ui
    @Environment(JobsModel.self) private var jobs
    @Environment(QuickAddCenter.self) private var quickAdd
    @Environment(\.openSettings) private var openSettings

    /// 详情页的导航栈。快捷提交的通知点进来时直接推一集进去。
    @State private var path: [String] = []

    @State private var episodes: [EpisodeSummary] = []
    @State private var phase: Phase = .loading
    @State private var selection: SidebarSelection = .status(.all)
    @State private var categoryStore = CategoryStore()
    @State private var naming: CategoryNaming?
    @State private var pendingCategoryDelete: EpisodeCategory?
    @State private var dropTarget: SidebarSelection?
    @State private var showCategorize = false
    @State private var query = ""
    @State private var pendingDelete: EpisodeSummary?
    @State private var actionError: String?

    enum Phase: Equatable {
        case loading, loaded, failed(String)
    }

    enum Filter: String, CaseIterable, Identifiable {
        case all, done, running, scored
        var id: String { rawValue }

        var label: String {
            switch self {
            case .all:     return tr("全部", "All")
            case .done:    return tr("已完成", "Done")
            case .running: return tr("进行中", "In Progress")
            case .scored:  return tr("已评分", "Scored")
            }
        }

        var icon: String {
            switch self {
            case .all:     return "square.grid.2x2"
            case .done:    return "checkmark.circle"
            case .running: return "clock"
            case .scored:  return "star"
            }
        }

        func matches(_ e: EpisodeSummary) -> Bool {
            switch self {
            case .all:     return true
            case .done:    return e.status.value == .done
            case .running: return e.status.value == .processing || e.status.value == .pending
            case .scored:  return e.usefulness != nil
            }
        }
    }

    /// 侧边栏选中的是什么：状态筛选、某个分类，或「未分类」（004）
    enum SidebarSelection: Hashable {
        case status(Filter)
        case category(String)
        case uncategorized

        func matches(_ e: EpisodeSummary) -> Bool {
            switch self {
            case .status(let filter):  return filter.matches(e)
            case .category(let id):    return e.category?.id == id
            case .uncategorized:       return e.category == nil
            }
        }
    }

    private var visible: [EpisodeSummary] {
        episodes.filter { e in
            guard selection.matches(e) else { return false }
            guard !query.isEmpty else { return true }
            let hay = [e.title, e.podcastName].compactMap { $0 }.joined(separator: " ")
            return hay.localizedCaseInsensitiveContains(query)
        }
    }

    var body: some View {
        @Bindable var ui = ui

        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(min: 168, ideal: 200, max: 260)
        } detail: {
            NavigationStack(path: $path) {
                content
                    .navigationDestination(for: String.self) { id in
                        EpisodeDetailView(
                            episodeID: id,
                            onDeleted: { await load() },
                            onCategoryChanged: { assignment in applyLocally(id, assignment) }
                        )
                        // Set here, not on the NavigationStack: a pushed
                        // destination did not inherit it from there.
                        .environment(categoryStore)
                    }
            }
            .navigationTitle("Podsum")
            .navigationSubtitle(subtitle)
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { ui.showQuickAddLog.toggle() } label: {
                        Label(tr("快捷提交", "Quick Add"),
                              systemImage: quickAdd.pending.isEmpty ? "tray" : "tray.and.arrow.down.fill")
                    }
                    .help(tr("快捷键送来的链接", "Links sent with the hotkey"))
                    .popover(isPresented: $ui.showQuickAddLog, arrowEdge: .bottom) {
                        QuickAddLog { id in
                            ui.showQuickAddLog = false
                            path = [id]
                        }
                        .environment(quickAdd)
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { ui.showSubmit = true } label: {
                        Label(tr("添加剧集", "Add Episodes"), systemImage: "plus")
                    }
                    .help(tr("添加剧集（⌘N）", "Add Episodes (⌘N)"))
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await load() }
                    } label: {
                        Label(tr("刷新", "Refresh"), systemImage: "arrow.clockwise")
                    }
                    .disabled(phase == .loading)
                }
            }
            .searchable(text: $query, placement: .toolbar, prompt: tr("搜索标题或播客", "Search titles or podcasts"))
        }
        .task { await load() }
        .task(id: repositoryIdentity) { await categoryStore.refresh(repository) }
        .onChange(of: ui.showNewCategory) { _, show in
            guard show else { return }
            ui.showNewCategory = false
            naming = .create(assigning: nil)
        }
        .onChange(of: ui.showCategorize) { _, show in
            guard show else { return }
            ui.showCategorize = false
            showCategorize = true
        }
        .task { connectJobs() }
        .onChange(of: ui.refreshToken) { _, _ in Task { await load() } }
        .onChange(of: ui.pendingEpisodeID, initial: true) { _, id in
            guard let id else { return }
            path = [id]
            ui.pendingEpisodeID = nil
        }
        .sheet(isPresented: $ui.showSubmit) {
            SubmitSheet { created in
                // 新提交的剧集立刻插到前面，不必等下一次拉取——
                // 后端已经返回了完整的 EpisodeSummary。
                episodes.insert(contentsOf: created.map(\.episode), at: 0)
            }
            .environment(\.episodeRepository, repository)
            .environment(\.textScale, scale)
        }
        .alert(tr("删除这一集？", "Delete This Episode?"), isPresented: Binding(
            get: { pendingDelete != nil },
            set: { if !$0 { pendingDelete = nil } }
        ), presenting: pendingDelete) { episode in
            Button(tr("删除", "Delete"), role: .destructive) { Task { await delete(episode) } }
            Button(tr("取消", "Cancel"), role: .cancel) { pendingDelete = nil }
        } message: { episode in
            Text(tr("「\(episode.displayTitle)」的音频、文稿与摘要都会从磁盘上一并删掉，且无法撤销。",
                    "The audio, transcript, and summary of “\(episode.displayTitle)” will all be deleted from disk. This can’t be undone."))
        }
        .alert(tr("操作失败", "Action Failed"), isPresented: Binding(
            get: { actionError != nil },
            set: { if !$0 { actionError = nil } }
        )) {
            Button(tr("好", "OK")) { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
        .sheet(item: $naming) { naming in
            CategoryNameSheet(naming: naming, existing: categoryStore.items) { name in
                try await submitName(name, for: naming)
            }
        }
        .confirmationDialog(
            tr("删除分类？", "Delete Category?"),
            isPresented: Binding(get: { pendingCategoryDelete != nil },
                                 set: { if !$0 { pendingCategoryDelete = nil } }),
            presenting: pendingCategoryDelete
        ) { category in
            Button(tr("删除分类", "Delete Category"), role: .destructive) {
                Task { await deleteCategory(category) }
            }
            Button(tr("取消", "Cancel"), role: .cancel) { pendingCategoryDelete = nil }
        } message: { category in
            Text(category.episodeCount == 0
                 ? tr("「\(category.name)」里没有视频。", "“\(category.name)” has no videos in it.")
                 : tr("「\(category.name)」里的 \(category.episodeCount) 条视频会回到「未分类」，视频本身不会被删除。",
                      "The \(category.episodeCount) videos in “\(category.name)” go back to Uncategorized. The videos themselves aren’t deleted."))
        }
        .sheet(isPresented: $showCategorize) {
            CategorizeSheet(onApplied: { Task { await load() } })
                .environment(categoryStore)
                .environment(\.episodeRepository, repository)
        }
    }

    /// 仓库换了（后端起来了）就重新拉分类
    private var repositoryIdentity: String { String(describing: type(of: repository)) }

    private var subtitle: String {
        switch phase {
        case .loading:    return tr("载入中…", "Loading…")
        case .failed:     return tr("载入失败", "Failed to Load")
        case .loaded:
            let count = tr("\(visible.count) 集", visible.count == 1 ? "1 episode" : "\(visible.count) episodes")
            guard let scope = selectionName else { return count }
            return "\(scope) · \(count)"
        }
    }

    private var selectionName: String? {
        switch selection {
        case .status:               return nil
        case .category(let id):     return categoryStore.category(id: id)?.name
        case .uncategorized:        return tr("未分类", "Uncategorized")
        }
    }

    @ViewBuilder
    private var content: some View {
        switch phase {
        case .loading:
            ProgressView(tr("读取剧集…", "Loading episodes…"))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Tone.bg)

        case .failed(let message):
            ContentUnavailableView {
                Label(tr("载入失败", "Failed to Load"), systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button(tr("重试", "Retry")) { Task { await load() } }
            }
            .background(Tone.bg)

        case .loaded where visible.isEmpty:
            ContentUnavailableView {
                Label(query.isEmpty ? tr("没有符合条件的剧集", "No Matching Episodes") : tr("无搜索结果", "No Results"),
                      systemImage: "tray")
            } description: {
                Text(query.isEmpty ? tr("换一个筛选条件试试。", "Try a different filter.")
                                    : tr("「\(query)」没有匹配到任何剧集。", "No episodes match “\(query)”."))
            } actions: {
                if query.isEmpty { Button(tr("添加剧集", "Add Episodes")) { ui.showSubmit = true } }
            }
            .background(Tone.bg)

        case .loaded:
            ScrollView {
                VStack(spacing: Space.l) {
                    if offlineNotice { offlineBanner }
                    if !jobs.active.isEmpty {
                        ActiveJobsStrip(
                            jobs: jobs.active,
                            titles: Dictionary(episodes.map { ($0.id, $0.displayTitle) }, uniquingKeysWith: { a, _ in a }),
                            onSelect: { _ in }
                        )
                    }

                    LazyVGrid(
                        columns: [GridItem(.adaptive(minimum: 278 * scale), spacing: Space.l)],
                        spacing: 16
                    ) {
                        ForEach(visible) { episode in
                            NavigationLink(value: episode.id) {
                                EpisodeCard(episode: episode, showsCategory: !isCategoryScope)
                            }
                            .buttonStyle(.plain)
                            .draggable(EpisodeDrag.payload(episode.id)) {
                                Label(episode.displayTitle, systemImage: "film")
                                    .padding(8)
                                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
                            }
                            .contextMenu { menu(for: episode) }
                        }
                    }
                }
                .padding(20)
            }
            .background(Tone.bg)
        }
    }

    private var offlineBanner: some View {
        HStack(spacing: Space.s) {
            Image(systemName: "wifi.slash").foregroundStyle(Tone.warn)
            Text(tr("离线示例：读的是打进 app 的真实响应快照，写操作不会真的发生。",
                    "Offline samples: these are real response snapshots bundled into the app. Nothing you change will actually happen."))
                .podsumFont(.meta)
                .foregroundStyle(Tone.textMuted)
            Spacer()
            Button(tr("去设置", "Settings")) { openSettings() }
                .buttonStyle(.plain)
                .podsumFont(.meta)
                .foregroundStyle(Tone.info)
        }
        .padding(Space.m)
        .background(Tone.warn.opacity(0.10), in: RoundedRectangle(cornerRadius: Radius.small))
    }

    // MARK: 侧边栏

    private var sidebar: some View {
        List(selection: $selection) {
            Section {
                ForEach(Filter.allCases) { f in
                    Label(f.label, systemImage: f.icon)
                        .badge(episodes.filter(f.matches).count)
                        .tag(SidebarSelection.status(f))
                }
            }

            Section {
                ForEach(categoryStore.items) { category in
                    dropRow(.category(category.id)) {
                        Label(category.name, systemImage: "folder")
                            .badge(category.episodeCount)
                    }
                    .tag(SidebarSelection.category(category.id))
                    .contextMenu {
                        Button(tr("重命名…", "Rename…")) { naming = .rename(category) }
                        Button(tr("删除…", "Delete…"), role: .destructive) { pendingCategoryDelete = category }
                    }
                }
                .onMove { source, destination in
                    Task {
                        do { try await categoryStore.move(from: source, to: destination, repository) }
                        catch { actionError = error.localizedDescription }
                    }
                }

                dropRow(.uncategorized) {
                    Label(tr("未分类", "Uncategorized"), systemImage: "tray")
                        .badge(categoryStore.uncategorizedCount)
                }
                .tag(SidebarSelection.uncategorized)
            } header: {
                HStack(spacing: Space.s) {
                    Text(tr("分类", "Categories"))
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button { showCategorize = true } label: {
                        Image(systemName: "sparkles")
                    }
                    .buttonStyle(.borderless)
                    .accessibilityLabel(tr("AI 分类", "AI Categorize"))
                    .disabled(categoryStore.isRunning && !showCategorize)
                    .help(tr("AI 分类：把「未分类」里的视频放进已有分类或新分类，你确认后才生效。只在点这里时运行。",
                             "AI Categorize: file your Uncategorized videos into existing or new categories. Nothing changes until you confirm. Runs only when you click here."))
                    Button { naming = .create(assigning: nil) } label: {
                        Image(systemName: "plus")
                    }
                    .buttonStyle(.borderless)
                    .help(tr("新建分类", "New Category"))
                    .accessibilityLabel(tr("新建分类", "New Category"))
                }
                // A sidebar section header is flattened into one AX heading by
                // default, which leaves these two buttons unreachable by
                // VoiceOver (and by anything else driving the app through AX).
                .accessibilityElement(children: .contain)
            }
        }
    }

    /// 能把视频拖上来的一行。放下即手动归类（锁定）；拖到「未分类」即移出分类。
    private func dropRow<Content: View>(_ target: SidebarSelection, @ViewBuilder content: () -> Content) -> some View {
        content()
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(Tone.info.opacity(dropTarget == target ? 0.22 : 0))
                    .padding(.horizontal, -6)
            )
            .dropDestination(for: String.self) { items, _ in
                let ids = items.compactMap(EpisodeDrag.episodeID)
                guard !ids.isEmpty else { return false }
                let categoryID: String? = if case .category(let id) = target { id } else { nil }
                Task { for id in ids { await assign(id, to: categoryID) } }
                return true
            } isTargeted: { targeted in
                if targeted { dropTarget = target } else if dropTarget == target { dropTarget = nil }
            }
    }

    private var isCategoryScope: Bool {
        if case .category = selection { return true }
        return false
    }

    @ViewBuilder
    private func menu(for episode: EpisodeSummary) -> some View {
        Menu(tr("移到分类", "Move to Category")) {
            ForEach(categoryStore.items) { category in
                Button {
                    Task { await assign(episode.id, to: category.id) }
                } label: {
                    if episode.category?.id == category.id {
                        Label(category.name, systemImage: "checkmark")
                    } else {
                        Text(category.name)
                    }
                }
            }
            if !categoryStore.items.isEmpty { Divider() }
            Button(tr("新建分类…", "New Category…")) { naming = .create(assigning: episode.id) }
        }
        if episode.category != nil {
            Button(tr("移出分类", "Remove from Category")) { Task { await assign(episode.id, to: nil) } }
        }
        // Only a video you took out by hand is kept away from AI; one already
        // in a category is left alone anyway.
        if episode.category == nil, episode.categoryOrigin?.value == .manual {
            Button(tr("交给 AI 分类", "Let AI Categorize")) { Task { await release(episode.id) } }
                .help(tr("你把它移出过分类，所以 AI 一直跳过它。交还后，下次 AI 分类会处理它。",
                         "You took it out of a category, so AI skips it. Hand it back and the next AI categorization will file it."))
        }
        Divider()
        Button(tr("重新处理", "Reprocess")) { Task { await retry(episode) } }
            .disabled(episode.status.value == .processing || episode.status.value == .pending)
        Divider()
        Button(tr("删除…", "Delete…"), role: .destructive) { pendingDelete = episode }
    }

    // MARK: 动作

    private func load() async {
        phase = .loading
        do {
            episodes = try await repository.list()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    // MARK: 分类（004）

    private func assign(_ episodeID: String, to categoryID: String?) async {
        do {
            let assignment = try await categoryStore.assign(episodeID, to: categoryID, repository)
            applyLocally(episodeID, assignment)
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func release(_ episodeID: String) async {
        do {
            applyLocally(episodeID, try await categoryStore.release(episodeID, repository))
        } catch {
            actionError = error.localizedDescription
        }
    }

    /// 只改这一条，不整页重载
    private func applyLocally(_ episodeID: String, _ assignment: CategoryAssignment) {
        guard let index = episodes.firstIndex(where: { $0.id == episodeID }) else { return }
        episodes[index].category = assignment.category
        episodes[index].categoryOrigin = assignment.categoryOrigin
        Task { await categoryStore.refresh(repository) }
    }

    private func submitName(_ name: String, for naming: CategoryNaming) async throws {
        switch naming {
        case .create(let episodeID):
            let category = try await categoryStore.create(name, repository)
            if let episodeID { await assign(episodeID, to: category.id) }
        case .rename(let category):
            try await categoryStore.rename(category.id, to: name, repository)
            let renamed = categoryStore.category(id: category.id)?.name ?? name
            for index in episodes.indices where episodes[index].category?.id == category.id {
                episodes[index].category = CategoryRef(id: category.id, name: renamed)
            }
        }
    }

    private func deleteCategory(_ category: EpisodeCategory) async {
        pendingCategoryDelete = nil
        do {
            try await categoryStore.delete(category.id, repository)
            for index in episodes.indices where episodes[index].category?.id == category.id {
                episodes[index].category = nil
                episodes[index].categoryOrigin = nil
            }
            if selection == .category(category.id) { selection = .status(.all) }
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func connectJobs() {
        jobs.onFinished = { _ in Task { await load() } }
        jobs.connect(to: repository)
    }

    private func retry(_ episode: EpisodeSummary) async {
        do {
            _ = try await repository.retry(id: episode.id)
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func delete(_ episode: EpisodeSummary) async {
        pendingDelete = nil
        do {
            try await repository.delete(id: episode.id)
            episodes.removeAll { $0.id == episode.id }
        } catch {
            actionError = error.localizedDescription
        }
    }
}

#Preview("列表页") {
    EpisodeListView()
        .environment(UIState())
        .environment(JobsModel())
        .environment(QuickAddCenter(backend: BackendController()))
        .frame(width: 1120, height: 760)
}

/// 列表里拖出来的视频。用带前缀的纯文本，免得从别处拖进来的任意文字被当成剧集 id。
enum EpisodeDrag {
    private static let prefix = "podsum-episode:"

    static func payload(_ id: String) -> String { prefix + id }

    static func episodeID(_ payload: String) -> String? {
        payload.hasPrefix(prefix) ? String(payload.dropFirst(prefix.count)) : nil
    }
}
