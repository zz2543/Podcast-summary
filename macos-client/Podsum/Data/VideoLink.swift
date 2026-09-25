import Foundation

/// 快捷提交只收「单个视频」：B 站与 YouTube。
///
/// 提交面板对陌生链接一律当音频直链放行（`Submission.guessSourceType`），
/// 这里刻意更严——快捷键是盲按的，按在新闻页上就该被拒，
/// 而不是让后端把一张网页当音频去下载。
///
/// 通过的链接还会被规整成一种写法。同一个视频在地址栏里是
/// `…/video/BV1xx/?spm_id_from=…`，分享出来是 `…/video/BV1xx?vd_source=…`，
/// 后端按原样比对重复，写法不一就认不出是同一集。
public enum VideoLink {
    /// 从一段文字（纯链接或分享文案）里找出第一个可接受的视频链接，规整后返回。
    public static func recognize(_ text: String) -> String? {
        // 与后端 `_URL_PATTERN` 同一套排除：CJK 标点与全角符号会紧贴着链接出现。
        // 这里用 Swift 字面量把字符直接放进字符类——NSRegularExpression 不认 `\\u{…}` 写法。
        let pattern = "https?://[^\\s<>\"'\u{3000}-\u{303f}\u{ff00}-\u{ffef}]+"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return nil }
        let range = NSRange(text.startIndex..., in: text)
        let trailing = CharacterSet(charactersIn: ".,;:!?)]}\"'")
        for match in regex.matches(in: text, range: range) {
            guard let r = Range(match.range, in: text) else { continue }
            let candidate = String(text[r]).trimmingCharacters(in: trailing)
            if let url = canonical(candidate) { return url }
        }
        return nil
    }

    static func canonical(_ raw: String) -> String? {
        guard let components = URLComponents(string: raw),
              let host = components.host?.lowercased() else { return nil }
        let path = components.path
        let query = Dictionary(
            (components.queryItems ?? []).map { ($0.name, $0.value ?? "") },
            uniquingKeysWith: { first, _ in first }
        )
        let segments = path.split(separator: "/").map(String.init)

        if host == "youtu.be" {
            guard let id = segments.first, isYouTubeID(id) else { return nil }
            return youTube(id)
        }
        if matches(host, "youtube.com") {
            if segments.first == "watch", let id = query["v"], isYouTubeID(id) { return youTube(id) }
            if segments.count >= 2, ["shorts", "live", "embed"].contains(segments[0]), isYouTubeID(segments[1]) {
                return youTube(segments[1])
            }
            return nil   // 频道、播放列表、搜索页
        }

        if host == "b23.tv" {
            // 短链只能交给后端去展开，这里判断不了指向什么
            guard let code = segments.first, !code.isEmpty else { return nil }
            return "https://b23.tv/\(code)"
        }
        if matches(host, "bilibili.com") {
            if segments.count >= 2, segments[0] == "video", isBilibiliID(segments[1]) {
                return bilibili(segments[1], page: query["p"])
            }
            // 番剧：ep / ss 各自就是一集或一季的入口
            if segments.count >= 3, segments[0] == "bangumi", segments[1] == "play",
               segments[2].hasPrefix("ep") || segments[2].hasPrefix("ss") {
                return "https://www.bilibili.com/bangumi/play/\(segments[2])"
            }
            // 稍后再看、收藏夹、合集等播放页：地址里带着正在播的那一个
            if let bvid = query["bvid"], isBilibiliID(bvid) {
                return bilibili(bvid, page: query["p"])
            }
            return nil   // 首页、空间、搜索页
        }
        return nil
    }

    private static func matches(_ host: String, _ domain: String) -> Bool {
        host == domain || host.hasSuffix("." + domain)
    }

    private static func youTube(_ id: String) -> String {
        "https://www.youtube.com/watch?v=\(id)"
    }

    /// 分 P 视频保留页码；第 1 P 与不带页码是同一个，统一成不带。
    private static func bilibili(_ id: String, page: String?) -> String {
        let base = "https://www.bilibili.com/video/\(id)"
        guard let page, let n = Int(page), n > 1 else { return base }
        return base + "?p=\(n)"
    }

    private static func isYouTubeID(_ s: String) -> Bool {
        s.count == 11 && s.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-" || $0 == "_") }
    }

    private static func isBilibiliID(_ s: String) -> Bool {
        let lower = s.lowercased()
        if lower.hasPrefix("bv") { return s.count == 12 && s.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber) } }
        if lower.hasPrefix("av") { return s.count > 2 && s.dropFirst(2).allSatisfy(\.isNumber) }
        return false
    }
}
