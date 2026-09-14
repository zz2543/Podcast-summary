import SwiftUI
import UniformTypeIdentifiers

/// 提交新剧集。对应 React 版的 SubmitModal，但做成 Mac 的 sheet：
/// 拖放进窗口、⌘⏎ 提交、Esc 取消。
struct SubmitSheet: View {
    @Environment(\.episodeRepository) private var repository
    @Environment(\.dismiss) private var dismiss
    @Environment(\.textScale) private var scale

    /// 提交成功后让列表刷新
    var onSubmitted: ([CreateEpisodeResponse]) -> Void

    @State private var mode: Mode = .links
    @State private var linkText = ""
    @State private var files: [URL] = []
    @State private var style = SummaryStyleInput()
    @State private var submitting = false
    @State private var failure: String?
    @State private var dropTargeted = false

    enum Mode: String, CaseIterable, Identifiable {
        case links, files
        var id: String { rawValue }
        var label: String { self == .links ? "链接" : "本地文件" }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Space.l) {
            Text("添加剧集")
                .podsumFont(.hook)
                .foregroundStyle(Tone.text)

            Picker("", selection: $mode) {
                ForEach(Mode.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            Group {
                switch mode {
                case .links: linksEditor
                case .files: filesArea
                }
            }

            styleControls

            if let failure {
                Label(failure, systemImage: "exclamationmark.triangle")
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.err)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Text(countSummary)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.textSubtle)
                Spacer()
                Button("取消") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(submitting ? "提交中…" : "提交") { submit() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(submitting || items.isEmpty)
            }
        }
        .padding(Space.xxl)
        .frame(width: 560 * min(scale, 1.4))
        .background(Tone.bg)
        // 整个 sheet 都是拖放区：拖文件进来自动切到「本地文件」
        .dropDestination(for: URL.self) { dropped, _ in
            let accepted = dropped.filter { $0.isFileURL }
            guard !accepted.isEmpty else { return false }
            files.append(contentsOf: accepted.filter { !files.contains($0) })
            mode = .files
            return true
        } isTargeted: { dropTargeted = $0 }
        .overlay {
            if dropTargeted {
                RoundedRectangle(cornerRadius: Radius.large)
                    .strokeBorder(Tone.info, style: StrokeStyle(lineWidth: 2, dash: [6, 4]))
                    .padding(4)
            }
        }
    }

    // MARK: 链接

