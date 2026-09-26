import SwiftUI

/// 设置面板（⌘,）。
///
/// **这个 app 不内置任何凭据。** 所有字段默认为空，填好之前后端起不来，
/// 界面会明说缺哪几项。密钥写钥匙串，不落明文。
struct SettingsView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(OnboardingGuide.self) private var guide

    var body: some View {
        @Bindable var guide = guide

        TabView(selection: $guide.settingsTab) {
            GeneralSettings()
                .tabItem { Label(tr("通用", "General"), systemImage: "gearshape") }
                .tag(SettingsTab.general)
            ProviderSettings()
                .tabItem { Label(tr("接口", "Providers"), systemImage: "key") }
                .tag(SettingsTab.providers)
            BackendSettings()
                .tabItem { Label(tr("服务", "Service"), systemImage: "server.rack") }
                .tag(SettingsTab.service)
            QuickAddSettings()
                .tabItem { Label(tr("快捷提交", "Quick Add"), systemImage: "bolt") }
                .tag(SettingsTab.quickAdd)
        }
        .safeAreaInset(edge: .top, spacing: 0) {
            if guide.isActive && guide.settingsTab != .providers {
                OnboardingReturnBanner()
            }
        }
        // 引导时加高一些：气泡要放在输入框旁边，又不能把下一格全挡住
        .frame(width: guide.isActive ? 620 : 580, height: guide.isActive ? 700 : 520)
    }
}

// MARK: - 通用

struct GeneralSettings: View {
    @State private var localizer = Localizer.shared
    @State private var updates = AppUpdateChecker()
    @Environment(OnboardingGuide.self) private var guide

