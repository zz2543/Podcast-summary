import Foundation

/// 真后端。`baseURL` 指向 `BackendController` 拉起的 uvicorn（或用户填的外部地址）。
///
/// 两个刻意的选择：
///
/// 1. **音频优先走 `file://`。** 后端就在本机，数据目录的绝对路径 app 自己配的，
///    直接读文件比走 HTTP 少一层，拖动进度条也不依赖服务端的 Range 支持。
///    找不到文件才回退到 `/files/audio`（连外部后端时就是这条路）。
/// 2. **错误体按后端的信封解。** `{"error":{"code","message"}}` 里的 code
///    是可判定的（conflict / not_found / tts_disabled…），界面据此给不同提示，
///    而不是把 HTTP 状态码丢给读者。
public struct LiveRepository: EpisodeRepository {
    public let baseURL: URL
    /// 数据目录的绝对路径，用于把音频落到 file://。外部后端模式下为 nil。
    public let dataRoot: URL?
    /// 后端的工作目录，用于解析 artifact_paths 里的相对路径
    public let backendRoot: URL?

    private let session: URLSession
    /// 只给「新建剧集」用。后端要把音频抓完才回响应，中途一个字节都不发，
    /// B 站慢的时候一集要下好几分钟——按普通请求的超时算，客户端先报错，后端照样建出来。
    private let submitSession: URLSession

    /// `requestTimeout` 是两段数据之间最长的沉默。视频提交要等后端把音频抓完
    /// 才回响应，中途一个字节都不发——快捷提交因此要放得很宽，
    /// 否则客户端先超时报错，后端却照样把这一集建出来了。
    public init(baseURL: URL, dataRoot: URL? = nil, backendRoot: URL? = nil, requestTimeout: TimeInterval = 30) {
        self.baseURL = baseURL
        self.dataRoot = dataRoot
        self.backendRoot = backendRoot
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = requestTimeout
        // 抓取一集要几分钟，但那是后端的事；这里只等 HTTP 响应头。
        config.timeoutIntervalForResource = 600
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)

