{
  "score": 4.9,
  "reason": "The description matches the implementation very closely. It correctly states that the function closes the previously owned handle when appropriate before storing a different handle, and that resetting to the same handle is rejected if the current handle is closeable via a failing check. This is sufficient to implement the function accurately, with only minor omission of the exact validity rule used by `IsCloseable()`.",
  "missing_functionality": [
    "It does not explicitly mention that the old handle is closed only when `IsCloseable()` is true, where closeable specifically excludes `nullptr` and `INVALID_HANDLE_VALUE`."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
