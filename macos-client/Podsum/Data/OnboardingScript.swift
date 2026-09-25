import Foundation

/// 引导的一步：指向哪一格、讲什么、去哪儿拿、完成条件是什么。
struct OnboardingStep: Identifiable {
    struct Link {
        let title: String
        let url: URL
    }

    /// 一键填入。只动与这一步相关的字段。
    struct Preset {
        let title: String
        let apply: @MainActor (AppSettings) -> Void
    }

    enum Status: Equatable {
        case waiting(String)
        case working(String)
        case done(String)
        case problem(String)

        var isDone: Bool { if case .done = self { return true }; return false }
    }

    let id: String
    /// nil = 没有目标，气泡居中（欢迎页、收尾页）
    var target: OnboardingTarget?
    var symbol: String
    var title: String
    /// 支持 Markdown 的 **加粗** 与 `代码`
    var body: String
    var tips: [String] = []
    var example: String?
    var links: [Link] = []
    var presets: [Preset] = []
    /// 这一格的值要去厂商网站拿：气泡上给一个「带我去网站创建」，打开浏览器 + 悬浮面板逐步指引
    var walkthrough: WebWalkthrough.ID?
    /// nil = 纯说明，没有完成条件
    var status: (@MainActor (AppSettings, OnboardingGuide, BackendController) -> Status)?
}

/// 引导的全部内容。按当前所选供应商现算：换了供应商，后面的步骤随之换成那一家的字段，
/// 永远不会指向一个此刻不在界面上的输入框。
///
/// 写法上的要求：每一格都要讲到能照着做——去哪个控制台、点哪几下、值长什么样、常见的坑。
@MainActor
enum OnboardingScript {
    static func steps(_ s: AppSettings) -> [OnboardingStep] {
        var steps = [welcome]
        steps += llmSteps(s)
        steps += asrSteps(s)
        steps += ttsSteps(s)
        steps += [apply, done]
        return steps
    }

    // MARK: - 欢迎

    static var welcome: OnboardingStep {
        OnboardingStep(
        id: "welcome",
        target: nil,
        symbol: "hand.wave",
        title: tr("欢迎使用 Podsum", "Welcome to Podsum"),
        body: tr("接下来几分钟，我会在这个设置页上**一格一格**带你把 API 填好。Podsum 不内置任何人的账号——摘要和转写用的是**你自己的** API，按用量付给你选的厂商；密钥只存在这台 Mac 的钥匙串里。",
                 "Over the next few minutes I’ll walk you through this settings page **one field at a time**. Podsum ships with no accounts — summaries and transcripts run on **your own** APIs, billed by usage to the vendors you pick, and keys stay in this Mac’s keychain."),
        tips: [
            tr("**必填两样**：写摘要用的大模型（LLM），把音频转成文字的转写服务（ASR）。",
               "**Two required**: a language model (LLM) for summaries, and a transcription service (ASR) that turns audio into text."),
            tr("**可选一样**：音频摘要（TTS），把摘要读给你听，可以以后再开。",
               "**One optional**: audio summaries (TTS) that read the summary aloud — you can turn it on later."),
            tr("每一步都直接在**高亮的输入框**里操作，填好的瞬间气泡底部会打勾。随时可以「跳过引导」，以后在「设置 › 通用」里重新开始。",
               "Type straight into the **highlighted field** each time — the bubble ticks the moment it’s filled. You can skip anytime and restart from Settings › General."),
            tr("不知道怎么选？点下面的按钮用推荐组合，之后每一步都还能改。",
               "Not sure what to pick? Use the recommended setup below — every step can still be changed."),
        ],
        presets: [
            .init(title: tr("推荐：DeepSeek 写摘要 + 豆包转写", "Recommended: DeepSeek + Doubao")) { s in
                s.llmProvider = .openAICompatible
                if s.llmBaseURL.isBlank { s.llmBaseURL = "https://api.deepseek.com" }
                if s.llmModel.isBlank { s.llmModel = "deepseek-flash" }
                s.asrProvider = .doubao
                s.ttsEnabled = false
            },
        ],
        status: { s, _, _ in
            .done(tr("当前组合：摘要用 \(s.llmProvider.label)，转写用 \(s.asrProvider.label)",
                     "Current setup: summaries via \(s.llmProvider.label), transcription via \(s.asrProvider.label)"))
        }
        )
    }

    // MARK: - 摘要（LLM）

