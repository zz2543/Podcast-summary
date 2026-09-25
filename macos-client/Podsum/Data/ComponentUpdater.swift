import Foundation
import Observation

/// 「更新解析组件」：让用户自己把 yt-dlp 升到最新，不必等重新发包。
///
/// YouTube / B 站隔几周到几个月就会改一次接口，旧版 yt-dlp 随之失效（研究记录里
/// 7 月版对 YouTube 全部 403，8 月版才恢复）。包里那份只作保底；更新装在 bundle 外面：
///
///     ~/Library/Application Support/Podsum/components/
///         active -> yt-dlp-2026.09.20-1A2B3C   当前生效的那份（符号链接）
///         yt-dlp-2026.09.20-1A2B3C/            pip --target 装出来的 yt_dlp + yt_dlp_ejs
///
/// 为什么每次装进新目录、再切链接，而不是原地覆盖：后端进程里的 yt-dlp 是懒加载提取器的，
/// 文件在它脚下被换掉，就会出现半新半旧的模块。`BackendController` 只在启动时解析一次
/// `active`，于是正在跑的后端一直用旧目录，重启后才换新——旧目录在那时清掉。
///
/// 不碰 `.app`，签名不受影响；升级 app 也不会覆盖它。
@MainActor
@Observable
final class ComponentUpdater {
    enum State: Equatable {
        case idle
        case working(String)
        case upToDate(String)
        case updated(from: String, to: String)
        case reverted
        case failed(String)

        var isWorking: Bool { if case .working = self { return true }; return false }
    }

    struct Installed: Equatable {
        let version: String
        /// true = 用户更新过的那份；false = 包里内嵌（或开发环境里）的那份
        let isUpdated: Bool
    }

    private(set) var state: State = .idle
    /// 后端**下次启动**会加载的版本。正在跑的后端可能还是旧的，见 `needsRestart`。
    private(set) var installed: Installed?
    /// 切过版本、后端还没重启
    private(set) var needsRestart = false
    /// pip 输出的尾巴，失败时给人看
    private(set) var log = ""

    private let backend: BackendController

    init(backend: BackendController) {
        self.backend = backend
    }

    nonisolated static var root: URL { BackendController.componentsDirectory }
    nonisolated static var activeLink: URL { root.appending(path: "active") }

    // MARK: 查询

    func refresh() async {
        guard let context = try? backend.pythonContext() else { installed = nil; return }
        installed = await Self.probe(context.python, environment: context.environment,
                                     workingDirectory: context.workingDirectory)
    }

    // MARK: 更新

