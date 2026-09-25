import SwiftUI

/// On-demand AI categorisation: explain → run with progress → preview and edit
/// → apply. Nothing is written until "Apply"; closing the sheet at any point
/// leaves the library as it was (SC-003).
struct CategorizeSheet: View {
    var onApplied: () -> Void = {}

    @Environment(CategoryStore.self) private var store
    @Environment(\.episodeRepository) private var repository
    @Environment(\.dismiss) private var dismiss

    /// Edits made in the preview
    @State private var excluded: Set<String> = []
    @State private var rejected: Set<String> = []
    @State private var names: [String: String] = [:]
    @State private var applyError: String?
    @State private var result: CategorizeApplyResult?

    var body: some View {
        VStack(alignment: .leading, spacing: Space.l) {
            HStack(spacing: Space.s) {
                Image(systemName: "sparkles").foregroundStyle(Tone.info)
                Text(tr("AI 分类", "AI Categorize")).podsumFont(.hook)
            }
            content
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .padding(20)
        // One fixed size for every state. A macOS sheet takes its size from the
        // first state it shows (the short intro) and does not grow when the
        // preview arrives — the preview was left centred and clipped, with its
        // title and Apply button cut off.
        .frame(width: 580, height: 540)
        .onDisappear {
            // Closing discards the run or the proposal; nothing was written.
            switch store.aiRun {
            case .running: Task { await store.cancelAI(repository) }
            case .preview, .failed: store.dismissAI()
            default: break
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if let result {
            resultView(result)
        } else {
            switch store.aiRun {
            case .idle:
                intro
            case .running(_, let progress, let phase):
                running(progress, phase)
            case .preview(let proposal):
                preview(proposal)
            case .applying:
                ProgressView(tr("正在应用…", "Applying…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .failed(let message):
                failed(message)
            }
        }
    }

    // MARK: states

    private var intro: some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Text(tr("AI 会读一遍「未分类」里视频的总结，把它们放进已有分类，必要时建议几个新分类。",
                    "AI reads the summaries of your Uncategorized videos and files them into your existing categories, suggesting new ones where needed."))
            Text(tr("已经在分类里的视频不会被动。方案先给你看，确认后才生效。",
                    "Videos already in a category are never touched. You see the proposal first; nothing changes until you confirm."))
                .foregroundStyle(Tone.textMuted)
            Spacer(minLength: 0)
            HStack {
                Spacer()
                Button(tr("取消", "Cancel"), role: .cancel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(tr("开始", "Start")) { Task { await store.startAI(repository) } }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .podsumFont(.secondary)
    }

    private func running(_ progress: CategorizeRun.Progress?, _ phase: CategorizeRun.Phase?) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            if let progress, progress.total > 0 {
                ProgressView(value: Double(progress.done), total: Double(progress.total))
            } else {
                ProgressView().progressViewStyle(.linear)
            }
            Text(phaseText(progress, phase))
                .podsumFont(.meta)
                .foregroundStyle(Tone.textMuted)
            Spacer(minLength: 0)
            HStack {
                Spacer()
                Button(tr("取消", "Cancel"), role: .cancel) {
                    Task { await store.cancelAI(repository); dismiss() }
                }
                .keyboardShortcut(.cancelAction)
            }
        }
    }

    private func phaseText(_ progress: CategorizeRun.Progress?, _ phase: CategorizeRun.Phase?) -> String {
        switch phase {
        case .assign:
            let batch = max((progress?.done ?? 1), 1)
            let batches = max((progress?.total ?? 2) - 1, 1)
            return tr("正在归类 \(batch)/\(batches)…", "Sorting videos \(batch)/\(batches)…")
        default:
            return tr("正在拟定分类…", "Drafting categories…")
        }
    }

    private func failed(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Label(message, systemImage: "exclamationmark.triangle")
                .foregroundStyle(Tone.warn)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            HStack {
                Spacer()
                Button(tr("关闭", "Close"), role: .cancel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(tr("再试一次", "Try Again")) { Task { await store.startAI(repository) } }
                    .keyboardShortcut(.defaultAction)
            }
        }
    }

    // MARK: preview

    private func preview(_ proposal: CategorizeProposal) -> some View {
        let kept = keptChanges(proposal)
        return VStack(alignment: .leading, spacing: Space.m) {
            if proposal.changes.isEmpty {
                Text(tr("AI 没找到合适的分类，这些视频留在「未分类」。", "AI found no good fit; these videos stay in Uncategorized."))
                    .foregroundStyle(Tone.textMuted)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: Space.l) {
                        ForEach(proposal.categories) { category in
                            group(category, proposal.changes.filter { $0.toKey == category.key })
                        }
                    }
                    .padding(.vertical, Space.xs)
                }
                .frame(maxHeight: .infinity)
            }

            summaryLine(proposal, kept: kept.count)

            if let applyError {
                Text(applyError).podsumFont(.meta).foregroundStyle(Tone.err)
            }

            HStack {
                Spacer()
                Button(tr("取消", "Cancel"), role: .cancel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(tr("应用 \(kept.count) 条", kept.count == 1 ? "Apply 1 Change" : "Apply \(kept.count) Changes")) {
                    Task { await apply(proposal) }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(kept.isEmpty || hasNameProblem(proposal))
            }
        }
    }

    private func group(_ category: CategorizeProposal.ProposedCategory, _ changes: [CategorizeProposal.Change]) -> some View {
        let isRejected = rejected.contains(category.key)
        return VStack(alignment: .leading, spacing: Space.s) {
            HStack(spacing: Space.s) {
                Image(systemName: "folder")
                if category.isNew {
                    TextField(tr("分类名", "Category name"), text: nameBinding(category))
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 220)
                        .disabled(isRejected)
                    Text(tr("新", "New"))
                        .podsumFont(.micro, weight: .semibold)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Tone.info.opacity(0.15), in: Capsule())
                        .foregroundStyle(Tone.info)
                } else {
                    Text(category.name).podsumFont(.secondary, weight: .semibold)
                }
                Spacer()
                if category.isNew {
                    Button(isRejected ? tr("恢复", "Restore") : tr("不要这个分类", "Skip This Category")) {
                        if isRejected { rejected.remove(category.key) } else { rejected.insert(category.key) }
                    }
                    .buttonStyle(.link)
                }
            }
            if category.isNew, !isRejected, let problem = nameProblem(category) {
                Text(problem).podsumFont(.micro).foregroundStyle(Tone.warn)
            }
            if let reason = category.reason, !reason.isEmpty {
                Text(reason).podsumFont(.meta).foregroundStyle(Tone.textMuted)
            }
            ForEach(changes) { change in
                Toggle(isOn: includedBinding(change.episodeID)) {
                    Text(change.title ?? tr("未命名剧集", "Untitled Episode")).lineLimit(1)
                }
                .toggleStyle(.checkbox)
                .disabled(isRejected)
            }
        }
        .opacity(isRejected ? 0.45 : 1)
        .padding(Space.m)
        .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: Radius.small))
    }

