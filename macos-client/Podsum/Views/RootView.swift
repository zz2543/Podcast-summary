import SwiftUI

/// 后端没就绪之前挡在前面的那一层。
///
/// 三种不就绪的原因给三种不同的出口，而不是一句"启动失败"：
///   没填 API   → 直接打开设置
///   起不来     → 给日志尾巴 + 重试
///   正在启动   → 说清楚卡在哪一步
///
/// 任何时候都可以选择「先看离线示例」——fixture 就打在 bundle 里，
/// 没有后端也能翻 29 集列表和 5 集详情。
struct RootView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendController.self) private var backend
    @Environment(UIState.self) private var ui
    @Environment(JobsModel.self) private var jobs
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        Group {
            if let baseURL = backend.phase.baseURL {
                EpisodeListView()
                    .environment(\.episodeRepository, liveRepository(baseURL))
            } else if ui.offlineBrowsing {
                EpisodeListView(offlineNotice: true)
                    .environment(\.episodeRepository, Self.mock)
            } else {
                gate
            }
        }
        .onChange(of: backend.phase.baseURL) { _, url in
            if url != nil { ui.offlineBrowsing = false }
        }
    }

    /// Mock 只建一次：它内部攒着"假装提交"的剧集，每次重建都会丢掉。
    private static let mock = MockRepository()

    private func liveRepository(_ baseURL: URL) -> LiveRepository {
        LiveRepository(
            baseURL: baseURL,
            dataRoot: backend.attachedToExisting ? nil : URL(filePath: settings.dataDirectory, directoryHint: .isDirectory),
            backendRoot: settings.backendRoot.isBlank ? nil : URL(filePath: settings.backendRoot, directoryHint: .isDirectory)
        )
    }

    @ViewBuilder
    private var gate: some View {
        VStack(spacing: Space.l) {
            Image(systemName: icon)
                .font(.system(size: 40))
                .foregroundStyle(Tone.textSubtle)

            Text(headline)
                .podsumFont(.hook)
                .foregroundStyle(Tone.text)

            detail

            HStack(spacing: Space.m) {
                switch backend.phase {
                case .needsConfiguration:
                    Button("打开设置") { openSettings() }
                        .keyboardShortcut(.defaultAction)
                case .starting:
                    EmptyView()
                default:
                    Button("重试") { Task { await backend.restart() } }
                        .keyboardShortcut(.defaultAction)
                    Button("打开设置") { openSettings() }
                }
                Button("先看离线示例") { ui.offlineBrowsing = true }
            }
        }
        .padding(Space.section)
        .frame(maxWidth: 620)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Tone.bg)
    }

    private var icon: String {
        switch backend.phase {
        case .needsConfiguration: return "key"
        case .starting:           return "hourglass"
        case .ready:              return "checkmark.circle"
        default:                  return "exclamationmark.triangle"
        }
    }

    private var headline: String {
        switch backend.phase {
        case .idle:               return "后端还没启动"
        case .needsConfiguration: return "先填你自己的 API"
        case .starting(let step): return step
        case .noRuntime:          return "找不到运行环境"
        case .failed:             return "后端起不来"
        case .ready:              return "就绪"
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch backend.phase {
        case .needsConfiguration(let missing):
            VStack(spacing: Space.s) {
                Text("这个 app 不内置任何人的 API 凭据，默认全为空。缺的是：")
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                Text(missing.joined(separator: "、"))
                    .podsumFont(.body)
                    .foregroundStyle(Tone.text)
                    .multilineTextAlignment(.center)
            }
            .fixedSize(horizontal: false, vertical: true)

        case .noRuntime(let message), .failed(let message):
            VStack(spacing: Space.s) {
                Text(message)
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                    .multilineTextAlignment(.center)
                    .textSelection(.enabled)
                if !backend.logTail.isEmpty {
                    ScrollView {
                        Text(backend.logTail)
                            .podsumFont(.monoSmall)
                            .foregroundStyle(Tone.textSubtle)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 140)
                    .padding(Space.m)
                    .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.small))
                }
            }
            .fixedSize(horizontal: false, vertical: true)

        case .starting:
            ProgressView()

        default:
            EmptyView()
        }
    }
}
