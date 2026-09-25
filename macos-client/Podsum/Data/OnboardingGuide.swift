import Foundation
import Observation

/// 设置窗口的几页。放在这里是因为引导要能把窗口切到「接口」那一页。
enum SettingsTab: Hashable {
    case general, providers, service, quickAdd
}

/// 引导能指向的输入行。同一个钥匙串字段在界面上可能出现在好几处
/// （DashScope key 在摘要、转写、音频摘要三段里各有一个框），按出现的位置分开。
enum OnboardingTarget: Hashable {
    case llmProvider, llmBaseURL, llmModel, llmKey, llmTest
    case asrProvider, asrVolcAK, asrVolcSK, asrAppID, asrToken, asrOpenAIKey, asrDeepgramKey, asrDashscopeKey
    case ttsToggle, ttsProvider, ttsVolcAK, ttsVolcSK, ttsAppID, ttsToken, ttsDashscopeKey
    case apply
}

/// 首次打开时的 API 填写引导：浮在「设置 › 接口」真实表单上的聚光灯 + 气泡。
///
/// 这里只管状态：进行到第几步、设置窗口在哪一页、各输入行在窗口里的位置、
/// 测试连接的结果。步骤内容由 `OnboardingScript` 按当前所选供应商现算，
/// 画法在 `OnboardingOverlay`。
@MainActor
@Observable
final class OnboardingGuide {
    enum LLMTest: Equatable {
        case untested, testing, passed
        case failed(String)
    }

    private(set) var isActive = false
    private(set) var index = 0
    /// 设置窗口当前显示的页；引导开始时切到「接口」
    var settingsTab: SettingsTab = .general
    /// 「测试连接」的结果——引导的第五步以它为完成条件
    var llmTest: LLMTest = .untested
    /// 各输入行在**窗口坐标**里的框，由 `onboardingTarget(_:)` 上报
    var targetFrames: [OnboardingTarget: CGRect] = [:]

    private let defaults = UserDefaults.standard
    private static let offeredKey = "podsum.onboardingOffered"

    /// 还没配置、也从没自动弹过引导——只在这种情况下自动开始一次。
    /// 用户跳过之后不再自己冒出来，想看可以从主窗口或「设置 › 通用」重新开始。
    func shouldAutoStart(isConfigured: Bool) -> Bool {
        !isConfigured && !isActive && !defaults.bool(forKey: Self.offeredKey)
    }

    func start() {
        defaults.set(true, forKey: Self.offeredKey)
        index = 0
        settingsTab = .providers
        isActive = true
    }

    func next(stepCount: Int) {
        if index + 1 < stepCount { index += 1 } else { finish() }
    }

    func back() {
        if index > 0 { index -= 1 }
    }

    func finish() {
        isActive = false
        index = 0
    }

    /// 换了供应商以后步骤数会变，当前序号可能越界
    func clampedIndex(stepCount: Int) -> Int {
        min(index, max(stepCount - 1, 0))
    }
}
