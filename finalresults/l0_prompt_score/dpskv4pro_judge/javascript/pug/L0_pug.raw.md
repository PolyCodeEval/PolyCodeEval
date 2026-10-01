{
  "project": "pug",
  "scores": {
    "completeness": {
      "score": 4.3,
      "reason": "Prompt 覆盖 pug 模板编译管线：render/compile/compileClient/compileClientWithDependenciesTracked、标签语法（p/p=/p!=/if/each/include）、options（pretty/filename/name）。覆盖核心模板引擎能力。"
    },
    "unambiguity": {
      "score": 4.2,
      "reason": "编译方法签名和返回值类型明确（render→string、compile→function、compileClient→string、compileClientWithDependenciesTracked→{body,dependencies}）。模板语法与 HTML 映射清楚。"
    },
    "testability": {
      "score": 4.5,
      "reason": "测试需求覆盖基本标签渲染、变量插值、安全/不转义输出、条件、迭代、include、空模板。黑盒测试覆盖充分。"
    },
    "consistency": {
      "score": 4.4,
      "reason": "编译管线 API（render/compile/compileClient）和标签语法与真实 pug 一致。模板语法映射准确。"
    }
  }
}
