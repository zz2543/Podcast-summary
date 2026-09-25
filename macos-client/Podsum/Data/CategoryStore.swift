import Foundation
import Observation

/// Categories shown in the sidebar, plus the state of an on-demand AI run.
///
/// Owned by `EpisodeListView` and handed to the detail view through the
/// environment. The repository is passed in per call rather than held, because
/// the list view's repository changes when the backend comes up.
///
/// Counts come from the backend (`GET /api/categories`), not from counting the
/// list, which stops at 200 episodes.
@Observable @MainActor
final class CategoryStore {
    private(set) var items: [EpisodeCategory] = []
    private(set) var uncategorizedCount = 0

    enum AIRun: Equatable {
        case idle
        case running(runID: String, progress: CategorizeRun.Progress?, phase: CategorizeRun.Phase?)
        case preview(CategorizeProposal)
        case applying
        case failed(String)
    }

    var aiRun: AIRun = .idle
    private var pollTask: Task<Void, Never>?

    var isRunning: Bool {
        switch aiRun {
        case .running, .applying: return true
        default: return false
        }
    }

    func category(id: String) -> EpisodeCategory? { items.first { $0.id == id } }

    // MARK: manual categories

    func refresh(_ repository: any EpisodeRepository) async {
        guard let list = try? await repository.categories() else { return }
        items = list.items.sorted { $0.position < $1.position }
        uncategorizedCount = list.uncategorizedCount
    }

    @discardableResult
    func create(_ name: String, _ repository: any EpisodeRepository) async throws -> EpisodeCategory {
        let category = try await repository.createCategory(name: name)
        await refresh(repository)
        return category
    }

    func rename(_ id: String, to name: String, _ repository: any EpisodeRepository) async throws {
        _ = try await repository.renameCategory(id: id, name: name)
        await refresh(repository)
    }

    func delete(_ id: String, _ repository: any EpisodeRepository) async throws {
        _ = try await repository.deleteCategory(id: id)
        await refresh(repository)
    }

    /// Reorders locally first so the drag lands immediately; puts it back if the
    /// backend refuses.
    func move(from source: IndexSet, to destination: Int, _ repository: any EpisodeRepository) async throws {
        let before = items
        items.move(fromOffsets: source, toOffset: destination)
        do {
            let list = try await repository.reorderCategories(ids: items.map(\.id))
            items = list.items.sorted { $0.position < $1.position }
            uncategorizedCount = list.uncategorizedCount
        } catch {
            items = before
            throw error
        }
    }

    func assign(_ episodeID: String, to categoryID: String?, _ repository: any EpisodeRepository) async throws -> CategoryAssignment {
        let assignment = try await repository.setCategory(episodeID: episodeID, categoryID: categoryID)
        await refresh(repository)
        return assignment
    }

    func release(_ episodeID: String, _ repository: any EpisodeRepository) async throws -> CategoryAssignment {
        try await repository.releaseCategory(episodeID: episodeID)
    }

    // MARK: AI categorisation — runs only when the user asks

    func startAI(_ repository: any EpisodeRepository) async {
        guard !isRunning else { return }
        do {
            let runID = try await repository.startCategorize()
            aiRun = .running(runID: runID, progress: nil, phase: nil)
            poll(runID, repository)
        } catch {
            aiRun = .failed(Self.startFailure(error))
        }
    }

    func cancelAI(_ repository: any EpisodeRepository) async {
        pollTask?.cancel()
        pollTask = nil
        if case .running(let runID, _, _) = aiRun {
            try? await repository.cancelCategorize(id: runID)
        }
        aiRun = .idle
    }

    /// Closing the preview without applying changes nothing (SC-003).
    func dismissAI() {
        pollTask?.cancel()
        pollTask = nil
        aiRun = .idle
    }

    func apply(_ edited: CategorizeApply, _ repository: any EpisodeRepository) async throws -> CategorizeApplyResult {
        let proposal = aiRun
        aiRun = .applying
        do {
            let result = try await repository.applyCategorization(edited)
            await refresh(repository)
            aiRun = .idle
            return result
        } catch {
            aiRun = proposal
            throw error
        }
    }

    private func poll(_ runID: String, _ repository: any EpisodeRepository) {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard !Task.isCancelled, let self else { return }
                do {
                    let run = try await repository.categorizeRun(id: runID)
                    guard case .running(let current, _, _) = self.aiRun, current == runID else { return }
                    switch run.state.value {
                    case .ready:
                        if let proposal = run.proposal { self.aiRun = .preview(proposal) }
                        else { self.aiRun = .failed(tr("AI 没有给出方案", "AI returned no proposal")) }
                        return
                    case .failed:
                        self.aiRun = .failed(Self.runFailure(run.error))
                        return
                    case .cancelled:
                        self.aiRun = .idle
                        return
                    case .running, .none:
                        self.aiRun = .running(runID: runID, progress: run.progress, phase: run.phase?.value)
                    }
                } catch RepositoryError.api(code: "not_found", _, _) {
                    self.aiRun = .failed(tr("后端重启过，这次运行已经丢失，请重新运行。",
                                            "The backend restarted and this run was lost. Please run it again."))
                    return
                } catch {
                    // A transient hiccup: keep polling.
                }
            }
        }
    }

    private static func startFailure(_ error: Error) -> String {
        switch error {
        case RepositoryError.conflict:
            return tr("已经有一次 AI 分类在进行。", "An AI categorization is already running.")
        case RepositoryError.api(code: "bad_input", _, _):
            return tr("「未分类」里没有可以交给 AI 的视频：它们要么是你手动移出的，要么还没有总结。",
                      "Nothing in Uncategorized for AI to file: those videos were taken out by you or have no summary yet.")
        default:
            return error.localizedDescription
        }
    }

    private static func runFailure(_ message: String?) -> String {
        switch message {
        case "no_taxonomy":
            return tr("AI 没能提出可用的分类，请再试一次。", "AI couldn’t come up with usable categories. Please try again.")
        case "every assignment batch failed":
            return tr("AI 归类时全部失败了，库没有任何变化。请稍后再试。",
                      "AI failed on every batch. Nothing in your library changed. Please try again later.")
        case let message?:
            return tr("AI 分类失败：\(message)", "AI categorization failed: \(message)")
        case nil:
            return tr("AI 分类失败", "AI categorization failed")
        }
    }
}
