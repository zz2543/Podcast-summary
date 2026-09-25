import Foundation

/// Offline stand-in for the feature-004 endpoints. Everything lives in memory,
/// like the rest of MockRepository, and mirrors the backend's rules closely
/// enough to exercise the UI: name checks, manual locks, and an AI run that
/// reports progress before handing back a proposal.
extension MockRepository {
    func mockAssignment(for episodeID: String) -> CategoryAssignment? {
        categoryLock.withLock { mockAssignments[episodeID] }
    }

    func withMockCategories(_ episodes: [EpisodeSummary]) -> [EpisodeSummary] {
        let assignments = categoryLock.withLock { mockAssignments }
        return episodes.map { episode in
            guard let assignment = assignments[episode.id] else { return episode }
            var copy = episode
            copy.category = assignment.category
            copy.categoryOrigin = assignment.categoryOrigin
            return copy
        }
    }

    public func categories() async throws -> CategoryList {
        try? await Task.sleep(for: latency)
        let total = (try? await list().count) ?? 0
        return categoryLock.withLock { snapshot(total: total) }
    }

    public func createCategory(name: String) async throws -> EpisodeCategory {
        let display = try CategoryName.validate(name)
        return try categoryLock.withLock {
            try ensureUnique(display, except: nil)
            let category = EpisodeCategory(id: "MOCKCAT" + UUID().uuidString.prefix(8), name: display,
                                           position: mockCategories.count, origin: "user", episodeCount: 0)
            mockCategories.append(category)
            return category
        }
    }

    public func renameCategory(id: String, name: String) async throws -> EpisodeCategory {
        let display = try CategoryName.validate(name)
        return try categoryLock.withLock {
            guard let index = mockCategories.firstIndex(where: { $0.id == id }) else {
                throw RepositoryError.api(code: "not_found", message: "category not found", status: 404)
            }
            try ensureUnique(display, except: id)
            let old = mockCategories[index]
            let renamed = EpisodeCategory(id: id, name: display, position: old.position, origin: old.origin,
                                          episodeCount: count(in: id))
            mockCategories[index] = renamed
            for (episodeID, assignment) in mockAssignments where assignment.category?.id == id {
                mockAssignments[episodeID] = CategoryAssignment(category: CategoryRef(id: id, name: display),
                                                                categoryOrigin: assignment.categoryOrigin)
            }
            return renamed
        }
    }

    public func deleteCategory(id: String) async throws -> Int {
        categoryLock.withLock {
            let released = mockAssignments.filter { $0.value.category?.id == id }.map(\.key)
            for episodeID in released {
                mockAssignments[episodeID] = CategoryAssignment(category: nil, categoryOrigin: nil)
            }
            mockCategories.removeAll { $0.id == id }
            return released.count
        }
    }

    public func reorderCategories(ids: [String]) async throws -> CategoryList {
        let total = (try? await list().count) ?? 0
        return categoryLock.withLock {
            let byID = Dictionary(uniqueKeysWithValues: mockCategories.map { ($0.id, $0) })
            mockCategories = ids.enumerated().compactMap { position, id in
                byID[id].map { EpisodeCategory(id: $0.id, name: $0.name, position: position,
                                               origin: $0.origin, episodeCount: 0) }
            }
            return snapshot(total: total)
        }
    }

    public func setCategory(episodeID: String, categoryID: String?) async throws -> CategoryAssignment {
        categoryLock.withLock {
            let ref = categoryID.flatMap { id in mockCategories.first { $0.id == id } }
                .map { CategoryRef(id: $0.id, name: $0.name) }
            let assignment = CategoryAssignment(category: ref, categoryOrigin: .known(.manual))
            mockAssignments[episodeID] = assignment
            return assignment
        }
    }

    public func releaseCategory(episodeID: String) async throws -> CategoryAssignment {
        categoryLock.withLock {
            let current = mockAssignments[episodeID] ?? CategoryAssignment(category: nil, categoryOrigin: nil)
            guard current.categoryOrigin?.value == .manual else { return current }
            let released = CategoryAssignment(category: current.category,
                                              categoryOrigin: current.category == nil ? nil : .known(.auto))
            mockAssignments[episodeID] = released
            return released
        }
    }

    public func startCategorize() async throws -> String {
        let id = "MOCKRUN" + UUID().uuidString.prefix(8)
        categoryLock.withLock { mockRunPolls[id] = 0 }
        return id
    }

    /// Two polls of progress, then a proposal that files every uncategorized,
    /// unlocked episode by a keyword in its title.
    public func categorizeRun(id: String) async throws -> CategorizeRun {
        let polls: Int? = categoryLock.withLock {
            guard let n = mockRunPolls[id] else { return nil }
            mockRunPolls[id] = n + 1
            return n
        }
        guard let polls else {
            throw RepositoryError.api(code: "not_found", message: "categorisation run not found", status: 404)
        }
        if polls < 2 {
            return CategorizeRun(runID: id, state: .known(.running), phase: .known(polls == 0 ? .taxonomy : .assign),
                                 progress: .init(done: polls, total: 2), error: nil, proposal: nil)
        }
        let episodes = try await list()
        return CategorizeRun(runID: id, state: .known(.ready), phase: .known(.assign),
                             progress: .init(done: 2, total: 2), error: nil, proposal: mockProposal(for: episodes))
    }

