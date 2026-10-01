{
  "project": "stocktrends",
  "scores": {
    "completeness": {
      "score": 4.3,
      "reason": "Prompt 覆盖 stocktrends 的股票趋势分析：数据获取（yahoo/pandas-datareader）、K 线渲染、技术指标计算（MA/布林带等）。覆盖核心股票分析流程。"
    },
    "unambiguity": {
      "score": 4.1,
      "reason": "K 线图表格式、技术指标参数、数据显示顺序描述清楚。但数据源依赖（yahoo finance）的 API 变化不确定性未被强调。"
    },
    "testability": {
      "score": 4.8,
      "reason": "测试需求精确覆盖图表输出（像素级匹配）、数据列顺序、日期格式。黑盒测试要求高但 prompt 描述充分。"
    },
    "consistency": {
      "score": 3.9,
      "reason": "核心分析逻辑与真实 stocktrends 库一致。数据获取依赖外部 API 使 prompt 的静态描述与动态数据源存在天然偏差。"
    }
  }
}
