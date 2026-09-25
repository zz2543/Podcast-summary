import SwiftUI

struct ChapterRow: View {
    let chapter: Chapter
    /// 有音频时时间戳才是可点的。没有音频还画成按钮是骗人。
    var onSeek: ((Int) -> Void)?
    /// 播放头是否落在本章内
    var isCurrent = false

    var body: some View {
        VStack(alignment: .leading, spacing: Space.m) {
            HStack(alignment: .firstTextBaseline) {
                Text("\(chapter.idx + 1). \(chapter.title)")
                    .podsumFont(.cardTitle)
                    .foregroundStyle(Tone.text)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 12)
                TimestampButton(
                    label: "\(Fmt.timestamp(chapter.startMs)) – \(Fmt.timestamp(chapter.endMs))",
                    ms: chapter.startMs,
                    onSeek: onSeek
                )
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
                        QuoteBlock(quote: q, onSeek: onSeek)
                    }
                }
                .padding(.top, 2)
            }
        }
        .padding(Space.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.medium)
                .strokeBorder(isCurrent ? Tone.info.opacity(0.75) : Tone.border.opacity(0.5),
                              lineWidth: isCurrent ? 1.5 : 1)
        )
    }
}

/// 时间戳。能跳就是按钮，不能跳就是一段普通文字——
/// 外观上必须看得出区别，否则点了没反应会让人以为坏了。
struct TimestampButton: View {
    let label: String
    let ms: Int
    var onSeek: ((Int) -> Void)?
    var tint: Color = Tone.textMuted

    var body: some View {
        if let onSeek {
            Button { onSeek(ms) } label: {
                HStack(spacing: 3) {
                    Image(systemName: "play.fill").font(.system(size: 8))
                    Text(label).podsumFont(.mono).lineLimit(1)
                }
                .fixedSize(horizontal: true, vertical: false)
                .foregroundStyle(Tone.info)
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(Tone.info.opacity(0.10), in: Capsule())
                .contentShape(Capsule())
            }
            .buttonStyle(.plain)
            .help(tr("从这里开始播放", "Play from here"))
        } else {
            Text(label)
                .podsumFont(.mono)
                .lineLimit(1)
                .fixedSize(horizontal: true, vertical: false)
                .foregroundStyle(tint)
        }
    }
}

/// 关键时刻。text 是经过逐字校验的原文，takeaway 是给读者的一句话解读——
/// 老数据没有 takeaway（5 份 fixture 里 3 份全 nil），那时只显示原文。
struct QuoteBlock: View {
    let quote: Quote
    var onSeek: ((Int) -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .top, spacing: 8) {
                TimestampButton(label: Fmt.timestamp(quote.startMs), ms: quote.startMs,
                                onSeek: onSeek, tint: Tone.info)

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
