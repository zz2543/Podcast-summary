//
//  离屏设计核对：用 ImageRenderer 把组件渲染成 PNG，不启动 app、
//  也不需要屏幕解锁就能看到真实渲染结果。改完样式跑一遍核对。
//
//  swiftc -O specs/002-macos-native/contracts/PodsumModels.swift \
//         macos-client/Podsum/Design/Theme.swift \
//         macos-client/Podsum/Views/UsefulnessCard.swift \
//         macos-client/design-check/main.swift -o /tmp/podsum-design \
//    && /tmp/podsum-design /tmp/cards.png && open /tmp/cards.png
//
//  注意：ImageRenderer 不触发 onAppear，带入场动画的视图要用
//  animate: false 构造，否则截出来是未落位的空状态。
//
//  本文件不属于 app target——gen-project.py 只扫描 Podsum/，
//  这里另有一个 main，混进去会和 @main PodsumApp 冲突。
//

import SwiftUI
import AppKit

struct Sheet: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.l) {
            Text("有用性评分卡 · 四档 + 未评分")
                .font(Typo.sectionLabel).tracking(0.8)
                .foregroundStyle(Tone.textSubtle)
            UsefulnessCard(usefulness: .init(score: 92, band: .known(.mustListen),
                rationale: "信息密度极高，几乎每段都有可直接落地的做法。"),
                stage: .known(.present), promptVersion: "v1", animate: false)
            UsefulnessCard(usefulness: .init(score: 72, band: .known(.worthListening),
                rationale: "有干货，但前三分之一是寒暄，可以跳过。"),
                stage: .known(.present), animate: false)
            UsefulnessCard(usefulness: .init(score: 62, band: .known(.skimmable),
                rationale: "主播以出生人口下降、AI 冲击、学历扩招等具体背景支撑“衰退时代”论点，并给出实习、拥抱不确定性等建议，但缺乏新颖洞见且夹杂重复与闲聊，摘要即可获取核心要点。"),
                stage: .known(.present), promptVersion: "v1", animate: false)
            UsefulnessCard(usefulness: .init(score: 31, band: .known(.skippable),
                rationale: "重复较多，核心信息一段话即可概括。"),
                stage: .known(.present), animate: false)
            UsefulnessCard(usefulness: nil, stage: .known(.missing), animate: false)
            UsefulnessCard(usefulness: nil, stage: .known(.failedAfterRetries), animate: false)
        }
        .padding(Space.xxl)
        .frame(width: 760)
        .background(Tone.bg)
    }
}

// ImageRenderer 是 main-actor 隔离的；顶层代码本就跑在主线程，声明即可。
MainActor.assumeIsolated {
    let renderer = ImageRenderer(content: Sheet())
    renderer.scale = 2
    guard let img = renderer.nsImage,
          let tiff = img.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else {
        print("✗ 渲染失败"); exit(1)
    }
    let out = CommandLine.arguments[1]
    try! png.write(to: URL(fileURLWithPath: out))
    print("✓ 渲染 \(Int(img.size.width))×\(Int(img.size.height)) → \(out)")
}
