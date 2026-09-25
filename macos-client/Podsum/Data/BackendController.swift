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
        let dir = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appending(path: "Logs/Podsum", directoryHint: .isDirectory)
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
    }

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
        return Runtime(python: python, root: root, extraPythonPath: extras)
    }

    private func environment(_ runtime: Runtime, dataDir: URL) -> [String: String] {
        var env = settings.environment(dataDirectory: dataDir)

        let pythonPath = ([runtime.root.appending(path: "backend/src")] + runtime.extraPythonPath)
            .map { $0.path(percentEncoded: false) }
            .joined(separator: ":")
        env["PYTHONPATH"] = pythonPath
        env["PYTHONUNBUFFERED"] = "1"

        // 从 Finder 启动时 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin，
        // yt-dlp 与 ffmpeg 都在 Homebrew 里——不补上，抓取阶段必然失败。
        let inherited = ProcessInfo.processInfo.environment["PATH"] ?? ""
        let home = FileManager.default.homeDirectoryForCurrentUser.path(percentEncoded: false)
        let extra = ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin"]
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