    static func llmSteps(_ s: AppSettings) -> [OnboardingStep] {
        var steps = [OnboardingStep(
            id: "llm.provider",
            target: .llmProvider,
            symbol: "text.bubble",
            title: tr("① 摘要用哪个大模型", "① Which model writes the summaries"),
            body: tr("大模型负责写摘要、划章节、回答你对某一集的追问。点高亮这一行右边的下拉框选一种接法：",
                     "The model writes summaries, splits chapters and answers your follow-up questions. Use the menu on the highlighted row to pick how to connect:"),
            tips: [
                tr("**OpenAI 兼容接口**：DeepSeek、OpenAI、阿里云百炼、Kimi、硅基流动……只要支持 `/chat/completions` 都能接，地址自己填。新手推荐 **DeepSeek**：便宜，中文好。",
                   "**OpenAI-compatible**: DeepSeek, OpenAI, Alibaba Bailian, Kimi, SiliconFlow… anything that speaks `/chat/completions`. **DeepSeek** is a good first pick: cheap and strong in Chinese."),
                tr("**通义千问（DashScope）**：阿里云百炼的原生接口，和音频摘要可以**共用一个 key**。",
                   "**Qwen (DashScope)**: Alibaba Bailian’s native API — **one key** can also cover audio summaries."),
                tr("**Anthropic**：Claude 系列模型，需要当前网络能访问 Anthropic。",
                   "**Anthropic**: Claude models; your network must be able to reach Anthropic."),
                tr("选完以后，下面的输入框会跟着换，引导也会跟着换。",
                   "The fields below — and the rest of this guide — follow your choice."),
            ],
            status: { s, _, _ in .done(tr("已选：\(s.llmProvider.label)", "Selected: \(s.llmProvider.label)")) }
        )]

        switch s.llmProvider {
        case .openAICompatible:
            steps += [llmBaseURL, llmModel(s), llmKey(s), llmTest]
        case .qwen:
            steps += [qwenModel, dashscopeKey(target: .llmKey, id: "llm.dashscope", title: tr("③ DashScope API Key", "③ DashScope API Key"), alreadyShared: false)]
        case .anthropic:
            steps += [anthropicModel, anthropicKey]
        }
        return steps
    }

    static var llmBaseURL: OnboardingStep {
        OnboardingStep(
        id: "llm.baseURL",
        target: .llmBaseURL,
        symbol: "link",
        title: tr("② 接口地址（Base URL）", "② Base URL"),
        body: tr("厂商文档里写的 **base_url**。Podsum 会在后面自动拼上 `/chat/completions`，所以不要把它也写进来，也不要填网页控制台的地址。",
                 "The **base_url** from the vendor’s docs. Podsum appends `/chat/completions` itself — don’t include it, and don’t use the web console address."),
        tips: [
            tr("用下面的按钮一键填入常见厂商（地址取自各家官方文档），或者从你所用厂商的文档里复制。",
               "Use a button below for a common vendor (taken from their official docs), or copy it from your vendor’s docs."),
            tr("各家写法不同：DeepSeek 是不带 `/v1` 的根地址，OpenAI 和百炼要带。照文档原样填即可。",
               "Vendors differ: DeepSeek’s is the bare root without `/v1`; OpenAI and Bailian include it. Copy exactly what the docs say."),
        ],
        example: "https://api.deepseek.com",
        presets: [
            .init(title: "DeepSeek") { $0.llmBaseURL = "https://api.deepseek.com" },
            .init(title: "OpenAI") { $0.llmBaseURL = "https://api.openai.com/v1" },
            .init(title: tr("阿里云百炼", "Alibaba Bailian")) { $0.llmBaseURL = "https://dashscope.aliyuncs.com/compatible-mode/v1" },
        ],
        status: { s, _, _ in
            let url = s.llmBaseURL.trimmed
            if url.isEmpty { return .waiting(tr("等你填写，或点上面的按钮一键填入", "Waiting — type it or use a button above")) }
            if !url.hasPrefix("http://") && !url.hasPrefix("https://") {
                return .problem(tr("地址要以 https:// 开头", "The address should start with https://"))
            }
            if url.contains("chat/completions") {
                return .problem(tr("去掉末尾的 /chat/completions，Podsum 会自己加", "Drop the trailing /chat/completions — Podsum adds it"))
            }
            return .done(tr("已填好", "Filled in"))
        }
        )
    }

    /// 按接口地址认出厂商，给出对应的模型建议与取 key 的页面
    private enum Vendor { case deepseek, openai, bailian, other }

    private static func vendor(of baseURL: String) -> Vendor {
        let host = URL(string: baseURL.trimmed)?.host ?? ""
        if host.hasSuffix("deepseek.com") { return .deepseek }
        if host.hasSuffix("openai.com") { return .openai }
        if host.hasSuffix("aliyuncs.com") { return .bailian }
        return .other
    }

