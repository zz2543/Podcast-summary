import SwiftUI

/// 播放条。停在详情页正文上方，随内容滚动——
/// 固定悬浮会遮住正文，而这一页的主体是读，不是听。
struct AudioPlayerBar: View {
    @Bindable var player: AudioPlayerModel
    /// 章节起点，画在进度条上。知道"现在在第几章"比一条光秃秃的进度条有用得多。
    var chapters: [Chapter] = []

    @Environment(\.textScale) private var scale
    @State private var dragFraction: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            HStack(spacing: Space.m) {
                transport
                scrubber
                trailing
            }

            if let failure = player.failure {
                Label(failure, systemImage: "exclamationmark.triangle")
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.err)
            } else if let title = currentChapterTitle {
                Text(title)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.textSubtle)
                    .lineLimit(1)
            }
        }
        .padding(Space.l)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(RoundedRectangle(cornerRadius: Radius.medium).strokeBorder(Tone.border.opacity(0.5)))
        .background(shortcuts)
    }

    // MARK: 传输控制

    private var transport: some View {
        HStack(spacing: Space.s) {
            Button { player.skip(seconds: -15) } label: {
                Image(systemName: "gobackward.15").font(.system(size: 16 * scale))
            }
            .buttonStyle(.plain)
            .help(tr("后退 15 秒（⌥←）", "Back 15 seconds (⌥←)"))

            Button { player.toggle() } label: {
                Image(systemName: player.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                    .font(.system(size: 30 * scale))
                    .foregroundStyle(Tone.info)
            }
            .buttonStyle(.plain)
            .help(player.isPlaying ? tr("暂停（⌘K）", "Pause (⌘K)") : tr("播放（⌘K）", "Play (⌘K)"))

            Button { player.skip(seconds: 15) } label: {
                Image(systemName: "goforward.15").font(.system(size: 16 * scale))
            }
            .buttonStyle(.plain)
            .help(tr("前进 15 秒（⌥→）", "Forward 15 seconds (⌥→)"))
        }
        .foregroundStyle(Tone.text)
        .disabled(!player.hasAudio)
    }

    // MARK: 进度条

    private var scrubber: some View {
        VStack(spacing: 3) {
            GeometryReader { geo in
                let height = 6 * scale
                ZStack(alignment: .leading) {
                    Capsule().fill(Tone.surfaceElev).frame(height: height)

                    Capsule()
                        .fill(Tone.info)
                        .frame(width: geo.size.width * shownFraction, height: height)

                    // 章节刻度。拖动时能看见自己正越过哪一章。
                    ForEach(chapterMarks, id: \.self) { fraction in
                        Rectangle()
                            .fill(Tone.bg.opacity(0.85))
                            .frame(width: 1.5, height: height)
                            .offset(x: geo.size.width * fraction)
                    }

                    Circle()
                        .fill(Tone.info)
                        .frame(width: 11 * scale, height: 11 * scale)
                        .offset(x: geo.size.width * shownFraction - 5.5 * scale)
                        .shadow(color: .black.opacity(0.2), radius: 2, y: 1)
                        .opacity(player.hasAudio ? 1 : 0)
                }
                .frame(height: max(height, 12 * scale))
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { value in
                            guard player.hasAudio, geo.size.width > 0 else { return }
                            dragFraction = min(1, max(0, value.location.x / geo.size.width))
                        }
                        .onEnded { value in
                            guard player.hasAudio, geo.size.width > 0, player.durationMs > 0 else {
                                dragFraction = nil
                                return
                            }
                            let fraction = min(1, max(0, value.location.x / geo.size.width))
                            player.seek(toMs: Int(fraction * Double(player.durationMs)), autoPlay: false)
                            dragFraction = nil
                        }
                )
            }
            .frame(height: 14 * scale)

            HStack {
                Text(Fmt.timestamp(shownMs))
                Spacer()
                Text(Fmt.timestamp(player.durationMs))
            }
            .podsumFont(.monoSmall)
            .foregroundStyle(Tone.textSubtle)
        }
    }

    // MARK: 右侧

    private var trailing: some View {
        HStack(spacing: Space.s) {
            if player.availableTracks.count > 1 {
                Picker("", selection: Binding(
                    get: { player.track },
                    set: { player.select($0) }
                )) {
                    ForEach(player.availableTracks) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .fixedSize()
            }

            Menu {
                ForEach([0.75, 1.0, 1.25, 1.5, 1.75, 2.0], id: \.self) { rate in
                    Button("\(rate, format: .number.precision(.fractionLength(0...2)))×") {
                        player.rate = Float(rate)
                    }
                }
            } label: {
                Text("\(player.rate, format: .number.precision(.fractionLength(0...2)))×")
                    .podsumFont(.meta)
                    .monospacedDigit()
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
            .help(tr("播放速度", "Playback speed"))
        }
        .disabled(!player.hasAudio)
    }

    // MARK: 快捷键
    //
    // 刻意不用空格：详情页有对话输入框，空格在那里必须是空格。
    // ⌘K 播放/暂停、⌥←/⌥→ 跳 15 秒，都不与文本输入冲突。

    private var shortcuts: some View {
        ZStack {
            Button("") { player.toggle() }.keyboardShortcut("k", modifiers: .command)
            Button("") { player.skip(seconds: -15) }.keyboardShortcut(.leftArrow, modifiers: .option)
            Button("") { player.skip(seconds: 15) }.keyboardShortcut(.rightArrow, modifiers: .option)
        }
        .opacity(0)
        .frame(width: 0, height: 0)
        .accessibilityHidden(true)
        .disabled(!player.hasAudio)
    }

    // MARK: 派生值

    private var shownFraction: Double { dragFraction ?? player.progress }

    private var shownMs: Int {
        guard let dragFraction, player.durationMs > 0 else { return player.currentMs }
        return Int(dragFraction * Double(player.durationMs))
    }

    private var chapterMarks: [Double] {
        guard player.durationMs > 0, player.track == .original else { return [] }
        return chapters.dropFirst().map { Double($0.startMs) / Double(player.durationMs) }
            .filter { $0 > 0 && $0 < 1 }
    }

    private var currentChapterTitle: String? {
        guard player.track == .original else { return nil }
        guard let chapter = chapters.last(where: { $0.startMs <= shownMs }) else { return nil }
        return tr("第 \(chapter.idx + 1) 章 · \(chapter.title)", "Chapter \(chapter.idx + 1) · \(chapter.title)")
    }
}

/// 没有音频时的占位。说清楚为什么没有，而不是干脆不画。
struct AudioUnavailableNote: View {
    let reason: String

    var body: some View {
        Label(reason, systemImage: "speaker.slash")
            .podsumFont(.meta)
            .foregroundStyle(Tone.textSubtle)
            .padding(Space.m)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Tone.surfaceElev.opacity(0.6), in: RoundedRectangle(cornerRadius: Radius.small))
    }
}
