import Foundation
import Observation

/// 后端生命周期。
///
/// 取代 `~/Applications/Podsum.app` 那个 bash 启动器：它起两个子进程
/// （uvicorn + vite）再开浏览器；这里只剩一个 uvicorn，界面就在本进程里。
///
/// 状态机是刻意显式的——"起不来"有四种完全不同的原因，
/// 混成一个"失败"会让人无从下手：
///   .needsConfiguration  没填 API → 引导去设置
///   .noRuntime           找不到 Python 或后端目录 → 说清楚找过哪些路径
///   .failed              进程起来了但退出/超时 → 给日志尾巴
///   .ready               可用
@MainActor
@Observable
public final class BackendController {
    public enum Phase: Equatable {
        case idle
        case needsConfiguration([String])
        case noRuntime(String)
        case starting(String)
        case ready(URL)
        case failed(String)

        public var baseURL: URL? { if case .ready(let u) = self { return u }; return nil }
        public var isBusy: Bool { if case .starting = self { return true }; return false }
    }

    public private(set) var phase: Phase = .idle
    /// 子进程日志的尾巴，出错时展示。全量在 ~/Library/Logs/Podsum/backend.log
    public private(set) var logTail: String = ""
    /// true 表示连的是别人起的后端，退出时不要去杀它
    public private(set) var attachedToExisting = false

    private let settings: AppSettings
    private var process: Process?
    private var logHandle: FileHandle?

    public init(settings: AppSettings = .shared) {
        self.settings = settings
    }

    public static let logURL: URL = {
        let dir = AppStorageRoot.logs
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appending(path: "backend.log")
    }()

    // MARK: 启动

    public func start() async {
        guard !phase.isBusy else { return }

        if settings.backendMode == .external {
            let url = URL(string: settings.externalBaseURL.trimmed) ?? URL(string: "http://127.0.0.1:8000")!
            phase = .starting(tr("连接 \(url.absoluteString)…", "Connecting to \(url.absoluteString)…"))
            if await Self.healthy(url) {
                attachedToExisting = true
                phase = .ready(url)
            } else {
                phase = .failed(tr("连不上 \(url.absoluteString)。确认那个后端还在跑。",
                                  "Can’t reach \(url.absoluteString). Make sure that backend is still running."))
            }
            return
        }

        let missing = settings.missingFields
        guard missing.isEmpty else {
            phase = .needsConfiguration(missing)
            return
        }

        let url = URL(string: "http://127.0.0.1:\(settings.port)")!

        // 端口上已经有一个健康的 podsum：可能是上次退出没收干净的孤儿，
        // 也可能是终端里的 `make run`。两种情况都该用它，而不是再起一个。
        phase = .starting(tr("检查 \(settings.port) 端口…", "Checking port \(settings.port)…"))
        if await Self.healthy(url) {
            attachedToExisting = true
            phase = .ready(url)
            return
        }

        let resolved: Runtime
        do { resolved = try resolveRuntime() }
        catch { phase = .noRuntime(error.localizedDescription); return }

        do {
            let dataDir = URL(filePath: settings.dataDirectory, directoryHint: .isDirectory)
            try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)
            let env = environment(resolved, dataDir: dataDir)

            if let problem = checkTools(env) {
                phase = .noRuntime(problem)
                return
            }

            // 旧的后端已经停了，清掉不再生效的组件版本
            ComponentUpdater.pruneInactive()

            phase = .starting(tr("应用数据库迁移…", "Applying database migrations…"))
            try await runMigrations(resolved, env: env)

            phase = .starting(tr("启动后端…", "Starting backend…"))
            try launch(resolved, env: env)
        } catch {
            phase = .failed(error.localizedDescription)
            logTail = Self.tail(of: Self.logURL)
            return
        }