    static func llmModel(_ s: AppSettings) -> OnboardingStep {
        let presets: [OnboardingStep.Preset]
        switch vendor(of: s.llmBaseURL) {
        case .deepseek: presets = [.init(title: "deepseek-flash") { $0.llmModel = "deepseek-flash" },
                                   .init(title: "deepseek-v4-pro") { $0.llmModel = "deepseek-v4-pro" }]
        case .openai:   presets = [.init(title: "gpt-6-luna") { $0.llmModel = "gpt-6-luna" },
                                   .init(title: "gpt-6-sol") { $0.llmModel = "gpt-6-sol" }]
        case .bailian:  presets = [.init(title: "qwen3.7-plus") { $0.llmModel = "qwen3.7-plus" },
                                   .init(title: "qwen3.8-flash") { $0.llmModel = "qwen3.8-flash" }]
        case .other:    presets = []
        }
        return OnboardingStep(
            id: "llm.model",
            target: .llmModel,
            symbol: "cpu",
            title: tr("③ 模型名", "③ Model"),
            body: tr("填厂商文档里的**模型 ID**，区分大小写。写摘要不需要最贵的模型，各家的主力对话模型就够了。",
                     "Enter the **model ID** from the vendor’s docs (case-sensitive). Summaries don’t need the priciest model — a vendor’s main chat model is plenty."),
            tips: presets.isEmpty
                ? [tr("不确定就去厂商的「模型列表」或「定价」页面复制 ID。", "Not sure? Copy the ID from the vendor’s model list or pricing page.")]
                : [tr("根据你填的接口地址推荐（取自该厂商官方的模型列表，2026-09）：第一个便宜够用，第二个更强也更贵。",
                      "Suggested from your base URL (vendor’s official model list, 2026-09): the first is cheap and plenty, the second stronger and pricier.")],
            example: presets.first?.title ?? "deepseek-flash",
            presets: presets,
            status: { s, _, _ in filled(s.llmModel) }
        )
    }

    static func llmKey(_ s: AppSettings) -> OnboardingStep {
        var tips: [String]
        var links: [OnboardingStep.Link] = []
        var walkthrough: WebWalkthrough.ID?
        switch vendor(of: s.llmBaseURL) {
        case .deepseek:
            tips = [tr("打开 DeepSeek 开放平台 → 左侧「API keys」→「创建 API key」，名字随便起（比如 Podsum）。",
                       "Open the DeepSeek platform → “API keys” on the left → “Create API key”; any name works (e.g. Podsum)."),
                    tr("账户里要先**充值少量余额**，否则调用会报余额不足。",
                       "Top up a **small balance** first, or calls fail with insufficient balance.")]
            links = [.init(title: tr("打开 DeepSeek 开放平台", "Open DeepSeek Platform"), url: URL(string: "https://platform.deepseek.com/api_keys")!)]
            walkthrough = .deepseek
        case .openai:
            tips = [tr("OpenAI Platform → API keys →「Create new secret key」。",
                       "OpenAI Platform → API keys → “Create new secret key”."),
                    tr("账户的 Billing 里要有可用额度。", "Your account needs available credit under Billing.")]
            links = [.init(title: tr("打开 OpenAI API keys", "Open OpenAI API keys"), url: URL(string: "https://platform.openai.com/api-keys")!)]
        case .bailian:
            tips = bailianKeyTips
            links = [bailianKeyLink]
            walkthrough = .bailian
        case .other:
            tips = [tr("在你所用厂商的控制台里找「API Keys」或「密钥管理」，新建一个。",
                       "Look for “API Keys” in your vendor’s console and create one.")]
        }
        tips.append(tr("**key 一般只在创建时完整显示一次**，先复制再关窗口。粘贴时注意别带上前后空格。",
                       "**Keys are usually shown in full only once** — copy before closing. Watch for stray spaces when pasting."))
        tips.append(tr("它存进系统钥匙串，不写进任何明文文件。", "It goes into the system keychain, never a plain-text file."))
        return OnboardingStep(
            id: "llm.key",
            target: .llmKey,
            symbol: "key",
            title: tr("④ API Key", "④ API Key"),
            body: tr("去厂商控制台新建一个 API Key，复制后粘贴到高亮的框里。", "Create an API key in the vendor’s console and paste it into the highlighted field."),
            tips: tips,
            example: tr("sk- 开头的一长串", "a long string starting with sk-"),
            links: links,
            walkthrough: walkthrough,
            status: { s, _, _ in filled(s.llmAPIKey) }
        )
    }

