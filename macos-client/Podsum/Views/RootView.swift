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
    @Environment(OnboardingGuide.self) private var guide

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
                    Button(tr("开始引导", "Start Setup Guide")) { startGuide() }
                        .keyboardShortcut(.defaultAction)
                    Button(tr("我自己填", "Fill In Myself")) { openSettings() }
                case .starting:
                    EmptyView()
                default:
                    Button(tr("重试", "Retry")) { Task { await backend.restart() } }
                        .keyboardShortcut(.defaultAction)
                    Button(tr("打开设置", "Open Settings")) { openSettings() }
                }
                Button(tr("先看离线示例", "Browse Offline Samples")) { ui.offlineBrowsing = true }
            }
        }
        .padding(Space.section)
        .frame(maxWidth: 620)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Tone.bg)
        // 第一次打开、什么都没填：直接把设置窗口打开并开始引导（只自动这一次）
        .onChange(of: backend.phase, initial: true) { _, phase in
            if case .needsConfiguration = phase, guide.shouldAutoStart(isConfigured: settings.isConfigured) {
                startGuide()
            }
        }
    }

    private func startGuide() {
        guide.start()
        openSettings()
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
        case .idle:               return tr("后端还没启动", "Backend not started")
        case .needsConfiguration: return tr("先填你自己的 API", "Add your own API keys first")
        case .starting(let step): return step
        case .noRuntime:          return tr("找不到运行环境", "No runtime found")
        case .failed:             return tr("后端起不来", "Backend failed to start")
        case .ready:              return tr("就绪", "Ready")
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch backend.phase {
        case .needsConfiguration(let missing):
            VStack(spacing: Space.s) {
                Text(tr("这个 app 不内置任何人的 API 凭据，默认全为空。缺的是：",
                        "This app ships with no API credentials — every field starts empty. Still missing:"))
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                Text(missing.joined(separator: tr("、", ", ")))
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
