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

print(failed == 0 ? "\n全部通过" : "\n失败 \(failed) 项")
exit(failed == 0 ? 0 : 1)
