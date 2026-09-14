import Foundation
import SwiftUI

// MARK: - 接缝
//
// 视图只认这个协议。Mock 读打进 bundle 的真实快照，不需要后端；
// LiveRepository 走 HTTP。两者的差别对视图不可见。

/// 一次提交。链接与文件不能混在同一个批次里——后端的 /batch
/// 对二者走的是两条路径（JSON items vs multipart files）。
public struct Submission: Sendable {
    public enum Item: Sendable, Hashable, Identifiable {
        case link(String, sourceType: SourceType)
        case file(URL)

        public var id: String {
            switch self {
            case .link(let s, _): return "link:" + s
            case .file(let u):    return "file:" + u.path()
            }
        }

        public var isFile: Bool { if case .file = self { return true }; return false }

        public var display: String {
            switch self {
            case .link(let s, _): return s
            case .file(let u):    return u.lastPathComponent
            }
        }
    }

    public var items: [Item]
    public var style: SummaryStyleInput

    public init(items: [Item], style: SummaryStyleInput = SummaryStyleInput()) {
        self.items = items
        self.style = style
    }

    /// 链接归哪一类：视频站走 yt-dlp（后端叫 "youtube"，实际也吃 bilibili），
    /// 其余当直链音频。判断用 host —— source_type 字段本身不可信，
    /// 真实数据里 29 集全标 youtube，其中一堆是 bilibili（见 api-shapes.md 第 1 条）。
    public static func guessSourceType(_ raw: String) -> SourceType {
        guard let host = URL(string: raw.trimmed)?.host()?.lowercased() else { return .directURL }
        let videoHosts = ["youtube.com", "youtu.be", "bilibili.com", "b23.tv", "www.youtube.com",
                          "m.youtube.com", "www.bilibili.com", "m.bilibili.com"]
        return videoHosts.contains(where: { host == $0 || host.hasSuffix("." + $0) }) ? .youtube : .directURL
    }
}

public protocol EpisodeRepository: Sendable {
    func list() async throws -> [EpisodeSummary]
    func detail(id: String) async throws -> EpisodeDetail

    // 写操作
    func create(_ submission: Submission) async throws -> [CreateEpisodeResponse]
    func retry(id: String) async throws -> Job
    func delete(id: String) async throws
    func requestDigest(id: String) async throws -> DigestResponse

    /// SSE 流式回答。逐 token 吐出，抛错即中断。
    func chat(id: String, message: String, history: [ChatTurn]) -> AsyncThrowingStream<String, Error>

    /// 原声音频。能落到本地文件就给 file://（免走 HTTP，拖动进度条不受 Range 影响），
    /// 否则回退到 /files/audio。
    func audioURL(for episode: EpisodeDetail) -> URL?
    /// 合成的音频摘要，没有则 nil
    func digestURL(for episode: EpisodeDetail) -> URL?

    /// 实时任务事件。Mock 用定时器假装，Live 走 WebSocket。
    func jobEvents() -> AsyncStream<JobEvent>
}

public enum RepositoryError: LocalizedError {
    case fixtureMissing(String)
    case notFound(String)
    /// 阶段 1 只抓了 5 集详情快照，其余 24 集在 Mock 下打不开。
    /// 这不是错误，是 Mock 的已知边界——接上后端即消失。
    case noDetailFixture(String)
    case mockUnsupported(String)
    case api(code: String, message: String, status: Int)
    case transport(String)

    public var errorDescription: String? {
        switch self {
        case .fixtureMissing(let n):
            return "缺少 fixture：\(n).json"
        case .notFound(let id):
            return "找不到剧集：\(id)"
        case .noDetailFixture:
            return "这一集还没有本地详情快照。\n\n"
                 + "离线模式只内置了 5 集详情（覆盖 done / partial / processing / 老数据 / 极短时长）。"
                 + "接上后端后，29 集全部可以打开。"
        case .mockUnsupported(let what):
            return "离线模式下不能\(what)——这一步需要真的后端。"
        case .api(let code, let message, _):
            return "\(message)（\(code)）"
        case .transport(let message):
            return message
        }
    }
}

// MARK: - Mock

/// 读打进 bundle 的真实 API 响应快照。不需要后端在跑。
///
/// 写操作在这里是"假装成功"：新提交的剧集只存在内存里，
/// 并由一个定时器推着走完流水线阶段，好让 ActiveJobsStrip 的动效
/// 在没有后端时也能验收。关掉 app 就没了——这是 Mock，不是持久化。
public final class MockRepository: EpisodeRepository, @unchecked Sendable {
    /// 人为延迟，用来验证加载态真的会出现
    public var latency: Duration = .milliseconds(280)

    private let lock = NSLock()
    private var pending: [EpisodeSummary] = []
    private var continuations: [UUID: AsyncStream<JobEvent>.Continuation] = [:]

    public init() {}

    public func list() async throws -> [EpisodeSummary] {
        try? await Task.sleep(for: latency)
        let fixtures = try Self.decode(EpisodeListResponse.self, from: "episodes-list").items
        return pendingSnapshot() + fixtures
    }

    public func detail(id: String) async throws -> EpisodeDetail {
        try? await Task.sleep(for: latency)
        for name in Self.detailFixtures {
            if let d = try? Self.decode(EpisodeDetail.self, from: name), d.id == id {
                return d
            }
        }
        throw RepositoryError.noDetailFixture(id)
    }

