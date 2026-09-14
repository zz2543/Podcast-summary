import SwiftUI

/// 列表页顶部的进行中条。只在真有任务时出现——
/// 一条常驻的空横幅只会占地方。
struct ActiveJobsStrip: View {
    let jobs: [Job]
    /// episodeID → 标题，用于把任务对上剧集名
    let titles: [String: String]
    var onSelect: (String) -> Void

    var body: some View {
        VStack(spacing: Space.s) {
            ForEach(jobs) { job in
                Button { onSelect(job.episodeID) } label: { row(job) }
                    .buttonStyle(.plain)
            }
        }
        .padding(Space.m)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(RoundedRectangle(cornerRadius: Radius.medium).strokeBorder(Tone.border.opacity(0.5)))
    }

    private func row(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: Space.s) {
                ProgressView().controlSize(.small)
                Text(titles[job.episodeID] ?? job.episodeID)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.text)
                    .lineLimit(1)
                Spacer(minLength: Space.s)
                Text(job.state.label)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.textMuted)
                if job.attempt > 1 {
                    Text("第 \(job.attempt) 次")
                        .podsumFont(.micro)
                        .foregroundStyle(Tone.warn)
                }
            }
            // 后端不发百分比，只发当前阶段——进度由阶段序号推出来，
            // 所以它是跳变的而不是连续的。这一点如实呈现，不做假的平滑动画。
            ProgressView(value: job.state.fraction)
                .progressViewStyle(.linear)
                .tint(Tone.info)
        }
        .contentShape(Rectangle())
    }
}