    static var llmTest: OnboardingStep {
        OnboardingStep(
        id: "llm.test",
        target: .llmTest,
        symbol: "bolt.horizontal",
        title: tr("⑤ 测一下通不通", "⑤ Test the connection"),
        body: tr("点高亮的「测试连接」。Podsum 会用你填的地址、模型和 key 发一个极小的请求（花费可以忽略），当场告诉你通不通。",
                 "Click the highlighted “Test Connection”. Podsum sends one tiny request with your URL, model and key (negligible cost) and tells you right away."),
        tips: [
            tr("**401 / invalid api key**：key 复制错了，或者多了空格。", "**401 / invalid api key**: the key was mis-copied or has extra spaces."),
            tr("**404**：接口地址多写或少写了 `/v1`。", "**404**: the base URL has an extra or missing `/v1`."),
            tr("**model not found**：模型名拼错。", "**model not found**: the model name is misspelled."),
            tr("**402 / 余额不足**：账户需要充值。", "**402 / insufficient balance**: top up the account."),
            tr("**超时**：当前网络连不上这个地址。", "**Timeout**: this network can’t reach that address."),
        ],
        status: { _, guide, _ in
            switch guide.llmTest {
            case .untested: return .waiting(tr("点「测试连接」，通过后这里会打勾", "Click “Test Connection” — this ticks when it passes"))
            case .testing:  return .working(tr("正在测试…", "Testing…"))
            case .passed:   return .done(tr("连接通过", "Connection works"))
            case .failed(let message): return .problem(message)
            }
        }
        )
    }

    static var qwenModel: OnboardingStep {
        OnboardingStep(
        id: "llm.qwenModel",
        target: .llmModel,
        symbol: "cpu",
        title: tr("② 模型名", "② Model"),
        body: tr("填通义千问的模型 ID。按百炼官方模型列表（2026-09）：**qwen3.7-plus** 效果与价格均衡，**qwen3.8-flash** 最便宜，**qwen3.8-max** 最强也最贵。",
                 "Enter a Qwen model ID. Per Bailian’s official model list (2026-09): **qwen3.7-plus** is balanced, **qwen3.8-flash** cheapest, **qwen3.8-max** strongest and priciest."),
        tips: [
            tr("旧的 `qwen-max`、`qwen-plus` 已不在官方模型列表里，不建议再用。",
               "The older `qwen-max` / `qwen-plus` are no longer in the official list — avoid them."),
        ],
        example: "qwen3.7-plus",
        presets: [
            .init(title: "qwen3.7-plus") { $0.llmModel = "qwen3.7-plus" },
            .init(title: "qwen3.8-flash") { $0.llmModel = "qwen3.8-flash" },
            .init(title: "qwen3.8-max") { $0.llmModel = "qwen3.8-max" },
        ],
        status: { s, _, _ in filled(s.llmModel) }
        )
    }

    static var anthropicModel: OnboardingStep {
        OnboardingStep(
        id: "llm.anthropicModel",
        target: .llmModel,
        symbol: "cpu",
        title: tr("② 模型名", "② Model"),
        body: tr("填 Claude 官方文档「Models overview」里的模型 ID。**claude-sonnet-5** 效果与价格均衡，**claude-haiku-4-5-20251001** 最便宜。",
                 "Enter a model ID from Claude’s “Models overview”. **claude-sonnet-5** is balanced; **claude-haiku-4-5-20251001** is cheapest."),
        example: "claude-sonnet-5",
        presets: [
            .init(title: "claude-sonnet-5") { $0.llmModel = "claude-sonnet-5" },
            .init(title: "claude-haiku-4-5") { $0.llmModel = "claude-haiku-4-5-20251001" },
        ],
        status: { s, _, _ in filled(s.llmModel) }
        )
    }

    static var anthropicKey: OnboardingStep {
        OnboardingStep(
        id: "llm.anthropicKey",
        target: .llmKey,
        symbol: "key",
        title: tr("③ Anthropic API Key", "③ Anthropic API Key"),
        body: tr("Claude Platform（原 Anthropic Console）→ Settings → API keys →「Create Key」，复制后粘贴到高亮的框里。",
                 "Claude Platform (formerly Anthropic Console) → Settings → API keys → “Create Key”, then paste it into the highlighted field."),
        tips: [
            tr("账户需要先在 Billing 里充值。", "The account needs credit under Billing first."),
            tr("key 只在创建时显示一次。", "The key is shown only once."),
        ],
        example: tr("sk-ant- 开头", "starts with sk-ant-"),
        links: [.init(title: tr("打开 Claude Platform", "Open Claude Platform"), url: URL(string: "https://platform.claude.com/settings/keys")!)],
        status: { s, _, _ in filled(s.anthropicAPIKey) }
        )
    }

    /// DashScope key 在三段里各有一个框，但背后是同一个值：在前面填过，后面就自动有了。
    static func dashscopeKey(target: OnboardingTarget, id: String, title: String, alreadyShared: Bool) -> OnboardingStep {
        OnboardingStep(
            id: id,
            target: target,
            symbol: "key",
            title: title,
            body: alreadyShared
                ? tr("这一格和前面填过的 DashScope key 是**同一个值**，已经自动带过来了，直接下一步。",
                     "This is the **same** DashScope key you entered earlier — it’s already filled in, so just continue.")
                : tr("阿里云百炼的 API Key。一个 key 可以同时用于摘要、转写和音频摘要。",
                     "Your Alibaba Cloud Bailian API key — one key covers summaries, transcription and audio summaries."),
            tips: alreadyShared ? [] : bailianKeyTips,
            links: alreadyShared ? [] : [bailianKeyLink],
            walkthrough: alreadyShared ? nil : .bailian,
            status: { s, _, _ in filled(s.dashscopeAPIKey) }
        )
    }

