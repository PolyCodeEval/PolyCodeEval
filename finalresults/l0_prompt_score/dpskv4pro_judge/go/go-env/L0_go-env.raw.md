{
  "project": "go-env",
  "scores": {
    "completeness": {
      "score": 4.4,
      "reason": "Prompt 覆盖 Parse/ParseWithOptions、struct tag 语法（env/envDefault/required/envPrefix/envSeparator）、Options 配置、支持字段类型列表。覆盖核心解析能力。但实际库还支持 file/expand/notEmpty/unset 标签及 FuncMap 等高级特性，prompt 仅覆盖测试所需。"
    },
    "unambiguity": {
      "score": 4.3,
      "reason": "Struct tag 语义（required/envDefault）和 Options 结构体清晰。但 required 字段无默认值时的错误类型未说明，嵌套结构体的 envPrefix 前缀规则需推断。"
    },
    "testability": {
      "score": 4.8,
      "reason": "测试需求覆盖了基本解析、默认值、required 错误、嵌套前缀、分隔符、duration 解析。黑盒测试覆盖与 prompt 描述匹配度高。"
    },
    "consistency": {
      "score": 4.6,
      "reason": "核心 API（Parse/Options/struct tags）与真实 go-env 库一致。支持字段类型列表匹配。轻微：实际库 v11 有许多高级特性 prompt 未要求覆盖。"
    }
  }
}