    var body: some View {
        Form {
            Section {
                Picker(tr("界面语言", "Interface Language"), selection: $localizer.preference) {
                    ForEach(InterfaceLanguage.allCases) { Text($0.label).tag($0) }
                }
                if localizer.needsRelaunch {
                    HStack {
                        Label(tr("菜单栏的系统项（文件、编辑、窗口…）要重启懂听才会换语言。",
                                 "System menus (File, Edit, Window…) switch language after GotIt restarts."),
                              systemImage: "arrow.clockwise.circle")
                            .foregroundStyle(Tone.warn)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer()
                        Button(tr("立即重启", "Restart Now")) { Relauncher.relaunch() }
                    }
                }
            } footer: {
                Text(tr("只改界面上的文字。转写与摘要的语言跟着剧集本身走，不受这里影响。",
                        "Changes only the app’s interface. Transcripts and summaries stay in each episode’s own language."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section(tr("关于", "About")) {
                LabeledContent(tr("版本", "Version"),
                               value: "\(AppUpdateChecker.currentVersion) (build \(AppUpdateChecker.buildNumber))")
                HStack {
                    Button(updates.state == .checking ? tr("检查中…", "Checking…") : tr("检查新版本", "Check for Updates")) {
                        Task { await updates.check() }
                    }
                    .disabled(updates.state == .checking)
                    AppUpdateStatus(state: updates.state)
                }
            }

            Section {
                Button(tr("重新开始新手引导", "Restart Setup Guide")) { guide.start() }
            } footer: {
                Text(tr("在「接口」页上一格一格带你把 API 填好。", "Walks you through the Providers page one field at a time."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }
        }
        .formStyle(.grouped)
    }
}

private struct AppUpdateStatus: View {
    let state: AppUpdateChecker.State

    var body: some View {
        switch state {
        case .idle, .checking:
            EmptyView()
        case .upToDate:
            Label(tr("已是最新版本", "You’re up to date"), systemImage: "checkmark.circle")
                .foregroundStyle(Tone.ok)
        case .available(let version, let page):
            HStack {
                Label(tr("有新版本 \(version)", "Version \(version) is available"), systemImage: "arrow.down.circle")
                    .foregroundStyle(Tone.warn)
                Button(tr("前往下载", "Download")) { NSWorkspace.shared.open(page) }
            }
        case .noReleases:
            Text(tr("还没有发布过正式版本", "No releases have been published yet"))
                .foregroundStyle(Tone.textSubtle)
        case .failed(let message):
            Label(message, systemImage: "exclamationmark.triangle")
                .foregroundStyle(Tone.err)
                .lineLimit(2)
        }
    }
}

// MARK: - 接口

struct ProviderSettings: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(OnboardingGuide.self) private var guide

    @State private var testResult: String?
    @State private var testPassed = false
    @State private var testing = false
    @State private var asrTestResult: String?
    @State private var asrTestPassed = false
    @State private var asrTesting = false
    @State private var ttsTestResult: String?
    @State private var ttsTestPassed = false
    @State private var ttsTesting = false

    var body: some View {
        @Bindable var settings = settings

        ScrollViewReader { proxy in
        Form {
            Section {
                Picker(tr("供应商", "Provider"), selection: $settings.llmProvider) {
                    ForEach(LLMChoice.allCases) { Text($0.label).tag($0) }
                }
                .onboardingTarget(.llmProvider)

                switch settings.llmProvider {
                case .openAICompatible:
                    TextField(tr("接口地址", "Base URL"), text: $settings.llmBaseURL, prompt: Text(tr("厂商文档里的 base_url", "base_url from the vendor’s docs")))
                        .onboardingTarget(.llmBaseURL)
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text(tr("例如 deepseek-flash", "e.g. deepseek-flash")))
                        .onboardingTarget(.llmModel)
                    SecureField("API Key", text: $settings.llmAPIKey, prompt: Text("sk-…"))
                        .onboardingTarget(.llmKey)
                    HStack {
                        Button(testing ? tr("测试中…", "Testing…") : tr("测试连接", "Test Connection")) { test() }
                            .disabled(testing || settings.llmBaseURL.isBlank || settings.llmAPIKey.isBlank)
                        if let testResult {
                            Text(testResult)
                                .podsumFont(.micro)
                                .foregroundStyle(testPassed ? Tone.ok : Tone.err)
                                .textSelection(.enabled)
                        }
                    }
                    .onboardingTarget(.llmTest)
                case .qwen:
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text("qwen3.7-plus"))
                        .onboardingTarget(.llmModel)
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                        .onboardingTarget(.llmKey)
                case .anthropic:
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text("claude-sonnet-5"))
                        .onboardingTarget(.llmModel)
                    SecureField("Anthropic API Key", text: $settings.anthropicAPIKey)
                        .onboardingTarget(.llmKey)
                }
            } header: {
                Text(tr("摘要与对话（LLM）", "Summaries & Chat (LLM)"))
            } footer: {
                Text(tr("「OpenAI 兼容接口」走的是标准 /chat/completions 协议，自己填地址即可，不限厂商。",
                        "“OpenAI-compatible” uses the standard /chat/completions protocol — fill in any vendor’s URL."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section(tr("转写（ASR）", "Transcription (ASR)")) {
                Picker(tr("供应商", "Provider"), selection: $settings.asrProvider) {
                    ForEach(ASRChoice.allCases) { Text($0.label).tag($0) }
                }
                .onboardingTarget(.asrProvider)
                switch settings.asrProvider {
                case .doubao:
                    SecureField(tr("火山 Access Key ID", "Volcengine Access Key ID"), text: $settings.volcAccessKeyID)
                        .onboardingTarget(.asrVolcAK)
                    SecureField(tr("火山 Secret Access Key", "Volcengine Secret Access Key"), text: $settings.volcSecretKey)
                        .onboardingTarget(.asrVolcSK)
                    TextField(tr("豆包 ASR App ID", "Doubao ASR App ID"), text: $settings.doubaoASRAppID)
                        .onboardingTarget(.asrAppID)
                    SecureField(tr("豆包 ASR Access Token", "Doubao ASR Access Token"), text: $settings.doubaoASRToken)
                        .onboardingTarget(.asrToken)
                    HStack {
                        Button(asrTesting ? tr("测试中…", "Testing…") : tr("测试连接", "Test Connection")) { testDoubaoASR() }
                            .disabled(asrTesting || settings.doubaoASRAppID.isBlank || settings.doubaoASRToken.isBlank)
                        if let asrTestResult {
                            Text(asrTestResult)
                                .podsumFont(.micro)
                                .foregroundStyle(asrTestPassed ? Tone.ok : Tone.err)
                                .textSelection(.enabled)
                        }
                    }
                case .openaiWhisper:
                    SecureField("OpenAI API Key", text: $settings.openAIAPIKey)
                        .onboardingTarget(.asrOpenAIKey)
                case .deepgram:
                    SecureField("Deepgram API Key", text: $settings.deepgramAPIKey)
                        .onboardingTarget(.asrDeepgramKey)
                case .qwen:
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                        .onboardingTarget(.asrDashscopeKey)
                }
            }

            Section {
                Toggle(tr("启用音频摘要", "Enable Audio Summaries"), isOn: $settings.ttsEnabled)
                    .onboardingTarget(.ttsToggle)
                if settings.ttsEnabled {
                    Picker(tr("供应商", "Provider"), selection: $settings.ttsProvider) {
                        ForEach(TTSChoice.allCases) { Text($0.label).tag($0) }
                    }
                    .onboardingTarget(.ttsProvider)
                    switch settings.ttsProvider {
                    case .doubao:
                        SecureField(tr("火山 Access Key ID", "Volcengine Access Key ID"), text: $settings.volcAccessKeyID)
                            .onboardingTarget(.ttsVolcAK)
                        SecureField(tr("火山 Secret Access Key", "Volcengine Secret Access Key"), text: $settings.volcSecretKey)
                            .onboardingTarget(.ttsVolcSK)
                        TextField(tr("豆包 TTS App ID", "Doubao TTS App ID"), text: $settings.doubaoTTSAppID)
                            .onboardingTarget(.ttsAppID)
                        SecureField(tr("豆包 TTS Access Token", "Doubao TTS Access Token"), text: $settings.doubaoTTSToken)
                            .onboardingTarget(.ttsToken)
                        HStack {
                            Button(ttsTesting ? tr("测试中…", "Testing…") : tr("测试连接", "Test Connection")) { testDoubaoTTS() }
                                .disabled(ttsTesting || settings.doubaoTTSAppID.isBlank || settings.doubaoTTSToken.isBlank)
                            if let ttsTestResult {
                                Text(ttsTestResult)
                                    .podsumFont(.micro)
                                    .foregroundStyle(ttsTestPassed ? Tone.ok : Tone.err)
                                    .textSelection(.enabled)
                            }
                        }
                    case .qwen:
                        SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                            .onboardingTarget(.ttsDashscopeKey)
                    }
                }
            } header: {
                Text(tr("音频摘要（TTS）", "Audio Summaries (TTS)"))
            } footer: {
                Text(tr("关掉就不必填这一段——音频摘要是独立的可选流水线，不影响转写与摘要。",
                        "Turn this off and you can skip this section — audio summaries are a separate, optional pipeline that doesn’t affect transcription or summaries."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section {
                if settings.missingFields.isEmpty {
                    Label(tr("配置齐了", "All set"), systemImage: "checkmark.circle")
                        .foregroundStyle(Tone.ok)
                } else {
                    Label(tr("还缺：", "Still missing: ") + settings.missingFields.joined(separator: tr("、", ", ")),
                          systemImage: "exclamationmark.circle")
                        .foregroundStyle(Tone.warn)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Button(tr("应用并重启后端", "Apply & Restart Backend")) { Task { await backend.restart() } }
                    .disabled(!settings.isConfigured || backend.phase.isBusy)
                    .onboardingTarget(.apply)
            }
        }
        .formStyle(.grouped)
        .overlay {
            if guide.isActive { OnboardingOverlay() }
        }
        // 引导换到下一格时，先把那一格滚进视野中间
        .onChange(of: currentGuideTarget, initial: true) { _, target in
            guard guide.isActive, let target else { return }
            withAnimation(.easeInOut(duration: 0.3)) { proxy.scrollTo(target, anchor: .center) }
        }
        // 地址、模型、key 任何一个改了，上一次的测试结果就不算数了
        .onChange(of: [settings.llmBaseURL, settings.llmModel, settings.llmAPIKey]) { _, _ in
            if guide.llmTest != .untested { guide.llmTest = .untested }
        }
        .onChange(of: [settings.doubaoASRAppID, settings.doubaoASRToken]) { _, _ in
            asrTestResult = nil
        }
        .onChange(of: [settings.doubaoTTSAppID, settings.doubaoTTSToken]) { _, _ in
            ttsTestResult = nil
        }
        }
    }

    private var currentGuideTarget: OnboardingTarget? {
        guard guide.isActive else { return nil }
        let steps = OnboardingScript.steps(settings)
        return steps[guide.clampedIndex(stepCount: steps.count)].target
    }

    /// 直接打用户填的那个地址。地址和 key 都是手输的，最容易错的就是这里——
    /// 与其等提交一集之后在流水线里失败，不如当场问一句。
    private func test() {
        testing = true
        testResult = nil
        testPassed = false
        let base = settings.llmBaseURL.trimmed
        let model = settings.llmModel.trimmed
        let key = settings.llmAPIKey.trimmed

        guide.llmTest = .testing
        Task {
            defer {
                testing = false
                guide.llmTest = testPassed ? .passed : .failed(testResult ?? tr("测试失败", "Test failed"))
            }
            guard var url = URL(string: base) else { testResult = tr("地址不合法", "Invalid URL"); return }
            url.append(path: "chat/completions")

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.timeoutInterval = 20
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            request.httpBody = try? JSONSerialization.data(withJSONObject: [
                "model": model,
                "messages": [["role": "user", "content": "ping"]],
                "max_tokens": 1,
            ])

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                if (200..<300).contains(code) {
                    testPassed = true
                    testResult = tr("通过", "Passed")
                } else {
                    let body = String(data: data.prefix(200), encoding: .utf8) ?? ""
                    testResult = "HTTP \(code) \(body)"
                }
            } catch {
                testResult = error.localizedDescription
            }
        }
    }
}

extension ProviderSettings {
    /// 跟后端转写走同一个接口和资源（录音文件识别模型2.0），提交 1 秒静音，
    /// 只看提交是否被受理：App ID、Token 对不对、这个应用开没开通这项服务，一次就能看出来。
    /// 不去查识别结果——静音本来也识别不出字。
    fileprivate func testDoubaoASR() {
        asrTesting = true
        asrTestResult = nil
        asrTestPassed = false
        let appID = settings.doubaoASRAppID.trimmed
        let token = settings.doubaoASRToken.trimmed

        Task {
            defer { asrTesting = false }
            var request = URLRequest(url: URL(string: "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit")!)
            request.httpMethod = "POST"
            request.timeoutInterval = 20
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(appID, forHTTPHeaderField: "X-Api-App-Key")
            request.setValue(token, forHTTPHeaderField: "X-Api-Access-Key")
            request.setValue("volc.seedasr.auc", forHTTPHeaderField: "X-Api-Resource-Id")
            request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Api-Request-Id")
            request.setValue("-1", forHTTPHeaderField: "X-Api-Sequence")
            request.httpBody = try? JSONSerialization.data(withJSONObject: [
                "user": ["uid": "podsum"],
                "audio": ["format": "wav", "data": Self.silentWAV.base64EncodedString()],
                "request": ["model_name": "bigmodel"],
            ])

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                let http = response as? HTTPURLResponse
                let status = http?.value(forHTTPHeaderField: "X-Api-Status-Code") ?? ""
                if status == "20000000" {
                    asrTestPassed = true
                    asrTestResult = tr("通过", "Passed")
                } else if status == "45000010" {
                    asrTestResult = tr("App ID 或 Access Token 不对，或这个应用没开通「豆包录音文件识别模型2.0」",
                                       "Wrong App ID or Access Token, or this app doesn’t have 豆包录音文件识别模型2.0 enabled")
                } else {
                    let message = http?.value(forHTTPHeaderField: "X-Api-Message")
                        ?? String(data: data.prefix(200), encoding: .utf8) ?? ""
                    asrTestResult = "\(status.isEmpty ? "HTTP \(http?.statusCode ?? 0)" : status) \(message)"
                }
            } catch {
                asrTestResult = error.localizedDescription
            }
        }
    }

    /// 跟后端音频摘要走同一个接口（语音合成 v1，cluster volcano_tts，默认中文音色），
    /// 合成「测试」两个字：能拿回音频，App ID、Token 和「语音合成」能力就都对。
    fileprivate func testDoubaoTTS() {
        ttsTesting = true
        ttsTestResult = nil
        ttsTestPassed = false
        let appID = settings.doubaoTTSAppID.trimmed
        let token = settings.doubaoTTSToken.trimmed

        Task {
            defer { ttsTesting = false }
            var request = URLRequest(url: URL(string: "https://openspeech.bytedance.com/api/v1/tts")!)
            request.httpMethod = "POST"
            request.timeoutInterval = 20
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer;\(token)", forHTTPHeaderField: "Authorization")
            request.httpBody = try? JSONSerialization.data(withJSONObject: [
                "app": ["appid": appID, "token": token, "cluster": "volcano_tts"],
                "user": ["uid": "podsum"],
                "audio": ["voice_type": "BV700_streaming", "encoding": "mp3"],
                "request": ["reqid": UUID().uuidString, "text": "测试", "text_type": "plain", "operation": "query"],
            ])

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                let http = response as? HTTPURLResponse
                let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
                let code = (json?["code"] as? NSNumber)?.intValue
                let message = json?["message"] as? String ?? ""
                if http?.mimeType?.hasPrefix("audio/") == true
                    || (code == 3000 && !((json?["data"] as? String) ?? "").isEmpty) {
                    ttsTestPassed = true
                    ttsTestResult = tr("通过", "Passed")
                } else if message.contains("grant") {
                    ttsTestResult = tr("App ID 或 Access Token 不对，或这个应用没勾「语音合成」",
                                       "Wrong App ID or Access Token, or this app doesn’t have Speech Synthesis enabled")
                } else if let code {
                    ttsTestResult = "\(code) \(message)"
                } else {
                    ttsTestResult = "HTTP \(http?.statusCode ?? 0) \(String(data: data.prefix(200), encoding: .utf8) ?? "")"
                }
            } catch {
                ttsTestResult = error.localizedDescription
            }
        }
    }

    /// 1 秒 16 kHz 单声道 16-bit 静音
    private static let silentWAV: Data = {
        let sampleRate: UInt32 = 16_000
        let pcm = Data(count: Int(sampleRate) * 2)
        var d = Data()
        func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        func u16(_ v: UInt16) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        d.append(contentsOf: Array("RIFF".utf8)); u32(36 + UInt32(pcm.count))
        d.append(contentsOf: Array("WAVEfmt ".utf8)); u32(16); u16(1); u16(1)
        u32(sampleRate); u32(sampleRate * 2); u16(2); u16(16)
        d.append(contentsOf: Array("data".utf8)); u32(UInt32(pcm.count))
        d.append(pcm)
        return d
    }()
}

// MARK: - 服务

struct BackendSettings: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(ComponentUpdater.self) private var components

    var body: some View {
        @Bindable var settings = settings

        Form {
            Section(tr("后端", "Backend")) {
                Picker(tr("运行方式", "Mode"), selection: $settings.backendMode) {
                    ForEach(BackendMode.allCases) { Text($0.label).tag($0) }
                }
                switch settings.backendMode {
                case .embedded:
                    TextField(tr("端口", "Port"), value: $settings.port, format: .number.grouping(.never))
                    PathField(title: tr("后端目录", "Backend Folder"), path: $settings.backendRoot,
                              placeholder: tr("留空＝用 app 内嵌的那份", "Empty = use the copy bundled in the app"), chooseDirectories: true)
                    PathField(title: "Python", path: $settings.pythonPath,
                              placeholder: tr("留空＝自动查找", "Empty = find automatically"), chooseDirectories: false)
                case .external:
                    TextField(tr("地址", "URL"), text: $settings.externalBaseURL, prompt: Text("http://127.0.0.1:8000"))
                }
            }

            Section {
                PathField(title: tr("数据目录", "Data Folder"), path: $settings.dataDirectory,
                          placeholder: AppSettings.defaultDataDirectory, chooseDirectories: true)
            } header: {
                Text(tr("数据", "Data"))
            } footer: {
                Text(tr("音频、文稿与 SQLite 都落在这里。指到现有的 data/ 目录就能接着用原来的剧集。",
                        "Audio, transcripts, and the SQLite database live here. Point it at an existing data/ folder to keep your episodes."))
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            ComponentSection(external: settings.backendMode == .external)

            Section(tr("状态", "Status")) {
                BackendStatusLine(phase: backend.phase)
                HStack {
                    Button(tr("重启后端", "Restart Backend")) { Task { await backend.restart() } }
                        .disabled(backend.phase.isBusy)
                    Button(tr("打开日志", "Open Log")) {
                        NSWorkspace.shared.open(BackendController.logURL)
                    }
                }
                if !backend.logTail.isEmpty {
                    ScrollView {
                        Text(backend.logTail)
                            .podsumFont(.monoSmall)
                            .foregroundStyle(Tone.textMuted)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(height: 110)
                }
            }
        }
        .formStyle(.grouped)
        .task { await components.refresh() }
    }
}

/// 「更新解析组件」。YouTube / B 站改接口后，旧版 yt-dlp 就下不动了——
/// 用户自己点一下就能升级，不用等重新发包。机制见 `ComponentUpdater`。
private struct ComponentSection: View {
    @Environment(ComponentUpdater.self) private var components
    @Environment(BackendController.self) private var backend
    let external: Bool

    var body: some View {
        Section {
            LabeledContent(tr("视频解析（yt-dlp）", "Video extraction (yt-dlp)")) {
                if let installed = components.installed {
                    Text(installed.version + (installed.isUpdated ? tr("（已更新）", " (updated)") : tr("（内置）", " (built in)")))
                        .textSelection(.enabled)
                } else {
                    Text("—").foregroundStyle(Tone.textSubtle)
                }
            }

            HStack {
                Button(tr("检查并更新", "Check & Update")) { Task { await components.update() } }
                    .disabled(external || components.state.isWorking)
                if components.installed?.isUpdated == true {
                    Button(tr("恢复内置版本", "Revert to Built-in")) { Task { await components.revertToBundled() } }
                        .disabled(external || components.state.isWorking)
                }
                Spacer()
                if components.needsRestart {
                    Button(tr("重启后端以生效", "Restart Backend to Apply")) { Task { await components.restartBackend() } }
                        .disabled(backend.phase.isBusy || components.state.isWorking)
                }
            }

            status

            if !components.log.isEmpty, case .failed = components.state {
                ScrollView {
                    Text(components.log)
                        .podsumFont(.monoSmall)
                        .foregroundStyle(Tone.textMuted)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 90)
            }
        } header: {
            Text(tr("解析组件", "Extraction Component"))
        } footer: {
            Text(external
                 ? tr("连接的是外部后端，它用的是自己环境里的 yt-dlp，不归本 app 管。",
                      "You’re connected to an external backend; it uses the yt-dlp in its own environment.")
                 : tr("视频网站改版后下载失败时，先点这里更新。更新装在 app 外面，不影响 app 本身；随时可以恢复内置版本。",
                      "If video downloads start failing after a site change, update here first. Updates live outside the app and can be reverted at any time."))
                .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
        }
    }

    @ViewBuilder private var status: some View {
        switch components.state {
        case .idle:
            EmptyView()
        case .working(let step):
            HStack { ProgressView().controlSize(.small); Text(step) }
                .foregroundStyle(Tone.textMuted)
        case .upToDate(let version):
            Label(tr("已是最新（\(version)）", "Already up to date (\(version))"), systemImage: "checkmark.circle")
                .foregroundStyle(Tone.ok)
        case .updated(let from, let to):
            Label(tr("已从 \(from) 更新到 \(to)，重启后端后生效。", "Updated from \(from) to \(to). Restart the backend to apply."),
                  systemImage: "arrow.down.circle")
                .foregroundStyle(Tone.ok)
        case .reverted:
            Label(tr("已恢复内置版本，重启后端后生效。", "Reverted to the built-in version. Restart the backend to apply."),
                  systemImage: "arrow.uturn.backward.circle")
                .foregroundStyle(Tone.textMuted)
        case .failed(let message):
            Label(message, systemImage: "exclamationmark.triangle")
                .foregroundStyle(Tone.err)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct BackendStatusLine: View {
    let phase: BackendController.Phase

    var body: some View {
        switch phase {
        case .idle:
            Label(tr("未启动", "Not started"), systemImage: "circle")
                .foregroundStyle(Tone.textSubtle)
        case .needsConfiguration(let missing):
            Label(tr("还缺：", "Still missing: ") + missing.joined(separator: tr("、", ", ")), systemImage: "key")
                .foregroundStyle(Tone.warn)
                .fixedSize(horizontal: false, vertical: true)
        case .noRuntime(let message), .failed(let message):
            Label(message, systemImage: "exclamationmark.triangle")
                .foregroundStyle(Tone.err)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        case .starting(let step):
            HStack { ProgressView().controlSize(.small); Text(step) }
                .foregroundStyle(Tone.textMuted)
        case .ready(let url):
            Label(tr("运行中 · \(url.absoluteString)", "Running · \(url.absoluteString)"), systemImage: "checkmark.circle")
                .foregroundStyle(Tone.ok)
        }
    }
}

/// 一行路径 + 「选择…」。手输和选择都要支持：
/// 选择更稳，但从别处拷一段路径粘进来也是常事。
struct PathField: View {
    let title: String
    @Binding var path: String
    let placeholder: String
    let chooseDirectories: Bool

    var body: some View {
        HStack {
            TextField(title, text: $path, prompt: Text(placeholder))
                .lineLimit(1)
            Button(tr("选择…", "Choose…")) {
                let panel = NSOpenPanel()
                panel.canChooseDirectories = chooseDirectories
                panel.canChooseFiles = !chooseDirectories
                panel.allowsMultipleSelection = false
                if !path.isBlank {
                    panel.directoryURL = URL(filePath: path, directoryHint: chooseDirectories ? .isDirectory : .notDirectory)
                }
                if panel.runModal() == .OK, let url = panel.url {
                    path = url.path(percentEncoded: false)
                }
            }
            if !path.isBlank {
                Button {
                    path = ""
                } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(Tone.textSubtle)
                }
                .buttonStyle(.plain)
                .help(tr("恢复默认", "Reset to default"))
            }
        }
    }
}
