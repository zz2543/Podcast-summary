import SwiftUI

/// 设置面板（⌘,）。
///
/// **这个 app 不内置任何凭据。** 所有字段默认为空，填好之前后端起不来，
/// 界面会明说缺哪几项。密钥写钥匙串，不落明文。
struct SettingsView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend

    var body: some View {
        TabView {
            GeneralSettings()
                .tabItem { Label(tr("通用", "General"), systemImage: "gearshape") }
            ProviderSettings()
                .tabItem { Label(tr("接口", "Providers"), systemImage: "key") }
            BackendSettings()
                .tabItem { Label(tr("服务", "Service"), systemImage: "server.rack") }
            QuickAddSettings()
                .tabItem { Label(tr("快捷提交", "Quick Add"), systemImage: "bolt") }
        }
        .frame(width: 580, height: 520)
    }
}

// MARK: - 通用

struct GeneralSettings: View {
    @State private var localizer = Localizer.shared

    var body: some View {
        Form {
            Section {
                Picker(tr("界面语言", "Interface Language"), selection: $localizer.preference) {
                    ForEach(InterfaceLanguage.allCases) { Text($0.label).tag($0) }
                }
                if localizer.needsRelaunch {
                    HStack {
                        Label(tr("菜单栏的系统项（文件、编辑、窗口…）要重启 Podsum 才会换语言。",
                                 "System menus (File, Edit, Window…) switch language after Podsum restarts."),
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
        }
        .formStyle(.grouped)
    }
}

// MARK: - 接口

struct ProviderSettings: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend

    @State private var testResult: String?
    @State private var testPassed = false
    @State private var testing = false

    var body: some View {
        @Bindable var settings = settings

        Form {
            Section {
                Picker(tr("供应商", "Provider"), selection: $settings.llmProvider) {
                    ForEach(LLMChoice.allCases) { Text($0.label).tag($0) }
                }

                switch settings.llmProvider {
                case .openAICompatible:
                    TextField(tr("接口地址", "Base URL"), text: $settings.llmBaseURL, prompt: Text("https://api.example.com/v1"))
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text(tr("例如 gpt-4o-mini", "e.g. gpt-4o-mini")))
                    SecureField("API Key", text: $settings.llmAPIKey, prompt: Text("sk-…"))
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
                case .qwen:
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text("qwen-max"))
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                case .anthropic:
                    TextField(tr("模型名", "Model"), text: $settings.llmModel, prompt: Text("claude-sonnet-4-5"))
                    SecureField("Anthropic API Key", text: $settings.anthropicAPIKey)
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
                switch settings.asrProvider {
                case .doubao:
                    SecureField(tr("火山 Access Key ID", "Volcengine Access Key ID"), text: $settings.volcAccessKeyID)
                    SecureField(tr("火山 Secret Access Key", "Volcengine Secret Access Key"), text: $settings.volcSecretKey)
                    TextField(tr("豆包 ASR App ID", "Doubao ASR App ID"), text: $settings.doubaoASRAppID)
                    SecureField(tr("豆包 ASR Access Token", "Doubao ASR Access Token"), text: $settings.doubaoASRToken)
                case .openaiWhisper:
                    SecureField("OpenAI API Key", text: $settings.openAIAPIKey)
                case .deepgram:
                    SecureField("Deepgram API Key", text: $settings.deepgramAPIKey)
                case .qwen:
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                }
            }

            Section {
                Toggle(tr("启用音频摘要", "Enable Audio Summaries"), isOn: $settings.ttsEnabled)
                if settings.ttsEnabled {
                    Picker(tr("供应商", "Provider"), selection: $settings.ttsProvider) {
                        ForEach(TTSChoice.allCases) { Text($0.label).tag($0) }
                    }
                    switch settings.ttsProvider {
                    case .doubao:
                        SecureField(tr("火山 Access Key ID", "Volcengine Access Key ID"), text: $settings.volcAccessKeyID)
                        SecureField(tr("火山 Secret Access Key", "Volcengine Secret Access Key"), text: $settings.volcSecretKey)
                        TextField(tr("豆包 TTS App ID", "Doubao TTS App ID"), text: $settings.doubaoTTSAppID)
                        SecureField(tr("豆包 TTS Access Token", "Doubao TTS Access Token"), text: $settings.doubaoTTSToken)
                    case .qwen:
                        SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
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
            }
        }
        .formStyle(.grouped)
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

        Task {
            defer { testing = false }
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

// MARK: - 服务

struct BackendSettings: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend

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
