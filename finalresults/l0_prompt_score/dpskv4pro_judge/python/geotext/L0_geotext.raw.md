{
  "project": "geotext",
  "scores": {
    "completeness": {
      "score": 4.5,
      "reason": "Prompt 覆盖 geotext 的地理实体识别：GeoText 类构造、城市/国家提取（cities/countries/nationalities）、多种语言支持、国家别名。API 合约详列了方法签名和返回格式。"
    },
    "unambiguity": {
      "score": 4.1,
      "reason": "cities/countries 返回格式（元组或列表）、countryflags 查询、国家简称/全称映射描述清楚。但多语言支持的边界情况（如混合语言文本）未详述。"
    },
    "testability": {
      "score": 4.8,
      "reason": "测试需求覆盖具体地名识别（大/小写混合、特殊拼写变体）、返回值类型、多语言支持。黑盒测试高度对应。"
    },
    "consistency": {
      "score": 4.2,
      "reason": "GeoText 类 API 和返回格式与真实 geotext 库一致。地理数据来源（geonames）的依赖方式和库版本细节略简。"
    }
  }
}
