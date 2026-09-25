import SwiftUI

/// What the category name sheet is for.
enum CategoryNaming: Identifiable, Hashable {
    /// New category; if `assigning` is set, that episode goes into it right away.
    case create(assigning: String?)
    case rename(EpisodeCategory)

    var id: String {
        switch self {
        case .create(let episodeID): return "create-\(episodeID ?? "")"
        case .rename(let category):  return "rename-\(category.id)"
        }
    }
}

/// A small sheet with one name field. Problems are explained while typing
/// (same rules as the backend); a refusal from the backend shows up in place.
struct CategoryNameSheet: View {
    let naming: CategoryNaming
    let existing: [EpisodeCategory]
    let onSubmit: (String) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var serverError: String?
    @State private var saving = false
    @FocusState private var focused: Bool

    init(naming: CategoryNaming, existing: [EpisodeCategory], onSubmit: @escaping (String) async throws -> Void) {
        self.naming = naming
        self.existing = existing
        self.onSubmit = onSubmit
        if case .rename(let category) = naming {
            _name = State(initialValue: category.name)
        } else {
            _name = State(initialValue: "")
        }
    }

    private var exceptID: String? {
        if case .rename(let category) = naming { return category.id }
        return nil
    }

    private var problem: CategoryName.Problem? {
        CategoryName.problem(name, among: existing, except: exceptID)
    }

    private var title: String {
        switch naming {
        case .create: return tr("新建分类", "New Category")
        case .rename: return tr("重命名分类", "Rename Category")
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Space.m) {
            Text(title).podsumFont(.hook)

            TextField(tr("分类名", "Category name"), text: $name)
                .textFieldStyle(.roundedBorder)
                .focused($focused)
                .onSubmit(submit)
                .onChange(of: name) { _, _ in serverError = nil }

            // Stay quiet about an empty field until the user has typed something.
            Text(message ?? " ")
                .podsumFont(.meta)
                .foregroundStyle(Tone.warn)
                .frame(maxWidth: .infinity, alignment: .leading)

            HStack {
                Spacer()
                Button(tr("取消", "Cancel"), role: .cancel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(naming.isCreate ? tr("新建", "Create") : tr("好", "OK"), action: submit)
                    .keyboardShortcut(.defaultAction)
                    .disabled(problem != nil || saving)
            }
        }
        .padding(20)
        .frame(width: 320)
        .onAppear { focused = true }
    }

    private var message: String? {
        if let serverError { return serverError }
        if name.isEmpty { return nil }
        return problem?.localizedDescription
    }

    private func submit() {
        guard problem == nil, !saving else { return }
        saving = true
        Task {
            defer { saving = false }
            do {
                try await onSubmit(name)
                dismiss()
            } catch RepositoryError.conflict {
                serverError = CategoryName.Problem.duplicate.localizedDescription
            } catch {
                serverError = error.localizedDescription
            }
        }
    }
}

private extension CategoryNaming {
    var isCreate: Bool {
        if case .create = self { return true }
        return false
    }
}
