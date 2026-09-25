import SwiftUI

/// 详情页评分卡：hook 说这集讲什么，这张卡说值不值得花时间。
///
/// 布局按 HIG 的"按重要性排序 + 对齐传达关联"：
/// 标签与档位在同一行两端，分数与 /100 共基线，刻度线在分数正下方对齐，
/// 理由独立成段。分数本身已在文字中写明，刻度线只是辅助，故对无障碍隐藏。
struct UsefulnessCard: View {
    let usefulness: Usefulness?
    let stage: Fallback<StageStatus>
    let promptVersion: String?

    /// 刻度条的填充比例。入场时从 0 动画到分数值。
    /// 传 animate: false 可跳过动画直接落位——离屏渲染（ImageRenderer）不触发
    /// onAppear，没有这个开关截出来的图会是空条。
    @State private var fill: CGFloat
    @Environment(\.textScale) private var scale

    init(usefulness: Usefulness?,
         stage: Fallback<StageStatus>,
         promptVersion: String? = nil,
         animate: Bool = true) {
        self.usefulness = usefulness
        self.stage = stage
        self.promptVersion = promptVersion
        let target = CGFloat(usefulness?.score ?? 0) / 100
        _fill = State(initialValue: animate ? 0 : target)
    }

    var body: some View {
        if let u = usefulness { scored(u) } else { unrated }
    }

    // MARK: 有评分

    private func scored(_ u: Usefulness) -> some View {
        VStack(alignment: .leading, spacing: Space.l) {
            HStack(alignment: .firstTextBaseline) {
                Text(tr("有用性评分", "Usefulness Score"))
                    .podsumFont(.sectionLabel)
                    .tracking(0.8)
                    .foregroundStyle(Tone.textSubtle)
                Spacer(minLength: Space.m)
                Text(u.band.label)
                    .podsumFont(.band)
                    .foregroundStyle(u.band.tint)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(u.band.tint.opacity(0.13), in: Capsule())
            }

            VStack(alignment: .leading, spacing: Space.m) {
                HStack(alignment: .firstTextBaseline, spacing: 5) {
                    Text("\(u.score)")
                        .podsumFont(.score)
                        .monospacedDigit()
                        .foregroundStyle(Tone.text)
                    Text("/ 100")
                        .podsumFont(.secondary)
                        .foregroundStyle(Tone.textSubtle)
                }

                scale(u)
            }

            Text(u.rationale)
                .podsumFont(.body)
                .foregroundStyle(Tone.text)
                .readable()
                .fixedSize(horizontal: false, vertical: true)

            if let v = promptVersion {
                Text(tr("Prompt 版本 \(v)", "Prompt version \(v)"))
                    .podsumFont(.micro)
                    .foregroundStyle(Tone.textSubtle)
            }
        }
        .padding(Space.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.large))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.large)
                .strokeBorder(Tone.border.opacity(0.5))
        )
        .onAppear {
            withAnimation(.easeOut(duration: 0.65).delay(0.08)) {
                fill = CGFloat(u.score) / 100
            }
        }
    }

    /// 分数刻度条。四档的分界（50 / 70 / 85）以缺口形式切穿整条，
    /// 让"62 落在可跳读这一档"在视觉上可验证，而不只是一个色块。
    ///
    /// 缺口用 destinationOut 挖出，因此无论落在已填充还是未填充的一侧都可见——
    /// 直接画线会被填充盖住。
    private func scale(_ u: Usefulness) -> some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Tone.border.opacity(0.34))

                Capsule()
                    .fill(u.band.tint)
                    .frame(width: max(7 * scale, geo.size.width * fill))

                ForEach([50, 70, 85], id: \.self) { mark in
                    Rectangle()
                        .frame(width: 2 * scale)
                        .offset(x: geo.size.width * CGFloat(mark) / 100 - scale)
                        .blendMode(.destinationOut)
                }
            }
            .compositingGroup()
        }
        // 条高随字号走，否则字放大后这条会显得过细
        .frame(height: 7 * scale)
        .accessibilityHidden(true)
    }

    // MARK: 无评分
    //
    // 29 集里有 26 集是这个状态，所以它是稳定终态，不能做成加载占位。
    // 读 stage_status 给出具体原因，而不是笼统的"暂无"。

    private var unrated: some View {
        HStack(alignment: .top, spacing: Space.l) {
            Image(systemName: "minus.circle")
                .font(.system(size: 17 * scale))
                .foregroundStyle(Tone.textSubtle)
                .frame(width: 34 * scale, height: 34 * scale)
                .background(Tone.surfaceElev, in: Circle())

            VStack(alignment: .leading, spacing: Space.xs) {
                Text(tr("未评分", "Unrated"))
                    .podsumFont(.cardTitle)
                    .foregroundStyle(Tone.text)
                Text(reason)
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                    .readable()
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(Space.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.large))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.large)
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
                .foregroundStyle(Tone.border.opacity(0.8))
        )
    }

    private var reason: String {
        switch stage.value {
        case .failedAfterRetries: return tr("评分阶段多次重试后仍失败，其余摘要不受影响；可在「更多」里重新处理。",
                                             "Scoring still failed after several retries. The rest of the summary is unaffected; reprocess it from “More”.")
        case .pending:            return tr("评分阶段尚未运行。", "Scoring hasn’t run yet.")
        case .missing:            return tr("这集入库时评分功能还不存在。", "This episode predates scoring.")
        default:                  return tr("这集没有评分记录。", "No score recorded for this episode.")
        }
    }
}

#Preview("四档 + 未评分") {
    ScrollView {
        VStack(spacing: Space.l) {
            UsefulnessCard(
                usefulness: .init(score: 92, band: .known(.mustListen),
                                  rationale: "信息密度极高，几乎每段都有可直接落地的做法。"),
                stage: .known(.present), promptVersion: "v1")
            UsefulnessCard(
                usefulness: .init(score: 72, band: .known(.worthListening),
                                  rationale: "有干货，但前三分之一是寒暄，可以跳过。"),
                stage: .known(.present))
            UsefulnessCard(
                usefulness: .init(score: 62, band: .known(.skimmable),
                                  rationale: "主播以出生人口下降、AI 冲击、学历扩招等具体背景支撑“衰退时代”论点，并给出实习、拥抱不确定性等建议，但缺乏新颖洞见且夹杂重复与闲聊，摘要即可获取核心要点。"),
                stage: .known(.present))
            UsefulnessCard(
                usefulness: .init(score: 31, band: .known(.skippable),
                                  rationale: "重复较多，核心信息一段话即可概括。"),
                stage: .known(.present))
            UsefulnessCard(usefulness: nil, stage: .known(.missing))
            UsefulnessCard(usefulness: nil, stage: .known(.failedAfterRetries))
        }
        .padding(Space.xxl)
    }
    .background(Tone.bg)
    .frame(width: 820, height: 900)
}
