{
  "score": 4.8,
  "reason": "The description matches the implementation very closely at both file and function level. It correctly captures the recovery flow, the special `http.ErrAbortHandler` re-panic behavior, the conditional 500 write suppression for `Connection: Upgrade`, and the pretty-stack formatting pipeline including reverse scanning, decoration, and fallback behavior. It is also unusually complete about line classification and formatting details in the helper methods, which makes it strong for full-file reconstruction. The only meaningful gaps are a few implementation-level specifics such as the exact use of `recovererErrorWriter` only on the success path, the fact that fallback writes specifically to `os.Stderr`, and some color/newline formatting details that are implied but not fully anchored to the surrounding helper infrastructure.",
  "missing_functionality": [
    "The description does not explicitly mention that `Recoverer` builds and returns an `http.HandlerFunc` around a local closure, though this is minor.",
    "It does not mention the exact initial formatting bytes in `parse` beyond the conceptual header, such as the leading newline and the exact spacing/newline sequence after the panic value.",
    "The description omits that `PrintPrettyStack` writes to `recovererErrorWriter` only on successful pretty formatting, while the fallback path bypasses that writer and writes raw stack bytes directly to `os.Stderr`."
  ],
  "incorrect_or_misleading_points": [
    "The statement that the source-line branch includes a tab-prefix check is technically misleading because `strings.TrimSpace` removes leading tabs first, making the `HasPrefix(line, \"\\t\")` checks effectively unreachable in practice.",
    "Saying the implementation 'always' uses the tab-prefix check as part of source-line classification slightly overstates its practical role, since the `.go:` containment test is what actually drives classification after trimming."
  ],
  "complete_enough": true
}
