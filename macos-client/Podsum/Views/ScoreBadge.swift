import SwiftUI

/// FR-027 有用性评分徽章。
/// usefulness 为 nil 时显示「未评分」——绝不渲染成 0，0 是一个真实且有意义的分数。
/// 真实数据里 29 个剧集只有 3 个有评分，所以「未评分」是稳定终态，不是加载占位。
struct ScoreBadge: View {
    let usefulness: Usefulness?

    var body: some View {
        if let u = usefulness {
            VStack(spacing: 0) {
                Text("\(u.score)")
                    .font(Typo.scoreSmall)
                    .monospacedDigit()
                Text(u.band.label)
                    .font(Typo.bandSmall)
            }
            .foregroundStyle(u.band.tint)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(u.band.tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
            .help(u.rationale)
            .accessibilityLabel("有用性 \(u.score) 分，\(u.band.label)")
        } else {
            Text("未评分")
                .font(Typo.band)
                .foregroundStyle(Tone.textSubtle)
                .padding(.horizontal, 9)
                .padding(.vertical, 9)
                .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: 10))
                .accessibilityLabel("未评分")
        }
    }
}

#Preview("四档 + 未评分") {
    HStack(spacing: 10) {
        ScoreBadge(usefulness: .init(score: 92, band: .known(.mustListen), rationale: "信息密度极高"))
        ScoreBadge(usefulness: .init(score: 72, band: .known(.worthListening), rationale: "有干货"))
        ScoreBadge(usefulness: .init(score: 62, band: .known(.skimmable), rationale: "摘要即可"))
        ScoreBadge(usefulness: .init(score: 31, band: .known(.skippable), rationale: "重复较多"))
        ScoreBadge(usefulness: nil)
    }
    .padding(24)
}
