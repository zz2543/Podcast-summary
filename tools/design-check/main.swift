//
//  离屏设计核对：用 ImageRenderer 把组件渲染成 PNG，不启动 app、
//  也不需要屏幕解锁就能看到真实渲染结果。改完样式跑一遍核对。
//
//  swiftc -O specs/002-macos-native/contracts/PodsumModels.swift \
//         macos-client/Podsum/Design/Theme.swift \
//         macos-client/Podsum/Design/Typography.swift \
//         macos-client/Podsum/Views/UsefulnessCard.swift \
//         tools/design-check/main.swift -o /tmp/podsum-design \
//    && /tmp/podsum-design /tmp/cards.png && open /tmp/cards.png
//
//  注意：ImageRenderer 不触发 onAppear，带入场动画的视图要用
//  animate: false 构造，否则截出来是未落位的空状态。
//
//  刻意放在 macos-client/ 之外：本文件有自己的顶层 main，
//  和 app 的 @main PodsumApp 属于两个程序。放在 app 目录旁边时，
//  轻量语言服务器会把两者当成同一模块而误报（Xcode 按 pbxproj 索引则正常）。
//

import SwiftUI
import AppKit

private let sample = Usefulness(
    score: 62, band: .known(.skimmable),
    rationale: "主播以出生人口下降、AI 冲击、学历扩招等具体背景支撑“衰退时代”论点，并给出实习、拥抱不确定性等建议，但缺乏新颖洞见且夹杂重复与闲聊，摘要即可获取核心要点。")

/// 四档评分 + 两种未评分态
struct Bands: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.l) {
            heading("有用性评分卡 · 四档 + 未评分")
            card(92, .mustListen, "信息密度极高，几乎每段都有可直接落地的做法。", "v1")
            card(72, .worthListening, "有干货，但前三分之一是寒暄，可以跳过。", nil)
            UsefulnessCard(usefulness: sample, stage: .known(.present),
                           promptVersion: "v1", animate: false)
            card(31, .skippable, "重复较多，核心信息一段话即可概括。", nil)
            UsefulnessCard(usefulness: nil, stage: .known(.missing), animate: false)
            UsefulnessCard(usefulness: nil, stage: .known(.failedAfterRetries), animate: false)
        }
        .padding(Space.xxl)
        .frame(width: 760)
        .background(Tone.bg)
    }

    private func card(_ s: Int, _ b: UsefulnessBand, _ r: String, _ v: String?) -> some View {
        UsefulnessCard(usefulness: .init(score: s, band: .known(b), rationale: r),
                       stage: .known(.present), promptVersion: v, animate: false)
    }
}

/// 同一张卡在各个 ⌘+ 档位下的样子——验证缩放是否真的贯穿到每个角色
struct Scales: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.xl) {
            heading("字号档位 · ⌘+ / ⌘- / ⌘0")
            ForEach([0.85, 1.0, 1.3, 1.75], id: \.self) { scale in
                VStack(alignment: .leading, spacing: Space.s) {
                    Text(TextScale.label(scale))
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Tone.textSubtle)
                    UsefulnessCard(usefulness: sample, stage: .known(.present),
                                   promptVersion: "v1", animate: false)
                        .environment(\.textScale, scale)
                }
            }
        }
        .padding(Space.xxl)
        .frame(width: 760)
        .background(Tone.bg)
    }
}

@ViewBuilder
func heading(_ t: String) -> some View {
    Text(t)
        .font(.system(size: 12, weight: .semibold))
        .tracking(0.8)
        .foregroundStyle(Tone.textSubtle)
}

@MainActor
func render(_ view: some View, to path: String) {
    let renderer = ImageRenderer(content: view)
    renderer.scale = 2
    guard let img = renderer.nsImage,
          let tiff = img.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else {
        print("✗ 渲染失败 \(path)"); exit(1)
    }
    do {
        try png.write(to: URL(fileURLWithPath: path))
        print("✓ \(Int(img.size.width))×\(Int(img.size.height)) → \(path)")
    } catch {
        print("✗ 写盘失败 \(path)：\(error)"); exit(1)
    }
}

// ImageRenderer 是 main-actor 隔离的；顶层代码本就跑在主线程，声明即可。
MainActor.assumeIsolated {
    let base = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "/tmp/cards.png"
    render(Bands(), to: base)
    let scales = base.replacingOccurrences(of: ".png", with: "-scales.png")
    render(Scales(), to: scales)
}
