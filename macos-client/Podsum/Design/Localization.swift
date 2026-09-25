import AppKit
import Observation

// MARK: - 界面语言
//
// 只管界面上的字。转写语言、摘要语言跟着剧集走，与这里无关——
// 这里切成英文，一集中文播客照样出中文文稿与摘要。
//
// 做法是把两种写法并排放在调用处：`tr("中文", "English")`。
// 只有两种语言，放在一起改一处就不会漏另一处；而且读的是 @Observable 的属性，
// 任何视图的 body 里调过 `tr` 就会被 Observation 记上，切换后当场重绘，不必重启。
//
// 系统菜单（文件、编辑、窗口、退出…）不归 app 画，由 AppKit 按 AppleLanguages 选，
// 进程起来后就定了（实测：切换后 app 自己的菜单项当场变，系统项纹丝不动）。
// 所以每次选定都把 AppleLanguages 写进本 app 的域，下次启动时跟上；
// 设置页据 `needsRelaunch` 提供「立即重启」。

public enum InterfaceLanguage: String, CaseIterable, Identifiable, Sendable {
    case system
    case chinese = "zh-Hans"
    case english = "en"

    public var id: String { rawValue }

    /// 两个具体语言各用各自的文字写——切错了也认得出怎么切回来。
    public var label: String {
        switch self {
        case .system:  return tr("跟随系统", "Match System")
        case .chinese: return "简体中文"
        case .english: return "English"
        }
    }
}

@Observable
public final class Localizer {
    public static let shared = Localizer()

    public var preference: InterfaceLanguage {
        didSet {
            UserDefaults.standard.set(preference.rawValue, forKey: Self.storageKey)
            pinAppKitLanguage()
        }
    }

    public var isChinese: Bool {
        switch preference {
        case .chinese: return true
        case .english: return false
        case .system:  return Self.systemPrefersChinese
        }
    }

    /// 日期、相对时间这类格式化用的 locale，与界面语言一致。
    public var locale: Locale { Locale(identifier: isChinese ? "zh_CN" : "en_US") }

    private static let storageKey = "podsum.interfaceLanguage"

    /// AppKit 这次启动实际用的语言。系统菜单按它画，进程内改不了。
    private static let appKitIsChinese =
        Bundle.main.preferredLocalizations.first?.hasPrefix("zh") ?? false

    /// 界面已经换了语言，系统菜单还是旧的——要重启 app 才一致。
    public var needsRelaunch: Bool { isChinese != Self.appKitIsChinese }

    private init() {
        let stored = UserDefaults.standard.string(forKey: Self.storageKey) ?? ""
        preference = InterfaceLanguage(rawValue: stored) ?? .system
        pinAppKitLanguage()
    }

    /// 电脑的首选语言是中文（简繁都算）才用中文，其余一律英文。
    ///
    /// 读的是全局域，不是 `Locale.preferredLanguages`：后者会被本 app 域里
    /// 我们自己写的 AppleLanguages 盖掉，选过一次「English」之后
    /// 就再也看不到电脑本来的语言了。
    public static let systemPrefersChinese: Bool = {
        let global = CFPreferencesCopyValue(
            "AppleLanguages" as CFString,
            kCFPreferencesAnyApplication,
            kCFPreferencesCurrentUser,
            kCFPreferencesAnyHost
        ) as? [String]
        let first = (global ?? Locale.preferredLanguages).first ?? ""
        return first.lowercased().hasPrefix("zh")
    }()

    /// 让系统菜单与界面同一种语言（下次启动生效）。
    private func pinAppKitLanguage() {
        UserDefaults.standard.set([isChinese ? "zh-Hans" : "en"], forKey: "AppleLanguages")
    }
}

/// 按当前界面语言二选一。
public func tr(_ zh: String, _ en: String) -> String {
    Localizer.shared.isChinese ? zh : en
}

// MARK: - 重启

public enum Relauncher {
    /// 退出后由一个脱离的 shell 等本进程真正结束再重新打开，
    /// 否则 `open` 会直接把还没退完的旧实例带到前台。
    /// 退出走正常的 terminate，后端子进程照常由 AppDelegate 收掉。
    @MainActor
    public static func relaunch() {
        let pid = ProcessInfo.processInfo.processIdentifier
        let task = Process()
        task.executableURL = URL(filePath: "/bin/sh")
        task.arguments = ["-c", "while kill -0 \(pid) 2>/dev/null; do sleep 0.2; done; /usr/bin/open \"$0\"",
                          Bundle.main.bundlePath]
        try? task.run()
        NSApplication.shared.terminate(nil)
    }
}
