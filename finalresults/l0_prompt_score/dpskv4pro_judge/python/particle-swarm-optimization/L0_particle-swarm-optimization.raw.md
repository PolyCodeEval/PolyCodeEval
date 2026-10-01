{
  "project": "particle-swarm-optimization",
  "scores": {
    "completeness": {
      "score": 4.1,
      "reason": "Prompt 覆盖 PSO 算法核心：粒子类、群体、速度/位置更新、适应度评估、惯性权重。覆盖优化算法核心流程。"
    },
    "unambiguity": {
      "score": 4.2,
      "reason": "PSO 参数（粒子数/迭代次数/惯性权重/认知和社会系数）、适应度函数接口、收敛条件描述清楚。"
    },
    "testability": {
      "score": 4.4,
      "reason": "测试需求覆盖优化结果精度、参数校验、收敛行为。黑盒测试可验证基本优化能力。"
    },
    "consistency": {
      "score": 4.0,
      "reason": "PSO 算法描述与经典实现一致。真实代码可能有额外的初始化策略或边界处理未在 prompt 中展开。"
    }
  }
}
