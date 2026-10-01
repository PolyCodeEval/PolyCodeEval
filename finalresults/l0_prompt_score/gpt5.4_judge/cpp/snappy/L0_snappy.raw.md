{
  "project": "snappy",
  "scores": {
    "completeness": {
      "score": 4.3,
      "reason": "Prompt 覆盖了仓库核心能力：C++/C 压缩解压接口、Source/Sink 流式接口、CompressionOptions、长度与校验工具函数、内部组件与 CMake/gtest 构建测试方向，也点到了 iovec 与 partial uncompress。缺口在于真实公开 API 中还包含 RawCompress/RawUncompress、RawUncompressToIOVec、IsValidCompressed(Source*)、GetUncompressedLength(Source*, uint32_t*)、Compress(Source*, Sink*, CompressionOptions) 等接口，且仓库内还带有较完整的单测支持与平台 stub 细节，prompt 未完整展开。"
    },
    "unambiguity": {
      "score": 4.5,
      "reason": "核心接口签名、命名空间、头文件路径、状态码、关键行为和若干精确断言都写得很清楚，足以约束主要实现并支持复现黑盒能力。少量表述仍有边界模糊，例如把 GetUncompressedLength 描述为从 header O(1) 解析但未说明 Source 版本会消费输入、流式解压与 iovec 接口的错误语义和 ownership 约束也未细讲，不过这些不妨碍主体实现。"
    },
    "testability": {
      "score": 4.8,
      "reason": "Prompt 明确列出了黑盒测试所需 include path、必须实现的 C/C++ API、精确返回值、公式、非法输入样例、空输入、大数据和高压缩数据等行为，和真实 blackbox_tests 的断言高度一致，因此可直接驱动实现并验证核心能力。轻微不足是没有细化构建入口与测试可执行组织方式，但对黑盒通过影响很小。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "整体描述与真实仓库实现一致：Snappy 的定位、64KB block、C/C++ API、Source/Sink 抽象、CompressionOptions 仅 1/2 两级、C API 默认级别、MaxCompressedLength 公式及非法输入行为都和代码与黑盒测试相符。主要偏差是将 streaming decompression、iovec decompression、UncompressAsMuchAsPossible 等写成更对称/产品化的功能清单，而真实测试只依赖部分接口；另外“tested with Google Test via CTest”更像构建期目标，仓库实际 CMake 位于 src 子目录并带 bundled googletest，这些都属轻微不完全对齐。"
    }
  }
}