    public func create(_ submission: Submission) async throws -> [CreateEpisodeResponse] {
        try? await Task.sleep(for: latency)
        let now = Date()
        let responses: [CreateEpisodeResponse] = submission.items.map { item in
            let id = "MOCK" + UUID().uuidString.prefix(22).replacingOccurrences(of: "-", with: "")
            let episode = EpisodeSummary(
                id: id,
                title: item.display,
                podcastName: nil,
                sourceType: .known(item.isFile ? .localFile : .youtube),
                durationSeconds: nil,
                language: nil,
                status: .known(.pending),
                stageStatus: .allPending,
                usefulness: nil,
                createdAt: now,
                updatedAt: now
            )
            let job = Job(id: "job-" + id, episodeID: id, state: .known(.queued),
                          stageProgress: [:], attempt: 1, error: nil,
                          startedAt: now, finishedAt: nil)
            return CreateEpisodeResponse(episode: episode, job: job)
        }
        insertPending(responses.map(\.episode))
        for response in responses { fakeProgress(for: response.job) }
        return responses
    }

    public func retry(id: String) async throws -> Job {
        throw RepositoryError.mockUnsupported("重试")
    }

    public func delete(id: String) async throws {
        guard removePending(id) else {
            throw RepositoryError.mockUnsupported("删除后端里的剧集")
        }
    }

    public func requestDigest(id: String) async throws -> DigestResponse {
        throw RepositoryError.mockUnsupported("生成音频摘要")
    }

    public func chat(id: String, message: String, history: [ChatTurn]) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                let reply = "离线模式没有接 LLM，所以这里只能复述你的问题：「\(message)」。"
                           + "接上后端后，回答会基于这一集的转录文稿逐字流式返回。"
                for character in reply {
                    try? await Task.sleep(for: .milliseconds(18))
                    continuation.yield(String(character))
                }
                continuation.finish()
            }
        }
    }

    /// Mock 下不给音频：fixture 是 API 响应快照，磁盘上未必有对应的 mp3。
    public func audioURL(for episode: EpisodeDetail) -> URL? { nil }
    public func digestURL(for episode: EpisodeDetail) -> URL? { nil }

    public func jobEvents() -> AsyncStream<JobEvent> {
        AsyncStream { continuation in
            let key = UUID()
            lock.lock(); continuations[key] = continuation; lock.unlock()
            continuation.onTermination = { [weak self] _ in
                guard let self else { return }
                lock.lock(); continuations[key] = nil; lock.unlock()
            }
            continuation.yield(.hello(serverVersion: "mock"))
            continuation.yield(.snapshot(jobs: []))
        }
    }

    // 下面几个是同步的：async 方法里直接持 NSLock 在 Swift 6 下是错误，
    // 而这些临界区都极短、不会挂起，抽成同步方法即可。
    private func pendingSnapshot() -> [EpisodeSummary] {
        lock.lock(); defer { lock.unlock() }
        return pending
    }

    private func insertPending(_ episodes: [EpisodeSummary]) {
        lock.lock(); defer { lock.unlock() }
        pending.insert(contentsOf: episodes, at: 0)
    }

    @discardableResult
    private func removePending(_ id: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard pending.contains(where: { $0.id == id }) else { return false }
        pending.removeAll { $0.id == id }
        return true
    }

    private func markPending(_ episodeID: String, status: EpisodeStatus) {
        lock.lock(); defer { lock.unlock() }
        guard let i = pending.firstIndex(where: { $0.id == episodeID }) else { return }
        let e = pending[i]
        pending[i] = EpisodeSummary(
            id: e.id, title: e.title, podcastName: e.podcastName, sourceType: e.sourceType,
            durationSeconds: e.durationSeconds, language: e.language,
            status: .known(status), stageStatus: e.stageStatus, usefulness: e.usefulness,
            createdAt: e.createdAt, updatedAt: Date()
        )
    }

    private func broadcast(_ event: JobEvent) {
        lock.lock(); let targets = Array(continuations.values); lock.unlock()
        for target in targets { target.yield(event) }
    }

    /// 把一个假任务推过完整的阶段序列，每 1.6 秒一步。
    private func fakeProgress(for job: Job) {
        Task { [weak self] in
            let states: [JobState] = [.queued, .fetching, .transcribing, .summarizing, .done]
            for state in states {
                try? await Task.sleep(for: .seconds(1.6))
                guard let self else { return }
                let updated = Job(id: job.id, episodeID: job.episodeID, state: .known(state),
                                  stageProgress: [state.rawValue: .object(["status": .string("running")])],
                                  attempt: 1, error: nil, startedAt: job.startedAt,
                                  finishedAt: state == .done ? Date() : nil)
                broadcast(.jobUpdate(job: updated, episodeStatus: .known(state == .done ? .done : .processing)))
                markPending(job.episodeID, status: state == .done ? .done : .processing)
            }
        }
    }

    /// 有详情快照的 5 集，列表页据此标出哪些现在点得开
    public static let availableDetailIDs: Set<String> = [
        "01M2FKVC8GT40083QZHH6VRSMW",   // done + 评分 62 + takeaway 齐全
        "01M24YD0Y31GTCCNDCYN19KV1R",   // partial + tts failed_after_retries
        "01M2519A4VN17APQPWS86FYERW",   // processing + chapter.summary
        "01KS40ADBZE4Y9ES3G88N9YQYF",   // 28 秒极短
        "01KRZNBZYAKE6G40GN02EQ1TRC",   // 老数据：takeaway / usefulness 全 nil
    ]

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

extension StageStatusSet {
    static var allPending: StageStatusSet {
        StageStatusSet(hook: .known(.pending), threeAct: .known(.pending), chapters: .known(.pending),
                       entities: .known(.pending), usefulness: .known(.pending), tts: .known(.pending))
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
