{
  "score": 5.0,
  "reason": "The description matches the implementation very closely and captures all important behavior: initialization of output length and decompressor state, incremental decompression from the source buffer, forced non-wrapping output with `HAS_MORE_INPUT` cleared, geometric heap growth with a 128-byte minimum, and cleanup/error handling on decompression failure, unexpected need for more input, or allocation failure. It also correctly notes that a successful zero-length decompression may return `NULL` because no buffer is ever allocated.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