    // MARK: - 转写（ASR）

    static func asrSteps(_ s: AppSettings) -> [OnboardingStep] {
        var steps = [OnboardingStep(
            id: "asr.provider",
            target: .asrProvider,
            symbol: "waveform",
            title: tr("转写用哪家", "Which service transcribes"),
            body: tr("转写服务把音频变成带时间戳的文字稿，摘要就是基于它写的。点高亮这一行的下拉框：",
                     "Transcription turns audio into a timestamped transcript that the summary is built on. Use the menu on the highlighted row:"),
            tips: [
                tr("**豆包 / 火山引擎**：中文识别效果最好，按时长计费；要开通语音服务、填 4 项，步骤最多，我会一格一格带你。",
                   "**Doubao / Volcengine**: best for Chinese, billed by duration; needs a speech app and 4 fields — I’ll walk you through each."),
                tr("**OpenAI Whisper**：一个 OpenAI key 即可，中英文都行。注意 OpenAI 已公告 `whisper-1` 将于 **2027-02-26 下线**。",
                   "**OpenAI Whisper**: just one OpenAI key; fine for Chinese and English. Note OpenAI has announced `whisper-1` **shuts down on 2027-02-26**."),
                tr("**Deepgram**：英文播客又快又准。", "**Deepgram**: fast and accurate for English podcasts."),
                tr("**通义千问**：暂不建议——Podsum 调用的 `qwen-audio-asr` 已不在百炼当前的模型列表里。",
                   "**Qwen**: not recommended for now — the `qwen-audio-asr` model Podsum calls is no longer in Bailian’s current model list."),
            ],
            status: { s, _, _ in .done(tr("已选：\(s.asrProvider.label)", "Selected: \(s.asrProvider.label)")) }
        )]

        switch s.asrProvider {
        case .doubao:
            steps += [volcAK(target: .asrVolcAK), volcSK(target: .asrVolcSK), doubaoAppID(target: .asrAppID, forTTS: false),
                      doubaoToken(target: .asrToken, forTTS: false)]
        case .openaiWhisper:
            steps.append(OnboardingStep(
                id: "asr.openai",
                target: .asrOpenAIKey,
                symbol: "key",
                title: "OpenAI API Key",
                body: tr("OpenAI Platform → API keys →「Create new secret key」，复制后粘贴到高亮的框里。",
                         "OpenAI Platform → API keys → “Create new secret key”, then paste it into the highlighted field."),
                tips: [
                    tr("如果摘要也用 OpenAI，可以填同一个 key。", "If your summaries also use OpenAI, the same key works."),
                    tr("账户的 Billing 里要有可用额度。", "Your account needs available credit under Billing."),
                ],
                example: tr("sk- 开头的一长串", "a long string starting with sk-"),
                links: [.init(title: tr("打开 OpenAI API keys", "Open OpenAI API keys"), url: URL(string: "https://platform.openai.com/api-keys")!)],
                status: { s, _, _ in filled(s.openAIAPIKey) }
            ))
        case .deepgram:
            steps.append(OnboardingStep(
                id: "asr.deepgram",
                target: .asrDeepgramKey,
                symbol: "key",
                title: "Deepgram API Key",
                body: tr("Deepgram Console → 左上角项目下拉框选中你的项目 → Settings → API Keys →「Create a New API Key」，复制后粘贴到高亮的框里。",
                         "Deepgram Console → pick your project in the top-left dropdown → Settings → API Keys → “Create a New API Key”, then paste it into the highlighted field."),
                tips: [tr("key 只在创建时显示一次。", "The key is shown only once.")],
                links: [.init(title: tr("打开 Deepgram Console", "Open Deepgram Console"), url: URL(string: "https://console.deepgram.com/")!)],
                status: { s, _, _ in filled(s.deepgramAPIKey) }
            ))
        case .qwen:
            steps.append(dashscopeKey(target: .asrDashscopeKey, id: "asr.dashscope",
                                      title: tr("DashScope API Key（转写）", "DashScope API Key (transcription)"),
                                      alreadyShared: s.llmProvider == .qwen))
        }
        return steps
    }

