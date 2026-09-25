import AppKit
import Observation

/// 一次快捷提交：按全局快捷键送进来的一个链接，以及它的去向。
struct QuickAddItem: Codable, Identifiable, Hashable {
    enum Source: String, Codable {
        /// 书签入口已经删掉；留着这个值只为读得出之前存下的记录
        case bookmarklet, hotkeyBrowser, hotkeyClipboard

        var label: String {
            switch self {
            case .bookmarklet:     return tr("书签", "Bookmarklet")
            case .hotkeyBrowser:   return tr("快捷键 · 浏览器", "Hotkey · Browser")
            case .hotkeyClipboard: return tr("快捷键 · 剪贴板", "Hotkey · Clipboard")
            }
        }
    }

    enum State: String, Codable {
        case queued, submitting, added, existing, unrecognized, failed

        var isTerminal: Bool { ![.queued, .submitting].contains(self) }

        var label: String {
            switch self {
            case .queued:       return tr("排队中", "Queued")
            case .submitting:   return tr("提交中", "Submitting")
            case .added:        return tr("已加入", "Added")
            case .existing:     return tr("已在库里", "Already in library")
            case .unrecognized: return tr("无法识别", "Not recognized")
            case .failed:       return tr("失败", "Failed")
            }
        }
    }

    var id = UUID()
    /// 原始输入：地址栏里的链接，或剪贴板里的整段文字（截断）
    var input: String
    /// 规整后的视频链接；无法识别时为 nil
    var url: String?
    var source: Source
    var receivedAt = Date()
    var state: State
    var title: String?
    var episodeID: String?
    /// 失败原因，或无法识别时的说明
    var message: String?

    var display: String { title ?? url ?? input }
}

/// 快捷提交的队列与记录。
///
/// 全局快捷键送来的链接都进这里。链接先落盘再提交，
/// 后端没就绪就等着，app 退出再启动也接着提交——送进来的链接不丢。
///
/// 一次只提交一条：后端确认一个视频要先把音频抓完（几十秒），
/// 同时压过去几条只会一起慢。
@MainActor
@Observable
final class QuickAddCenter {
    /// 新的在前。未完成的全部保留，已完成的只留最近 `historyLimit` 条。
    private(set) var items: [QuickAddItem] = []

    /// 有一集成功加入时回调，列表页据此刷新
    @ObservationIgnored var onAdded: (() -> Void)?

    private let backend: BackendController
    private let notifier = QuickAddNotifier.shared
    private let storeURL: URL
    private var pumping = false

    static let historyLimit = 50

    init(backend: BackendController, storeURL: URL = QuickAddCenter.defaultStoreURL) {
        self.backend = backend
        self.storeURL = storeURL
        load()
        observeBackend()
    }

    nonisolated static var defaultStoreURL: URL {
        AppStorageRoot.support.appending(path: "quick-add.json")
    }

    var pending: [QuickAddItem] { items.filter { !$0.state.isTerminal } }

    // MARK: 入口

    /// 全局快捷键：前台是受支持的浏览器就读当前标签页，否则读剪贴板。
    func hotKeyPressed() {
        let front = NSWorkspace.shared.frontmostApplication
        guard let bundleID = front?.bundleIdentifier, BrowserTab.isSupported(bundleID) else {
            receiveClipboard(browserNote: nil)
            return
        }
        Task {
            switch await BrowserTab.read(bundleID) {
            case .url(let address):
                // 以当前标签页为准：它不是视频就直说，不去剪贴板里捡一个用户没在看的链接
                receive(address, source: .hotkeyBrowser)
            case .notAuthorized:
                let name = BrowserTab.supported[bundleID] ?? bundleID
                receiveClipboard(browserNote: tr(
                    "读不到 \(name) 当前页面的地址：Podsum 还没被允许控制它。到「系统设置 › 隐私与安全性 › 自动化」里打开 Podsum 下的 \(name)，或者先复制链接再按快捷键。",
                    "Couldn’t read the page address from \(name): Podsum isn’t allowed to control it. Turn on \(name) under Podsum in System Settings › Privacy & Security › Automation, or copy the link first and press the hotkey again."))
            case .unavailable:
                receiveClipboard(browserNote: nil)
            }
        }
    }

    private func receiveClipboard(browserNote: String?) {
        let text = NSPasteboard.general.string(forType: .string)?.trimmed ?? ""
        if VideoLink.recognize(text) != nil {
            receive(text, source: .hotkeyClipboard)
            return
        }
        let reason = browserNote ?? (text.isEmpty
            ? tr("剪贴板里没有文字。在 B 站等 app 里先点「复制链接」，再按快捷键。",
                 "The clipboard has no text. Tap “Copy link” in the app first, then press the hotkey.")
            : tr("剪贴板里没有 B 站或 YouTube 的视频链接。",
                 "The clipboard has no Bilibili or YouTube video link."))
        reject(input: String(text.prefix(200)), source: .hotkeyClipboard, reason: reason)
    }