    public func cancelCategorize(id: String) async throws {
        _ = categoryLock.withLock { mockRunPolls.removeValue(forKey: id) }
    }

    public func applyCategorization(_ apply: CategorizeApply) async throws -> CategorizeApplyResult {
        categoryLock.withLock {
            var created: [CategorizeApplyResult.Created] = []
            var targets: [String: CategoryRef] = [:]
            let referenced = Set(apply.assignments.map(\.toKey))
            for new in apply.newCategories where referenced.contains(new.key) {
                let key = CategoryName.key(new.name)
                if let existing = mockCategories.first(where: { CategoryName.key($0.name) == key }) {
                    targets[new.key] = CategoryRef(id: existing.id, name: existing.name)
                    created.append(.init(key: new.key, categoryID: existing.id, name: existing.name, reused: true))
                } else {
                    let category = EpisodeCategory(id: "MOCKCAT" + UUID().uuidString.prefix(8), name: new.name,
                                                   position: mockCategories.count, origin: "ai", episodeCount: 0)
                    mockCategories.append(category)
                    targets[new.key] = CategoryRef(id: category.id, name: category.name)
                    created.append(.init(key: new.key, categoryID: category.id, name: category.name, reused: false))
                }
            }
            var applied = 0
            var skipped: [CategorizeApplyResult.SkippedRow] = []
            for row in apply.assignments {
                let current = mockAssignments[row.episodeID]
                if current?.categoryOrigin?.value == .manual {
                    skipped.append(.init(episodeID: row.episodeID, reason: "locked")); continue
                }
                if current?.category?.id != row.fromCategoryID {
                    skipped.append(.init(episodeID: row.episodeID, reason: "changed")); continue
                }
                let target = targets[row.toKey] ?? mockCategories
                    .first { "c:" + $0.id == row.toKey }
                    .map { CategoryRef(id: $0.id, name: $0.name) }
                guard let target else {
                    skipped.append(.init(episodeID: row.episodeID, reason: "category_gone")); continue
                }
                mockAssignments[row.episodeID] = CategoryAssignment(category: target, categoryOrigin: .known(.auto))
                applied += 1
            }
            return CategorizeApplyResult(created: created, applied: applied, skipped: skipped)
        }
    }

    // MARK: helpers — snapshot, count and ensureUnique expect categoryLock held

    private func snapshot(total: Int) -> CategoryList {
        let items = mockCategories.map {
            EpisodeCategory(id: $0.id, name: $0.name, position: $0.position, origin: $0.origin,
                            episodeCount: count(in: $0.id))
        }
        let filed = items.reduce(0) { $0 + $1.episodeCount }
        return CategoryList(items: items, uncategorizedCount: max(total - filed, 0))
    }

    private func count(in categoryID: String) -> Int {
        mockAssignments.values.filter { $0.category?.id == categoryID }.count
    }

    private func ensureUnique(_ name: String, except id: String?) throws {
        let key = CategoryName.key(name)
        if mockCategories.contains(where: { $0.id != id && CategoryName.key($0.name) == key }) {
            throw RepositoryError.conflict(message: "a category with this name already exists", existingEpisodeID: nil)
        }
    }

    private func mockProposal(for episodes: [EpisodeSummary]) -> CategorizeProposal {
        let rules: [(key: String, name: String, words: [String])] = [
            ("n:1", "AI 编程", ["Claude", "Codex", "Coding", "编程", "Agent", "AI"]),
            ("n:2", "访谈与播客", ["对谈", "播客", "访谈"]),
        ]
        let assignments = categoryLock.withLock { mockAssignments }
        var changes: [CategorizeProposal.Change] = []
        var used = Set<String>()
        let categorized = episodes.filter { assignments[$0.id]?.category != nil }.count
        let locked = episodes.filter {
            assignments[$0.id]?.category == nil && assignments[$0.id]?.categoryOrigin?.value == .manual
        }.count
        for episode in episodes where assignments[episode.id]?.category == nil
            && assignments[episode.id]?.categoryOrigin?.value != .manual {
            let title = episode.title ?? ""
            guard let rule = rules.first(where: { rule in rule.words.contains { title.localizedCaseInsensitiveContains($0) } })
            else { continue }
            used.insert(rule.key)
            changes.append(.init(episodeID: episode.id, title: episode.title, toKey: rule.key))
        }
        let categories = rules.filter { used.contains($0.key) }.map {
            CategorizeProposal.ProposedCategory(key: $0.key, categoryID: nil, name: $0.name, isNew: true,
                                                reason: tr("离线示例：按标题关键词归类", "Offline sample: grouped by title keywords"))
        }
        return CategorizeProposal(
            categories: categories, changes: changes,
            skipped: .init(categorized: categorized, locked: locked, noSummary: 0,
                           noSuggestion: episodes.count - changes.count - categorized - locked),
            failedBatches: 0
        )
    }
}
