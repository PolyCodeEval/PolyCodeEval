{
  "score": 4.9,
  "reason": "The description matches the implementation very closely. It correctly describes the precedence order for resolving the help function (explicitly set on the command, inherited from parent, otherwise default), and it accurately summarizes the default handler’s behavior: merging persistent flags, resolving the help template function, writing help to stdout, and printing any rendering error to stderr. It also correctly notes that the returned function takes a command and args, while the default implementation does not use the args slice. The only very minor gap is that the implementation specifically calls `c.getHelpTemplateFunc()` and renders via `fn(c.OutOrStdout(), c)`, so output goes to the command’s configured stdout writer rather than literally always the process standard output.",
  "missing_functionality": [
    "The description does not explicitly mention that the default handler writes to `c.OutOrStdout()` rather than directly to raw standard output."
  ],
  "incorrect_or_misleading_points": [
    "Saying the output is written to standard output is slightly imprecise; the implementation writes to the command’s configured stdout writer via `OutOrStdout()`."
  ],
  "complete_enough": true
}
