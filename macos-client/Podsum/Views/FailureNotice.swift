import SwiftUI

/// 把 `last_failure` 翻成人话：卡在哪一步、大概为什么、接下来该做什么。
/// 原始报错仍然保留（可选中复制），翻译只是给出方向，不替代它。
enum FailureCopy {
    static func stage(_ raw: String?) -> String {
        switch raw {
        case "fetch":               return tr("抓取音频", "fetching audio")
        case "transcribe":          return tr("转写", "transcription")
        case "summarize_hook":      return tr("生成一句话摘要", "one-line summary")
        case "summarize_three_act": return tr("生成三幕摘要", "three-act summary")
        case "usefulness_score":    return tr("评分", "scoring")
        case "chapter_outline":     return tr("划分章节", "chapter outline")
        case "quote_verify":        return tr("核对引文", "quote verification")
        case "entity_extract":      return tr("抽取提及", "extracting mentions")
        case "export":              return tr("导出文件", "export")
        case nil:                   return tr("处理", "processing")
        case let other?:            return other   // 后端新增的阶段：如实显示
        }
    }

    /// 能认出来的常见原因给一句建议；认不出就返回 nil，只展示原始报错。
    static func hint(_ error: String) -> String? {
        let e = error.lowercased()
        func has(_ needles: String...) -> Bool { needles.contains { e.contains($0) } }
        // 状态码只认独立的数字，免得撞上报错里的路径、时长或 ID
        func code(_ codes: String...) -> Bool {
            codes.contains { e.range(of: "\\b\($0)\\b", options: .regularExpression) != nil }
        }
        if has("insufficient balance") || code("402") {
            return tr("模型服务余额不足。充值后点「重新处理」。",
                      "The model provider is out of credit. Top up, then click Reprocess.")
        }
        if has("unauthorized", "forbidden", "is required", "invalid api key") || code("401", "403") {
            return tr("服务凭证无效或缺失，到设置里检查对应的密钥。",
                      "A credential is invalid or missing — check the matching key in Settings.")
        }
        if has("too many requests", "rate limit") || code("429") {
            return tr("请求太频繁被限流了，过几分钟再重新处理。",
                      "Rate limited for sending too many requests. Wait a few minutes, then reprocess.")
        }
        if has("connection reset", "connection aborted", "remote end closed", "timed out",
               "timeout", "writeerror", "readerror", "errno 54", "errno 60", "ssl", "eof occurred") {
            return tr("网络连接中途断了，通常是临时的，重新处理一般就能过。",
                      "The network connection dropped midway. It’s usually temporary — reprocessing normally gets through.")
        }
        if has("file exists") {
            return tr("上一次处理留下的文件挡住了这一次，重新处理即可。",
                      "Files left from the previous run got in the way. Just reprocess.")
        }
        if has("unsupported", "invalid audio", "audio convert failed") {
            return tr("音频格式识别不了，换个来源链接或本地文件再试。",
                      "The audio format wasn’t recognized. Try a different link or a local file.")
        }
        return nil
    }
}

/// 详情页顶部的失败说明。两种语气：
///  · 没有可读的摘要（status == failed）：醒目，这就是这一集现在的全部状况；
///  · 摘要还在，只是最近一次重新处理没成：轻提示，下面的内容仍然可信。
struct FailureNotice: View {
    let failure: JobFailure
    let hasSummary: Bool
    var working = false
    let onRetry: () -> Void

    @State private var showRaw = false

    var body: some View {
        HStack(alignment: .top, spacing: Space.m) {
            Image(systemName: hasSummary ? "exclamationmark.circle" : "exclamationmark.triangle.fill")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(hasSummary ? Tone.warn : Tone.err)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: Space.s) {
                Text(title)
                    .podsumFont(.cardTitle)
                    .foregroundStyle(Tone.text)

                if let hint = FailureCopy.hint(failure.error) {
                    Text(hint)
                        .podsumFont(.secondary)
                        .foregroundStyle(Tone.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if showRaw || FailureCopy.hint(failure.error) == nil {
                    Text(failure.error.isEmpty ? tr("（后端没有留下报错信息）", "(The backend left no error message)") : failure.error)
                        .podsumFont(.micro)
                        .monospaced()
                        .foregroundStyle(Tone.textSubtle)
                        .textSelection(.enabled)
                        .lineLimit(showRaw ? nil : 3)
                        .fixedSize(horizontal: false, vertical: true)
                }

                HStack(spacing: Space.m) {
                    Button(action: onRetry) {
                        Label(tr("重新处理", "Reprocess"), systemImage: "arrow.clockwise")
                    }
                    .controlSize(.small)
                    .disabled(working)

                    if FailureCopy.hint(failure.error) != nil {
                        Button(showRaw ? tr("收起原始报错", "Hide Raw Error") : tr("查看原始报错", "Show Raw Error")) { showRaw.toggle() }
                            .buttonStyle(.link)
                            .controlSize(.small)
                    }

                    if let at = failure.finishedAt {
                        Text(Fmt.relative(at))
                            .podsumFont(.meta)
                            .foregroundStyle(Tone.textSubtle)
                    }
                }
                .padding(.top, Space.xs)
            }
            Spacer(minLength: 0)
        }
        .padding(Space.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.07), in: RoundedRectangle(cornerRadius: Radius.large))
        .overlay(RoundedRectangle(cornerRadius: Radius.large).strokeBorder(tint.opacity(0.28)))
        .accessibilityElement(children: .contain)
    }

    private var tint: Color { hasSummary ? Tone.warn : Tone.err }

    private var title: String {
        let step = FailureCopy.stage(failure.stage)
        return hasSummary
            ? tr("最近一次重新处理卡在「\(step)」，下面仍是上一次的结果",
                 "The latest reprocess got stuck at \(step); below is still the previous result")
            : tr("处理卡在「\(step)」这一步，还没有生成摘要",
                 "Processing got stuck at \(step); no summary yet")
    }
}

#Preview("两种语气") {
    VStack(spacing: Space.l) {
        FailureNotice(
            failure: JobFailure(jobID: "J1", stage: "transcribe",
                                error: "[Errno 54] Connection reset by peer", attempt: 1,
                                finishedAt: Date().addingTimeInterval(-3600)),
            hasSummary: false, onRetry: {})
        FailureNotice(
            failure: JobFailure(jobID: "J2", stage: "summarize_hook",
                                error: "Error code: 402 - {'error': {'message': 'Insufficient Balance'}}",
                                attempt: 3, finishedAt: nil),
            hasSummary: true, onRetry: {})
        FailureNotice(
            failure: JobFailure(jobID: "J3", stage: "export",
                                error: "KeyError: 'chapters'", attempt: 2, finishedAt: nil),
            hasSummary: false, onRetry: {})
    }
    .padding(Space.xxl)
    .frame(width: 820)
    .background(Tone.bg)
}