    static func volcAK(target: OnboardingTarget) -> OnboardingStep {
        OnboardingStep(
            id: "volc.ak.\(target)",
            target: target,
            symbol: "person.badge.key",
            title: tr("火山引擎 Access Key ID", "Volcengine Access Key ID"),
            body: tr("这是火山引擎**账号级**的访问密钥，和后面的 App ID / Token 是两套东西，两套都要。",
                     "This is your Volcengine **account-level** access key — separate from the App ID / Token later on. You need both."),
            tips: [
                tr("还没有火山引擎账号的话，先注册并完成**实名认证**，否则后面开不了服务。",
                   "No Volcengine account yet? Sign up and complete **identity verification** first, or services can’t be enabled."),
                tr("火山引擎控制台 → 右上角**头像下拉菜单** →「API访问密钥」→ 新建。",
                   "Volcengine console → the **avatar menu** at the top right → “API Access Keys” → create one."),
                tr("这个页面能建两种密钥：**Access Key** 和 **API Key**。要建的是 **Access Key**——它会给出一对：**Access Key ID**（填这里）和 **Secret Access Key**（下一步填）。",
                   "That page can create two kinds: **Access Key** and **API Key**. Create an **Access Key** — it gives a pair: the **Access Key ID** (here) and the **Secret Access Key** (next step)."),
                tr("**Secret 只在创建时显示一次**，建议当场把两段都复制下来。",
                   "**The secret is shown only once** — copy both parts right away."),
            ],
            links: [.init(title: tr("打开密钥管理", "Open Key Management"), url: URL(string: "https://console.volcengine.com/iam/keymanage/")!)],
            walkthrough: .volcKeys,
            status: { s, _, _ in filled(s.volcAccessKeyID) }
        )
    }

    static func volcSK(target: OnboardingTarget) -> OnboardingStep {
        OnboardingStep(
            id: "volc.sk.\(target)",
            target: target,
            symbol: "lock",
            title: tr("火山引擎 Secret Access Key", "Volcengine Secret Access Key"),
            body: tr("上一步那对密钥的另一半，粘贴到高亮的框里。", "The other half of the key pair from the previous step — paste it here."),
            tips: [
                tr("如果当时没存下来，控制台里再也看不到了：删掉那对密钥，重新「新建密钥」即可。",
                   "If you didn’t save it, the console won’t show it again: delete that pair and create a new one."),
            ],
            example: tr("比 Access Key ID 更长的一串", "a longer string than the Access Key ID"),
            links: [.init(title: tr("打开密钥管理", "Open Key Management"), url: URL(string: "https://console.volcengine.com/iam/keymanage/")!)],
            walkthrough: .volcKeys,
            status: { s, _, _ in filled(s.volcSecretKey) }
        )
    }

    static func doubaoAppID(target: OnboardingTarget, forTTS: Bool) -> OnboardingStep {
        var tips: [String]
        if forTTS {
            tips = [
                tr("如果转写用的那个豆包应用里已经勾了「语音合成」，这里**填同一个 App ID**。",
                   "If the Doubao app you use for transcription already has “Speech Synthesis” enabled, **use the same App ID** here."),
                tr("否则在豆包语音**旧版**控制台（左上角下拉框切换）里编辑应用加上「语音合成」，或新建一个勾选它的应用。",
                   "Otherwise, in the **old** Doubao Speech console (switch via the top-left dropdown), edit an app to add “Speech Synthesis”, or create one with it."),
            ]
        } else {
            tips = [
                tr("新账号打开豆包语音控制台，默认是**新版控制台**——它发的是一个 API Key，而 Podsum 用的是 **APP ID + Access Token** 这一对。先点**左上角的下拉框**，切换到**旧版**控制台。",
                   "New accounts land in the **new Doubao Speech console**, which issues a single API Key — but Podsum uses the **APP ID + Access Token** pair. Use the **dropdown in the top-left** to switch to the **old console** first."),
                tr("旧版控制台 →「创建应用」：填应用名称和简介，勾选接入能力 **录音文件识别大模型**，连同它的**极速版**：前者转写网上链接里的音频，极速版转写你上传的本地文件。",
                   "Old console → “Create App”: give it a name and description, and enable **Recording-file Recognition (large model)** plus its **Turbo** edition — the first handles audio from links, Turbo handles files you upload."),
                tr("以后想开音频摘要的话，同一个应用里顺手勾上**语音合成**，APP ID / Token 就能共用（勾过的能力之后不能取消）。",
                   "If you’ll want audio summaries later, also tick **Speech Synthesis** in the same app so the APP ID / Token can be shared (ticked capabilities can’t be removed later)."),
                tr("新建的应用默认是**试用版**，带一定免费额度，够先跑通；用完再在服务详情里开通正式版（按量后付费）。",
                   "New apps start as a **trial** with some free quota — enough to get going; later, switch to the paid edition in the service details (pay as you go)."),
                tr("应用的服务详情里就能看到 **APP ID**（一串数字）和 **Access Token**。一个账号最多建 10 个应用。",
                   "The app’s service details show its **APP ID** (digits) and **Access Token**. An account can have at most 10 apps."),
            ]
        }
        tips.append(tr("链接打不开或页面改版的话，在火山引擎控制台顶部搜索「豆包语音」。",
                       "If the link has moved, search “豆包语音” (Doubao Speech) at the top of the Volcengine console."))
        return OnboardingStep(
            id: "doubao.appid.\(target)",
            target: target,
            symbol: "app.badge",
            title: forTTS ? tr("豆包 TTS App ID", "Doubao TTS App ID") : tr("豆包 ASR App ID", "Doubao ASR App ID"),
            body: tr("App ID 和 Access Token 来自「豆包语音」控制台里的一个**应用**。", "The App ID and Access Token come from an **app** in the Doubao Speech console."),
            tips: tips,
            example: tr("一串数字，例如 1234567890", "digits only, e.g. 1234567890"),
            links: [.init(title: tr("打开豆包语音控制台", "Open Doubao Speech console"), url: URL(string: "https://console.volcengine.com/speech/app")!)],
            walkthrough: forTTS ? nil : .volcApp,
            status: { s, _, _ in filled(forTTS ? s.doubaoTTSAppID : s.doubaoASRAppID) }
        )
    }

