import Foundation
import Observation

// MARK: - 供应商选择
//
// 三个环节各自独立：转写（ASR）、摘要（LLM）、音频摘要（TTS）。
// 取值与后端 config.py 的 Literal 一一对应，rawValue 就是要发给后端的环境变量值。

public enum ASRChoice: String, CaseIterable, Identifiable, Sendable {
    case doubao, openaiWhisper = "openai_whisper", deepgram, qwen
    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .doubao:        return "豆包 / 火山引擎"
        case .openaiWhisper: return "OpenAI Whisper"
        case .deepgram:      return "Deepgram"
        case .qwen:          return "通义千问（DashScope）"
        }
    }
}

public enum LLMChoice: String, CaseIterable, Identifiable, Sendable {
    /// 后端这一支走的是 OpenAI 兼容协议，base URL 与 model 都可配，
    /// 不限于 DeepSeek——环境变量名沿用 DEEPSEEK_* 只是历史原因。
    case openAICompatible = "deepseek"
    case qwen
    case anthropic

    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .openAICompatible: return "OpenAI 兼容接口（自填 URL）"
        case .qwen:             return "通义千问（DashScope）"
        case .anthropic:        return "Anthropic"
        }
    }
}

public enum TTSChoice: String, CaseIterable, Identifiable, Sendable {
    case doubao, qwen
    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .doubao: return "豆包 / 火山引擎"
        case .qwen:   return "通义千问（DashScope）"
        }
    }
}

public enum BackendMode: String, CaseIterable, Identifiable, Sendable {
    /// app 自己拉起 uvicorn 子进程，退出时一并收掉
    case embedded
    /// 连接一个已经在跑的后端（例如终端里的 `make run`）
    case external

    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .embedded: return "由本 app 启动"
        case .external: return "连接已在运行的后端"
        }
    }
}

// MARK: - 设置

/// 全部配置的唯一来源。
///
/// **默认一律为空。** 这个 app 不内置任何人的 API 凭据——不填就起不来，
/// 起不来时界面会明说缺哪一项。密钥存钥匙串（见 `Keychain`），
/// 其余存 UserDefaults。
///
/// 后端读的是环境变量。`environment()` 把这里的值铺成 uvicorn 子进程的 env，
/// 且**把所有受管字段都显式写一遍**（没填的写空串）——否则后端会去读
/// 工作目录下的 `.env`，悄悄用上别人的 key。
@Observable
public final class AppSettings {
    public static let shared = AppSettings()

    // MARK: 后端

    public var backendMode: BackendMode { didSet { put(backendMode.rawValue, "backendMode") } }
    public var externalBaseURL: String  { didSet { put(externalBaseURL, "externalBaseURL") } }
    public var port: Int                { didSet { put(String(port), "port") } }
    /// 含 backend/、prompts/、scripts/ 的目录。留空则用 app 内嵌的那份。
    public var backendRoot: String      { didSet { put(backendRoot, "backendRoot") } }
    /// 留空则按内嵌运行时 → 项目 .venv → Homebrew → /usr/bin 的顺序找
    public var pythonPath: String       { didSet { put(pythonPath, "pythonPath") } }
    /// 音频、文稿、SQLite 的落地位置
    public var dataDirectory: String    { didSet { put(dataDirectory, "dataDirectory") } }

    // MARK: 供应商

    public var asrProvider: ASRChoice { didSet { put(asrProvider.rawValue, "asrProvider") } }
    public var llmProvider: LLMChoice { didSet { put(llmProvider.rawValue, "llmProvider") } }
    public var ttsProvider: TTSChoice { didSet { put(ttsProvider.rawValue, "ttsProvider") } }
    /// 关掉就不必填 TTS 凭据——音频摘要是独立的可选流水线
    public var ttsEnabled: Bool { didSet { put(ttsEnabled, "ttsEnabled") } }

    // MARK: 非密钥字段

    public var llmBaseURL: String { didSet { put(llmBaseURL, "llmBaseURL") } }
    public var llmModel: String   { didSet { put(llmModel, "llmModel") } }
    public var doubaoASRAppID: String { didSet { put(doubaoASRAppID, "doubaoASRAppID") } }
    public var doubaoTTSAppID: String { didSet { put(doubaoTTSAppID, "doubaoTTSAppID") } }

    // MARK: 密钥（钥匙串）

