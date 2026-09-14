import SwiftUI

// 对齐 frontend-v2/tailwind.config.ts 的色板。
// 状态色直接用系统色——它们本就是 Apple 系统色，且自带深色模式适配。

public enum Tone {
    public static let bg          = Color(light: 0xFBFBFD, dark: 0x1C1C1E)
    public static let surface     = Color(light: 0xFFFFFF, dark: 0x2C2C2E)
    public static let surfaceElev = Color(light: 0xF5F5F7, dark: 0x3A3A3C)
    public static let border      = Color(light: 0xD2D2D7, dark: 0x48484A)
    public static let text        = Color.primary
    public static let textMuted   = Color.secondary
    public static let textSubtle  = Color(light: 0x86868B, dark: 0x8E8E93)

    public static let ok   = Color.green
    public static let warn = Color.orange
    public static let err  = Color.red
    public static let info = Color.blue
}

extension Color {
    /// 浅/深两套十六进制，随外观自动切换
    init(light: UInt32, dark: UInt32) {
        self.init(nsColor: NSColor(name: nil) { appearance in
            let hex = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? dark : light
            return NSColor(
                srgbRed: Double((hex >> 16) & 0xFF) / 255,
                green:   Double((hex >> 8) & 0xFF) / 255,
                blue:    Double(hex & 0xFF) / 255,
                alpha: 1
            )
        })
    }
}

// MARK: - 排版标度
//
// 不用 .callout / .caption 这类语义字体：macOS 上它们分别只有 12pt 和 10pt，
// 是为密集控件设计的，用在阅读型内容上偏小。这里给出显式尺寸。

public enum Typo {
    public static let pageTitle    = Font.system(size: 30, weight: .semibold)
    public static let hook         = Font.system(size: 20, weight: .medium)
    public static let cardTitle    = Font.system(size: 16, weight: .semibold)
    public static let sectionLabel = Font.system(size: 12, weight: .semibold)

    /// 正文阅读尺寸——要点、引用、论述都用它
    public static let body      = Font.system(size: 15)
    public static let secondary = Font.system(size: 13)
    public static let meta      = Font.system(size: 12)

    public static let mono      = Font.system(size: 12, design: .monospaced)
    public static let monoSmall = Font.system(size: 11, design: .monospaced)

    public static let score      = Font.system(size: 34, weight: .semibold, design: .rounded)
    public static let scoreSmall = Font.system(size: 17, weight: .semibold, design: .rounded)
    public static let band       = Font.system(size: 12, weight: .medium)
    public static let bandSmall  = Font.system(size: 10, weight: .medium)
}

public extension View {
    /// 阅读型段落的行距
    func readable() -> some View { self.lineSpacing(3.5) }
}

// MARK: - 格式化

public enum Fmt {
    /// 5790 → "1:36:30"，524 → "8:44"，nil → "—"
    public static func duration(_ seconds: Int?) -> String {
        guard let s = seconds, s > 0 else { return "—" }
        let (h, m, sec) = (s / 3600, (s % 3600) / 60, s % 60)
        return h > 0
            ? String(format: "%d:%02d:%02d", h, m, sec)
            : String(format: "%d:%02d", m, sec)
    }

    /// 930000 → "15:30"，5790000 → "1:36:30"
    public static func timestamp(_ ms: Int) -> String {
        duration(ms / 1000)
    }

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.unitsStyle = .short
        f.locale = Locale(identifier: "zh_CN")
        return f
    }()

    public static func relative(_ date: Date) -> String {
        relativeFormatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - 模型便利访问
//
// Fallback<T> 的未知值在 UI 里必须如实显示，不能悄悄当成某个已知值。

public extension EpisodeSummary {
    var displayTitle: String { title?.isEmpty == false ? title! : "未命名剧集" }
}

public extension Fallback where T == EpisodeStatus {
    var label: String {
        switch self {
        case .known(let s):
            switch s {
            case .pending:    return "排队中"
            case .processing: return "处理中"
            case .done:       return "已完成"
            case .partial:    return "部分完成"
            case .failed:     return "失败"
            }
        case .unknown(let raw):
            return raw   // 后端新增的取值：如实显示，不猜
        }
    }

    var tint: Color {
        switch value {
        case .done:                  return Tone.ok
        case .processing, .partial:  return Tone.warn
        case .failed:                return Tone.err
        case .pending:               return Tone.textSubtle
        case nil:                    return Tone.textSubtle
        }
    }

    var isAnimating: Bool { value == .processing }
}

public extension Fallback where T == UsefulnessBand {
    var label: String {
        switch self {
        case .known(let b):
            switch b {
            case .mustListen:     return "必听"
            case .worthListening: return "值得听"
            case .skimmable:      return "可跳读"
            case .skippable:      return "可跳过"
            }
        case .unknown(let raw):
            return raw
        }
    }

    var tint: Color {
        switch value {
        case .mustListen:     return Tone.ok
        case .worthListening: return Tone.info
        case .skimmable:      return Tone.warn
        case .skippable:      return Tone.textSubtle
        case nil:             return Tone.textSubtle
        }
    }
}
