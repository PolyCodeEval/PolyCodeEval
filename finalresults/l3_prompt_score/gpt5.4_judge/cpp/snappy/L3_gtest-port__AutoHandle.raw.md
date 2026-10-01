{
  "score": 4.6,
  "reason": "The description matches the class declaration very well: it correctly identifies `AutoHandle` as a non-copyable RAII wrapper for a Win32-style handle represented as `void*`, notes default and handle-taking construction, `Get()`, `Reset()` overloads, destruction-based cleanup, an internal closeability check, and deleted copy operations. It is also aligned with the surrounding intent of avoiding platform headers. The only limitation is that the provided implementation is just a declaration in the header, so details such as exactly which handle values are considered closeable or how cleanup is performed are not actually visible here; the description reasonably infers them from the API/comments, but those specifics are not fully grounded in the shown implementation.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [
    "The description states concrete runtime behavior for destruction and reset (closing valid handles and skipping invalid/null/non-closeable ones), but the shown code only declares these methods and documents `IsCloseable()`; the exact cleanup logic is not present in the provided implementation body."
  ],
  "complete_enough": true
}
