{
  "project": "gobreaker",
  "scores": {
    "completeness": {
      "score": 4.5,
      "reason": "Prompt 覆盖 CircuitBreaker 状态机（Closed/Open/HalfOpen）、Settings 配置、Execute 方法、v2 泛型版本。覆盖核心熔断器能力。"
    },
    "unambiguity": {
      "score": 4.5,
      "reason": "Settings 字段（MaxRequests/Interval/Timeout/ReadyToTrip/OnStateChange）语义清晰。状态转换规则（失败计数触发 trip、Timeout 后进入 HalfOpen、MaxRequests 成功后回 Closed）精确描述。"
    },
    "testability": {
      "score": 4.7,
      "reason": "测试需求精确描述了状态转换行为：trip 触发条件、HalfOpen 自动恢复、v2 泛型 Execute、isSuccessful 回调等。黑盒测试可直接映射。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "状态机语义、Settings 字段、Execute 签名与真实 gobreaker 库一致。轻微：实际 v2 版本功能更丰富但 prompt 聚焦测试子集。"
    }
  }
}
