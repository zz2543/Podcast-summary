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

public enum SummaryPreset: String, Codable, Sendable {
    case `default`, studyNotes = "study_notes", businessInsight = "business_insight"
    case debate, quickSkim = "quick_skim"
}

public enum SummaryDetail: String, Codable, Sendable {
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

    enum CodingKeys: String, CodingKey {
        case id, title, language, status, usefulness
        case podcastName = "podcast_name"
        case sourceType = "source_type"
        case durationSeconds = "duration_seconds"
        case stageStatus = "stage_status"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
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
    /// 后端发的是 "2026-09-14T09:27:15.770252"：无时区、6 位小数秒。
    /// .iso8601 解不了，必须用这个。无小数秒的变体也一并容纳。
    static let podsum = custom { decoder -> Date in
        let s = try decoder.singleValueContainer().decode(String.self)
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss"] {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.timeZone = TimeZone.current      // 后端写的是本机 naive 时间
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
