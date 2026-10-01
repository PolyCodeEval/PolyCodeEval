{
  "project": "mitt",
  "scores": {
    "completeness": {
      "score": 4.3,
      "reason": "Prompt 覆盖 mitt 全部核心功能：mitt() 创建、on/off/emit、通配符 *、EventHandlerMap、TypeScript 泛型支持。非常简洁但覆盖完整。"
    },
    "unambiguity": {
      "score": 4.6,
      "reason": "on/off/emit 签名和语义极其明确：通配符回调参数 (type, event)、emit 时注册不触发、off 未注册为 no-op、EventHandlerMap 通过 Map 实现。"
    },
    "testability": {
      "score": 4.8,
      "reason": "测试需求覆盖 on/off/emit 基本流程、通配符、多次注册、移除未注册处理程序、emit('*') 行为、emit 期间注册不触发。黑盒测试高度对应。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "mitt API 非常简洁，prompt 描述与真实源码几乎无偏差。通配符行为、EventHandlerMap、TypeScript 泛型匹配。"
    }
  }
}