        // 健康探测。冷启动要导入 SQLAlchemy / pydantic 这一堆，本机实测 2–4 秒。
        for _ in 0..<60 {
            if process?.isRunning == false {
                logTail = Self.tail(of: Self.logURL)
                phase = .failed(tr("后端进程退出了（code \(process?.terminationStatus ?? -1)）。",
                                   "The backend process exited (code \(process?.terminationStatus ?? -1))."))
                return
            }
            if await Self.healthy(url) {
                attachedToExisting = false
                phase = .ready(url)
                return
            }
            try? await Task.sleep(for: .milliseconds(500))
        }
        logTail = Self.tail(of: Self.logURL)
        phase = .failed(tr("后端 30 秒内没有就绪。", "The backend wasn’t ready within 30 seconds."))
    }

    /// 改完设置后重来一遍
    public func restart() async {
        stop()
        phase = .idle
        await start()
    }

    public func stop() {
        guard let process, process.isRunning, !attachedToExisting else {
            self.process = nil
            return
        }
        process.terminate()                       // SIGTERM：uvicorn 会收好任务队列
        let deadline = Date().addingTimeInterval(5)
        while process.isRunning, Date() < deadline {
            usleep(100_000)
        }
        if process.isRunning { kill(process.processIdentifier, SIGKILL) }
        self.process = nil
        try? logHandle?.close()
        logHandle = nil
    }

    // MARK: 运行时定位

    struct Runtime {
        let python: URL
        let root: URL              // 含 backend/、prompts/、scripts/
        let extraPythonPath: [URL] // 内嵌依赖目录（打包后才有）
        let toolsDirectory: URL?   // 内嵌的 ffmpeg / ffprobe / deno（打包后才有）
    }

    /// 用户在设置里更新过的解析组件（yt-dlp）。放在 bundle 外面：
    /// 改它不会弄坏签名，升级 app 也不会被覆盖。见 `ComponentUpdater`。
    nonisolated public static let componentsDirectory: URL =
        AppStorageRoot.support.appending(path: "components", directoryHint: .isDirectory)

    enum RuntimeError: LocalizedError {
        case noBackendRoot([String])
        case noPython([String])

        var errorDescription: String? {
            switch self {
            case .noBackendRoot(let tried):
                return tr("找不到后端目录（需要含 backend/ 与 prompts/）。找过：\n",
                          "Can’t find the backend folder (it must contain backend/ and prompts/). Looked in:\n")
                     + tried.joined(separator: "\n")
                     + tr("\n\n在「设置 › 后端」里手动指定即可。",
                          "\n\nSet it by hand in Settings › Service.")
            case .noPython(let tried):
                return tr("找不到 Python 解释器。找过：\n", "Can’t find a Python interpreter. Looked in:\n")
                     + tried.joined(separator: "\n")
                     + tr("\n\n在「设置 › 后端」里手动指定，或用 package.py 打一个内嵌运行时。",
                          "\n\nSet it by hand in Settings › Service, or build an embedded runtime with package.py.")
            }
        }
    }

    #if DEBUG
    /// 编译这份源码时它所在的仓库根。macos-client/Podsum/Data/ → 上四层。
    static let sourceTreeRoot = URL(filePath: #filePath)
        .deletingLastPathComponent()   // Data
        .deletingLastPathComponent()   // Podsum
        .deletingLastPathComponent()   // macos-client
        .deletingLastPathComponent()   // 仓库根
    #endif

    func resolveRuntime() throws -> Runtime {
        let fm = FileManager.default
        let bundled = Bundle.main.bundleURL.appending(path: "Contents/Resources/backend", directoryHint: .isDirectory)

        var rootCandidates: [URL] = []
        if !settings.backendRoot.isBlank {
            rootCandidates.append(URL(filePath: settings.backendRoot, directoryHint: .isDirectory))
        }
        rootCandidates.append(bundled)
        if let dev = ProcessInfo.processInfo.environment["PODSUM_BACKEND_ROOT"] {
            rootCandidates.append(URL(filePath: dev, directoryHint: .isDirectory))
        }
        #if DEBUG
        // 从 Xcode 跑的时候 bundle 在 DerivedData 里，内嵌后端只有 package.py
        // 打包时才会放进去——于是每次都要手动指目录。但 Debug 构建本来就知道
        // 自己是从哪棵工作树编出来的：#filePath 指向本文件，往上四层就是仓库根。
        // 只在 DEBUG 里用，Release 产物里不该留编译机的绝对路径。
        rootCandidates.append(Self.sourceTreeRoot)
        #endif

        func isBackendRoot(_ url: URL) -> Bool {
            fm.fileExists(atPath: url.appending(path: "backend/src/podsum/main.py").path(percentEncoded: false))
                && fm.fileExists(atPath: url.appending(path: "prompts").path(percentEncoded: false))
        }

        guard let root = rootCandidates.first(where: isBackendRoot) else {
            throw RuntimeError.noBackendRoot(rootCandidates.map { $0.path(percentEncoded: false) })
        }

        var pythonCandidates: [URL] = []
        if !settings.pythonPath.isBlank {
            pythonCandidates.append(URL(filePath: settings.pythonPath))
        }
        pythonCandidates.append(Bundle.main.bundleURL.appending(path: "Contents/Resources/python/bin/python3"))
        pythonCandidates.append(root.appending(path: ".venv/bin/python"))
        pythonCandidates += ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
            .map { URL(filePath: $0) }

        guard let python = pythonCandidates.first(where: { fm.isExecutableFile(atPath: $0.path(percentEncoded: false)) }) else {
            throw RuntimeError.noPython(pythonCandidates.map { $0.path(percentEncoded: false) })
        }

        let vendored = bundled.appending(path: "vendor", directoryHint: .isDirectory)
        let extras = fm.fileExists(atPath: vendored.path(percentEncoded: false)) ? [vendored] : []
        let tools = Bundle.main.bundleURL.appending(path: "Contents/Resources/bin", directoryHint: .isDirectory)
        return Runtime(python: python, root: root, extraPythonPath: extras,
                       toolsDirectory: fm.fileExists(atPath: tools.path(percentEncoded: false)) ? tools : nil)
    }

    /// 给「更新解析组件」用：与后端子进程完全相同的解释器、环境变量与工作目录，
    /// 这样它装进去、验过的，就是后端下次启动会加载的那一份。
    func pythonContext() throws -> (python: URL, environment: [String: String], workingDirectory: URL) {
        let runtime = try resolveRuntime()
        let dataDir = URL(filePath: settings.dataDirectory, directoryHint: .isDirectory)
        return (runtime.python, environment(runtime, dataDir: dataDir), runtime.root)
    }

    /// 抓取阶段要调 ffmpeg / ffprobe（转码、测时长、封面）。缺了它们后端照样起得来，
    /// 但每一集都会在下载之后失败——不如在启动时就说清楚。
    /// deno 只给 YouTube 解 JS 挑战用，缺了 yt-dlp 目前仍能退而求其次，所以只记日志。
    private func checkTools(_ env: [String: String]) -> String? {
        let dirs = (env["PATH"] ?? "").split(separator: ":").map(String.init)
        func find(_ tool: String) -> Bool {
            dirs.contains { FileManager.default.isExecutableFile(atPath: "\($0)/\(tool)") }
        }
        if !find("deno") {
            appendLog("警告：PATH 上没有 deno，YouTube 解析可能缺格式。\n")
        }
        let missing = ["ffmpeg", "ffprobe"].filter { !find($0) }
        guard !missing.isEmpty else { return nil }
        return tr("找不到 \(missing.joined(separator: "、"))。抓取音频要用它们转码。找过：\n",
                  "Can’t find \(missing.joined(separator: ", ")), needed to convert downloaded audio. Looked in:\n")
            + dirs.joined(separator: "\n")
            + tr("\n\n用 Homebrew 装一个（brew install ffmpeg），或使用打包好的 Podsum.app。",
                 "\n\nInstall it with Homebrew (brew install ffmpeg), or use the packaged Podsum.app.")
    }

    private func environment(_ runtime: Runtime, dataDir: URL) -> [String: String] {
        var env = settings.environment(dataDirectory: dataDir)

        // 顺序即优先级：源码 → 用户更新过的解析组件 → 内嵌依赖。
        // 组件目录在这里解析一次符号链接：之后再切版本，这个进程也不受影响。
        let components = ComponentUpdater.activeDirectory().map { [$0] } ?? []
        let pythonPath = ([runtime.root.appending(path: "backend/src")] + components + runtime.extraPythonPath)
            .map { $0.path(percentEncoded: false) }
            .joined(separator: ":")
        env["PYTHONPATH"] = pythonPath
        env["PYTHONUNBUFFERED"] = "1"
        // 不往 .app 里写 __pycache__：包内字节码已在打包时预编译，
        // 运行期再写会让签名失效（codesign 报 sealed resource invalid）。
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        // 从 Finder 启动时 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin。
        // 打包的 app 自带 ffmpeg / ffprobe / deno，放最前面；
        // 从源码跑时它们在 Homebrew 里——不补上，抓取阶段必然失败。
        let inherited = ProcessInfo.processInfo.environment["PATH"] ?? ""
        let home = FileManager.default.homeDirectoryForCurrentUser.path(percentEncoded: false)
        let bundledTools = runtime.toolsDirectory.map { [$0.path(percentEncoded: false)] } ?? []
        let extra = bundledTools + ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin"]
        var parts = extra + inherited.split(separator: ":").map(String.init)
        parts += ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        var seen = Set<String>()
        env["PATH"] = parts.filter { seen.insert($0).inserted }.joined(separator: ":")

        env["HOME"] = home
        env["LANG"] = ProcessInfo.processInfo.environment["LANG"] ?? "en_US.UTF-8"
        return env
    }

    // MARK: 子进程

    private func runMigrations(_ runtime: Runtime, env: [String: String]) async throws {
        let p = Process()
        p.executableURL = runtime.python
        p.arguments = [runtime.root.appending(path: "scripts/init_db.py").path(percentEncoded: false)]
        p.currentDirectoryURL = runtime.root
        p.environment = env

        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        try p.run()
        let output = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        appendLog("--- init_db (exit \(p.terminationStatus)) ---\n" + (String(data: output, encoding: .utf8) ?? ""))

        if p.terminationStatus != 0 {
            let text = String(data: output, encoding: .utf8) ?? ""
            throw NSError(domain: "Podsum", code: 1, userInfo: [
                NSLocalizedDescriptionKey: tr("数据库迁移失败：\n", "Database migration failed:\n") + Self.lastLines(text, 12),
            ])
        }
    }

    private func launch(_ runtime: Runtime, env: [String: String]) throws {
        appendLog("\n=== uvicorn 启动 \(Date().formatted()) ===\n")
        let handle = try FileHandle(forWritingTo: Self.logURL)
        handle.seekToEndOfFile()
        logHandle = handle

        let p = Process()
        p.executableURL = runtime.python
        p.arguments = [
            "-m", "uvicorn", "podsum.main:app",
            "--host", "127.0.0.1",
            "--port", String(settings.port),
        ]
        p.currentDirectoryURL = runtime.root
        p.environment = env
        p.standardOutput = handle
        p.standardError = handle
        try p.run()
        process = p
    }

    // MARK: 探测与日志

    static func healthy(_ baseURL: URL) async -> Bool {
        var request = URLRequest(url: baseURL.appending(path: "api/health"))
        request.timeoutInterval = 2
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 2
        guard let (data, response) = try? await URLSession(configuration: config).data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200,
              let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return false }
        return body["status"] as? String == "ok"
    }

    private func appendLog(_ text: String) {
        let fm = FileManager.default
        if !fm.fileExists(atPath: Self.logURL.path(percentEncoded: false)) {
            fm.createFile(atPath: Self.logURL.path(percentEncoded: false), contents: nil)
        }
        guard let h = try? FileHandle(forWritingTo: Self.logURL) else { return }
        h.seekToEndOfFile()
        try? h.write(contentsOf: Data(text.utf8))
        try? h.close()
    }

    static func tail(of url: URL, lines: Int = 20) -> String {
        guard let text = try? String(contentsOf: url, encoding: .utf8) else { return "" }
        return lastLines(text, lines)
    }

    static func lastLines(_ text: String, _ n: Int) -> String {
        text.split(separator: "\n", omittingEmptySubsequences: false).suffix(n).joined(separator: "\n")
    }
}
