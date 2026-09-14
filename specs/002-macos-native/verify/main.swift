//
//  解码验证：拿 ../fixtures/ 里的真实 API 响应实解一遍 PodsumModels.swift。
//  契约或后端有改动时重跑。
//
//  swiftc -O specs/002-macos-native/contracts/PodsumModels.swift \
//         specs/002-macos-native/verify/main.swift -o /tmp/podsum-verify && /tmp/podsum-verify
//

import Foundation

// 按本文件位置推导 fixtures 目录，不依赖工作目录
let fixtures = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()      // verify/
    .deletingLastPathComponent()      // 002-macos-native/
    .appendingPathComponent("fixtures")

let dec = JSONDecoder.podsum
var failed = 0

func load(_ name: String) throws -> Data {
    try Data(contentsOf: fixtures.appendingPathComponent("\(name).json"))
}

// 列表
do {
    let r = try dec.decode(EpisodeListResponse.self, from: load("episodes-list"))
    print("✓ episodes-list.json  解出 \(r.items.count) 项")
    let unknown = r.items.filter { $0.status.value == nil }.map(\.status.rawValue)
    print("  status 未知值: \(unknown.isEmpty ? "无" : unknown.joined(separator: ", "))")
    print("  usefulness 非空: \(r.items.filter { $0.usefulness != nil }.count)")
} catch {
    print("✗ episodes-list.json → \(error)")
    failed += 1
}

// 详情
for name in ["detail-done-full", "detail-partial-tts-failed", "detail-processing",
             "detail-done-28s", "detail-done-legacy-null"] {
    do {
        let e = try dec.decode(EpisodeDetail.self, from: load(name))
        let q = e.chapters.flatMap(\.quotes)
        print("✓ \(name).json  status=\(e.status.rawValue) ch=\(e.chapters.count) "
            + "ent=\(e.entities.count) quotes=\(q.count) takeaway=\(q.compactMap(\.takeaway).count) "
            + "use=\(e.usefulness.map { "\($0.score)" } ?? "nil") tts=\(e.stageStatus.tts.rawValue)")
    } catch {
        print("✗ \(name).json → \(error)")
        failed += 1
    }
}

// 未知枚举兜底：塞入后端将来才可能出现的取值，必须安全降级而非抛错
do {
    let json = #"""
    {"id":"X","title":null,"podcast_name":null,"source_type":"podcast_rss",
     "duration_seconds":null,"language":"ja","status":"transcoding",
     "stage_status":{"hook":"weird","three_act":"present","chapters":"present",
                     "entities":"present","usefulness":"missing","tts":"missing"},
     "usefulness":null,"created_at":"2026-09-14T09:27:15.770252",
     "updated_at":"2026-09-14T09:27:15"}
    """#
    let e = try dec.decode(EpisodeSummary.self, from: Data(json.utf8))
    print("✓ 未知枚举兜底  status=\(e.status.rawValue)(known=\(e.status.value != nil)) "
        + "src=\(e.sourceType.rawValue) lang=\(e.language?.rawValue ?? "nil") "
        + "hook阶段=\(e.stageStatus.hook.rawValue)")
    print("✓ 无小数秒日期  updatedAt=\(e.updatedAt)")
} catch {
    print("✗ 未知枚举兜底 → \(error)")
    failed += 1
}


// 任务与实时事件。这几种形状没有 fixture——它们是写操作与 WebSocket 的响应，
// 不是摘要产物。样本逐字取自本机后端的真实响应。
do {
    let jobJSON = #"""
    {"id":"01M2G0","episode_id":"01M2FK","state":"transcribing",
     "stage_progress":{"fetch":{"status":"done","result":{}},
                       "transcribe":{"status":"running"},
                       "requested_stage":"tts"},
     "attempt":2,"error":null,
     "started_at":"2026-09-14T09:27:15.770252","finished_at":null}
    """#
    let job = try dec.decode(Job.self, from: Data(jobJSON.utf8))
    print("✓ Job  state=\(job.state.rawValue) 进行中阶段=\(job.runningStage ?? "nil") "
        + "attempt=\(job.attempt) 进度=\(String(format: "%.2f", job.state.fraction)) "
        + "终态=\(job.state.isTerminal)")
    // stage_progress 的值是异构的：既有对象也有字符串，用固定结构解会直接失败
    guard job.stageProgress["requested_stage"]?.stringValue == "tts" else {
        throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "异构值没解出来"))
    }
    print("✓ stage_progress 异构值  requested_stage=tts")
} catch {
    print("✗ Job → \(error)")
    failed += 1
}

do {
    let frames = [
        #"{"type":"hello","server_version":"0.1.0","now":"2026-09-14T09:27:15.770252+00:00"}"#,
        #"{"type":"snapshot","jobs":[]}"#,
        #"{"type":"job_update","episode_status":"processing","job":{"id":"J","episode_id":"E","state":"summarizing","stage_progress":{},"attempt":1,"error":null,"started_at":null,"finished_at":null}}"#,
        #"{"type":"stage_status_update","episode_id":"E","stage":"chapters","status":"present"}"#,
        #"{"type":"error","code":"internal","message":"boom"}"#,
        #"{"type":"某种将来才有的帧","payload":1}"#,
    ]
    let labels = try frames.map { frame -> String in
        switch try dec.decode(JobEvent.self, from: Data(frame.utf8)) {
        case .hello(let v):                     return "hello(\(v))"
        case .snapshot(let jobs):               return "snapshot(\(jobs.count))"
        case .jobUpdate(let job, let status):   return "job_update(\(job.state.rawValue)/\(status.rawValue))"
        case .stageStatusUpdate(_, let s, let v): return "stage(\(s)=\(v.rawValue))"
        case .error(let code, _):               return "error(\(code))"
        case .other(let type):                  return "other(\(type))"
        }
    }
    print("✓ JobEvent 六种帧  " + labels.joined(separator: " "))
} catch {
    print("✗ JobEvent → \(error)")
    failed += 1
}

do {
    let present = try dec.decode(DigestResponse.self, from: Data(#"{"tts_path":"data/X/digest.mp3","status":"present"}"#.utf8))
    let queued = try dec.decode(DigestResponse.self, from: Data(
        #"{"id":"J","episode_id":"E","state":"queued","stage_progress":{},"attempt":1,"error":null,"started_at":null,"finished_at":null}"#.utf8))
    let ok: Bool
    switch (present, queued) {
    case (.alreadyPresent, .queued): ok = true
    default: ok = false
    }
    print(ok ? "✓ DigestResponse 两种形状都认" : "✗ DigestResponse 分支认错了")
    if !ok { failed += 1 }
} catch {
    print("✗ DigestResponse → \(error)")
    failed += 1
}

print(failed == 0 ? "\n全部通过" : "\n失败 \(failed) 项")
exit(failed == 0 ? 0 : 1)
