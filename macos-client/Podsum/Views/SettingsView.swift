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
            ProviderSettings()
                .tabItem { Label("接口", systemImage: "key") }
            BackendSettings()
                .tabItem { Label("服务", systemImage: "server.rack") }
        }
        .frame(width: 580, height: 520)
    }
}

// MARK: - 接口

struct ProviderSettings: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend

    @State private var testResult: String?
    @State private var testing = false

    var body: some View {
        @Bindable var settings = settings

        Form {
            Section {
                Picker("供应商", selection: $settings.llmProvider) {
                    ForEach(LLMChoice.allCases) { Text($0.label).tag($0) }
                }

                switch settings.llmProvider {
                case .openAICompatible:
                    TextField("接口地址", text: $settings.llmBaseURL, prompt: Text("https://api.example.com/v1"))
                    TextField("模型名", text: $settings.llmModel, prompt: Text("例如 gpt-4o-mini"))
                    SecureField("API Key", text: $settings.llmAPIKey, prompt: Text("sk-…"))
                    HStack {
                        Button(testing ? "测试中…" : "测试连接") { test() }
                            .disabled(testing || settings.llmBaseURL.isBlank || settings.llmAPIKey.isBlank)
                        if let testResult {
                            Text(testResult)
                                .podsumFont(.micro)
                                .foregroundStyle(testResult.hasPrefix("通过") ? Tone.ok : Tone.err)
                                .textSelection(.enabled)
                        }
                    }
                case .qwen:
                    TextField("模型名", text: $settings.llmModel, prompt: Text("qwen-max"))
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                case .anthropic:
                    TextField("模型名", text: $settings.llmModel, prompt: Text("claude-sonnet-4-5"))
                    SecureField("Anthropic API Key", text: $settings.anthropicAPIKey)
                }
            } header: {
                Text("摘要与对话（LLM）")
            } footer: {
                Text("「OpenAI 兼容接口」走的是标准 /chat/completions 协议，自己填地址即可，不限厂商。")
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section("转写（ASR）") {
                Picker("供应商", selection: $settings.asrProvider) {
                    ForEach(ASRChoice.allCases) { Text($0.label).tag($0) }
                }
                switch settings.asrProvider {
                case .doubao:
                    SecureField("火山 Access Key ID", text: $settings.volcAccessKeyID)
                    SecureField("火山 Secret Access Key", text: $settings.volcSecretKey)
                    TextField("豆包 ASR App ID", text: $settings.doubaoASRAppID)
                    SecureField("豆包 ASR Access Token", text: $settings.doubaoASRToken)
                case .openaiWhisper:
                    SecureField("OpenAI API Key", text: $settings.openAIAPIKey)
                case .deepgram:
                    SecureField("Deepgram API Key", text: $settings.deepgramAPIKey)
                case .qwen:
                    SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                }
            }

            Section {
                Toggle("启用音频摘要", isOn: $settings.ttsEnabled)
                if settings.ttsEnabled {
                    Picker("供应商", selection: $settings.ttsProvider) {
                        ForEach(TTSChoice.allCases) { Text($0.label).tag($0) }
                    }
                    switch settings.ttsProvider {
                    case .doubao:
                        SecureField("火山 Access Key ID", text: $settings.volcAccessKeyID)
                        SecureField("火山 Secret Access Key", text: $settings.volcSecretKey)
                        TextField("豆包 TTS App ID", text: $settings.doubaoTTSAppID)
                        SecureField("豆包 TTS Access Token", text: $settings.doubaoTTSToken)
                    case .qwen:
                        SecureField("DashScope API Key", text: $settings.dashscopeAPIKey)
                    }
                }
            } header: {
                Text("音频摘要（TTS）")
            } footer: {
                Text("关掉就不必填这一段——音频摘要是独立的可选流水线，不影响转写与摘要。")
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section {
                if settings.missingFields.isEmpty {
                    Label("配置齐了", systemImage: "checkmark.circle")
                        .foregroundStyle(Tone.ok)
                } else {
                    Label("还缺：" + settings.missingFields.joined(separator: "、"),
                          systemImage: "exclamationmark.circle")
                        .foregroundStyle(Tone.warn)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Button("应用并重启后端") { Task { await backend.restart() } }
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
        let base = settings.llmBaseURL.trimmed
        let model = settings.llmModel.trimmed
        let key = settings.llmAPIKey.trimmed

        Task {
            defer { testing = false }
            guard var url = URL(string: base) else { testResult = "地址不合法"; return }
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
                    testResult = "通过"
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
            Section("后端") {
                Picker("运行方式", selection: $settings.backendMode) {
                    ForEach(BackendMode.allCases) { Text($0.label).tag($0) }
                }
                switch settings.backendMode {
                case .embedded:
                    TextField("端口", value: $settings.port, format: .number.grouping(.never))
                    PathField(title: "后端目录", path: $settings.backendRoot,
                              placeholder: "留空＝用 app 内嵌的那份", chooseDirectories: true)
                    PathField(title: "Python", path: $settings.pythonPath,
                              placeholder: "留空＝自动查找", chooseDirectories: false)
                case .external:
                    TextField("地址", text: $settings.externalBaseURL, prompt: Text("http://127.0.0.1:8000"))
                }
            }

            Section {
                PathField(title: "数据目录", path: $settings.dataDirectory,
                          placeholder: AppSettings.defaultDataDirectory, chooseDirectories: true)
            } header: {
                Text("数据")
            } footer: {
                Text("音频、文稿与 SQLite 都落在这里。指到现有的 data/ 目录就能接着用原来的剧集。")
                    .podsumFont(.micro).foregroundStyle(Tone.textSubtle)
            }

            Section("状态") {
                BackendStatusLine(phase: backend.phase)
                HStack {
                    Button("重启后端") { Task { await backend.restart() } }
                        .disabled(backend.phase.isBusy)
                    Button("打开日志") {
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
            Label("未启动", systemImage: "circle")
                .foregroundStyle(Tone.textSubtle)
        case .needsConfiguration(let missing):
            Label("还缺：" + missing.joined(separator: "、"), systemImage: "key")
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
            Label("运行中 · \(url.absoluteString)", systemImage: "checkmark.circle")
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
            Button("选择…") {
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
                .help("恢复默认")
            }
        }
    }
}
