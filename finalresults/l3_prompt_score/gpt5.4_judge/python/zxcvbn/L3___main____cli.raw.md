{
  "score": 4.8,
  "reason": "The description closely matches the implementation: it covers argument parsing, the nonblocking stdin check, reading stdin versus prompting with getpass, stripping one trailing newline, calling `zxcvbn` with `args.user_input`, and emitting pretty-printed JSON plus a trailing newline. The only notable omission is that JSON serialization uses a custom `JSONEncoder`, which affects handling of non-default-serializable values, but that is a secondary detail rather than core behavior.",
  "missing_functionality": [
    "Uses a custom `JSONEncoder` when dumping JSON, which falls back to `str(o)` for otherwise non-serializable objects."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
