import SwiftUI

/// 基于本集转录文稿的问答，与正文并排显示。
struct ChatPanel: View {
    let episodeID: String
    let episodeTitle: String

    @Environment(\.episodeRepository) private var repository
    @Environment(\.textScale) private var scale

    @State private var turns: [ChatTurn] = []
    @State private var draft = ""
    /// 正在流式接收的那条回答。单独存，和已完成的历史分开，
    /// 这样打断时能干净地丢掉半句话。
    @State private var streaming: String?
    @State private var task: Task<Void, Never>?
    @State private var failure: String?
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            transcriptArea
            Divider()
            composer
        }
        .background(Tone.bg)
        .onDisappear { task?.cancel() }
    }

    // MARK: 对话区

    private var transcriptArea: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Space.l) {
                    if turns.isEmpty && streaming == nil {
                        emptyState
                    }
                    ForEach(turns) { turn in
                        bubble(role: turn.role, text: turn.content)
                            .id(turn.id)
                    }
                    if let streaming {
                        bubble(role: .assistant, text: streaming.isEmpty ? "…" : streaming)
                            .id("streaming")
                    }
                    if let failure {
                        Label(failure, systemImage: "exclamationmark.triangle")
                            .podsumFont(.meta)
                            .foregroundStyle(Tone.err)
                            .textSelection(.enabled)
                    }
                }
                .padding(Space.l)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .onChange(of: streaming) { _, _ in
                withAnimation(.easeOut(duration: 0.12)) { proxy.scrollTo("streaming", anchor: .bottom) }
            }
            .onChange(of: turns.count) { _, _ in
                if let last = turns.last { proxy.scrollTo(last.id, anchor: .bottom) }
            }
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: Space.s) {
            Text(tr("问这一集", "Ask This Episode"))
                .podsumFont(.cardTitle)
                .foregroundStyle(Tone.text)
            Text(tr("回答只依据这一集的转录文稿。没有文稿的剧集（还在处理、或抓取失败）问不了。",
                    "Answers draw only on this episode’s transcript. Episodes without one (still processing, or failed to fetch) can’t be asked."))
                .podsumFont(.meta)
                .foregroundStyle(Tone.textSubtle)
                .readable()
            ForEach(Self.starters, id: \.self) { prompt in
                Button(prompt) { send(prompt) }
                    .buttonStyle(.plain)
                    .podsumFont(.meta)
                    .foregroundStyle(Tone.info)
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .background(Tone.surface, in: Capsule())
                    .overlay(Capsule().strokeBorder(Tone.border.opacity(0.6)))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    static var starters: [String] {
        [tr("这一集最值得记住的一点是什么？", "What’s the one thing most worth remembering from this episode?"),
         tr("主持人和嘉宾在哪里有分歧？", "Where do the host and guest disagree?"),
         tr("有哪些可以直接用的建议？", "What advice can I put to use right away?")]
    }

    private func bubble(role: ChatTurn.Role, text: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(role == .user ? tr("你", "You") : tr("助手", "Assistant"))
                .podsumFont(.micro)
                .foregroundStyle(Tone.textSubtle)
            Text(text)
                .podsumFont(.body)
                .foregroundStyle(Tone.text)
                .readable()
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .padding(Space.m)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    role == .user ? Tone.info.opacity(0.10) : Tone.surface,
                    in: RoundedRectangle(cornerRadius: Radius.small)
                )
        }
    }

    // MARK: 输入区

    private var composer: some View {
        VStack(spacing: Space.s) {
            TextField(tr("问点什么…", "Ask something…"), text: $draft, axis: .vertical)
                .textFieldStyle(.plain)
                .podsumFont(.secondary)
                .lineLimit(1...5)
                .focused($inputFocused)
                .padding(Space.s)
                .background(Tone.surface, in: RoundedRectangle(cornerRadius: Radius.small))
                .overlay(RoundedRectangle(cornerRadius: Radius.small).strokeBorder(Tone.border.opacity(0.6)))
                .onSubmit { send(draft) }

            HStack {
                if streaming != nil {
                    Button(tr("停止", "Stop")) { stop() }
                        .buttonStyle(.plain)
                        .podsumFont(.meta)
                        .foregroundStyle(Tone.err)
                }
                Spacer()
                Text(tr("⏎ 发送", "⏎ to send"))
                    .podsumFont(.micro)
                    .foregroundStyle(Tone.textSubtle)
                Button(tr("发送", "Send")) { send(draft) }
                    .disabled(draft.isBlank || streaming != nil)
            }
        }
        .padding(Space.m)
    }

    // MARK: 发送

    private func send(_ text: String) {
        let message = text.trimmed
        guard !message.isEmpty, streaming == nil else { return }
        draft = ""
        failure = nil
        let history = turns
        turns.append(ChatTurn(role: .user, content: message))
        streaming = ""

        task = Task {
            do {
                for try await token in repository.chat(id: episodeID, message: message, history: history) {
                    if Task.isCancelled { break }
                    streaming = (streaming ?? "") + token
                }
                // 半句话也留下：读者看见了就该能回看，而不是一闪而过。
                if let final = streaming, !final.isEmpty {
                    turns.append(ChatTurn(role: .assistant, content: final))
                }
            } catch {
                if let partial = streaming, !partial.isEmpty {
                    turns.append(ChatTurn(role: .assistant, content: partial))
                }
                failure = error.localizedDescription
            }
            streaming = nil
        }
    }

    private func stop() {
        task?.cancel()
        if let partial = streaming, !partial.isEmpty {
            turns.append(ChatTurn(role: .assistant, content: partial))
        }
        streaming = nil
    }
}

#Preview("对话面板") {
    ChatPanel(episodeID: "01M2FKVC8GT40083QZHH6VRSMW", episodeTitle: "示例")
        .frame(width: 360, height: 560)
}