        let submit = URLSessionConfiguration.default
        submit.timeoutIntervalForRequest = max(requestTimeout, Self.submitTimeout)
        submit.timeoutIntervalForResource = max(requestTimeout, Self.submitTimeout)
        submit.waitsForConnectivity = false
        self.submitSession = URLSession(configuration: submit)
    }

    /// 新建剧集最多等 15 分钟
    static let submitTimeout: TimeInterval = 900

    // MARK: 读

    public func list() async throws -> [EpisodeSummary] {
        // 分页尚未实现（next_cursor 恒为 null，cursor 参数被后端丢弃），
        // 一次取满 limit 上限 200。
        try await get(EpisodeListResponse.self, path: "api/episodes", query: ["limit": "200"]).items
    }

    public func detail(id: String) async throws -> EpisodeDetail {
        try await get(EpisodeDetail.self, path: "api/episodes/\(escape(id))")
    }

    // MARK: 写

    public func create(_ submission: Submission) async throws -> [CreateEpisodeResponse] {
        guard !submission.items.isEmpty else { return [] }
        if submission.items.count == 1 {
            return [try await createOne(submission.items[0], style: submission.style)]
        }
        return try await createBatch(submission)
    }

    private func createOne(_ item: Submission.Item, style: SummaryStyleInput) async throws -> CreateEpisodeResponse {
        switch item {
        case .link(let ref, let sourceType):
            var body: [String: String] = ["source_type": sourceType.rawValue, "source_ref": ref.trimmed]
            body.merge(style.fields) { a, _ in a }
            return try await send(CreateEpisodeResponse.self, "POST", "api/episodes", json: body, slow: true)

        case .file(let url):
            var form = MultipartBody()
            form.addField("source_type", "local_file")
            for (key, value) in style.fields { form.addField(key, value) }
            try form.addFile(url, name: "file")
            return try await send(CreateEpisodeResponse.self, "POST", "api/episodes", multipart: form, slow: true)
        }
    }

    private func createBatch(_ submission: Submission) async throws -> [CreateEpisodeResponse] {
        let files = submission.items.filter(\.isFile)
        guard files.isEmpty || files.count == submission.items.count else {
            // 后端的 /batch 对文件与链接走两条路，混着发只会 400。
            // 与其让读者看后端报错，不如在这里拆成两次请求。
            let fileHalf = Submission(items: files, style: submission.style)
            let linkHalf = Submission(items: submission.items.filter { !$0.isFile }, style: submission.style)
            return try await create(fileHalf) + create(linkHalf)
        }

        if files.isEmpty {
            let items: [[String: String]] = submission.items.compactMap { item in
                guard case .link(let ref, let sourceType) = item else { return nil }
                return ["source_type": sourceType.rawValue, "source_ref": ref.trimmed]
            }
            var body: [String: Any] = ["items": items]
            for (key, value) in submission.style.fields { body[key] = value }
            return try await send(CreateEpisodeBatchResponse.self, "POST", "api/episodes/batch", jsonAny: body, slow: true).items
        }

        var form = MultipartBody()
        for (key, value) in submission.style.fields { form.addField(key, value) }
        for item in submission.items {
            if case .file(let url) = item { try form.addFile(url, name: "files") }
        }
        return try await send(CreateEpisodeBatchResponse.self, "POST", "api/episodes/batch", multipart: form, slow: true).items
    }

    public func retry(id: String) async throws -> Job {
        try await send(Job.self, "POST", "api/episodes/\(escape(id))/retry")
    }

    public func delete(id: String) async throws {
        _ = try await raw("DELETE", "api/episodes/\(escape(id))")
    }

    public func requestDigest(id: String) async throws -> DigestResponse {
        try await send(DigestResponse.self, "POST", "api/episodes/\(escape(id))/digest")
    }

    // MARK: 对话（SSE）

    public func chat(id: String, message: String, history: [ChatTurn]) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = URLRequest(url: baseURL.appending(path: "api/episodes/\(escape(id))/chat"))
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.httpBody = try JSONEncoder().encode(
                        ChatRequest(message: message, history: history)
                    )

                    let (bytes, response) = try await session.bytes(for: request)
                    guard let http = response as? HTTPURLResponse else {
                        throw RepositoryError.transport(tr("没有拿到 HTTP 响应", "No HTTP response"))
                    }
                    guard http.statusCode == 200 else {
                        // 错误体是一整个 JSON，不是 SSE——要把字节收完再解。
                        var data = Data()
                        for try await byte in bytes { data.append(byte) }
                        throw Self.decodeError(status: http.statusCode, data: data)
                    }

                    for try await line in bytes.lines {
                        guard line.hasPrefix("data: ") else { continue }
                        let payload = String(line.dropFirst(6))
                        if payload == "[DONE]" { break }
                        guard let chunk = try? JSONDecoder().decode(ChatChunk.self, from: Data(payload.utf8)) else { continue }
                        if let error = chunk.error {
                            throw RepositoryError.api(code: "llm_error", message: error, status: 200)
                        }
                        if let token = chunk.token { continuation.yield(token) }
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private struct ChatRequest: Encodable {
        let message: String
        let history: [ChatTurn]
    }

    private struct ChatChunk: Decodable {
        let token: String?
        let error: String?
    }

    // MARK: 文件

    public func audioURL(for episode: EpisodeDetail) -> URL? {
        if let local = dataRoot?.appending(path: "\(episode.id)/audio.normalized.mp3"),
           FileManager.default.fileExists(atPath: local.path(percentEncoded: false)) {
            return local
        }
        // 外部后端、或数据目录不在本机：走 HTTP。Starlette 的 FileResponse
        // 支持 Range，AVPlayer 因此仍能拖动。
        return baseURL.appending(path: "api/episodes/\(escape(episode.id))/files/audio")
    }

    public func digestURL(for episode: EpisodeDetail) -> URL? {
        guard episode.stageStatus.tts.value == .present else { return nil }
        if let path = episode.artifactPaths?.tts, let local = resolve(path),
           FileManager.default.fileExists(atPath: local.path(percentEncoded: false)) {
            return local
        }
        return baseURL.appending(path: "api/episodes/\(escape(episode.id))/files/digest")
    }

    public func coverURL(for episode: EpisodeSummary) -> URL? {
        if let local = dataRoot?.appending(path: "\(episode.id)/cover.jpg"),
           FileManager.default.fileExists(atPath: local.path(percentEncoded: false)) {
            return local
        }
        guard episode.hasCover == true else { return nil }
        return baseURL.appending(path: "api/episodes/\(escape(episode.id))/files/cover")
    }

    /// artifact_paths 里的路径可能是绝对的（app 传了绝对 DATA_DIR），
    /// 也可能是 "data/<ULID>/summary.md" 这种相对仓库根的老数据。
    private func resolve(_ path: String) -> URL? {
        if path.hasPrefix("/") { return URL(filePath: path) }
        return backendRoot?.appending(path: path)
    }

    // MARK: 实时事件

    public func jobEvents() -> AsyncStream<JobEvent> {
        AsyncStream { continuation in
            let socket = JobSocket(baseURL: baseURL, continuation: continuation)
            socket.start()
            continuation.onTermination = { _ in socket.stop() }
        }
    }

    // MARK: 分类（004）

    public func categories() async throws -> CategoryList {
        try await get(CategoryList.self, path: "api/categories")
    }

    public func createCategory(name: String) async throws -> EpisodeCategory {
        try await send(EpisodeCategory.self, "POST", "api/categories", json: ["name": name])
    }

    public func renameCategory(id: String, name: String) async throws -> EpisodeCategory {
        try await send(EpisodeCategory.self, "PATCH", "api/categories/\(escape(id))", json: ["name": name])
    }

    public func deleteCategory(id: String) async throws -> Int {
        try await send(Released.self, "DELETE", "api/categories/\(escape(id))").released
    }

    public func reorderCategories(ids: [String]) async throws -> CategoryList {
        try await send(CategoryList.self, "PUT", "api/categories/order", jsonAny: ["ids": ids])
    }

    public func setCategory(episodeID: String, categoryID: String?) async throws -> CategoryAssignment {
        try await send(CategoryAssignment.self, "PUT", "api/episodes/\(escape(episodeID))/category",
                       jsonAny: ["category_id": categoryID.map { $0 as Any } ?? NSNull()])
    }

    public func releaseCategory(episodeID: String) async throws -> CategoryAssignment {
        try await send(CategoryAssignment.self, "POST", "api/episodes/\(escape(episodeID))/category/release")
    }

    public func startCategorize() async throws -> String {
        try await send(RunStarted.self, "POST", "api/categorize").runID
    }

    public func categorizeRun(id: String) async throws -> CategorizeRun {
        try await get(CategorizeRun.self, path: "api/categorize/\(escape(id))")
    }

    public func cancelCategorize(id: String) async throws {
        _ = try await raw("DELETE", "api/categorize/\(escape(id))")
    }

    public func applyCategorization(_ apply: CategorizeApply) async throws -> CategorizeApplyResult {
        let body: [String: Any] = [
            "new_categories": apply.newCategories.map { ["key": $0.key, "name": $0.name] },
            "assignments": apply.assignments.map { row -> [String: Any] in
                ["episode_id": row.episodeID,
                 "from_category_id": row.fromCategoryID.map { $0 as Any } ?? NSNull(),
                 "to_key": row.toKey]
            },
        ]
        return try await send(CategorizeApplyResult.self, "POST", "api/categories/apply", jsonAny: body)
    }

    private struct Released: Decodable { let released: Int }

    private struct RunStarted: Decodable {
        let runID: String
        enum CodingKeys: String, CodingKey { case runID = "run_id" }
    }

    // MARK: HTTP 脚手架

    private func escape(_ value: String) -> String {
        value.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? value
    }

    private func get<T: Decodable>(_ type: T.Type, path: String, query: [String: String] = [:]) async throws -> T {
        var components = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!)
        request.httpMethod = "GET"
        return try decode(type, from: try await perform(request))
    }

    private func send<T: Decodable>(
        _ type: T.Type, _ method: String, _ path: String,
        json: [String: String]? = nil,
        jsonAny: [String: Any]? = nil,
        multipart: MultipartBody? = nil,
        slow: Bool = false
    ) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        if let json {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: json)
        } else if let jsonAny {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: jsonAny)
        } else if let multipart {
            request.setValue(multipart.contentType, forHTTPHeaderField: "Content-Type")
            request.httpBody = multipart.finished()
        }
        return try decode(type, from: try await perform(request, on: slow ? submitSession : session))
    }

    @discardableResult
    private func raw(_ method: String, _ path: String) async throws -> Data {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        return try await perform(request)
    }

    private func perform(_ request: URLRequest, on session: URLSession? = nil) async throws -> Data {
        let data: Data, response: URLResponse
        do { (data, response) = try await (session ?? self.session).data(for: request) }
        catch { throw RepositoryError.transport(tr("连不上后端：\(error.localizedDescription)", "Can’t reach the backend: \(error.localizedDescription)")) }

        guard let http = response as? HTTPURLResponse else {
            throw RepositoryError.transport(tr("没有拿到 HTTP 响应", "No HTTP response"))
        }
        guard (200..<300).contains(http.statusCode) else {
            throw Self.decodeError(status: http.statusCode, data: data)
        }
        return data
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        if T.self == EmptyResponse.self { return EmptyResponse() as! T }
        do { return try JSONDecoder.podsum.decode(type, from: data) }
        catch { throw RepositoryError.transport(tr("响应解不开：\(error)", "Couldn’t decode the response: \(error)")) }
    }

    struct EmptyResponse: Decodable {}

    static func decodeError(status: Int, data: Data) -> RepositoryError {
        if let envelope = try? JSONDecoder().decode(APIErrorEnvelope.self, from: data) {
            if envelope.error.code == "conflict" {
                var existing: String?
                if case .string(let id)? = envelope.error.details?["episode_id"] { existing = id }
                return .conflict(message: envelope.error.message, existingEpisodeID: existing)
            }
            return .api(code: envelope.error.code, message: envelope.error.message, status: status)
        }
        return .api(code: "http_\(status)", message: HTTPURLResponse.localizedString(forStatusCode: status), status: status)
    }
}

