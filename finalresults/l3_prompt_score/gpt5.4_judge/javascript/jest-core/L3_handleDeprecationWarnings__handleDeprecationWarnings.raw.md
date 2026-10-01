{
  "score": 4.8,
  "reason": "The description matches the implementation very closely. It correctly covers the raw-mode check, the warning prompt content and destination stream, enabling interactive input, resolving on Enter, rejecting on Esc/Ctrl-C/Ctrl-D, and resolving immediately when raw mode is unavailable. The only notable omission is that the implementation explicitly sets stdin encoding to UTF-8 before listening for data, which is a real detail but not central to the function's main behavior.",
  "missing_functionality": [
    "The implementation calls stdin.setEncoding('utf8') before handling key input."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