    func update() async {
        guard !state.isWorking else { return }
        log = ""
        let context: (python: URL, environment: [String: String], workingDirectory: URL)
        do { context = try backend.pythonContext() }
        catch { state = .failed(error.localizedDescription); return }

        let current = await Self.probe(context.python, environment: context.environment,
                                       workingDirectory: context.workingDirectory)
        let fm = FileManager.default
        let staging = Self.root.appending(path: "staging-\(UUID().uuidString.prefix(8))", directoryHint: .isDirectory)
        defer { try? fm.removeItem(at: staging) }

        do {
            try fm.createDirectory(at: Self.root, withIntermediateDirectories: true)

            // 1. 装进一个全新的暂存目录。--no-deps：只换解析器本身，
            //    不让它顺带升级 requests 之类、遮住内嵌依赖里验证过的版本。
            //    不指定索引：尊重用户自己的 pip.conf（国内用户常配了镜像）。
            state = .working(tr("下载最新版…", "Downloading the latest version…"))
            var pipEnv = context.environment
            pipEnv.removeValue(forKey: "PYTHONPATH")
            let pip = await Self.run(context.python, [
                "-m", "pip", "install", "--upgrade", "--no-deps", "--no-input",
                "--disable-pip-version-check", "--target", staging.path(percentEncoded: false),
                "yt-dlp", "yt-dlp-ejs",
            ], environment: pipEnv, workingDirectory: context.workingDirectory)
            log = BackendController.lastLines(pip.output, 12)
            guard pip.status == 0 else {
                state = .failed(tr("下载失败（pip 退出码 \(pip.status)）。检查网络后再试；原来的组件没有改动。",
                                   "Download failed (pip exit code \(pip.status)). Check your connection and try again — nothing was changed."))
                return
            }

            // 2. 用后端将要用的那套路径验一遍：真的 import 得了、确实是暂存目录里那份
            state = .working(tr("校验…", "Verifying…"))
            var checkEnv = context.environment
            checkEnv["PYTHONPATH"] = Self.replacingComponents(in: context.environment["PYTHONPATH"] ?? "",
                                                              with: staging)
            guard let fresh = await Self.probe(context.python, environment: checkEnv,
                                               workingDirectory: context.workingDirectory,
                                               expectUnder: staging) else {
                state = .failed(tr("新版本装上了但导入失败，已丢弃；原来的组件没有改动。详见下方输出。",
                                   "The new version installed but failed to import, so it was discarded — nothing was changed. See the output below."))
                return
            }

            // 3. 不比现在的新就不切（镜像可能滞后，别把人降级了）
            if let current, Self.compare(fresh.version, current.version) != .orderedDescending {
                state = .upToDate(current.version)
                return
            }

            // 4. 挪成正式目录，原子地切换 active 链接
            let destination = Self.root.appending(path: "yt-dlp-\(fresh.version)-\(UUID().uuidString.prefix(6))",
                                            directoryHint: .isDirectory)
            try fm.moveItem(at: staging, to: destination)
            try Self.pointActive(to: destination)

            installed = Installed(version: fresh.version, isUpdated: true)
            needsRestart = true
            state = .updated(from: current?.version ?? "?", to: fresh.version)
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    /// 回到包里内嵌的那份：去掉 active 链接即可，目录在后端下次启动时清掉。
    func revertToBundled() async {
        try? FileManager.default.removeItem(at: Self.activeLink)
        needsRestart = true
        state = .reverted
        await refresh()
    }

    func restartBackend() async {
        state = .working(tr("重启后端…", "Restarting the backend…"))
        await backend.restart()
        needsRestart = false
        state = .idle
        await refresh()
    }

    // MARK: 给 BackendController 用

    /// 当前生效的组件目录（已解析符号链接）；没有就返回 nil。
    nonisolated static func activeDirectory() -> URL? {
        let link = activeLink.path(percentEncoded: false)
        guard let target = try? FileManager.default.destinationOfSymbolicLink(atPath: link) else { return nil }
        let resolved = URL(filePath: target, directoryHint: .isDirectory,
                           relativeTo: root).standardizedFileURL
        return FileManager.default.fileExists(atPath: resolved.path(percentEncoded: false)) ? resolved : nil
    }

    /// 后端启动前调用：删掉不再生效的旧版本与没装完的暂存目录。
    /// 此时旧的后端进程已经停了，不会有人还在用它们。
    nonisolated static func pruneInactive() {
        let fm = FileManager.default
        let keep = activeDirectory()?.lastPathComponent
        guard let entries = try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else { return }
        for entry in entries where entry.lastPathComponent != "active" && entry.lastPathComponent != keep {
            try? fm.removeItem(at: entry)
        }
    }

    // MARK: 内部

    private static func pointActive(to directory: URL) throws {
        // 先建临时链接再 rename 覆盖：rename 是原子的，任何时刻 active 要么指旧的要么指新的
        let tmp = root.appending(path: "active.tmp")
        try? FileManager.default.removeItem(at: tmp)
        try FileManager.default.createSymbolicLink(atPath: tmp.path(percentEncoded: false),
                                                   withDestinationPath: directory.lastPathComponent)
        guard rename(tmp.path(percentEncoded: false), activeLink.path(percentEncoded: false)) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
        }
    }

    /// 把 PYTHONPATH 里的组件目录换成 `replacement`；原来没有就插在第二位（源码之后）。
    private static func replacingComponents(in pythonPath: String, with replacement: URL) -> String {
        let rootPath = root.path(percentEncoded: false)
        var parts = pythonPath.split(separator: ":").map(String.init)
            .filter { !$0.hasPrefix(rootPath) }
        parts.insert(replacement.path(percentEncoded: false), at: min(1, parts.count))
        return parts.joined(separator: ":")
    }

    /// 问解释器：import 到的 yt-dlp 是哪个版本、来自哪里。
    private static func probe(_ python: URL, environment: [String: String], workingDirectory: URL,
                              expectUnder: URL? = nil) async -> Installed? {
        let script = "import yt_dlp, yt_dlp.version as v\n"
            + (expectUnder != nil ? "import yt_dlp_ejs\n" : "")
            + "print(v.__version__); print(yt_dlp.__file__)"
        let result = await run(python, ["-c", script], environment: environment, workingDirectory: workingDirectory)
        let lines = result.output.split(separator: "\n").map(String.init)
        guard result.status == 0, lines.count >= 2 else { return nil }
        let version = lines[lines.count - 2].trimmingCharacters(in: .whitespaces)
        let file = URL(filePath: lines[lines.count - 1]).standardizedFileURL.path(percentEncoded: false)
        if let expectUnder, !file.hasPrefix(expectUnder.standardizedFileURL.path(percentEncoded: false)) {
            return nil
        }
        return Installed(version: version,
                         isUpdated: file.hasPrefix(root.standardizedFileURL.path(percentEncoded: false)))
    }

    /// yt-dlp 的版本号是日期：2026.08.19 / 2026.9.20.1。逐段按数字比。
    nonisolated static func compare(_ a: String, _ b: String) -> ComparisonResult {
        let x = a.split(separator: ".").map { Int($0) ?? 0 }
        let y = b.split(separator: ".").map { Int($0) ?? 0 }
        for i in 0..<max(x.count, y.count) {
            let l = i < x.count ? x[i] : 0, r = i < y.count ? y[i] : 0
            if l != r { return l < r ? .orderedAscending : .orderedDescending }
        }
        return .orderedSame
    }

    private static func run(_ executable: URL, _ arguments: [String], environment: [String: String],
                            workingDirectory: URL) async -> (status: Int32, output: String) {
        await Task.detached {
            let p = Process()
            p.executableURL = executable
            p.arguments = arguments
            p.environment = environment
            p.currentDirectoryURL = workingDirectory
            let pipe = Pipe()
            p.standardOutput = pipe
            p.standardError = pipe
            do { try p.run() } catch { return (-1, error.localizedDescription) }
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            return (p.terminationStatus, String(data: data, encoding: .utf8) ?? "")
        }.value
    }
}
