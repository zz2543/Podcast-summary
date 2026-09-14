import Foundation
import Security

/// 钥匙串读写。API key 不进 UserDefaults——那是一个明文 plist，
/// 任何进程都读得到；这是原生化相对 `.env` 的真正增量。
///
/// **全部密钥合成一条记录**（一个 JSON blob），不是一字段一条。
/// 原因是授权提示：钥匙串条目的访问控制绑定写入者的代码签名，
/// 换一个二进制去读就要问一次密码——一字段一条就意味着问九次。
/// 合成一条，最多问一次。
///
/// 实测过三种情形（macOS 26.5）：
///
/// | 情形 | 是否提示 |
/// |---|---|
/// | 同一份 app 反复启动 | 否 |
/// | 同一份 app 换了路径（拖进「应用程序」） | 否，ACL 认签名不认路径 |
/// | 重新编译出的新二进制 | 是 |
///
/// 也就是说日常使用不会弹；只有 app 升级到新版本时会再问一次。
/// 开发期反复重编译则每次都问——那是开发期的代价，不是用户的。
enum Keychain {
    static let service = "local.podsum.macclient"
    private static let account = "secrets"

    /// 合并之前的旧格式，一字段一条。只在迁移时读一次。
    static let legacyAccounts = [
        "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "DEEPGRAM_API_KEY",
        "ANTHROPIC_API_KEY", "VOLC_ACCESS_KEY_ID", "VOLC_SECRET_ACCESS_KEY",
        "DOUBAO_ASR_ACCESS_TOKEN", "DOUBAO_TTS_ACCESS_TOKEN",
    ]

    // MARK: 读写整份

    static func load() -> [String: String] {
        if let blob = readData(account: account),
           let values = try? JSONDecoder().decode([String: String].self, from: blob) {
            return values
        }
        return migrateLegacy()
    }

    @discardableResult
    static func save(_ values: [String: String]) -> Bool {
        // 空值等于不存在——设置面板里清空输入框就该是"这个 key 没有"，
        // 而不是"这个 key 是空字符串"。
        let kept = values.filter { !$0.value.isEmpty }
        guard !kept.isEmpty else { return delete(account: account) }
        guard let blob = try? JSONEncoder().encode(kept) else { return false }
        return writeData(blob, account: account)
    }

    // MARK: 迁移

    /// 把旧的九条读出来合成一条，然后删掉旧的。
    /// 这一次仍会逐条提示——躲不掉，旧条目就是分开存的。之后不再有。
    private static func migrateLegacy() -> [String: String] {
        var values: [String: String] = [:]
        for legacy in legacyAccounts {
            // 先看存不存在（只取属性不取数据，不会触发授权提示），
            // 免得为九个根本没有的条目白白问九次。
            guard exists(account: legacy) else { continue }
            if let data = readData(account: legacy),
               let text = String(data: data, encoding: .utf8), !text.isEmpty {
                values[legacy] = text
            }
        }
        guard !values.isEmpty else { return [:] }
        if save(values) {
            for legacy in legacyAccounts { delete(account: legacy) }
        }
        return values
    }

    // MARK: 底层

    private static func baseQuery(_ account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    private static func exists(account: String) -> Bool {
        var query = baseQuery(account)
        query[kSecReturnAttributes as String] = true   // 不取 data，就不需要授权
        return SecItemCopyMatching(query as CFDictionary, nil) == errSecSuccess
    }

    private static func readData(account: String) -> Data? {
        var query = baseQuery(account)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess else { return nil }
        return item as? Data
    }

    @discardableResult
    private static func writeData(_ data: Data, account: String) -> Bool {
        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        let status = SecItemUpdate(baseQuery(account) as CFDictionary, attrs as CFDictionary)
        if status == errSecSuccess { return true }
        if status == errSecItemNotFound {
            let merged = baseQuery(account).merging(attrs) { _, new in new }
            return SecItemAdd(merged as CFDictionary, nil) == errSecSuccess
        }
        return false
    }

    @discardableResult
    private static func delete(account: String) -> Bool {
        let status = SecItemDelete(baseQuery(account) as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}
