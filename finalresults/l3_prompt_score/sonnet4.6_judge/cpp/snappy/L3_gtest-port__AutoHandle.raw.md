{
  "score": 4.7,
  "reason": "The description accurately captures all key aspects of the implementation: the RAII ownership model, the `void*` handle typedef to avoid including `<windows.h>`, both constructor forms, `Get()`, both `Reset()` overloads, destruction behavior tied to `IsCloseable()`, and the deleted copy constructor and copy assignment operator. The description also correctly notes that the validity check (`IsCloseable`) is used consistently for both destruction and reset. No incorrect claims are made. The only minor gap is that the description doesn't explicitly mention this class is Windows-only (guarded by `GTEST_OS_WINDOWS`) or its intended use context (death tests and threading support), but these are contextual details rather than behavioral ones.",
  "missing_functionality": [
    "The description does not mention that AutoHandle is Windows-only (conditionally compiled under GTEST_OS_WINDOWS).",
    "The description omits the stated use context: leak-safe Windows kernel handle ownership used in death tests and threading support."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