    private func summaryLine(_ proposal: CategorizeProposal, kept: Int) -> some View {
        let s = proposal.skipped
        var parts: [String] = []
        if s.categorized > 0 { parts.append(tr("已在分类里 \(s.categorized)", "already filed \(s.categorized)")) }
        if s.locked > 0 { parts.append(tr("被你移出 \(s.locked)", "taken out by you \(s.locked)")) }
        if s.noSummary > 0 { parts.append(tr("无总结 \(s.noSummary)", "no summary \(s.noSummary)")) }
        if s.noSuggestion > 0 { parts.append(tr("无合适分类 \(s.noSuggestion)", "no fit \(s.noSuggestion)")) }
        return VStack(alignment: .leading, spacing: 2) {
            Text(tr("将改动 \(kept) 条", "\(kept) will change")
                 + (parts.isEmpty ? "" : tr(" · 不会改动：", " · unchanged: ") + parts.joined(separator: tr("、", ", "))))
            if proposal.failedBatches > 0 {
                Text(tr("有 \(proposal.failedBatches) 批没拿到 AI 的建议，那些视频保持原样。",
                        "\(proposal.failedBatches) batch(es) got no answer from AI; those videos stay as they are."))
                    .foregroundStyle(Tone.warn)
            }
        }
        .podsumFont(.meta)
        .foregroundStyle(Tone.textMuted)
    }