    private var linksEditor: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            TextEditor(text: $linkText)
                .podsumFont(.mono)
                .scrollContentBackground(.hidden)
                .frame(height: 104 * scale)
                .padding(Space.s)
                .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.small))
                .overlay(RoundedRectangle(cornerRadius: Radius.small).strokeBorder(Tone.border.opacity(0.6)))

            Text("一行一个链接，直接粘分享文案也行。YouTube 与 B 站走 yt-dlp 抓取，其余当作直链音频。")
                .podsumFont(.micro)
                .foregroundStyle(Tone.textSubtle)

            if !parsedLinks.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(parsedLinks, id: \.0) { link, kind in
                        HStack(spacing: 6) {
                            Text(kind == .youtube ? "视频" : "直链")
                                .podsumFont(.micro)
                                .foregroundStyle(kind == .youtube ? Tone.info : Tone.textSubtle)
                                .padding(.horizontal, 6).padding(.vertical, 1)
                                .background((kind == .youtube ? Tone.info : Tone.textSubtle).opacity(0.12), in: Capsule())
                            Text(link)
                                .podsumFont(.micro)
                                .foregroundStyle(Tone.textMuted)
                                .lineLimit(1).truncationMode(.middle)
                        }
                    }
                }
            }
        }
    }

    // MARK: 文件

    private var filesArea: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            if files.isEmpty {
                VStack(spacing: Space.s) {
                    Image(systemName: "square.and.arrow.down")
                        .font(.system(size: 22 * scale))
                        .foregroundStyle(Tone.textSubtle)
                    Text("把音频文件拖到这里")
                        .podsumFont(.secondary)
                        .foregroundStyle(Tone.textMuted)
                    Button("选择文件…") { chooseFiles() }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, Space.xxl)
                .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.medium))
                .overlay(
                    RoundedRectangle(cornerRadius: Radius.medium)
                        .strokeBorder(Tone.border, style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
                )
            } else {
                VStack(spacing: 0) {
                    ForEach(files, id: \.self) { url in
                        HStack {
                            Image(systemName: "waveform").foregroundStyle(Tone.textSubtle)
                            Text(url.lastPathComponent)
                                .podsumFont(.meta)
                                .lineLimit(1).truncationMode(.middle)
                            Spacer()
                            Text(Self.sizeText(url))
                                .podsumFont(.micro).monospacedDigit()
                                .foregroundStyle(Tone.textSubtle)
                            Button {
                                files.removeAll { $0 == url }
                            } label: {
                                Image(systemName: "xmark.circle.fill").foregroundStyle(Tone.textSubtle)
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, Space.m).padding(.vertical, Space.s)
                        if url != files.last { Divider() }
                    }
                }
                .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.small))
                .overlay(RoundedRectangle(cornerRadius: Radius.small).strokeBorder(Tone.border.opacity(0.6)))

                Button("再添加…") { chooseFiles() }
                    .buttonStyle(.plain)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.info)
            }
        }
    }

    // MARK: 摘要风格

    private var styleControls: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            Text("摘要风格")
                .podsumFont(.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)

            HStack(spacing: Space.m) {
                Picker("预设", selection: $style.preset) {
                    ForEach(SummaryPreset.allCases, id: \.self) { Text(Self.label(for: $0)).tag($0) }
                }
                Picker("详略", selection: $style.detail) {
                    ForEach(SummaryDetail.allCases, id: \.self) { Text(Self.label(for: $0)).tag($0) }
                }
            }
            .podsumFont(.meta)

            TextField("额外要求（可选，200 字以内）", text: $style.note)
                .textFieldStyle(.roundedBorder)
                .podsumFont(.meta)
                .onChange(of: style.note) { _, new in
                    if new.count > 200 { style.note = String(new.prefix(200)) }
                }
        }
    }

    static func label(for preset: SummaryPreset) -> String {
        switch preset {
        case .default:         return "默认"
        case .studyNotes:      return "学习笔记"
        case .businessInsight: return "商业洞察"
        case .debate:          return "观点交锋"
        case .quickSkim:       return "快速浏览"
        }
    }

    static func label(for detail: SummaryDetail) -> String {
        switch detail {
        case .concise:  return "精简"
        case .standard: return "标准"
        case .detailed: return "详尽"
        }
    }

    static func sizeText(_ url: URL) -> String {
        let bytes = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }

    // MARK: 数据

    /// 一行一项，抠出其中的链接。显示与提交用的都是抠出来的那一段而不是原文——
    /// 读者得看见系统究竟认出了什么，否则粘一段分享文案被归错类时，
    /// 界面上没有任何线索。
    private var parsedLinks: [(String, SourceType)] {
        linkText.split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
            .map { line in
                let url = Submission.extractURL(line)
                return (url, Submission.guessSourceType(url))
            }
    }

    private var items: [Submission.Item] {
        switch mode {
        case .links: return parsedLinks.map { .link($0.0, sourceType: $0.1) }
        case .files: return files.map { .file($0) }
        }
    }

    private var countSummary: String {
        items.isEmpty ? "还没有要提交的内容" : "将提交 \(items.count) 项"
    }

    private func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.audio, .mpeg4Audio, .mp3, .wav, .aiff, .movie, .mpeg4Movie]
        guard panel.runModal() == .OK else { return }
        files.append(contentsOf: panel.urls.filter { !files.contains($0) })
    }

    private func submit() {
        submitting = true
        failure = nil
        let submission = Submission(items: items, style: style)
        Task {
            do {
                let created = try await repository.create(submission)
                onSubmitted(created)
                dismiss()
            } catch {
                failure = error.localizedDescription
            }
            submitting = false
        }
    }
}

#Preview("提交") {
    SubmitSheet { _ in }
}
