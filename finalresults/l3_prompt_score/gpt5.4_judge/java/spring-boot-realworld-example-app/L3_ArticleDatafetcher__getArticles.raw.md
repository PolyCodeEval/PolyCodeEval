{
  "score": 4.7,
  "reason": "The description matches the implementation very closely: it correctly identifies the GraphQL resolver role, supported filters, use of the authenticated user, forward/backward cursor pagination, cursor parsing, connection/edges/pageInfo construction, and the local-context map keyed by slug. The main mismatch is that it says the function requires exactly one of `first` or `last`, while the implementation only rejects the case where both are absent; if both are provided, it silently prefers `first`. Aside from that overstatement, the description is complete enough to reproduce the implemented behavior.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [
    "It states that exactly one of `first` or `last` must be provided, but the implementation only throws when both are null. If both are non-null, it takes the `first` branch and ignores `last`."
  ],
  "complete_enough": true
}