    /// 所有入口汇到这里
    func receive(_ raw: String, source: QuickAddItem.Source) {
        let input = String(raw.trimmed.prefix(500))
        guard let url = VideoLink.recognize(input) else {
            reject(input: input, source: source,
                   reason: tr("只收 B 站与 YouTube 的单个视频。", "Only single Bilibili or YouTube videos are accepted."))
            return
        }

        if let twin = items.first(where: { $0.url == url && !$0.state.isTerminal }) {
            notifier.post(id: UUID().uuidString, title: tr("已在队列中", "Already queued"), body: twin.display)
            return
        }

        let item = QuickAddItem(input: input, url: url, source: source, state: .queued)
        items.insert(item, at: 0)
        trimAndSave()
        notifier.post(id: item.id.uuidString, title: receivedTitle, body: url)
        pump()
    }

    private func reject(input: String, source: QuickAddItem.Source, reason: String) {
        let item = QuickAddItem(input: input, source: source, state: .unrecognized, message: reason)
        items.insert(item, at: 0)
        trimAndSave()
        notifier.post(id: item.id.uuidString, title: tr("这不是可识别的视频链接", "Not a recognized video link"), body: reason)
    }

    /// 「已收到」的说法随后端状态变：没就绪时要说清楚链接已经存下了
    private var receivedTitle: String {
        switch backend.phase {
        case .ready:
            return pending.count > 1
                ? tr("已收到，前面还有 \(pending.count - 1) 个", "Received — \(pending.count - 1) ahead of it")
                : tr("已收到，正在提交", "Received — submitting")
        case .needsConfiguration:
            return tr("Podsum 还没配置好，链接已保存", "Podsum isn’t set up yet — link saved")
        default:
            return tr("已收到，等 Podsum 准备好后提交", "Received — will submit once Podsum is ready")
        }
    }

    // MARK: 记录上的动作

    func retry(_ id: QuickAddItem.ID) {
        guard let i = items.firstIndex(where: { $0.id == id }), items[i].url != nil else { return }
        items[i].state = .queued
        items[i].message = nil
        save()
        pump()
    }

    func clearFinished() {
        items.removeAll { $0.state.isTerminal }
        save()
    }

    // MARK: 提交

    /// 逐条提交排队中的链接，直到队列空或后端不可用。
    private func pump() {
        guard !pumping else { return }
        pumping = true
        Task {
            defer { pumping = false }
            while let next = items.last(where: { $0.state == .queued }),
                  let baseURL = backend.phase.baseURL {
                let keepGoing = await submit(next.id, to: baseURL)
                if !keepGoing { break }
            }
        }
    }

    /// 返回 false 表示后端掉了，该停下来等它回来。
    private func submit(_ id: QuickAddItem.ID, to baseURL: URL) async -> Bool {
        guard let url = items.first(where: { $0.id == id })?.url else { return true }
        update(id) { $0.state = .submitting }

        // 后端要把音频抓完才回响应，中途不发任何字节，超时放宽到 15 分钟
        let repository = LiveRepository(baseURL: baseURL, requestTimeout: 900)
        do {
            let created = try await repository.create(Submission(items: [.link(url, sourceType: .youtube)]))
            let episode = created.first?.episode
            update(id) {
                $0.state = .added
                $0.title = episode?.title
                $0.episodeID = episode?.id
            }
            notifier.post(id: id.uuidString,
                          title: tr("已加入", "Added"),
                          body: episode?.displayTitle ?? url,
                          episodeID: episode?.id)
            onAdded?()
        } catch RepositoryError.conflict(_, let existing) {
            update(id) {
                $0.state = .existing
                $0.episodeID = existing
            }
            notifier.post(id: id.uuidString,
                          title: tr("这一集已经在库里了", "Already in your library"),
                          body: url, episodeID: existing)
        } catch {
            // 连不上：多半是后端正在重启。放回队列，等它回来再提交。
            if case RepositoryError.transport = error, await !BackendController.healthy(baseURL) {
                update(id) { $0.state = .queued }
                return false
            }
            let reason = error.localizedDescription
            update(id) {
                $0.state = .failed
                $0.message = reason
            }
            notifier.post(id: id.uuidString, title: tr("没能加入", "Couldn’t add"), body: reason)
        }
        return true
    }

    private func update(_ id: QuickAddItem.ID, _ change: (inout QuickAddItem) -> Void) {
        guard let i = items.firstIndex(where: { $0.id == id }) else { return }
        change(&items[i])
        save()
    }

    /// 后端一就绪就把积压的链接送出去（刚启动、改完设置重启、配置刚补齐）
    private func observeBackend() {
        withObservationTracking {
            _ = backend.phase
        } onChange: { [weak self] in
            Task { @MainActor in
                guard let self else { return }
                if self.backend.phase.baseURL != nil { self.pump() }
                self.observeBackend()
            }
        }
    }

    // MARK: 落盘

    private func load() {
        guard let data = try? Data(contentsOf: storeURL),
              let stored = try? Self.decoder.decode([QuickAddItem].self, from: data) else { return }
        // 上次退出时正在提交的，重新排队。若后端其实已经建好了，
        // 再提交会得到「已在库里」，不会多出一集。
        items = stored.map { item in
            var item = item
            if item.state == .submitting { item.state = .queued }
            return item
        }
    }

    private func trimAndSave() {
        var kept = 0
        items.removeAll { item in
            guard item.state.isTerminal else { return false }
            kept += 1
            return kept > Self.historyLimit
        }
        save()
    }

    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    private func save() {
        do {
            try FileManager.default.createDirectory(at: storeURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Self.encoder.encode(items).write(to: storeURL, options: .atomic)
        } catch {
            NSLog("Podsum quick-add: couldn’t save queue: \(error)")
        }
    }
}