    static func doubaoToken(target: OnboardingTarget, forTTS: Bool) -> OnboardingStep {
        OnboardingStep(
            id: "doubao.token.\(target)",
            target: target,
            symbol: "key.horizontal",
            title: forTTS ? tr("豆包 TTS Access Token", "Doubao TTS Access Token") : tr("豆包 ASR Access Token", "Doubao ASR Access Token"),
            body: tr("同一个应用详情页里的 **Access Token**，点「显示」后复制，粘贴到高亮的框里。",
                     "The **Access Token** on the same app details page — reveal it, copy it, and paste it into the highlighted field."),
            tips: [
                tr("注意它**不是**前面的 Secret Access Key——那个是账号级的，这个属于某一个应用。",
                   "It is **not** the Secret Access Key from earlier — that one belongs to your account, this one to a single app."),
                forTTS
                    ? tr("App ID 和转写共用时，Token 也填同一个。", "When the App ID is shared with transcription, use the same token too.")
                    : tr("填完这一格，转写就配好了。", "With this filled in, transcription is set up."),
            ],
            links: [.init(title: tr("打开豆包语音控制台", "Open Doubao Speech console"), url: URL(string: "https://console.volcengine.com/speech/app")!)],
            walkthrough: forTTS ? nil : .volcApp,
            status: { s, _, _ in filled(forTTS ? s.doubaoTTSToken : s.doubaoASRToken) }
        )
    }

    // MARK: - 音频摘要（TTS）

    static func ttsSteps(_ s: AppSettings) -> [OnboardingStep] {
        var steps = [OnboardingStep(
            id: "tts.toggle",
            target: .ttsToggle,
            symbol: "speaker.wave.2",
            title: tr("音频摘要（可选）", "Audio summaries (optional)"),
            body: tr("打开后，Podsum 可以把摘要合成一段语音，通勤时听。它是**独立的可选功能**，不影响转写与摘要。",
                     "When on, Podsum can turn a summary into speech for your commute. It’s a **separate, optional** feature that doesn’t affect transcripts or summaries."),
            tips: [
                tr("**建议先关着**，把主流程跑通了再回来开。", "**Leave it off for now** and come back once the main flow works."),
                tr("要开的话，拨动高亮的开关，下面会多出它的供应商和凭据。", "To turn it on, flip the highlighted switch — its provider and credentials appear below."),
            ],
            status: { s, _, _ in
                s.ttsEnabled
                    ? .done(tr("已开启，接下来填它的凭据", "On — its credentials come next"))
                    : .done(tr("已关闭，可以直接下一步", "Off — you can move on"))
            }
        )]
        guard s.ttsEnabled else { return steps }

        steps.append(OnboardingStep(
            id: "tts.provider",
            target: .ttsProvider,
            symbol: "speaker.wave.2",
            title: tr("音频摘要用哪家", "Which service speaks"),
            body: tr("点高亮这一行的下拉框：", "Use the menu on the highlighted row:"),
            tips: [
                tr("**豆包 / 火山引擎**：和豆包转写共用账号密钥，App ID 也能共用。", "**Doubao / Volcengine**: shares the account keys with Doubao transcription, and can share the App ID."),
                tr("**通义千问**：和百炼共用一个 DashScope key。", "**Qwen**: shares one DashScope key with Bailian."),
            ],
            status: { s, _, _ in .done(tr("已选：\(s.ttsProvider.label)", "Selected: \(s.ttsProvider.label)")) }
        ))

        switch s.ttsProvider {
        case .doubao:
            // 转写已经用豆包时，账号密钥在上面填过，界面上这两格会自动带值，不必再走一遍
            if s.asrProvider != .doubao {
                steps += [volcAK(target: .ttsVolcAK), volcSK(target: .ttsVolcSK)]
            }
            steps += [doubaoAppID(target: .ttsAppID, forTTS: true), doubaoToken(target: .ttsToken, forTTS: true)]
        case .qwen:
            steps.append(dashscopeKey(target: .ttsDashscopeKey, id: "tts.dashscope",
                                      title: tr("DashScope API Key（音频摘要）", "DashScope API Key (audio)"),
                                      alreadyShared: s.llmProvider == .qwen || s.asrProvider == .qwen))
        }
        return steps
    }

