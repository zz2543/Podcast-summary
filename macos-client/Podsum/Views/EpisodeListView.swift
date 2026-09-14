import SwiftUI

struct EpisodeListView: View {
    /// 离线模式的横幅。接了后端就不显示。
    var offlineNotice = false

    @Environment(\.episodeRepository) private var repository
    @Environment(\.textScale) private var scale
    @Environment(UIState.self) private var ui
    @Environment(JobsModel.self) private var jobs
    @Environment(\.openSettings) private var openSettings

    @State private var episodes: [EpisodeSummary] = []
    @State private var phase: Phase = .loading
    @State private var filter: Filter = .all
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
            case .all:     return "全部"
            case .done:    return "已完成"
            case .running: return "进行中"
            case .scored:  return "已评分"
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

    private var visible: [EpisodeSummary] {
        episodes.filter { e in
            guard filter.matches(e) else { return false }
            guard !query.isEmpty else { return true }
            let hay = [e.title, e.podcastName].compactMap { $0 }.joined(separator: " ")
            return hay.localizedCaseInsensitiveContains(query)
        }
    }

    var body: some View {
        @Bindable var ui = ui

        NavigationSplitView {
            List(Filter.allCases, selection: $filter) { f in
                Label(f.label, systemImage: f.icon)
                    .badge(episodes.filter(f.matches).count)
                    .tag(f)
            }
            .navigationSplitViewColumnWidth(min: 168, ideal: 188, max: 240)
        } detail: {
            NavigationStack {
                content
                    .navigationDestination(for: String.self) { id in
                        EpisodeDetailView(episodeID: id, onDeleted: { await load() })
                    }
            }
            .navigationTitle("Podsum")
            .navigationSubtitle(subtitle)
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { ui.showSubmit = true } label: {
                        Label("添加剧集", systemImage: "plus")
                    }
                    .help("添加剧集（⌘N）")
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await load() }
                    } label: {
                        Label("刷新", systemImage: "arrow.clockwise")
                    }
                    .disabled(phase == .loading)
                }
            }
            .searchable(text: $query, placement: .toolbar, prompt: "搜索标题或播客")
        }
        .task { await load() }
        .task { connectJobs() }
        .onChange(of: ui.refreshToken) { _, _ in Task { await load() } }
        .sheet(isPresented: $ui.showSubmit) {
            SubmitSheet { created in
                // 新提交的剧集立刻插到前面，不必等下一次拉取——
                // 后端已经返回了完整的 EpisodeSummary。
                episodes.insert(contentsOf: created.map(\.episode), at: 0)
            }
            .environment(\.episodeRepository, repository)
            .environment(\.textScale, scale)
        }
        .alert("删除这一集？", isPresented: Binding(
            get: { pendingDelete != nil },
            set: { if !$0 { pendingDelete = nil } }
        ), presenting: pendingDelete) { episode in
            Button("删除", role: .destructive) { Task { await delete(episode) } }
            Button("取消", role: .cancel) { pendingDelete = nil }
        } message: { episode in
            Text("「\(episode.displayTitle)」的音频、文稿与摘要都会从磁盘上一并删掉，且无法撤销。")
        }
        .alert("操作失败", isPresented: Binding(
            get: { actionError != nil },
            set: { if !$0 { actionError = nil } }
        )) {
            Button("好") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
    }

    private var subtitle: String {
        switch phase {
        case .loading:    return "载入中…"
        case .failed:     return "载入失败"
        case .loaded:     return "\(visible.count) 集"
        }
    }

    @ViewBuilder
    private var content: some View {
        switch phase {
        case .loading:
            ProgressView("读取剧集…")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Tone.bg)

        case .failed(let message):
            ContentUnavailableView {
                Label("载入失败", systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button("重试") { Task { await load() } }
            }
            .background(Tone.bg)

        case .loaded where visible.isEmpty:
            ContentUnavailableView {
                Label(query.isEmpty ? "没有符合条件的剧集" : "无搜索结果",
                      systemImage: "tray")
            } description: {
                Text(query.isEmpty ? "换一个筛选条件试试。" : "「\(query)」没有匹配到任何剧集。")
            } actions: {
                if query.isEmpty { Button("添加剧集") { ui.showSubmit = true } }
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
                                EpisodeCard(episode: episode)
                            }
                            .buttonStyle(.plain)
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
            Text("离线示例：读的是打进 app 的真实响应快照，写操作不会真的发生。")
                .podsumFont(.meta)
                .foregroundStyle(Tone.textMuted)
            Spacer()
            Button("去设置") { openSettings() }
                .buttonStyle(.plain)
                .podsumFont(.meta)
                .foregroundStyle(Tone.info)
        }
        .padding(Space.m)
        .background(Tone.warn.opacity(0.10), in: RoundedRectangle(cornerRadius: Radius.small))
    }

    @ViewBuilder
    private func menu(for episode: EpisodeSummary) -> some View {
        Button("重新处理") { Task { await retry(episode) } }
            .disabled(episode.status.value == .processing || episode.status.value == .pending)
        Divider()
        Button("删除…", role: .destructive) { pendingDelete = episode }
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
        .frame(width: 1120, height: 760)
}
