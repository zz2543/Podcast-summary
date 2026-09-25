import Foundation
import Observation

/// 「检查新版本」：问 GitHub Releases 最新的发布是哪一版，比本机新就给出下载页。
///
/// 只提示、不自动下载安装——app 没有 Developer ID 签名，自动替换会被 Gatekeeper
/// 当成来路不明的程序拦下，还不如让人自己下 DMG、按安装说明放行。
@MainActor
@Observable
final class AppUpdateChecker {
    static let repository = "zz2543/Podcast-summary"

    enum State: Equatable {
        case idle
        case checking
        case upToDate
        case available(version: String, page: URL)
        case noReleases
        case failed(String)
    }

    private(set) var state: State = .idle

    static var currentVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
    }

    static var buildNumber: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
    }

    func check() async {
        state = .checking
        var request = URLRequest(url: URL(string: "https://api.github.com/repos/\(Self.repository)/releases/latest")!)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 15

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            // 仓库还没有任何正式发布时，GitHub 对 latest 回 404
            if code == 404 { state = .noReleases; return }
            guard (200..<300).contains(code) else {
                state = .failed(tr("GitHub 返回 HTTP \(code)", "GitHub returned HTTP \(code)"))
                return
            }
            let release = try JSONDecoder().decode(Release.self, from: data)
            let latest = release.tagName.trimmingCharacters(in: CharacterSet(charactersIn: "vV"))
            if ComponentUpdater.compare(latest, Self.currentVersion) == .orderedDescending,
               let page = URL(string: release.htmlURL) {
                state = .available(version: latest, page: page)
            } else {
                state = .upToDate
            }
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    private struct Release: Decodable {
        let tagName: String
        let htmlURL: String

        enum CodingKeys: String, CodingKey {
            case tagName = "tag_name"
            case htmlURL = "html_url"
        }
    }
}
