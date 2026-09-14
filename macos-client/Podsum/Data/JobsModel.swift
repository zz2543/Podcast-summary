import Foundation
import Observation

/// 正在跑的任务。一条 WebSocket 喂它，列表页据此显示进度条。
///
/// 后端的 snapshot 帧目前恒为空（`set_snapshot_provider` 没人调用），
/// 所以刚连上时这里是空的——进行中的剧集仍会由列表自己的 status 显示出来，
/// 只是没有阶段级进度，直到下一条 job_update 到达。这是已知边界，不是 bug。
@MainActor
@Observable
public final class JobsModel {
    public private(set) var jobs: [String: Job] = [:]          // episodeID → 最新任务
    public private(set) var connected = false
    /// 有任务走完时回调，列表页据此重新拉一次——
    /// job_update 里没有剧集正文，进度条走完不等于卡片内容更新了。
    public var onFinished: ((String) -> Void)?

    private var task: Task<Void, Never>?

    public init() {}

    public var active: [Job] {
        jobs.values
            .filter { !$0.state.isTerminal }
            .sorted { ($0.startedAt ?? .distantPast) > ($1.startedAt ?? .distantPast) }
    }

    public func connect(to repository: any EpisodeRepository) {
        task?.cancel()
        jobs = [:]
        task = Task { [weak self] in
            for await event in repository.jobEvents() {
                guard let self, !Task.isCancelled else { return }
                apply(event)
            }
            self?.connected = false
        }
    }

    public func disconnect() {
        task?.cancel()
        task = nil
        connected = false
        jobs = [:]
    }

    private func apply(_ event: JobEvent) {
        switch event {
        case .hello:
            connected = true
        case .snapshot(let incoming):
            for job in incoming { jobs[job.episodeID] = job }
        case .jobUpdate(let job, _):
            let wasRunning = jobs[job.episodeID]?.state.isTerminal == false
            jobs[job.episodeID] = job
            if job.state.isTerminal && wasRunning {
                onFinished?(job.episodeID)
            }
        case .stageStatusUpdate, .error, .other:
            break
        }
    }

    public func job(for episodeID: String) -> Job? { jobs[episodeID] }
}
