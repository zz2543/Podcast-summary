import AppKit
import SwiftUI
import Observation

/// 带着用户去厂商网站拿 key：系统浏览器打开页面，Podsum 在屏幕右侧放一块置顶面板，
/// 一步一步写清楚"看见什么、点哪个、选什么"。
///
/// 系统浏览器里的页面 Podsum 碰不到，所以网页上没有高亮——面板上的每一步要写到能照着点。
/// 点击路径按 2026-09 登录后的真实页面 / 官方文档核对过（见 specs/006-onboarding-guide/plan.md）。
struct WebWalkthrough: Identifiable {
    enum ID: String {
        case deepseek, bailian, volcKeys, volcApp, volcTTS
    }

    struct Step: Identifiable {
        let id: String
        /// 这一步要做的事，一句话
        let title: String
        /// 页面上会看到什么、怎么选、有什么坑
        var details: [String] = []
        /// 「打开这一页」
        var url: URL?
        /// 这一步会复制出一个值，面板据此监听剪贴板
        var capture: Capture?
    }

    /// 从剪贴板认出来、要写进设置的那个值
    struct Capture {
        let field: CaptureField
        let matches: (String) -> Bool
    }

    let id: ID
    let vendor: String
    let symbol: String
    let steps: [Step]
}

/// 能被「复制即填入」写进去的字段
enum CaptureField {
    case llmAPIKey, dashscopeAPIKey, volcAccessKeyID, volcSecretKey, doubaoASRAppID, doubaoASRToken,
         doubaoTTSAppID, doubaoTTSToken

    var label: String {
        switch self {
        case .llmAPIKey:        return "LLM API Key"
        case .dashscopeAPIKey:  return "DashScope API Key"
        case .volcAccessKeyID:  return tr("火山 Access Key ID", "Volcengine Access Key ID")
        case .volcSecretKey:    return tr("火山 Secret Access Key", "Volcengine Secret Access Key")
        case .doubaoASRAppID:   return tr("豆包 ASR App ID", "Doubao ASR App ID")
        case .doubaoASRToken:   return tr("豆包 ASR Access Token", "Doubao ASR Access Token")
        case .doubaoTTSAppID:   return tr("豆包 TTS App ID", "Doubao TTS App ID")
        case .doubaoTTSToken:   return tr("豆包 TTS Access Token", "Doubao TTS Access Token")
        }
    }

    @MainActor func value(in s: AppSettings) -> String {
        switch self {
        case .llmAPIKey:        return s.llmAPIKey
        case .dashscopeAPIKey:  return s.dashscopeAPIKey
        case .volcAccessKeyID:  return s.volcAccessKeyID
        case .volcSecretKey:    return s.volcSecretKey
        case .doubaoASRAppID:   return s.doubaoASRAppID
        case .doubaoASRToken:   return s.doubaoASRToken
        case .doubaoTTSAppID:   return s.doubaoTTSAppID
        case .doubaoTTSToken:   return s.doubaoTTSToken
        }
    }

    @MainActor func write(_ value: String, to s: AppSettings) {
        switch self {
        case .llmAPIKey:        s.llmAPIKey = value
        case .dashscopeAPIKey:  s.dashscopeAPIKey = value
        case .volcAccessKeyID:  s.volcAccessKeyID = value
        case .volcSecretKey:    s.volcSecretKey = value
        case .doubaoASRAppID:   s.doubaoASRAppID = value
        case .doubaoASRToken:   s.doubaoASRToken = value
        case .doubaoTTSAppID:   s.doubaoTTSAppID = value
        case .doubaoTTSToken:   s.doubaoTTSToken = value
        }
    }
}

// MARK: - 各家的步骤

extension WebWalkthrough {
    static func make(_ id: ID) -> WebWalkthrough {
        switch id {
        case .deepseek: return deepseek
        case .bailian:  return bailian
        case .volcKeys: return volcKeys
        case .volcApp:  return volcApp
        case .volcTTS:  return volcTTS
        }
    }

