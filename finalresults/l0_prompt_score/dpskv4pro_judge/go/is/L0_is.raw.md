{
  "project": "is",
  "scores": {
    "completeness": {
      "score": 4.4,
      "reason": "Prompt 覆盖 New/NewRelaxed、True/Equal/NoErr/Fail 断言、失败输出格式、strict/relaxed 模式。覆盖核心测试辅助能力。"
    },
    "unambiguity": {
      "score": 4.3,
      "reason": "断言方法签名和语义（reflect.DeepEqual 比较、不同类型不相等、NoErr 处理 wrapped error）清楚。但 Helper() 的作用和 TB 接口实现细节未详述。"
    },
    "testability": {
      "score": 4.6,
      "reason": "测试需求覆盖了所有断言方法、strict/relaxed 行为差异、nil 比较、类型不匹配、wrapped error。与黑盒测试一致。"
    },
    "consistency": {
      "score": 4.0,
      "reason": "核心 API 与真实 is 库一致。但实际 is 库还包含 New 可以接受带 log/slog 参数的变体、Lax 方法等，prompt 未覆盖这些次要特性。"
    }
  }
}
