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
// 校准依据（本机 macOS 26.5 实测 NSFont.preferredFont 的磅值 / 行高）：
//   largeTitle 26/32   title1 22/26   title2 17/22   title3 15/20
//   headline 13/16     body 13/16     callout 12/15  caption 10/13
// Apple HIG：macOS 默认正文 13pt、最小 10pt，且长段落应使用宽松行距。
//
// 所以不直接用 .callout(12) / .caption(10) 承载正文——它们在默认值以下。
// 阅读正文取 15pt，与系统 title3 的度量一致（15/20），是有依据的阅读尺寸。

public enum Typo {
    public static let pageTitle    = Font.system(size: 30, weight: .semibold)
    public static let hook         = Font.system(size: 20, weight: .medium)
    public static let cardTitle    = Font.system(size: 16, weight: .semibold)
    public static let sectionLabel = Font.system(size: 12, weight: .semibold)

    /// 正文阅读尺寸——要点、引用、论述都用它
    public static let body      = Font.system(size: 15)
    public static let secondary = Font.system(size: 13)
    public static let meta      = Font.system(size: 12)

    /// 脚注级：溯源、Prompt 版本这类元信息
    public static let micro     = Font.system(size: 11)

    public static let mono      = Font.system(size: 12, design: .monospaced)
    public static let monoSmall = Font.system(size: 11, design: .monospaced)

    public static let score      = Font.system(size: 44, weight: .semibold, design: .rounded)
    public static let scoreSmall = Font.system(size: 17, weight: .semibold, design: .rounded)
    public static let band       = Font.system(size: 12, weight: .medium)
    public static let bandSmall  = Font.system(size: 10, weight: .medium)
}

public extension View {
    /// 阅读型段落的行距：15pt 正文默认行高约 18pt，+3 得 21pt，
    /// 接近系统 title3 的 15/20 并略宽松，符合 HIG 对长段落的建议。
    func readable() -> some View { self.lineSpacing(3) }
}

// MARK: - 间距标度
//
// 统一的节奏比零散的魔数更容易对齐。HIG：对齐让内容易于扫读，
// 留白与容器形状用来表达分组。

public enum Space {
    public static let xs: CGFloat = 4
    public static let s:  CGFloat = 8
    public static let m:  CGFloat = 12
    public static let l:  CGFloat = 16
    public static let xl: CGFloat = 20
    public static let xxl: CGFloat = 28

    /// 卡片内边距
    public static let card: CGFloat = 18
    /// 区块之间
    public static let section: CGFloat = 30
}

public enum Radius {
    public static let pill: CGFloat = 999
    public static let small: CGFloat = 10
    public static let medium: CGFloat = 14
    public static let large: CGFloat = 16
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
