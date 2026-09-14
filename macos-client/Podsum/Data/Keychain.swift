import Foundation
import Security

/// 钥匙串读写。API key 不进 UserDefaults——那是一个明文 plist，
/// 任何进程都读得到；这是原生化相对 `.env` 的真正增量。
///
/// 用 `kSecClassGenericPassword`，service 固定，account 即字段名。
/// 没有 access group、没有 iCloud 同步：这是一台 Mac 上的本地配置。
enum Keychain {
    static let service = "local.podsum.macclient"

    static func read(_ account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let value = String(data: data, encoding: .utf8)
        else { return nil }
        return value
    }

    /// 空串等于删除——设置面板里清空输入框就应该是"这个 key 不存在"，
    /// 而不是"这个 key 是空字符串"。
    @discardableResult
    static func write(_ value: String, account: String) -> Bool {
        guard !value.isEmpty else { return delete(account) }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attrs: [String: Any] = [
            kSecValueData as String: Data(value.utf8),
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]

        let status = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if status == errSecSuccess { return true }
        if status == errSecItemNotFound {
            return SecItemAdd(query.merging(attrs) { _, new in new } as CFDictionary, nil) == errSecSuccess
        }
        return false
    }

    @discardableResult
    static func delete(_ account: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}
