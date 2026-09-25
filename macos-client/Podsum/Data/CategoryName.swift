import Foundation

/// The client-side copy of the backend's category-name rules
/// (`domain/categorizer.py`: `validate_name`, `name_key`). Checking here lets
/// the name field explain a problem while the user types; the backend still
/// has the final say.
enum CategoryName {
    static let maxLength = 30

    /// The sidebar's fixed rows, in both UI languages.
    static let reservedKeys: Set<String> = ["全部", "未分类", "all", "uncategorized"]

    enum Problem: LocalizedError, Equatable {
        case empty, tooLong, reserved, duplicate

        var errorDescription: String? {
            switch self {
            case .empty:     return tr("名字不能为空", "The name can’t be empty")
            case .tooLong:   return tr("最多 \(CategoryName.maxLength) 个字", "At most \(CategoryName.maxLength) characters")
            case .reserved:  return tr("这个名字是侧边栏固定项，换一个", "That name belongs to a fixed sidebar item")
            case .duplicate: return tr("已经有叫这个名字的分类了", "A category with this name already exists")
            }
        }
    }

    /// What "the same name" means: NFKC-folded, trimmed, case-insensitive.
    static func key(_ name: String) -> String {
        name.precomposedStringWithCompatibilityMapping
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .folding(options: .caseInsensitive, locale: nil)
    }

    /// The display form of a valid name, or the problem with it.
    static func validate(_ name: String) throws -> String {
        let display = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let key = key(display)
        if key.isEmpty { throw Problem.empty }
        if display.unicodeScalars.count > maxLength { throw Problem.tooLong }
        if reservedKeys.contains(key) { throw Problem.reserved }
        return display
    }

    /// `validate` plus a duplicate check against the categories already shown.
    static func problem(_ name: String, among existing: [EpisodeCategory], except id: String? = nil) -> Problem? {
        do {
            let display = try validate(name)
            let key = key(display)
            if existing.contains(where: { $0.id != id && Self.key($0.name) == key }) { return .duplicate }
            return nil
        } catch let problem as Problem {
            return problem
        } catch {
            return nil
        }
    }
}
