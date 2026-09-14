import SwiftUI

@main
struct PodsumApp: App {
    /// 阶段 1 注入 Mock；阶段 3 换成 LiveRepository，视图一行不改。
    @State private var repository: any EpisodeRepository = MockRepository()

    var body: some Scene {
        WindowGroup {
            EpisodeListView()
                .environment(\.episodeRepository, repository)
                .frame(minWidth: 880, minHeight: 560)
        }
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1120, height: 760)
    }
}
