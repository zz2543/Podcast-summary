import AVFoundation
import Foundation
import Observation

/// 详情页的播放器。
///
/// 一集只有一个实例，章节与关键时刻的时间戳都往这里 `seek`。
/// 时间在 UI 里一律用毫秒——后端给的 `start_ms` 就是毫秒，
/// 中间不做单位转换才不会差一秒。
@MainActor
@Observable
public final class AudioPlayerModel {
    public enum Track: String, CaseIterable, Identifiable, Sendable {
        case original, digest
        public var id: String { rawValue }
        public var label: String { self == .original ? "原声" : "音频摘要" }
    }

    public private(set) var track: Track = .original
    public private(set) var isPlaying = false
    public private(set) var currentMs: Int = 0
    public private(set) var durationMs: Int = 0
    public private(set) var failure: String?
    public private(set) var isReady = false
    public var rate: Float = 1.0 {
        didSet { if isPlaying { player.rate = rate } }
    }

    // deinit 是 nonisolated 的，要在那里撤观察者，存储本身就不能是主线程隔离的。
    // AVPlayer 的这几个调用（removeTimeObserver / replaceCurrentItem）本身线程安全。
    private nonisolated(unsafe) let player = AVPlayer()
    private nonisolated(unsafe) var observer: Any?
    private var statusObservation: NSKeyValueObservation?
    private nonisolated(unsafe) var endObserver: Any?
    private var sources: [Track: URL] = [:]
    /// 时长兜底：后端已经知道这一集多长，音频还没加载完时先用它，
    /// 进度条就不会从 0 跳一下。
    private var fallbackDurationMs: Int = 0

    public init() {
        observer = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 0.25, preferredTimescale: 600),
            queue: .main
        ) { [weak self] time in
            guard let self else { return }
            currentMs = Int(time.seconds * 1000)
            if let item = player.currentItem, item.duration.isNumeric {
                durationMs = Int(item.duration.seconds * 1000)
            }
        }
        endObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.didPlayToEndTimeNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.isPlaying = false }
        }
    }

    deinit {
        if let observer { player.removeTimeObserver(observer) }
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
    }

    public var availableTracks: [Track] { Track.allCases.filter { sources[$0] != nil } }
    public var hasAudio: Bool { !sources.isEmpty }

    /// 换一集时调用。同一集重复调用不会打断正在播的音频。
    public func configure(original: URL?, digest: URL?, fallbackDurationSeconds: Int?) {
        let next: [Track: URL] = [.original: original, .digest: digest]
            .compactMapValues { $0 }
        guard next != sources else { return }
        sources = next
        fallbackDurationMs = (fallbackDurationSeconds ?? 0) * 1000
        durationMs = fallbackDurationMs
        currentMs = 0
        isPlaying = false
        isReady = false
        failure = nil
        player.replaceCurrentItem(with: nil)
        if let first = availableTracks.first { select(first) }
    }

    public func select(_ track: Track) {
        guard let url = sources[track] else { return }
        self.track = track
        let item = AVPlayerItem(url: url)
        // KVO 的回调线程不保证是主线程，所以 hop 一次而不是 assumeIsolated
        statusObservation = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                switch item.status {
                case .readyToPlay:
                    self.isReady = true
                    self.failure = nil
                    if item.duration.isNumeric { self.durationMs = Int(item.duration.seconds * 1000) }
                case .failed:
                    self.isReady = false
                    self.failure = item.error?.localizedDescription ?? "音频打不开"
                default:
                    break
                }
            }
        }
        player.replaceCurrentItem(with: item)
        currentMs = 0
        // 摘要音频比原声短得多，切换后别留着上一条的时长
        durationMs = track == .original ? fallbackDurationMs : 0
        if isPlaying { player.rate = rate }
    }

    public func toggle() { isPlaying ? pause() : play() }

    public func play() {
        guard hasAudio else { return }
        player.rate = rate
        isPlaying = true
    }

    public func pause() {
        player.pause()
        isPlaying = false
    }

    /// 章节与关键时刻都走这里。`autoPlay` 为真时点一下时间戳就开始听——
    /// 这是"跳到这一刻"的本意，不是"把播放头挪过去然后等你再点一次播放"。
    public func seek(toMs ms: Int, autoPlay: Bool = true) {
        guard hasAudio else { return }
        let target = CMTime(value: CMTimeValue(max(0, ms)), timescale: 1000)
        player.seek(to: target, toleranceBefore: .zero, toleranceAfter: .zero)
        currentMs = max(0, ms)
        if autoPlay && !isPlaying { play() }
    }

    public func skip(seconds: Int) {
        seek(toMs: currentMs + seconds * 1000, autoPlay: false)
    }

    public var progress: Double {
        guard durationMs > 0 else { return 0 }
        return min(1, max(0, Double(currentMs) / Double(durationMs)))
    }
}
