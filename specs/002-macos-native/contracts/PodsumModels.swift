//
//  PodsumModels.swift
//  Podsum — macOS 原生客户端的数据契约
//
//  来源：specs/001-podcast-summary/contracts/episode-output.schema.json
//  校准：2026-09-14 对本机运行中的后端 http://127.0.0.1:8000 抓取 29 个真实剧集响应逐字段核对。
//
//  三条硬约束，改动前先读：
//
//  1. 列表和详情是两种形状，不是一种。
//     GET /api/episodes      → EpisodeSummary（11 字段，无 hook/three_act/chapters/entities）
//     GET /api/episodes/{id} → EpisodeDetail （20 字段）
//     后端分别由 _episode_summary / _episode_detail 构造，不要试图合并成一个类型。
//
//  2. 所有枚举必须能容纳未知值。
//     后端枚举会随 pipeline 演进新增取值；一个未知的 status 不该让整个列表解码失败。
//     故全部枚举用 UnknownFallback 包装，解码永不抛错。
//
//  3. 日期不是标准 ISO8601。
//     实际形如 "2026-09-14T09:27:15.770252" —— 无时区后缀、6 位小数秒。
//     JSONDecoder.DateDecodingStrategy.iso8601 会直接解码失败。必须用下方 .podsum 策略。
//

import Foundation

// MARK: - 枚举（全部带未知值兜底）

/// 让未知的服务端枚举值降级为 .unknown(原始串) 而不是抛错。
public enum Fallback<T: RawRepresentable & Codable & Sendable & Hashable>: Codable, Sendable, Hashable
where T.RawValue == String {
    case known(T)
    case unknown(String)

    public init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = T(rawValue: raw).map(Fallback.known) ?? .unknown(raw)
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        try c.encode(rawValue)
    }

    public var value: T? { if case .known(let v) = self { return v }; return nil }
    public var rawValue: String {
        switch self {
        case .known(let v): return v.rawValue
        case .unknown(let s): return s
        }
    }
}

/// 由剧集"有什么"推出来，不再照抄最近一个任务的结局（后端 domain/episode_status.py）：
/// processing 摘要任务在排队或在跑 · done 一句话/三幕/章节齐全 ·
/// partial 齐全但评分或提及失败 · failed 摘要任务跑完了却没产出这三样 · pending 还没跑过。
/// 音频摘要（tts）永远不影响它。
public enum EpisodeStatus: String, Codable, Sendable {
    case pending, processing, done, partial, failed
}

public enum StageStatus: String, Codable, Sendable {
    case pending, present, missing
    case failedAfterRetries = "failed_after_retries"
}

/// 注意：真实数据里 29 个剧集全部标为 .youtube，但其中大量 source_ref 实际是
/// bilibili.com 链接。判断来源平台请解析 sourceRef 的 host，不要信这个字段。
public enum SourceType: String, Codable, Sendable {
    case localFile = "local_file"
    case directURL = "direct_url"
    case youtube
}

public enum Language: String, Codable, Sendable {
    case zh, en, mixed
}

public enum UsefulnessBand: String, Codable, Sendable {
    case mustListen = "must_listen"
    case worthListening = "worth_listening"
    case skimmable, skippable
}

public enum SummaryPreset: String, Codable, Sendable, CaseIterable {
    case `default`, studyNotes = "study_notes", businessInsight = "business_insight"
    case debate, quickSkim = "quick_skim"
}

public enum SummaryDetail: String, Codable, Sendable, CaseIterable {
    case concise, standard, detailed
}

public enum EntityKind: String, Codable, Sendable {
    case person, book, product
}

// MARK: - 子结构

public struct StageStatusSet: Codable, Sendable, Hashable {
    public let hook: Fallback<StageStatus>
    public let threeAct: Fallback<StageStatus>
    public let chapters: Fallback<StageStatus>
    public let entities: Fallback<StageStatus>
    public let usefulness: Fallback<StageStatus>
    public let tts: Fallback<StageStatus>

