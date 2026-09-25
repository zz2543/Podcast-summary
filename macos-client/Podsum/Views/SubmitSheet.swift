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
        var label: String { self == .links ? tr("链接", "Links") : tr("本地文件", "Local Files") }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Space.l) {
            HStack(spacing: Space.s) {
                Image(systemName: "sparkles")
                    .font(.system(size: 20 * scale, weight: .semibold))
                    .foregroundStyle(LinearGradient(colors: AIPalette.colors,
                                                    startPoint: .topLeading, endPoint: .bottomTrailing))
                Text(tr("添加剧集", "Add Episodes"))
                    .podsumFont(.hook)
                    .foregroundStyle(Tone.text)
            }

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
                Button(tr("取消", "Cancel")) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                    .glassButton()
                Button(submitting ? tr("提交中…", "Submitting…") : tr("提交", "Submit")) { submit() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(submitting || items.isEmpty)
                    .glassButton(prominent: true)
            }
            .controlSize(.large)
        }
        .padding(Space.xxl)
        .frame(width: 560 * min(scale, 1.4))
        .sheetPanel()
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
                RoundedRectangle(cornerRadius: Radius.large - 4)
                    .strokeBorder(Tone.info, style: StrokeStyle(lineWidth: 2, dash: [6, 4]))
                    .padding(4)
            }
        }
        // 光圈在拖文件进来、提交进行中时重新亮起：东西正要交给 AI
        .aiGlowBorder(in: SheetShape(), isActive: submitting || dropTargeted)
        .transparentHostWindow()
    }

    // MARK: 链接

    private var linksEditor: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            TextEditor(text: $linkText)
                .podsumFont(.mono)
                .scrollContentBackground(.hidden)
                .frame(height: 104 * scale)
                .padding(Space.s)
                .inputWell(RoundedRectangle(cornerRadius: Radius.medium))

            Text(tr("一行一个链接，直接粘分享文案也行。YouTube 与 B 站走 yt-dlp 抓取，其余当作直链音频。",
                    "One link per line — pasting share text works too. YouTube and Bilibili are fetched with yt-dlp; anything else is treated as a direct audio link."))
                .podsumFont(.micro)
                .foregroundStyle(Tone.textSubtle)

            if !parsedLinks.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(parsedLinks, id: \.0) { link, kind in
                        HStack(spacing: 6) {
                            Text(kind == .youtube ? tr("视频", "Video") : tr("直链", "Direct"))
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
                    Text(tr("把音频文件拖到这里", "Drop audio files here"))
                        .podsumFont(.secondary)
                        .foregroundStyle(Tone.textMuted)
                    Button(tr("选择文件…", "Choose Files…")) { chooseFiles() }
                        .glassButton()
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, Space.xxl)
                .inputWell(RoundedRectangle(cornerRadius: Radius.medium), dashed: true)
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
                .inputWell(RoundedRectangle(cornerRadius: Radius.medium))

                Button(tr("再添加…", "Add More…")) { chooseFiles() }
                    .glassButton()
            }
        }
    }

    // MARK: 摘要风格

    private var styleControls: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            Text(tr("摘要风格", "Summary Style"))
                .podsumFont(.sectionLabel).textCase(.uppercase)
                .foregroundStyle(Tone.textSubtle)

            HStack(spacing: Space.m) {
                StylePicker(title: tr("预设", "Preset"), selection: $style.preset,
                            options: SummaryPreset.allCases, label: Self.label(for:))
                StylePicker(title: tr("详略", "Detail"), selection: $style.detail,
                            options: SummaryDetail.allCases, label: Self.label(for:))
            }
            .podsumFont(.meta)

            TextField(tr("额外要求（可选，200 字以内）", "Extra instructions (optional, up to 200 characters)"), text: $style.note)
                .textFieldStyle(.plain)
                .podsumFont(.meta)
                .padding(.horizontal, Space.m).padding(.vertical, Space.s)
                .inputWell(RoundedRectangle(cornerRadius: Radius.small))
                .onChange(of: style.note) { _, new in
                    if new.count > 200 { style.note = String(new.prefix(200)) }
                }
        }
    }

    static func label(for preset: SummaryPreset) -> String {
        switch preset {
        case .default:         return tr("默认", "Default")
        case .studyNotes:      return tr("学习笔记", "Study Notes")
        case .businessInsight: return tr("商业洞察", "Business Insight")
        case .debate:          return tr("观点交锋", "Debate")
        case .quickSkim:       return tr("快速浏览", "Quick Skim")
        }
    }

    static func label(for detail: SummaryDetail) -> String {
        switch detail {
        case .concise:  return tr("精简", "Concise")
        case .standard: return tr("标准", "Standard")
        case .detailed: return tr("详尽", "Detailed")
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
        items.isEmpty ? tr("还没有要提交的内容", "Nothing to submit yet")
                      : tr("将提交 \(items.count) 项", items.count == 1 ? "1 item to submit" : "\(items.count) items to submit")
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

// MARK: - 外观
//
// 底板保持实色，玻璃只用在控件上：按钮、下拉菜单用 macOS 26 的玻璃样式，
// 更早的系统没有这些 API，退回系统默认控件。

/// sheet 的外轮廓。底板与光圈共用这一个形状，光才贴得住边。
struct SheetShape: Shape {
    func path(in rect: CGRect) -> Path {
        RoundedRectangle(cornerRadius: Radius.large).path(in: rect)
    }
}

/// 摘要风格的下拉选择。macOS 26 起是一颗玻璃按钮，点开弹出系统菜单，
/// 与底部按钮一致。
///
/// 没用 SwiftUI 的 Menu：它在 macOS 上画成系统弹出按钮，套不上玻璃胶囊；
/// 自己画胶囊再叠一个透明 Menu，点击又会被玻璃吃掉（实测都不行）。
private struct StylePicker<Value: Hashable>: View {
    var title: String
    @Binding var selection: Value
    var options: [Value]
    var label: (Value) -> String

    @State private var frame: CGRect = .zero

    var body: some View {
        if #available(macOS 26.0, *) {
            HStack(spacing: Space.s) {
                Text(title)
                Button(action: showMenu) {
                    HStack(spacing: 4) {
                        Text(label(selection))
                        Image(systemName: "chevron.down")
                            .font(.system(size: 9, weight: .semibold))
                            .foregroundStyle(Tone.textMuted)
                    }
                }
                .glassButton()
                .background(GeometryReader { geo in
                    Color.clear
                        .onAppear { frame = geo.frame(in: .global) }
                        .onChange(of: geo.frame(in: .global)) { _, new in frame = new }
                })
                .accessibilityLabel(title)
                .accessibilityValue(label(selection))
            }
        } else {
            Picker(title, selection: $selection) {
                ForEach(options, id: \.self) { Text(label($0)).tag($0) }
            }
        }
    }

    /// 在按钮正下方弹出菜单，当前选项打勾
    private func showMenu() {
        let menu = NSMenu()
        for option in options {
            let item = ActionMenuItem(title: label(option)) { selection = option }
            item.state = option == selection ? .on : .off
            menu.addItem(item)
        }
        guard let host = NSApp.keyWindow?.contentView else {
            menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
            return
        }
        // SwiftUI 的 global 坐标以宿主视图左上角为原点
        let y = host.isFlipped ? frame.maxY + 4 : host.bounds.height - frame.maxY - 4
        menu.popUp(positioning: nil, at: NSPoint(x: frame.minX, y: y), in: host)
    }
}

/// 带闭包的菜单项
private final class ActionMenuItem: NSMenuItem {
    private let handler: () -> Void

    init(title: String, handler: @escaping () -> Void) {
        self.handler = handler
        super.init(title: title, action: #selector(fire), keyEquivalent: "")
        target = self
    }

    required init(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    @objc private func fire() { handler() }
}

private extension View {
    /// 实色底板 + 细边 + 阴影。系统的 sheet 底板、边框和窗口阴影已被
    /// `transparentHostWindow()` 去掉（光圈要画在底板外面），这里照原样补上。
    func sheetPanel() -> some View {
        self
            .background(Tone.bg)
            .clipShape(SheetShape())
            .overlay(SheetShape().stroke(Color.primary.opacity(0.12), lineWidth: 1))
            // 阴影画在裁剪之外，否则会被一起裁掉
            .background(SheetShape().fill(Tone.bg).shadow(color: .black.opacity(0.3), radius: 24, y: 10))
    }

    /// 输入区：实色填充加一圈细边
    func inputWell(_ shape: some InsettableShape, dashed: Bool = false) -> some View {
        self
            .background(Tone.surface, in: shape)
            .overlay(shape.strokeBorder(Tone.border.opacity(dashed ? 1 : 0.6),
                                        style: StrokeStyle(lineWidth: 1, dash: dashed ? [5, 4] : [])))
    }

    @ViewBuilder
    func glassButton(prominent: Bool = false) -> some View {
        if #available(macOS 26.0, *) {
            // 统一成胶囊：常规尺寸的玻璃按钮默认是圆角矩形，和大号按钮不一致
            if prominent {
                self.buttonStyle(.glassProminent).buttonBorderShape(.capsule)
            } else {
                self.buttonStyle(.glass).buttonBorderShape(.capsule)
            }
        } else {
            self
        }
    }
}

#Preview("提交") {
    SubmitSheet { _ in }
}
