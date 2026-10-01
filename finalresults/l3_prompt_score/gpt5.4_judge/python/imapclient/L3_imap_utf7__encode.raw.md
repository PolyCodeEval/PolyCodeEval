{
  "score": 5.0,
  "reason": "The description matches the implementation very closely. It correctly states that non-string inputs are returned unchanged, printable ASCII characters from U+0020 to U+007E are passed through except '&' becoming '&-', non-ASCII/out-of-range characters are buffered into consecutive runs and emitted as IMAP modified UTF-7 base64 segments wrapped with '&' and '-', and any trailing buffered run is flushed at the end. It also correctly notes that string input produces a bytes result. This is complete enough to implement the function's behavior.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