    enum CodingKeys: String, CodingKey {
        case hook, chapters, entities, usefulness, tts
        case threeAct = "three_act"
    }
}

public struct Usefulness: Codable, Sendable, Hashable {
    public let score: Int          // 0–100，后端保证不裁剪
    public let band: Fallback<UsefulnessBand>
    public let rationale: String   // 一句话，用剧集源语言
}

public struct ThreeAct: Codable, Sendable, Hashable {
    public let background: String
    public let coreArgument: String
    public let conclusion: String

    enum CodingKeys: String, CodingKey {
        case background, conclusion
        case coreArgument = "core_argument"
    }
}

public struct Quote: Codable, Sendable, Hashable {
    public let text: String          // 已逐字校验过的原文，用于对准时间戳
    public let takeaway: String?     // 老数据为 null：key moments 上线前入库的引用
    public let startMs: Int

    enum CodingKeys: String, CodingKey {
        case text, takeaway
        case startMs = "start_ms"
    }
}

public struct Chapter: Codable, Sendable, Hashable, Identifiable {
    public let idx: Int
    public let title: String
    public let startMs: Int
    public let endMs: Int
    public let keyPoints: [String]
    public let summary: String?      // 仅在要点本身丢失因果链时才有；多数为 null
    public let quotes: [Quote]

    public var id: Int { idx }

    enum CodingKeys: String, CodingKey {
        case idx, title, summary, quotes
        case startMs = "start_ms"
        case endMs = "end_ms"
        case keyPoints = "key_points"
    }
}

public struct Entity: Codable, Sendable, Hashable, Identifiable {
    public let name: String
    public let kind: Fallback<EntityKind>
    public let count: Int
    public let sampleTimestampsMs: [Int]?   // 最多 5 个

    public var id: String { "\(name)-\(kind.rawValue)" }

    enum CodingKeys: String, CodingKey {
        case name, kind, count
        case sampleTimestampsMs = "sample_timestamps_ms"
    }
}

public struct PromptVersions: Codable, Sendable, Hashable {
    public let oneLiner: String
    public let threeAct: String
    public let chapterOutline: String
    public let entityExtraction: String
    public let usefulnessScore: String?   // 老数据缺此键
    public let summaryStyle: String?

    enum CodingKeys: String, CodingKey {
        case oneLiner = "one_liner"
        case threeAct = "three_act"
        case chapterOutline = "chapter_outline"
        case entityExtraction = "entity_extraction"
        case usefulnessScore = "usefulness_score"
        case summaryStyle = "summary_style"
    }
}

public struct SummaryStyle: Codable, Sendable, Hashable {
    public let preset: Fallback<SummaryPreset>
    public let note: String?               // ≤ 200 字
    public let detail: Fallback<SummaryDetail>?
}

/// 相对于仓库根目录的路径，例如 "data/<ULID>/summary.md"。
/// 磁盘上的 summary.json 里这三个字段恒为 null；只有 API 响应里才是填好的。
public struct ArtifactPaths: Codable, Sendable, Hashable {
    public let markdown: String?
    public let json: String?
    public let tts: String?
}

// MARK: - 顶层：列表项

/// GET /api/episodes 的单项。刻意不含正文字段。
public struct EpisodeSummary: Codable, Sendable, Identifiable, Hashable {
    public let id: String                  // ULID
    public let title: String?
    public let podcastName: String?
    public let sourceType: Fallback<SourceType>
    public let durationSeconds: Int?
    public let language: Fallback<Language>?
    public let status: Fallback<EpisodeStatus>
    public let stageStatus: StageStatusSet
    public let usefulness: Usefulness?     // 29 个真实剧集里仅 3 个非 null
    public let createdAt: Date
    public let updatedAt: Date
    /// 最近一个摘要任务失败的原因；没失败就是 nil。老后端不发这个键，同样解成 nil。
    public var lastFailure: JobFailure? = nil

