{
  "project": "ddd-example-ecommerce",
  "scores": {
    "completeness": {
      "score": 4.0,
      "reason": "Prompt 覆盖了 DDD 分层架构（domain/application/infrastructure/interfaces）、商品/订单领域模型、应用服务和仓库接口。覆盖核心电商能力。但实际的 DDD example 包含更多聚合和值对象细节未展开（如 Address/Money 等值对象）。"
    },
    "unambiguity": {
      "score": 4.0,
      "reason": "DDD 层次结构（interfaces→application→domain→infrastructure）和核心实体关系描述清楚。但具体的 API 合约方法签名（如 Product/Order 类）不如其他 Java 项目详细，Command/Query 模型未细化。"
    },
    "testability": {
      "score": 4.2,
      "reason": "黑盒测试需求若有商品/订单 CRUD 行为说明则足以驱动测试实现，但 prompt 的 API 合约部分相比其他项目略显概括。"
    },
    "consistency": {
      "score": 4.1,
      "reason": "DDD 分层架构描述与真实项目一致。但实际 ddd-example-ecommerce 项目的具体类名和方法可能与 prompt 概括描述略有差异，属于 DDD 模板项目的常见特征。"
    }
  }
}
