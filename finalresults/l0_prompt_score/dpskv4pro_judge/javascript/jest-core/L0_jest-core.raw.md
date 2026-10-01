{
  "project": "jest-core",
  "scores": {
    "completeness": {
      "score": 4.1,
      "reason": "Prompt 覆盖 @jest/core 的测试发现（SearchSource）、调度（TestScheduler）、报告协调、FailedTestsCache、交互模式。覆盖核心编排能力。但 jest-core 实际功能非常庞大，prompt 仅覆盖测试所需子集。"
    },
    "unambiguity": {
      "score": 4.3,
      "reason": "FailedTestsCache 的 setTestResults/filterTests 方法签名和语义（存储失败测试、过滤仅返回之前失败的）描述精确。但其他模块（SearchSource/TestScheduler）仅概述。"
    },
    "testability": {
      "score": 4.6,
      "reason": "测试需求精确覆盖 FailedTestsCache 的行为（空缓存/设置结果/过滤/空输入），与黑盒测试完全对应。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "FailedTestsCache 的 setTestResults→filterTests 流程和 Jest 的 testResult 结构匹配真实 jest-core 包。"
    }
  }
}