    enum CodingKeys: String, CodingKey {
        case id, title, language, status, usefulness
        case podcastName = "podcast_name"
        case sourceType = "source_type"
        case durationSeconds = "duration_seconds"
        case stageStatus = "stage_status"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastFailure = "last_failure"
    }
}

/// 摘要任务失败在哪一步、为什么。与 status 相互独立：
/// 重新处理失败了，而上一次的结果还完整，那么 status 仍是 done，这里讲清楚"这次没成"。
public struct JobFailure: Codable, Sendable, Hashable {
    public let jobID: String
    public let stage: String?      // 流水线阶段名：fetch / transcribe / summarize_hook …
    public let error: String       // 原始报错，给人看之前先过一遍 FailureCopy
    public let attempt: Int
    public let finishedAt: Date?

    enum CodingKeys: String, CodingKey {
        case stage, error, attempt
        case jobID = "job_id"
        case finishedAt = "finished_at"
    }
}

public struct EpisodeListResponse: Codable, Sendable {
    public let items: [EpisodeSummary]
    public let nextCursor: String?         // 后端目前恒为 null，分页尚未实现

    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}

// MARK: - 顶层：详情

/// GET /api/episodes/{id}
public struct EpisodeDetail: Codable, Sendable, Identifiable, Hashable {
    public let id: String
    public let title: String?
    public let podcastName: String?
    public let guests: [String]?           // 真实数据里始终为 null
    public let sourceType: Fallback<SourceType>
    public let sourceRef: String           // 原始 URL —— 判断平台请用这个
    public let durationSeconds: Int?
    public let language: Fallback<Language>?
    public let status: Fallback<EpisodeStatus>
    public let stageStatus: StageStatusSet
    public let promptVersions: PromptVersions
    public let summaryStyle: SummaryStyle?
    public let hook: String?               // 一句话钩子，≤ 50 字
    public let threeAct: ThreeAct?
    public let usefulness: Usefulness?
    public let chapters: [Chapter]
    public let entities: [Entity]
    public let artifactPaths: ArtifactPaths?
    public let createdAt: Date
    public let updatedAt: Date
    public var lastFailure: JobFailure? = nil   // 只在 API 响应里有，summary.json 里没有

    enum CodingKeys: String, CodingKey {
        case id, title, guests, hook, chapters, entities, language, status, usefulness
        case podcastName = "podcast_name"
        case sourceType = "source_type"
        case sourceRef = "source_ref"
        case durationSeconds = "duration_seconds"
        case stageStatus = "stage_status"
        case promptVersions = "prompt_versions"
        case summaryStyle = "summary_style"
        case threeAct = "three_act"
        case artifactPaths = "artifact_paths"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastFailure = "last_failure"
    }
}

// MARK: - API 错误

/// 后端错误体：{"error": {"code": ..., "message": ..., "details": {...}}}
public struct APIErrorEnvelope: Codable, Sendable {
    public struct Payload: Codable, Sendable {
        public let code: String        // not_found / bad_input / conflict / payload_too_large / unsupported_media
        public let message: String
    }
    public let error: Payload
}

// MARK: - 解码器

public extension JSONDecoder.DateDecodingStrategy {
    /// 后端发的多是 "2026-09-14T09:27:15.770252"：无时区、6 位小数秒。
    /// .iso8601 解不了，必须用这个。无小数秒的变体也一并容纳。
    ///
    /// 无时区的串是 UTC：后端一律用 datetime.now(timezone.utc) 取时间，
    /// 只是 SQLite 存盘时丢了时区后缀。早先按本机时区解，东八区的"更新于"整整慢 8 小时。
    /// 刚在内存里生成、还没回过库的时间（WS 帧里任务的 started_at）会带 +00:00，也要认。
    static let podsum = custom { decoder -> Date in
        let s = try decoder.singleValueContainer().decode(String.self)
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX", "yyyy-MM-dd'T'HH:mm:ssXXXXX",
                    "yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss"] {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.timeZone = TimeZone(identifier: "UTC")   // 仅对无后缀的格式生效
            f.dateFormat = fmt
            if let d = f.date(from: s) { return d }
        }
        throw DecodingError.dataCorrupted(
            .init(codingPath: decoder.codingPath, debugDescription: "无法解析日期: \(s)")
        )
    }
}

