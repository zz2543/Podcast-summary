import SwiftUI

/// 详情页评分卡：hook 说这集讲什么，这张卡说值不值得花时间。
/// 无评分时不是留白，而是明确说明原因——29 集里有 26 集是这个状态。
struct UsefulnessCard: View {
    let usefulness: Usefulness?
    let stage: Fallback<StageStatus>

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            if let u = usefulness {
                VStack(spacing: 1) {
                    Text("\(u.score)")
                        .font(Typo.score)
                        .monospacedDigit()
                    Text(u.band.label)
                        .font(Typo.band)
                }
                .foregroundStyle(u.band.tint)
                .frame(width: 78)
                .padding(.vertical, 12)
                .background(u.band.tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 14))

                VStack(alignment: .leading, spacing: 5) {
                    Text("有用性评分")
                        .font(Typo.sectionLabel).textCase(.uppercase)
                        .foregroundStyle(Tone.textSubtle)
                    Text(u.rationale)
                        .font(Typo.body)
                        .foregroundStyle(Tone.text)
                        .readable()
                        .fixedSize(horizontal: false, vertical: true)
                }
            } else {
                Image(systemName: "minus.circle")
                    .font(.system(size: 28))
                    .foregroundStyle(Tone.textSubtle)
                    .frame(width: 78, height: 66)
                    .background(Tone.surfaceElev, in: RoundedRectangle(cornerRadius: 14))

                VStack(alignment: .leading, spacing: 5) {
                    Text("未评分")
                        .font(Typo.sectionLabel).textCase(.uppercase)
                        .foregroundStyle(Tone.textSubtle)
                    Text(reason)
                        .font(Typo.body)
                        .foregroundStyle(Tone.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Tone.border.opacity(0.55)))
    }

    private var reason: String {
        switch stage.value {
        case .failedAfterRetries: return "评分阶段多次重试后仍失败。"
        case .pending:            return "评分阶段尚未运行。"
        case .missing:            return "这集入库时评分功能还不存在。"
        default:                  return "这集没有评分记录。"
        }
    }
}
