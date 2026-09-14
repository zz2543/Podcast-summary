import Foundation
import SwiftUI

// MARK: - 接缝
//
// 视图只认这个协议。阶段 3 接后端时新增 LiveRepository 并换掉注入点，
// 视图与预览都不需要改动。

public protocol EpisodeRepository: Sendable {
    func list() async throws -> [EpisodeSummary]
    func detail(id: String) async throws -> EpisodeDetail
}

public enum RepositoryError: LocalizedError {
    case fixtureMissing(String)
    case notFound(String)

    public var errorDescription: String? {
        switch self {
        case .fixtureMissing(let n): return "缺少 fixture：\(n).json"
        case .notFound(let id): return "找不到剧集：\(id)"
        }
    }
}

// MARK: - Mock

/// 读打进 bundle 的真实 API 响应快照。不需要后端在跑。
public struct MockRepository: EpisodeRepository {
    /// 人为延迟，用来验证加载态真的会出现
    public var latency: Duration = .milliseconds(280)

    public init() {}

    public func list() async throws -> [EpisodeSummary] {
        try? await Task.sleep(for: latency)
        return try Self.decode(EpisodeListResponse.self, from: "episodes-list").items
    }

    public func detail(id: String) async throws -> EpisodeDetail {
        try? await Task.sleep(for: latency)
        for name in Self.detailFixtures {
            if let d = try? Self.decode(EpisodeDetail.self, from: name), d.id == id {
                return d
            }
        }
        throw RepositoryError.notFound(id)
    }

    static let detailFixtures = [
        "detail-done-full", "detail-partial-tts-failed", "detail-processing",
        "detail-done-28s", "detail-done-legacy-null",
    ]

    static func decode<T: Decodable>(_ type: T.Type, from name: String) throws -> T {
        guard let url = Bundle.main.url(forResource: name, withExtension: "json") else {
            throw RepositoryError.fixtureMissing(name)
        }
        return try JSONDecoder.podsum.decode(type, from: Data(contentsOf: url))
    }
}

// MARK: - 注入

private struct EpisodeRepositoryKey: EnvironmentKey {
    static let defaultValue: any EpisodeRepository = MockRepository()
}

public extension EnvironmentValues {
    var episodeRepository: any EpisodeRepository {
        get { self[EpisodeRepositoryKey.self] }
        set { self[EpisodeRepositoryKey.self] = newValue }
    }
}
