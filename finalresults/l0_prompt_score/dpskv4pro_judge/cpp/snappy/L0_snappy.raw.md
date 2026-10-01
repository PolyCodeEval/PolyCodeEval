{
  "project": "snappy",
  "scores": {
    "completeness": {
      "score": 4.3,
      "reason": "Prompt 覆盖 C++/C API、Source/Sink 流式接口、CompressionOptions、长度/校验工具函数、内部组件。详见 MaxCompressedLength 公式和边界行为。遗漏：部分实际公开接口（RawCompress/RawUncompress、RawUncompressToIOVec、Source 版本的 GetUncompressedLength 和 IsValidCompressed）。"
    },
    "unambiguity": {
      "score": 4.5,
      "reason": "核心接口签名、命名空间、头文件路径、状态码、关键行为和精确断言（如 MaxCompressedLength(0)==32）写得清楚。高级功能（流式解压、iovec）边界语义未细化但不影响核心实现。"
    },
    "testability": {
      "score": 4.8,
      "reason": "明确列出黑盒测试所需 include path、必须实现的 C/C++ API、精确返回值、公式、非法输入样例、空输入、大数据和高压缩数据等行为，与黑盒测试高度一致。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "整体描述与真实仓库一致：Snappy 定位、64KB block、C/C++ API、Source/Sink 抽象、CompressionOptions 1/2 两级、C API 默认级别、MaxCompressedLength 公式及非法输入行为均与代码和黑盒测试相符。"
    }
  }
}
