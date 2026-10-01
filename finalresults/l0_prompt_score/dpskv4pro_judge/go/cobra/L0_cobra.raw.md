{
  "project": "cobra",
  "scores": {
    "completeness": {
      "score": 4.6,
      "reason": "Prompt 覆盖了命令行创建（Command 结构体）、标志（Flags）、参数校验（Args）、子命令、钩子（PreRun/PostRun）、Execute 入口。覆盖了 cobra 的核心使用模式。"
    },
    "unambiguity": {
      "score": 4.4,
      "reason": "Command 结构体字段（Use/Short/Long/Run/RunE）、Args 校验函数、PersistentFlags vs Flags 区别、Execute 调用方式均描述清楚。但部分高级特性如 help 模板自定义未展开。"
    },
    "testability": {
      "score": 4.8,
      "reason": "测试需求非常具体：子命令执行、Args 校验器行为、PreRun/PostRun 钩子调用顺序、标志默认值等，与黑盒测试高度对齐。"
    },
    "consistency": {
      "score": 4.2,
      "reason": "API 描述与真实 cobra 库一致。但实际 cobra 功能远比 prompt 描述丰富（如 completion、help 自定义、TraverseRunHooks），prompt 聚焦于测试可覆盖子集。"
    }
  }
}