    /// 密钥全部写进钥匙串里同一条记录（见 `Keychain`）。
    /// `llmAPIKey` 只管 OpenAI 兼容那一支；千问与 Anthropic 各有各的字段，
    /// 分开存才不会在切换供应商时互相覆盖。
    public var llmAPIKey: String        { didSet { secret(llmAPIKey, "DEEPSEEK_API_KEY") } }
    public var dashscopeAPIKey: String  { didSet { secret(dashscopeAPIKey, "DASHSCOPE_API_KEY") } }
    public var openAIAPIKey: String     { didSet { secret(openAIAPIKey, "OPENAI_API_KEY") } }
    public var deepgramAPIKey: String   { didSet { secret(deepgramAPIKey, "DEEPGRAM_API_KEY") } }
    public var anthropicAPIKey: String  { didSet { secret(anthropicAPIKey, "ANTHROPIC_API_KEY") } }
    public var volcAccessKeyID: String  { didSet { secret(volcAccessKeyID, "VOLC_ACCESS_KEY_ID") } }
    public var volcSecretKey: String    { didSet { secret(volcSecretKey, "VOLC_SECRET_ACCESS_KEY") } }
    public var doubaoASRToken: String   { didSet { secret(doubaoASRToken, "DOUBAO_ASR_ACCESS_TOKEN") } }
    public var doubaoTTSToken: String   { didSet { secret(doubaoTTSToken, "DOUBAO_TTS_ACCESS_TOKEN") } }

    /// 钥匙串那条记录的内存副本。整份读、整份写。
    private var secrets: [String: String]

    private let defaults = UserDefaults.standard
    private static let prefix = "podsum."

    private init() {
        let d = UserDefaults.standard
        func s(_ k: String, _ fallback: String = "") -> String {
            d.string(forKey: Self.prefix + k) ?? fallback
        }
        backendMode = BackendMode(rawValue: s("backendMode")) ?? .embedded
        externalBaseURL = s("externalBaseURL", "http://127.0.0.1:8000")
        port = d.object(forKey: Self.prefix + "port") as? Int ?? 8756
        backendRoot = s("backendRoot")
        pythonPath = s("pythonPath")
        dataDirectory = s("dataDirectory", Self.defaultDataDirectory)

        asrProvider = ASRChoice(rawValue: s("asrProvider")) ?? .doubao
        llmProvider = LLMChoice(rawValue: s("llmProvider")) ?? .openAICompatible
        ttsProvider = TTSChoice(rawValue: s("ttsProvider")) ?? .doubao
        ttsEnabled = d.object(forKey: Self.prefix + "ttsEnabled") as? Bool ?? false

        llmBaseURL = s("llmBaseURL")
        llmModel = s("llmModel")
        doubaoASRAppID = s("doubaoASRAppID")
        doubaoTTSAppID = s("doubaoTTSAppID")

        // 一次读完。分成九次读就意味着九次授权提示。
        let stored = Keychain.load()
        secrets = stored
        llmAPIKey = stored["DEEPSEEK_API_KEY"] ?? ""
        dashscopeAPIKey = stored["DASHSCOPE_API_KEY"] ?? ""
        openAIAPIKey = stored["OPENAI_API_KEY"] ?? ""
        deepgramAPIKey = stored["DEEPGRAM_API_KEY"] ?? ""
        anthropicAPIKey = stored["ANTHROPIC_API_KEY"] ?? ""
        volcAccessKeyID = stored["VOLC_ACCESS_KEY_ID"] ?? ""
        volcSecretKey = stored["VOLC_SECRET_ACCESS_KEY"] ?? ""
        doubaoASRToken = stored["DOUBAO_ASR_ACCESS_TOKEN"] ?? ""
        doubaoTTSToken = stored["DOUBAO_TTS_ACCESS_TOKEN"] ?? ""
    }

    private func put(_ value: String, _ key: String) { defaults.set(value, forKey: Self.prefix + key) }
    private func put(_ value: Bool, _ key: String) { defaults.set(value, forKey: Self.prefix + key) }
    private func secret(_ value: String, _ key: String) {
        secrets[key] = value
        Keychain.save(secrets)
    }

    public static var defaultDataDirectory: String {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appending(path: "Podsum/data", directoryHint: .isDirectory).path(percentEncoded: false)
    }

    // MARK: 校验

