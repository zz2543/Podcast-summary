import SwiftUI

struct ChapterRow: View {
    let chapter: Chapter

    var body: some View {
        VStack(alignment: .leading, spacing: Space.m) {
            HStack(alignment: .firstTextBaseline) {
                Text("\(chapter.idx + 1). \(chapter.title)")
                    .podsumFont(.cardTitle)
                    .foregroundStyle(Tone.text)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 12)
                Text("\(Fmt.timestamp(chapter.startMs)) – \(Fmt.timestamp(chapter.endMs))")
                    .podsumFont(.mono)
                    .foregroundStyle(Tone.textMuted)
            }

            if !chapter.keyPoints.isEmpty {
                VStack(alignment: .leading, spacing: Space.s) {
                    ForEach(Array(chapter.keyPoints.enumerated()), id: \.offset) { _, point in
                        HStack(alignment: .top, spacing: 8) {
                            Circle()
                                .fill(Tone.textSubtle)
                                .frame(width: 4, height: 4)
                                .padding(.top, 8)
                            Text(point)
                                .podsumFont(.body)
                                .foregroundStyle(Tone.text)
                                .readable()
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }

            // 仅在要点本身丢失因果链时后端才给 summary，多数章节为 nil
            if let summary = chapter.summary, !summary.isEmpty {
                Text(summary)
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                    .readable()
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.leading, 10)
                    .overlay(alignment: .leading) {
                        Rectangle().fill(Tone.border).frame(width: 2)
                    }
            }

            if !chapter.quotes.isEmpty {
                VStack(alignment: .leading, spacing: Space.s) {
                    ForEach(Array(chapter.quotes.enumerated()), id: \.offset) { _, q in
                        QuoteBlock(quote: q)
                    }
                }
                .padding(.top, 2)
            }
        }
        .padding(Space.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(RoundedRectangle(cornerRadius: Radius.medium).strokeBorder(Tone.border.opacity(0.5)))
    }
}

/// 关键时刻。text 是经过逐字校验的原文，takeaway 是给读者的一句话解读——
/// 老数据没有 takeaway（5 份 fixture 里 3 份全 nil），那时只显示原文。
struct QuoteBlock: View {
    let quote: Quote

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .top, spacing: 8) {
                Text(Fmt.timestamp(quote.startMs))
                    .podsumFont(.monoSmall)
                    .foregroundStyle(Tone.info)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(Tone.info.opacity(0.10), in: Capsule())

                Text(quote.text)
                    .podsumFont(.body)
                    .italic()
                    .foregroundStyle(Tone.text)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let t = quote.takeaway, !t.isEmpty {
                Text(t)
                    .podsumFont(.secondary)
                    .foregroundStyle(Tone.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.leading, 56)
            }
        }
        .padding(Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surfaceElev.opacity(0.7), in: RoundedRectangle(cornerRadius: Radius.small))
    }
}
