import SwiftUI

struct EpisodeListView: View {
    @Environment(\.episodeRepository) private var repository

    @State private var episodes: [EpisodeSummary] = []
    @State private var phase: Phase = .loading
    @State private var filter: Filter = .all
    @State private var query = ""

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
        NavigationSplitView {
            List(Filter.allCases, selection: $filter) { f in
                Label(f.label, systemImage: f.icon)
                    .badge(episodes.filter(f.matches).count)
                    .tag(f)
            }
            .navigationSplitViewColumnWidth(min: 168, ideal: 188, max: 240)
        } detail: {
            content
                .navigationTitle("Podsum")
                .navigationSubtitle(subtitle)
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            Task { await load() }
                        } label: {
                            Label("刷新", systemImage: "arrow.clockwise")
                        }
                        .disabled(phase == .loading)
                        .keyboardShortcut("r", modifiers: .command)
                    }
                }
                .searchable(text: $query, placement: .toolbar, prompt: "搜索标题或播客")
        }
        .task { await load() }
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
            }
            .background(Tone.bg)

        case .loaded:
            ScrollView {
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 252), spacing: 16)],
                    spacing: 16
                ) {
                    ForEach(visible) { EpisodeCard(episode: $0) }
                }
                .padding(20)
            }
            .background(Tone.bg)
        }
    }

    private func load() async {
        phase = .loading
        do {
            episodes = try await repository.list()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }
}

#Preview("列表页") {
    EpisodeListView()
        .frame(width: 1120, height: 760)
}