    // MARK: - 收尾

    static var apply: OnboardingStep {
        OnboardingStep(
        id: "apply",
        target: .apply,
        symbol: "play.circle",
        title: tr("启动后端", "Start the backend"),
        body: tr("都填好了。点高亮的「应用并重启后端」，Podsum 会用这些配置在后台启动服务，通常几秒钟。",
                 "All set. Click the highlighted “Apply & Restart Backend” and Podsum starts its background service with this setup — usually a few seconds."),
        tips: [
            tr("第一次读取钥匙串时，macOS 可能会问是否允许 Podsum 访问——点「始终允许」，以后就不再问了。",
               "The first time it reads the keychain, macOS may ask whether Podsum can access it — choose “Always Allow” and it won’t ask again."),
        ],
        status: { s, _, backend in
            let missing = s.missingFields
            if !missing.isEmpty {
                return .problem(tr("还缺：", "Still missing: ") + missing.joined(separator: tr("、", ", "))
                                + tr("——点「上一步」回去补上", " — go back to fill them in"))
            }
            switch backend.phase {
            case .ready:
                return .done(tr("后端已就绪", "The backend is ready"))
            case .starting(let step):
                return .working(step)
            case .failed(let message), .noRuntime(let message):
                let first = message.split(separator: "\n").first.map(String.init) ?? message
                return .problem(first + tr("（详情见「服务」页的日志）", " (see the log on the Service tab)"))
            case .idle, .needsConfiguration:
                return .waiting(tr("点「应用并重启后端」", "Click “Apply & Restart Backend”"))
            }
        }
        )
    }

    static var done: OnboardingStep {
        OnboardingStep(
        id: "done",
        target: nil,
        symbol: "checkmark.seal",
        title: tr("全部就绪", "You’re all set"),
        body: tr("接下来可以这样用：", "Here’s how to get going:"),
        tips: [
            tr("回到主窗口按 **⌘N** 添加剧集：粘贴播客或视频链接（整段分享文案也行），或者把音频文件拖进去。",
               "Back in the main window, press **⌘N** to add episodes: paste a podcast or video link (a whole share message works too), or drop in audio files."),
            tr("在浏览器里看视频时按 **⌥⌘S**，直接把当前标签页送去总结（快捷键可在「设置 › 快捷提交」里改）。",
               "While watching a video in your browser, press **⌥⌘S** to send the current tab (change it in Settings › Quick Add)."),
            tr("哪天视频下载开始大量失败：「设置 › 服务 › 解析组件」→「检查并更新」。",
               "If video downloads start failing: Settings › Service › Extraction Component → “Check & Update”."),
            tr("想再看一遍这个引导：「设置 › 通用 › 重新开始新手引导」。",
               "To see this guide again: Settings › General › Restart Setup Guide."),
        ]
        )
    }

    // MARK: - 小工具

    /// 百炼的 key 按地域隔离，不能跨地域混用；Podsum 连的是北京地域的接口（dashscope.aliyuncs.com）。
    private static var bailianKeyTips: [String] {
        [
        tr("打开阿里云百炼的 API Key 页 → 右上角地域选 **华北2（北京）** →「创建 API Key」→ 业务空间选默认 →「确定」→ 复制。",
           "Open Bailian’s API Key page → set the region at the top right to **China (Beijing)** → “Create API Key” → default workspace → “OK” → copy."),
        tr("**一定要是北京地域的 key**：百炼各地域的 key 不能混用，Podsum 连的是北京的接口。",
           "**It must be a Beijing-region key**: Bailian keys don’t work across regions, and Podsum calls the Beijing endpoint."),
        tr("同一个 key 以后还能用于音频摘要。", "The same key also works for audio summaries."),
        ]
    }

    private static var bailianKeyLink: OnboardingStep.Link {
        .init(title: tr("打开百炼 API Key 页", "Open Bailian API Keys"),
              url: URL(string: "https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key")!)
    }

    private static func filled(_ value: String) -> OnboardingStep.Status {
        value.isBlank
            ? .waiting(tr("等你填写…", "Waiting for you…"))
            : .done(tr("已填好", "Filled in"))
    }
}