// MARK: - multipart/form-data

/// 手搓的表单体。文件用 `Data(contentsOf:)` 整个读进内存——
/// 提交的是播客音频，几十 MB 量级，后端的上限也在那儿（413）。
struct MultipartBody {
    let boundary = "podsum-" + UUID().uuidString
    private var data = Data()

    var contentType: String { "multipart/form-data; boundary=\(boundary)" }

    mutating func addField(_ name: String, _ value: String) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        append(value + "\r\n")
    }

    mutating func addFile(_ url: URL, name: String) throws {
        let bytes = try Data(contentsOf: url)
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(url.lastPathComponent)\"\r\n")
        append("Content-Type: application/octet-stream\r\n\r\n")
        data.append(bytes)
        append("\r\n")
    }

    func finished() -> Data {
        var out = data
        out.append(Data("--\(boundary)--\r\n".utf8))
        return out
    }

    private mutating func append(_ text: String) { data.append(Data(text.utf8)) }
}

// MARK: - WebSocket

/// `WS /api/ws/jobs`。断线自动重连（退避 1→8 秒），
/// 因为后端重启时这条连接必然断，而重启恰恰是最需要看进度的时候。
final class JobSocket: NSObject, @unchecked Sendable {
    private let baseURL: URL
    private let continuation: AsyncStream<JobEvent>.Continuation
    private var task: URLSessionWebSocketTask?
    private var session: URLSession?
    private var stopped = false
    private var backoff: Double = 1

