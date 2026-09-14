import SwiftUI

// 可缩放的排版层。
//
// macOS 不支持 Dynamic Type（HIG 明说），所以读者自己调字号这件事必须 app 自己做——
// Safari、邮件、图书的 ⌘+ / ⌘- 都是各自实现的。这里同样：
// 角色只声明基准磅值，实际字号 = 基准 × 环境里的 textScale。
//
// 基准值的依据见 Theme.swift 顶部：本机 NSFont 实测度量 + Apple HIG 的
// macOS 默认 13pt / 最小 10pt。正文基准 17pt 是在默认值之上的阅读尺寸，
// 缩到最小档（×0.85 ≈ 14.5pt）仍高于 13pt 默认值，不会掉进难读的区间。

public enum TypeRole {
    case pageTitle, hook, cardTitle, sectionLabel
    case body, secondary, meta, micro
    case mono, monoSmall
    case score, scoreSmall, band, bandSmall

    var size: CGFloat {
        switch self {
        case .pageTitle:    return 32
        case .hook:         return 22
        case .cardTitle:    return 17
        case .sectionLabel: return 13
        case .body:         return 17
        case .secondary:    return 15
        case .meta:         return 13
        case .micro:        return 12
        case .mono:         return 13
        case .monoSmall:    return 12
        case .score:        return 46
        case .scoreSmall:   return 18
        case .band:         return 13
        case .bandSmall:    return 11
        }
    }

    var weight: Font.Weight {
        switch self {
        case .pageTitle, .cardTitle, .score, .scoreSmall: return .semibold
        case .hook, .sectionLabel, .band, .bandSmall:     return .medium
        default:                                          return .regular
        }
    }

    var design: Font.Design {
        switch self {
        case .score, .scoreSmall: return .rounded
        case .mono, .monoSmall:   return .monospaced
        default:                  return .default
        }
    }

    public func font(scale: Double, weight override: Font.Weight? = nil) -> Font {
        .system(size: size * scale, weight: override ?? weight, design: design)
    }
}

// MARK: - 缩放档位

public enum TextScale {
    /// 离散档位而非连续缩放——和 Safari 一样，每一档都是调过的，不会落在怪尺寸上。
    public static let steps: [Double] = [0.85, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0]
    public static let standard: Double = 1.0

    public static func larger(than current: Double) -> Double {
        steps.first { $0 > current + 0.001 } ?? steps.last!
    }

    public static func smaller(than current: Double) -> Double {
        steps.last { $0 < current - 0.001 } ?? steps.first!
    }

    public static func canGrow(_ v: Double) -> Bool { v < steps.last! - 0.001 }
    public static func canShrink(_ v: Double) -> Bool { v > steps.first! + 0.001 }

    /// 菜单与状态里显示的百分比
    public static func label(_ v: Double) -> String { "\(Int((v * 100).rounded()))%" }
}

// MARK: - 环境注入

private struct TextScaleKey: EnvironmentKey {
    static let defaultValue: Double = 1.0
}

public extension EnvironmentValues {
    var textScale: Double {
        get { self[TextScaleKey.self] }
        set { self[TextScaleKey.self] = newValue }
    }
}

private struct PodsumFont: ViewModifier {
    @Environment(\.textScale) private var scale
    let role: TypeRole
    let weightOverride: Font.Weight?

    func body(content: Content) -> some View {
        content.font(role.font(scale: scale, weight: weightOverride))
    }
}

public extension View {
    /// 按角色取字体，自动应用当前缩放档位。
    func podsumFont(_ role: TypeRole, weight: Font.Weight? = nil) -> some View {
        modifier(PodsumFont(role: role, weightOverride: weight))
    }
}
