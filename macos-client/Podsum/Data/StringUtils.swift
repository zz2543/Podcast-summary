import Foundation

// 全客户端共用的两个小工具。放在这里而不是某个功能文件里，
// 是因为 Repository、设置面板、提交表单都要用——
// 谁先用就搁谁那儿会让后来者以为它属于那个功能。

public extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
    /// 空白也算空。设置面板里敲一个空格不该算"填了"。
    var isBlank: Bool { trimmed.isEmpty }
}
