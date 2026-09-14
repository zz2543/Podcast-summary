import Foundation

/// 供 #Preview 同步取用的真实数据。解码失败时返回空数组，
/// 预览里看到空列表就说明 fixture 没打进 bundle。
enum PreviewFixtures {
    static let episodes: [EpisodeSummary] = {
        (try? MockRepository.decode(EpisodeListResponse.self, from: "episodes-list").items) ?? []
    }()

    /// 挑出覆盖面最广的几条：有评分的、处理中的、部分完成的、无评分的
    static var assorted: [EpisodeSummary] {
        let all = episodes
        var picked: [EpisodeSummary] = []
        if let scored = all.first(where: { $0.usefulness != nil }) { picked.append(scored) }
        if let proc = all.first(where: { $0.status.value == .processing }) { picked.append(proc) }
        if let part = all.first(where: { $0.status.value == .partial }) { picked.append(part) }
        if let plain = all.first(where: { $0.usefulness == nil }) { picked.append(plain) }
        return picked.isEmpty ? Array(all.prefix(4)) : picked
    }
}