    init(baseURL: URL, continuation: AsyncStream<JobEvent>.Continuation) {
        self.baseURL = baseURL
        self.continuation = continuation
    }

    func start() {
        guard !stopped else { return }
        var components = URLComponents(url: baseURL.appending(path: "api/ws/jobs"), resolvingAgainstBaseURL: false)!
        components.scheme = baseURL.scheme == "https" ? "wss" : "ws"
        guard let url = components.url else { return }

        let session = URLSession(configuration: .default)
        self.session = session
        let task = session.webSocketTask(with: url)
        self.task = task
        task.resume()
        receive()
    }

    func stop() {
        stopped = true
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        session?.invalidateAndCancel()
        session = nil
    }

    private func receive() {
        task?.receive { [weak self] result in
            guard let self, !stopped else { return }
            switch result {
            case .success(let message):
                backoff = 1
                if let data = Self.payload(message),
                   let event = try? JSONDecoder.podsum.decode(JobEvent.self, from: data) {
                    continuation.yield(event)
                }
                receive()
            case .failure:
                reconnect()
            }
        }
    }

    private static func payload(_ message: URLSessionWebSocketTask.Message) -> Data? {
        switch message {
        case .data(let data): return data
        case .string(let text): return Data(text.utf8)
        @unknown default: return nil
        }
    }

    private func reconnect() {
        guard !stopped else { return }
        let delay = backoff
        backoff = min(backoff * 2, 8)
        task = nil
        session?.invalidateAndCancel()
        session = nil
        DispatchQueue.global().asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.start()
        }
    }
}