    /// 缺哪几项。非空即视为"没配好"，界面据此拦在启动之前——
    /// 后端在 `Settings` 构造期就会因缺 key 抛错退出，
    /// 与其让读者看一段 Python traceback，不如提前说清楚。
    public var missingFields: [String] {
        var missing: [String] = []

        switch llmProvider {
        case .openAICompatible:
            if llmBaseURL.isBlank { missing.append("LLM 接口地址") }
            if llmModel.isBlank { missing.append("LLM 模型名") }
            if llmAPIKey.isBlank { missing.append("LLM API Key") }
        case .qwen:
            if llmModel.isBlank { missing.append("LLM 模型名") }
            if dashscopeAPIKey.isBlank { missing.append("DashScope API Key") }
        case .anthropic:
            if llmModel.isBlank { missing.append("LLM 模型名") }
            if anthropicAPIKey.isBlank { missing.append("Anthropic API Key") }
        }

        switch asrProvider {
        case .doubao:
            if volcAccessKeyID.isBlank { missing.append("火山 Access Key ID") }
            if volcSecretKey.isBlank { missing.append("火山 Secret Access Key") }
            if doubaoASRAppID.isBlank { missing.append("豆包 ASR App ID") }
            if doubaoASRToken.isBlank { missing.append("豆包 ASR Access Token") }
        case .openaiWhisper:
            if openAIAPIKey.isBlank { missing.append("OpenAI API Key") }
        case .deepgram:
            if deepgramAPIKey.isBlank { missing.append("Deepgram API Key") }
        case .qwen:
            if dashscopeAPIKey.isBlank { missing.append("DashScope API Key") }
        }

        if ttsEnabled {
            switch ttsProvider {
            case .doubao:
                if volcAccessKeyID.isBlank { missing.append("火山 Access Key ID") }
                if volcSecretKey.isBlank { missing.append("火山 Secret Access Key") }
                if doubaoTTSAppID.isBlank { missing.append("豆包 TTS App ID") }
                if doubaoTTSToken.isBlank { missing.append("豆包 TTS Access Token") }
            case .qwen:
                if dashscopeAPIKey.isBlank { missing.append("DashScope API Key") }
            }
        }

        var seen = Set<String>()
        return missing.filter { seen.insert($0).inserted }
    }

    public var isConfigured: Bool { missingFields.isEmpty }

    // MARK: 环境变量

    /// 传给 uvicorn / alembic 子进程的环境。
    ///
    /// 受管的每一个键都会出现——没填的是空串。这一点不能省：
    /// 后端的 pydantic-settings 会读工作目录下的 `.env`，
    /// 如果这里不写，后端就会用上 `.env` 里别人的凭据，
    /// 而设置面板显示的是空。显式写空串让面板成为唯一事实来源。
    public func environment(dataDirectory dataDir: URL) -> [String: String] {
        var env: [String: String] = [:]
        for key in Env.managed { env[key] = "" }

        env["DATA_DIR"] = dataDir.path(percentEncoded: false)
        env["DB_PATH"] = dataDir.appending(path: "podsum.sqlite3").path(percentEncoded: false)

        env["ASR_PROVIDER"] = asrProvider.rawValue
        env["LLM_PROVIDER"] = llmProvider.rawValue
        env["TTS_PROVIDER"] = ttsProvider.rawValue
        env["TTS_ENABLED"] = ttsEnabled ? "true" : "false"

        switch llmProvider {
        case .openAICompatible:
            env["DEEPSEEK_BASE_URL"] = llmBaseURL.trimmed
            env["DEEPSEEK_MODEL"] = llmModel.trimmed
            env["DEEPSEEK_API_KEY"] = llmAPIKey.trimmed
        case .qwen:
            env["QWEN_LLM_MODEL"] = llmModel.trimmed
        case .anthropic:
            env["ANTHROPIC_MODEL"] = llmModel.trimmed
        }

        env["DASHSCOPE_API_KEY"] = dashscopeAPIKey.trimmed
        env["OPENAI_API_KEY"] = openAIAPIKey.trimmed
        env["DEEPGRAM_API_KEY"] = deepgramAPIKey.trimmed
        env["ANTHROPIC_API_KEY"] = anthropicAPIKey.trimmed
        env["VOLC_ACCESS_KEY_ID"] = volcAccessKeyID.trimmed
        env["VOLC_SECRET_ACCESS_KEY"] = volcSecretKey.trimmed
        env["DOUBAO_ASR_APP_ID"] = doubaoASRAppID.trimmed
        env["DOUBAO_ASR_ACCESS_TOKEN"] = doubaoASRToken.trimmed
        env["DOUBAO_TTS_APP_ID"] = doubaoTTSAppID.trimmed
        env["DOUBAO_TTS_ACCESS_TOKEN"] = doubaoTTSToken.trimmed

        return env
    }
}

// MARK: - 受管的环境变量清单

public enum Env {
    /// 设置面板负责的全部键。每次启动都会被显式写入（空串也写），
    /// 好让工作目录下的 `.env` 无法悄悄顶上。
    public static let managed: [String] = [
        "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
        "QWEN_LLM_MODEL", "ANTHROPIC_MODEL",
        "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY",
        "VOLC_ACCESS_KEY_ID", "VOLC_SECRET_ACCESS_KEY",
        "DOUBAO_ASR_APP_ID", "DOUBAO_ASR_ACCESS_TOKEN",
        "DOUBAO_TTS_APP_ID", "DOUBAO_TTS_ACCESS_TOKEN",
    ]
}