public extension JSONDecoder {
    static var podsum: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .podsum
        return d
    }
}

// MARK: - 任务（Job）与实时事件
//
// 这一节对应写操作与 WebSocket，schema 里没有——它们是 API 的形状而非
// 摘要产物的形状。来源：backend/src/podsum/api/episodes.py `_job_payload`
// 与 api/ws_progress.py 的四种帧。fixtures/ 里没有对应快照，
// 解码验证用 verify/main.swift 里的内联样本（取自真实响应）。

public enum JobState: String, Codable, Sendable {
    case queued, fetching, transcribing, summarizing, tts
    case done, partial, failed
}

public extension Fallback where T == JobState {
    var label: String {
        switch self {
        case .known(let s):
            switch s {
            case .queued:       return "排队中"
            case .fetching:     return "抓取音频"
            case .transcribing: return "转写"
            case .summarizing:  return "生成摘要"
            case .tts:          return "合成音频"
            case .done:         return "已完成"
            case .partial:      return "部分完成"
            case .failed:       return "失败"
            }
        case .unknown(let raw):
            return raw
        }
    }

    /// 流水线里已走过的比例。用于进度条——后端不发百分比，
    /// 只发当前处在哪个阶段，进度只能由阶段序号推出来。
    var fraction: Double {
        let order: [JobState] = [.queued, .fetching, .transcribing, .summarizing, .tts]
        switch value {
        case .done, .partial, .failed: return 1
        case .some(let s):
            guard let i = order.firstIndex(of: s) else { return 0 }
            return Double(i) / Double(order.count)
        case nil: return 0
        }
    }

    var isTerminal: Bool {
        switch value {
        case .done, .partial, .failed: return true
        default: return false        // 未知取值按"仍在进行"处理，不会卡死进度条
        }
    }
}

/// 任意 JSON。`stage_progress` 的值是异构的——流水线阶段写的是
/// `{"status": "running"}` 这样的对象，而 digest 任务写的是
/// `{"requested_stage": "tts"}`（值为字符串）。用固定结构解会直接失败。
public enum JSONValue: Codable, Sendable, Hashable {
    case string(String), number(Double), bool(Bool), null
    case array([JSONValue]), object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null; return }
        if let v = try? c.decode(Bool.self) { self = .bool(v); return }
        if let v = try? c.decode(Double.self) { self = .number(v); return }
        if let v = try? c.decode(String.self) { self = .string(v); return }
        if let v = try? c.decode([JSONValue].self) { self = .array(v); return }
        if let v = try? c.decode([String: JSONValue].self) { self = .object(v); return }
        throw DecodingError.dataCorrupted(
            .init(codingPath: decoder.codingPath, debugDescription: "无法解析的 JSON 值")
        )
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v):   try c.encode(v)
        case .null:          try c.encodeNil()
        case .array(let v):  try c.encode(v)
        case .object(let v): try c.encode(v)
        }
    }

    public var stringValue: String? { if case .string(let s) = self { return s }; return nil }
    public subscript(key: String) -> JSONValue? {
        if case .object(let o) = self { return o[key] }
        return nil
    }
}

/// POST /api/episodes 等返回的任务对象。
public struct Job: Codable, Sendable, Identifiable, Hashable {
    public let id: String
    public let episodeID: String
    public let state: Fallback<JobState>
    public let stageProgress: [String: JSONValue]
    public let attempt: Int
    public let error: String?
    public let startedAt: Date?
    public let finishedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, state, attempt, error
        case episodeID = "episode_id"
        case stageProgress = "stage_progress"
        case startedAt = "started_at"
        case finishedAt = "finished_at"
    }

    /// 正在跑的阶段名，取 stage_progress 里 status == "running" 的那个。
    public var runningStage: String? {
        stageProgress.first { $0.value["status"]?.stringValue == "running" }?.key
    }
}

