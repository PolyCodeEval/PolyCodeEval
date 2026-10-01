{
  "score": 4.6,
  "reason": "The description accurately captures all five logical branches of the implementation in the correct order: the post-STARTTLS NONAUTH invalidation, the cached capabilities fast-path, the untagged response normalization and caching, the AUTH/SELECTED explicit fetch, and the pre-auth fallback to imaplib's own capabilities. The detail about clearing the cache before fetching post-STARTTLS is correctly noted. The description is complete enough to implement the function faithfully. Minor omissions: it doesn't mention that the untagged response is popped (mutating `untagged_responses`), and it doesn't specify that the pre-auth fallback result is NOT cached (unlike the other paths), but these are secondary implementation details that don't affect correctness of a reimplementation.",
  "missing_functionality": [
    "The pre-auth fallback result is not cached, unlike the AUTH/SELECTED path — the description doesn't make this distinction explicit.",
    "The untagged CAPABILITY response is popped from `untagged_responses` (mutating the underlying dict), which the description omits."
  ],
  "incorrect_or_misleading_points": [
    "The description says 'treat any cached capabilities as invalid' post-STARTTLS, which is accurate, but it also implies the cache is cleared before fetching — this is correct per the implementation, so no real inaccuracy here."
  ],
  "complete_enough": true
}