    // MARK: result

    private func resultView(_ result: CategorizeApplyResult) -> some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Label(tr("已应用 \(result.applied) 条", "Applied \(result.applied)"), systemImage: "checkmark.circle")
                .foregroundStyle(Tone.ok)
            Text(tr("有 \(result.skipped.count) 条没有应用，因为方案生成之后它们变了：",
                    "\(result.skipped.count) weren’t applied because they changed after the proposal was made:"))
            ForEach(Array(skipReasons(result).enumerated()), id: \.offset) { _, line in
                Text("· " + line).foregroundStyle(Tone.textMuted)
            }
            Spacer(minLength: 0)
            HStack {
                Spacer()
                Button(tr("好", "OK")) { dismiss() }.keyboardShortcut(.defaultAction)
            }
        }
        .podsumFont(.secondary)
    }

    private func skipReasons(_ result: CategorizeApplyResult) -> [String] {
        let counts = Dictionary(grouping: result.skipped, by: \.reason).mapValues(\.count)
        return counts.sorted { $0.key < $1.key }.map { reason, count in
            switch reason {
            case "locked":        return tr("\(count) 条已被你手动放好", "\(count) you placed by hand meanwhile")
            case "changed":       return tr("\(count) 条这期间已被放进分类", "\(count) were filed meanwhile")
            case "episode_gone":  return tr("\(count) 条已被删除", "\(count) were deleted")
            case "category_gone": return tr("\(count) 条的目标分类已被删除", "\(count) whose category was deleted")
            default:              return "\(count) · \(reason)"
            }
        }
    }

    // MARK: editing

    private func keptChanges(_ proposal: CategorizeProposal) -> [CategorizeProposal.Change] {
        proposal.changes.filter { !excluded.contains($0.episodeID) && !rejected.contains($0.toKey) }
    }

    private func name(_ category: CategorizeProposal.ProposedCategory) -> String {
        names[category.key] ?? category.name
    }

    private func nameBinding(_ category: CategorizeProposal.ProposedCategory) -> Binding<String> {
        Binding(get: { name(category) }, set: { names[category.key] = $0 })
    }

    private func includedBinding(_ episodeID: String) -> Binding<Bool> {
        Binding(get: { !excluded.contains(episodeID) },
                set: { included in if included { excluded.remove(episodeID) } else { excluded.insert(episodeID) } })
    }

    /// Same rules as the backend. A name equal to an existing category is fine:
    /// the backend files those videos into the existing one.
    private func nameProblem(_ category: CategorizeProposal.ProposedCategory) -> String? {
        do { _ = try CategoryName.validate(name(category)); return nil }
        catch { return error.localizedDescription }
    }

    private func hasNameProblem(_ proposal: CategorizeProposal) -> Bool {
        let used = Set(keptChanges(proposal).map(\.toKey))
        return proposal.categories.contains { $0.isNew && used.contains($0.key) && nameProblem($0) != nil }
    }

    private func apply(_ proposal: CategorizeProposal) async {
        applyError = nil
        let kept = keptChanges(proposal)
        let used = Set(kept.map(\.toKey))
        let request = CategorizeApply(
            newCategories: proposal.categories
                .filter { $0.isNew && used.contains($0.key) }
                .map { .init(key: $0.key, name: name($0)) },
            // Every proposed video was in no category when the run read it.
            assignments: kept.map { .init(episodeID: $0.episodeID, fromCategoryID: nil, toKey: $0.toKey) }
        )
        do {
            let outcome = try await store.apply(request, repository)
            onApplied()
            if outcome.skipped.isEmpty { dismiss() } else { result = outcome }
        } catch {
            applyError = error.localizedDescription
        }
    }
}
