{
  "score": 4.2,
  "reason": "The description accurately captures the two-stage processing pipeline, the ordering rationale (item-level processors before collection-level ones), and the chaining of output from stage one into stage two. It correctly identifies that context (`many`, `original_data`) is forwarded to both stages. The main gap is that the description uses vague language like 'individual items or on the already-expanded collection shape' instead of the precise `pass_collection=False` / `pass_collection=True` distinction, which is the actual mechanism. A developer could still implement the function correctly from this description, though they'd need to infer the `pass_collection` flag semantics.",
  "missing_functionality": [
    "No mention of the `pass_collection` parameter that controls the two stages — this is the concrete mechanism distinguishing the two `_invoke_processors` calls.",
    "The `tag` parameter's role is not described at all."
  ],
  "incorrect_or_misleading_points": [
    "Saying 'operates on individual items or on the already-expanded collection shape' is an imprecise paraphrase of `pass_collection=False`; it could mislead about what the flag actually controls."
  ],
  "complete_enough": true
}
