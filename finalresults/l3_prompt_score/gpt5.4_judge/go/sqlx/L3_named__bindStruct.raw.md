{
  "score": 5.0,
  "reason": "The description matches the implementation closely. The function compiles a named query into the requested bind style, then binds arguments from the provided struct-like argument using the mapper conventions, and returns the rewritten query plus ordered args. It also correctly notes that errors from either query compilation or argument binding produce empty return values alongside the error. Although the implementation delegates much of the actual work to helpers, the description captures the full behavior of this wrapper function accurately enough to reimplement it.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
