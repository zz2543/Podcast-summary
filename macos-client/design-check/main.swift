import AppKit
import SwiftUI

// 离屏渲染组件成 PNG。不启动 app、不需要屏幕解锁，也能看到真实渲染结果。
//
//   swiftc -O specs/002-macos-native/contracts/PodsumModels.swift \
//          macos-client/Podsum/Design/{Theme,Typography,Localization}.swift \
//          macos-client/Podsum/Data/{StringUtils,AudioPlayerModel}.swift \
//          macos-client/Podsum/Views/{AudioPlayerBar,ActiveJobsStrip,ChapterRow}.swift \
//          macos-client/design-check/main.swift -o /tmp/podsum-design \
//     && /tmp/podsum-design /tmp/check.png <fixtures 目录> [音频文件]
//
// 注意 ImageRenderer 不触发 onAppear，带入场动画的视图要用 animate: false 构造。

@MainActor
func render(_ view: some View, to url: URL, width: CGFloat) {
    let renderer = ImageRenderer(content:
        view.frame(width: width).padding(20).background(Tone.bg)
    )
    renderer.scale = 2
    guard let image = renderer.nsImage,
          let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:])
    else { fatalError("渲染失败") }
    try! png.write(to: url)
    print("✓ \(url.lastPathComponent)  \(Int(image.size.width))×\(Int(image.size.height))")
}

@main
enum DesignCheck {
    static func main() async {
        let out = URL(filePath: CommandLine.arguments[1])
        let fixtures = URL(filePath: CommandLine.arguments[2], directoryHint: .isDirectory)
        let audio = CommandLine.arguments.count > 3 ? URL(filePath: CommandLine.arguments[3]) : nil

        let data = try! Data(contentsOf: fixtures.appending(path: "detail-done-full.json"))
        let detail = try! JSONDecoder.podsum.decode(EpisodeDetail.self, from: data)

        let player = await AudioPlayerModel()
        await player.configure(original: audio, digest: nil,
                               fallbackDurationSeconds: detail.durationSeconds)
        if audio != nil {
            // 等 AVPlayerItem 真读到时长再渲染，否则进度条画的是占位值
            for _ in 0..<40 where await !player.isReady {
                try? await Task.sleep(for: .milliseconds(100))
            }
            await player.seek(toMs: detail.chapters.count > 2 ? detail.chapters[2].startMs : 60_000,
                              autoPlay: false)
            try? await Task.sleep(for: .milliseconds(400))
        }

        let jobs = [
            Job(id: "j1", episodeID: "E1", state: .known(.transcribing),
                stageProgress: ["transcribe": .object(["status": .string("running")])],
                attempt: 1, error: nil, startedAt: Date(), finishedAt: nil),
            Job(id: "j2", episodeID: "E2", state: .known(.summarizing),
                stageProgress: [:], attempt: 3, error: nil, startedAt: Date(), finishedAt: nil),
        ]

        await MainActor.run {
            render(
                VStack(alignment: .leading, spacing: 24) {
                    Text("播放条 · 真实音频与章节刻度").podsumFont(.sectionLabel).foregroundStyle(Tone.textSubtle)
                    AudioPlayerBar(player: player, chapters: detail.chapters)

                    Text("没有音频时").podsumFont(.sectionLabel).foregroundStyle(Tone.textSubtle)
                    AudioUnavailableNote(reason: "音频还在抓取或转写中，处理完就能播。")

                    Text("进行中的任务").podsumFont(.sectionLabel).foregroundStyle(Tone.textSubtle)
                    ActiveJobsStrip(jobs: jobs,
                                    titles: ["E1": "一集正在转写的播客", "E2": "另一集，重试到第 3 次"],
                                    onSelect: { _ in })

                    Text("对照组：ImageRenderer 画不了 AppKit 控件")
                        .podsumFont(.sectionLabel).foregroundStyle(Tone.textSubtle)
                    HStack(spacing: 16) {
                        ProgressView(value: 0.5).frame(width: 160)
                        Menu("菜单") { Button("甲") {} }.fixedSize()
                        Text("← 这两个若也是黄块，说明是渲染器限制").podsumFont(.micro)
                    }

                    Text("章节（时间戳可点）").podsumFont(.sectionLabel).foregroundStyle(Tone.textSubtle)
                    ChapterRow(chapter: detail.chapters[0], onSeek: { _ in }, isCurrent: true)
                },
                to: out, width: 760
            )
        }
        exit(0)
    }
}