    /// `sk-` 开头、后面一长串字母数字（DeepSeek、百炼都是这个形状）
    private static func looksLikeSK(_ s: String) -> Bool {
        s.range(of: #"^sk-[A-Za-z0-9_\-]{16,}$"#, options: .regularExpression) != nil
    }

    private static var deepseek: WebWalkthrough {
        WebWalkthrough(id: .deepseek, vendor: "DeepSeek", symbol: "text.bubble", steps: [
            Step(id: "login",
                 title: tr("登录 DeepSeek 开放平台", "Sign in to the DeepSeek Platform"),
                 details: [
                    tr("没有账号就在登录页选「注册」，用手机号或邮箱注册。", "No account? Choose “Sign up” and register with a phone number or email."),
                 ],
                 url: URL(string: "https://platform.deepseek.com/")),
            Step(id: "topup",
                 title: tr("先充一点余额", "Top up a small balance"),
                 details: [
                    tr("左侧菜单点「充值」（浏览器窗口窄时，菜单收在左上角的 ≡ 里）。充个几块钱就够试很多集；没有余额时调用会报「余额不足」。",
                       "Click “Top up” in the left menu (in a narrow window the menu hides behind ≡ at the top left). A few yuan covers many episodes; without a balance, calls fail with “insufficient balance”."),
                    tr("已经有余额可以直接下一步。", "Already have a balance? Skip ahead."),
                 ],
                 url: URL(string: "https://platform.deepseek.com/top_up")),
            Step(id: "create",
                 title: tr("创建 API key", "Create an API key"),
                 details: [
                    tr("左侧菜单点「API keys」，再点列表上方的「创建 API key」。", "Click “API keys” in the left menu, then “Create API key” above the list."),
                    tr("弹窗里「输入 API key 的名称」随便填，比如 GotIt，然后点「创建」。", "In the dialog, enter any name (e.g. GotIt) and click “Create”."),
                 ],
                 url: URL(string: "https://platform.deepseek.com/api_keys")),
            Step(id: "copy",
                 title: tr("点「复制」，懂听会自动认出来", "Click “Copy” — GotIt picks it up"),
                 details: [
                    tr("创建后弹窗里显示完整的 key，点它旁边的「复制」。**只显示这一次**，列表里之后只剩打码的样子。",
                       "After creating, the dialog shows the full key — click “Copy” next to it. It’s shown **only once**; the list only keeps a masked version."),
                 ],
                 capture: Capture(field: .llmAPIKey, matches: looksLikeSK)),
        ])
    }

    private static var bailian: WebWalkthrough {
        WebWalkthrough(id: .bailian, vendor: tr("阿里云百炼", "Alibaba Cloud Bailian"), symbol: "cloud", steps: [
            Step(id: "login",
                 title: tr("打开百炼的 API Key 页并登录阿里云", "Open Bailian’s API Key page and sign in"),
                 details: [
                    tr("用阿里云账号登录；没有的话先注册并完成实名认证。", "Sign in with an Alibaba Cloud account; if you don’t have one, register and verify your identity."),
                    tr("第一次使用会提示开通百炼服务，按提示开通即可，新账号一般有免费额度。",
                       "First time here you’ll be asked to activate Bailian — follow the prompt; new accounts usually get a free quota."),
                 ],
                 url: URL(string: "https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key")),
            Step(id: "region",
                 title: tr("确认地域是「华北2（北京）」", "Make sure the region is China (Beijing)"),
                 details: [
                    tr("看页面顶部的地域，要显示 **华北2（北京）**；不是的话点它切过去（从懂听打开的链接默认就是北京）。",
                       "The region at the top must read **China (Beijing)**; switch it if not (the link from GotIt opens Beijing by default)."),
                    tr("百炼各地域的 key 不能混用，懂听连的是北京的接口，别的地域的 key 用不了。",
                       "Bailian keys don’t work across regions, and GotIt calls the Beijing endpoint."),
                 ]),
            Step(id: "create",
                 title: tr("创建 API Key", "Create an API Key"),
                 details: [
                    tr("点「创建API-KEY」。", "Click “创建API-KEY” (Create API Key)."),
                    tr("弹窗里「归属业务空间」保持「默认业务空间」，「描述」可以写 GotIt，「权限」选「全部」，点「确定」。",
                       "In the dialog keep the default workspace, optionally describe it as GotIt, set permissions to “All”, and click “OK”."),
                 ]),
            Step(id: "copy",
                 title: tr("复制新 key，懂听会自动认出来", "Copy the new key — GotIt picks it up"),
                 details: [
                    tr("创建后会弹出完整的 key，点「复制」（或下载保存）。**它只显示这一次**，之后列表里只剩 `sk-a1****9z` 这样的打码。",
                       "After creating, the full key appears — click “Copy” (or download it). **It’s shown only once**; the list later shows only a masked form."),
                 ],
                 capture: Capture(field: .dashscopeAPIKey, matches: looksLikeSK)),
        ])
    }

    private static var volcKeys: WebWalkthrough {
        WebWalkthrough(id: .volcKeys, vendor: tr("火山引擎 · 账号密钥", "Volcengine · Account Keys"), symbol: "person.badge.key", steps: [
            Step(id: "login",
                 title: tr("登录火山引擎控制台", "Sign in to the Volcengine console"),
                 details: [
                    tr("没有账号先注册，并按页面提示完成**实名认证**——不认证开不了语音服务。",
                       "No account? Sign up and complete **identity verification** — speech services can’t be enabled without it."),
                 ],
                 url: URL(string: "https://console.volcengine.com/")),
            Step(id: "open",
                 title: tr("打开「API访问密钥」", "Open “API Access Keys”"),
                 details: [
                    tr("点右上角的**头像**，在下拉菜单里点「API访问密钥」。也可以直接点下面的按钮打开。",
                       "Click your **avatar** at the top right and choose “API Access Keys” — or use the button below."),
                 ],
                 url: URL(string: "https://console.volcengine.com/iam/keymanage/")),
            Step(id: "create",
                 title: tr("新建一对 Access Key（不是 API Key）", "Create an Access Key (not an API Key)"),
                 details: [
                    tr("这个页面能建两种密钥：**Access Key** 和 **API Key**。要建的是 **Access Key**，点它那边的「新建密钥」。",
                       "This page offers two kinds: **Access Key** and **API Key**. Create an **Access Key** with its “Create key” button."),
                    tr("可能会要求手机验证码。", "You may be asked for an SMS code."),
                    tr("建好后会同时显示 **Access Key ID** 和 **Secret Access Key**，Secret **只显示这一次**。",
                       "You’ll see both the **Access Key ID** and the **Secret Access Key** — the secret is shown **only once**."),
                 ]),
            Step(id: "copyAK",
                 title: tr("先复制 Access Key ID", "Copy the Access Key ID first"),
                 details: [
                    tr("点 Access Key ID 旁边的复制按钮。", "Click the copy button next to the Access Key ID."),
                 ],
                 capture: Capture(field: .volcAccessKeyID) { s in
                     s.range(of: #"^[A-Za-z0-9]{16,64}$"#, options: .regularExpression) != nil
                 }),
            Step(id: "copySK",
                 title: tr("再复制 Secret Access Key", "Then copy the Secret Access Key"),
                 details: [
                    tr("点 Secret Access Key 旁边的复制按钮。", "Click the copy button next to the Secret Access Key."),
                    tr("如果窗口已经关了、Secret 看不到了：删掉这对密钥，回上一步重新新建。",
                       "If the dialog is gone and the secret is hidden: delete that pair and create a new one."),
                 ],
                 capture: Capture(field: .volcSecretKey) { s in
                     s.range(of: #"^[A-Za-z0-9+/=]{24,128}$"#, options: .regularExpression) != nil
                 }),
        ])
    }

    private static var volcApp: WebWalkthrough {
        WebWalkthrough(id: .volcApp, vendor: tr("火山引擎 · 豆包语音应用", "Volcengine · Doubao Speech App"), symbol: "app.badge", steps: [
            Step(id: "open",
                 title: tr("打开豆包语音控制台", "Open the Doubao Speech console"),
                 details: [
                    tr("用同一个火山引擎账号登录。", "Sign in with the same Volcengine account."),
                 ],
                 url: URL(string: "https://console.volcengine.com/speech/app")),
            Step(id: "legacy",
                 title: tr("切换到「旧版」控制台", "Switch to the old console"),
                 details: [
                    tr("新账号默认进**新版控制台**（左侧有「体验中心」「API Key管理」）。它发的是一个 API Key，懂听要的是 **APP ID + Access Token**。",
                       "New accounts land in the **new console** (with “Experience Center” and “API Key Management” on the left). It issues an API Key, but GotIt needs the **APP ID + Access Token**."),
                    tr("点页面**左上角的下拉框**，选「旧版」。已经在旧版（左侧有「应用管理」）就直接下一步。",
                       "Use the **dropdown at the top left** to pick the old console. Already there (with “App Management” on the left)? Move on."),
                 ]),
            Step(id: "create",
                 title: tr("创建应用，勾选录音文件识别", "Create an app with recording-file recognition"),
                 details: [
                    tr("点「创建应用」，名称随便填（比如 GotIt），简介可留空。", "Click “Create App”; any name works (e.g. GotIt), description optional."),
                    tr("在接入能力里勾选 **豆包录音文件识别模型2.0**（认准 2.0，不是 1.0 的「录音文件识别大模型」），它转写网上链接里的音频。",
                       "Under capabilities, tick **豆包录音文件识别模型2.0** (make sure it’s 2.0, not the 1.0 “录音文件识别大模型”) — it transcribes audio from links."),
                    tr("再勾上录音文件识别的**极速版**，它转写你上传的本地文件。",
                       "Also tick the **Turbo (极速版)** recording-file recognition — it transcribes files you upload."),
                    tr("以后想开音频摘要，顺手也勾上**语音合成**。勾过的能力之后不能取消。",
                       "Want audio summaries later? Also tick **Speech Synthesis**. Ticked capabilities can’t be removed."),
                    tr("新建的应用默认是**试用版**，带免费额度，够先跑通。", "New apps start as a **trial** with free quota — enough to get going."),
                 ]),
            Step(id: "copyAppID",
                 title: tr("复制 APP ID", "Copy the APP ID"),
                 details: [
                    tr("在左侧「API服务中心」下点 **豆包录音文件识别模型2.0**，顶部「应用名称」选刚建的应用。",
                       "In the left sidebar under “API服务中心”, click **豆包录音文件识别模型2.0**, then pick your new app in “应用名称” at the top."),
                    tr("「服务接口认证信息」里的 **APP ID**（一串数字），点复制。", "Under “服务接口认证信息”, copy the **APP ID** (digits)."),
                 ],
                 capture: Capture(field: .doubaoASRAppID, matches: looksLikeAppID)),
            Step(id: "copyToken",
                 title: tr("复制 Access Token", "Copy the Access Token"),
                 details: [
                    tr("同一页「服务接口认证信息」里的 **Access Token**，点显示后复制。它不是前面那对 Access Key。",
                       "The **Access Token** under “服务接口认证信息” on the same page — reveal and copy it. It isn’t the Access Key pair from before."),
                    tr("看不到？「应用管理」页不显示它，要先点左侧的 **豆包录音文件识别模型2.0**。",
                       "Don’t see it? The App Management page doesn’t show it — click **豆包录音文件识别模型2.0** in the left sidebar first."),
                 ],
                 capture: Capture(field: .doubaoASRToken, matches: looksLikeAppToken)),
        ])
    }

    /// 豆包应用的 APP ID：一串数字
    private static func looksLikeAppID(_ s: String) -> Bool {
        s.range(of: #"^[0-9]{6,20}$"#, options: .regularExpression) != nil
    }

    /// 豆包应用的 Access Token
    private static func looksLikeAppToken(_ s: String) -> Bool {
        s.range(of: #"^[A-Za-z0-9_\-]{16,64}$"#, options: .regularExpression) != nil
    }

    /// 音频摘要用的豆包应用。APP ID / Access Token 是按应用发的，
    /// 转写那个应用勾了「语音合成」就是同一对值。
    private static var volcTTS: WebWalkthrough {
        WebWalkthrough(id: .volcTTS, vendor: tr("火山引擎 · 豆包语音合成", "Volcengine · Doubao Speech Synthesis"), symbol: "speaker.wave.2", steps: [
            Step(id: "open",
                 title: tr("打开豆包语音控制台", "Open the Doubao Speech console"),
                 details: [
                    tr("用配转写时的同一个火山引擎账号登录。", "Sign in with the same Volcengine account you used for transcription."),
                 ],
                 url: URL(string: "https://console.volcengine.com/speech/app")),
            Step(id: "legacy",
                 title: tr("切换到「旧版」控制台", "Switch to the old console"),
                 details: [
                    tr("点页面**左上角的下拉框**，选「旧版」。已经在旧版（左侧有「应用管理」）就直接下一步。",
                       "Use the **dropdown at the top left** to pick the old console. Already there (with “App Management” on the left)? Move on."),
                 ]),
            Step(id: "enable",
                 title: tr("让应用带上「语音合成」", "Give the app Speech Synthesis"),
                 details: [
                    tr("左侧点「应用管理」，看转写用的那个应用的接入能力里有没有**语音合成**。有就直接下一步。",
                       "Click “应用管理” on the left and check whether your transcription app lists **Speech Synthesis**. If it does, move on."),
                    tr("没有就点那一行的「编辑」勾上**语音合成**并保存；或者「创建应用」新建一个勾选它的。勾过的能力之后不能取消。",
                       "If not, click “Edit” on that row, tick **Speech Synthesis** and save — or “Create App” with it ticked. Ticked capabilities can’t be removed."),
                 ]),
            Step(id: "copyAppID",
                 title: tr("复制 APP ID", "Copy the APP ID"),
                 details: [
                    tr("「应用管理」页看不到凭据：在左侧「API服务中心」下点这个应用开通的任一项服务（比如 **豆包录音文件识别模型2.0**），顶部「应用名称」选这个应用。",
                       "App Management doesn’t show credentials: under “API服务中心” on the left, click any service this app has (e.g. **豆包录音文件识别模型2.0**) and pick the app in “应用名称” at the top."),
                    tr("「服务接口认证信息」里的 **APP ID**（一串数字），点复制。跟转写共用一个应用时，就是转写那个 APP ID。",
                       "Under “服务接口认证信息”, copy the **APP ID** (digits). If the app is shared with transcription, it’s the same APP ID."),
                 ],
                 capture: Capture(field: .doubaoTTSAppID, matches: looksLikeAppID)),
            Step(id: "copyToken",
                 title: tr("复制 Access Token", "Copy the Access Token"),
                 details: [
                    tr("同一页「服务接口认证信息」里的 **Access Token**，点显示后复制。它不是前面那对 Access Key。",
                       "The **Access Token** under “服务接口认证信息” on the same page — reveal and copy it. It isn’t the Access Key pair from before."),
                 ],
                 capture: Capture(field: .doubaoTTSToken, matches: looksLikeAppToken)),
        ])
    }
}

// MARK: - 控制器

/// 悬浮面板的状态与剪贴板监听。
///
/// 剪贴板只在"当前这一步要复制出一个值"时才看，而且先只看 `changeCount`（不触发系统的粘贴授权），
/// 变了才读内容。认出来的值只放在内存里等用户确认，确认后才写进设置（钥匙串）。
@MainActor
@Observable
final class WebGuideController {
    struct Candidate: Equatable {
        let field: CaptureField
        let value: String

        /// 面板上只露头尾，中间打码
        var masked: String {
            value.count <= 10 ? String(repeating: "•", count: value.count)
                : "\(value.prefix(5))…\(value.suffix(4))"
        }

        static func == (a: Candidate, b: Candidate) -> Bool { a.value == b.value }
    }

    private(set) var walkthrough: WebWalkthrough?
    private(set) var index = 0
    private(set) var candidate: Candidate?
    /// 本次面板里已经填进去的字段
    private(set) var filled: Set<String> = []

    private let settings: AppSettings
    private var panel: NSPanel?
    private var timer: Timer?
    private var lastChangeCount = WebGuideController.pasteboard.changeCount

    private static func openInBrowser(_ url: URL) {
        #if DEBUG
        // 验证时不真的把用户的浏览器弹到前面
        if ProcessInfo.processInfo.environment["PODSUM_DEBUG_NO_BROWSER"] != nil { return }
        #endif
        NSWorkspace.shared.open(url)
    }

    /// 验证用：Debug 构建可以用 `PODSUM_DEBUG_PASTEBOARD=<名字>` 换成一块私有的具名剪贴板，
    /// 测试时往那里写假 key，不碰用户真正的剪贴板。
    private static var pasteboard: NSPasteboard {
        #if DEBUG
        if let name = ProcessInfo.processInfo.environment["PODSUM_DEBUG_PASTEBOARD"] {
            return NSPasteboard(name: NSPasteboard.Name(name))
        }
        #endif
        return .general
    }

    init(settings: AppSettings) {
        self.settings = settings
    }

    var isOpen: Bool { walkthrough != nil }
    var step: WebWalkthrough.Step? { walkthrough.map { $0.steps[min(index, $0.steps.count - 1)] } }

    func open(_ id: WebWalkthrough.ID) {
        let w = WebWalkthrough.make(id)
        walkthrough = w
        index = 0
        candidate = nil
        filled = []
        lastChangeCount = Self.pasteboard.changeCount
        showPanel()
        if let url = w.steps.first?.url { Self.openInBrowser(url) }
        startWatching()
    }

    func go(to i: Int) {
        guard let w = walkthrough else { return }
        index = max(0, min(i, w.steps.count - 1))
        candidate = nil
        // 进到新的一步时，之前复制的内容不算
        lastChangeCount = Self.pasteboard.changeCount
    }

    func next() { go(to: index + 1) }
    func back() { go(to: index - 1) }

    func openCurrentPage() {
        if let url = step?.url { Self.openInBrowser(url) }
    }

    func accept() {
        guard let c = candidate else { return }
        c.field.write(c.value, to: settings)
        filled.insert(step?.id ?? "")
        candidate = nil
        if let w = walkthrough, index + 1 < w.steps.count { next() }
    }

    func dismissCandidate() { candidate = nil }

    /// 回到 Podsum 的设置窗口继续
    func returnToApp() {
        close()
        NSApp.activate()
        NSApp.windows.first { $0.isVisible && !AppBrand.allNames.contains($0.title) && $0.canBecomeKey }?.makeKeyAndOrderFront(nil)
    }

    func close() {
        timer?.invalidate()
        timer = nil
        panel?.orderOut(nil)
        panel = nil
        walkthrough = nil
        candidate = nil
    }

    var isFinished: Bool {
        guard let w = walkthrough else { return false }
        let captures = w.steps.filter { $0.capture != nil }
        return !captures.isEmpty && captures.allSatisfy { $0.capture.map { !$0.field.value(in: settings).isBlank } ?? true }
    }

    // MARK: 剪贴板

    private func startWatching() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.poll() }
        }
    }

    private func poll() {
        let pb = Self.pasteboard
        guard pb.changeCount != lastChangeCount else { return }
        lastChangeCount = pb.changeCount
        guard let capture = step?.capture,
              let text = pb.string(forType: .string)?.trimmingCharacters(in: .whitespacesAndNewlines),
              capture.matches(text),
              text != capture.field.value(in: settings)
        else { return }
        candidate = Candidate(field: capture.field, value: text)
    }

    // MARK: 面板

    private func showPanel() {
        if panel == nil {
            let p = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 360, height: 600),
                            styleMask: [.titled, .closable, .nonactivatingPanel, .utilityWindow, .fullSizeContentView],
                            backing: .buffered, defer: false)
            p.title = tr("懂听引导", "GotIt Guide")
            p.titlebarAppearsTransparent = true
            p.isFloatingPanel = true
            p.level = .floating
            // Podsum 退到后台（用户在浏览器里操作）时面板也要留着
            p.hidesOnDeactivate = false
            p.becomesKeyOnlyIfNeeded = true
            p.isReleasedWhenClosed = false
            p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
            p.contentView = NSHostingView(rootView: WebGuidePanel(controller: self, settings: settings))
            NotificationCenter.default.addObserver(forName: NSWindow.willCloseNotification, object: p, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated {
                    self?.timer?.invalidate()
                    self?.walkthrough = nil
                    self?.panel = nil
                }
            }
            panel = p
        }
        // 贴在当前屏幕的右侧，给浏览器留出左边的地方
        if let screen = NSScreen.main ?? NSScreen.screens.first, let p = panel {
            let area = screen.visibleFrame
            let height = min(640, area.height - 40)
            p.setFrame(NSRect(x: area.maxX - 360 - 16, y: area.maxY - height - 16, width: 360, height: height), display: true)
        }
        panel?.orderFrontRegardless()
    }
}