/// WS /api/ws/jobs 的帧。五种 type，未知 type 降级为 .other 而不是抛错——
/// 一条没见过的帧不该让整条连接断掉。
public enum JobEvent: Decodable, Sendable {
    case hello(serverVersion: String)
    case snapshot(jobs: [Job])
    case jobUpdate(job: Job, episodeStatus: Fallback<EpisodeStatus>)
    case stageStatusUpdate(episodeID: String, stage: String, status: Fallback<StageStatus>)
    case error(code: String, message: String)
    case other(String)

    enum CodingKeys: String, CodingKey {
        case type, job, jobs, stage, status, code, message
        case serverVersion = "server_version"
        case episodeID = "episode_id"
        case episodeStatus = "episode_status"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        switch try c.decode(String.self, forKey: .type) {
        case "hello":
            self = .hello(serverVersion: (try? c.decode(String.self, forKey: .serverVersion)) ?? "")
        case "snapshot":
            self = .snapshot(jobs: (try? c.decode([Job].self, forKey: .jobs)) ?? [])
        case "job_update":
            self = .jobUpdate(
                job: try c.decode(Job.self, forKey: .job),
                episodeStatus: try c.decode(Fallback<EpisodeStatus>.self, forKey: .episodeStatus)
            )
        case "stage_status_update":
            self = .stageStatusUpdate(
                episodeID: try c.decode(String.self, forKey: .episodeID),
                stage: try c.decode(String.self, forKey: .stage),
                status: try c.decode(Fallback<StageStatus>.self, forKey: .status)
            )
        case "error":
            self = .error(
                code: (try? c.decode(String.self, forKey: .code)) ?? "unknown",
                message: (try? c.decode(String.self, forKey: .message)) ?? ""
            )
        case let other:
            self = .other(other)
        }
    }
}

// MARK: - 写操作的请求与响应

public struct CreateEpisodeResponse: Codable, Sendable {
    public let episode: EpisodeSummary
    public let job: Job
}

public struct CreateEpisodeBatchResponse: Codable, Sendable {
    public let items: [CreateEpisodeResponse]
}

/// POST /{id}/digest 有两种成功响应：已经合成过则直接回路径，
/// 否则回一个排好队的 Job（202）。
public enum DigestResponse: Decodable, Sendable {
    case alreadyPresent(path: String)
    case queued(Job)

    enum CodingKeys: String, CodingKey { case ttsPath = "tts_path" }

    public init(from decoder: Decoder) throws {
        if let c = try? decoder.container(keyedBy: CodingKeys.self),
           let path = try? c.decode(String.self, forKey: .ttsPath) {
            self = .alreadyPresent(path: path)
            return
        }
        self = .queued(try Job(from: decoder))
    }
}

/// 提交时可选的摘要风格。全部留默认时请求体里一个字段都不带——
/// 与 frontend-v2 的行为一致，避免老请求形状被改动。
public struct SummaryStyleInput: Sendable, Equatable {
    public var preset: SummaryPreset = .default
    public var note: String = ""
    public var detail: SummaryDetail = .standard

    public init() {}

    public var fields: [String: String] {
        var out: [String: String] = [:]
        if preset != .default { out["summary_style"] = preset.rawValue }
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty { out["style_note"] = String(trimmed.prefix(200)) }
        if detail != .standard { out["detail_level"] = detail.rawValue }
        return out
    }
}

/// 只发不收：`/chat` 的请求体带 history，响应是 SSE token 流，
/// 所以这个类型只需要 Encodable。
public struct ChatTurn: Encodable, Sendable, Identifiable, Hashable {
    public enum Role: String, Codable, Sendable { case user, assistant }
    public let role: Role
    public var content: String
    public let id: UUID

    public init(role: Role, content: String, id: UUID = UUID()) {
        self.role = role
        self.content = content
        self.id = id
    }

    enum CodingKeys: String, CodingKey { case role, content }   // id 只在本地列表里用
}
