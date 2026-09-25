import SwiftUI

/// 剧集封面。拿不到封面（本地上传、直链音频、没补抓到）时画一块由 id 决定颜色的渐变，
/// 这样卡片栅格仍然整齐，同一集每次看到的颜色也不变。
///
/// 自带一层内存缓存：LazyVGrid 滚出屏幕的卡片会被回收，回来时若重新解码，
/// 封面会先闪一下占位再出现。
struct CoverArt: View {
    let url: URL?
    let seed: String

    @State private var image: NSImage?

    init(url: URL?, seed: String) {
        self.url = url
        self.seed = seed
        _image = State(initialValue: url.flatMap { CoverCache.images.object(forKey: $0 as NSURL) })
    }

    var body: some View {
        ZStack {
            placeholder
            if let image {
                Image(nsImage: image)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFill()
                    .transition(.opacity)
            }
        }
        .task(id: url) { await load() }
    }

    private var placeholder: some View {
        let hue = Self.hue(for: seed)
        return LinearGradient(
            colors: [
                Color(hue: hue, saturation: 0.42, brightness: 0.78),
                Color(hue: (hue + 0.09).truncatingRemainder(dividingBy: 1), saturation: 0.55, brightness: 0.46),
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(alignment: .top) {
            Image(systemName: "waveform")
                .font(.system(size: 54, weight: .light))
                .foregroundStyle(.white.opacity(0.28))
                .padding(.top, 28)
        }
    }

    private func load() async {
        guard let url else {
            image = nil
            return
        }
        if let cached = CoverCache.images.object(forKey: url as NSURL) {
            image = cached
            return
        }
        let data: Data?
        if url.isFileURL {
            data = await Task.detached(priority: .utility) { try? Data(contentsOf: url) }.value
        } else {
            data = try? await URLSession.shared.data(from: url).0
        }
        guard let data, let decoded = NSImage(data: data) else { return }
        CoverCache.images.setObject(decoded, forKey: url as NSURL)
        withAnimation(.easeOut(duration: 0.2)) { image = decoded }
    }

    /// 稳定的哈希：String.hashValue 每次启动都换种子，颜色会跟着变
    private static func hue(for seed: String) -> Double {
        var h: UInt64 = 1469598103934665603
        for byte in seed.utf8 { h = (h ^ UInt64(byte)) &* 1099511628211 }
        return Double(h % 360) / 360
    }
}

enum CoverCache {
    /// NSCache 自身线程安全
    nonisolated(unsafe) static let images: NSCache<NSURL, NSImage> = {
        let cache = NSCache<NSURL, NSImage>()
        cache.countLimit = 300
        return cache
    }()
}

extension View {
    /// 叠在封面上的玻璃。深色调色保证白字在任何封面上都看得清：
    /// 纯透明的玻璃遇上浅色、花哨的封面，字就糊进去了。
    @ViewBuilder
    func coverGlass<S: Shape>(in shape: S) -> some View {
        if #available(macOS 26.0, *) {
            self.glassEffect(.regular.tint(.black.opacity(0.38)), in: shape)
        } else {
            self
                .background(Color.black.opacity(0.28), in: shape)
                .background(.ultraThinMaterial, in: shape)
        }
    }
}
