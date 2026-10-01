{
  "score": 4.8,
  "reason": "The description accurately captures all major behaviors of the implementation: the null/array type assertion, null-to-array conversion, clearing on zero size, growing by accessing new indices (which creates default null values via `operator[]`), and shrinking by erasing elements from the map with a post-condition assertion. The description is thorough and complete enough to implement the function faithfully. The only minor omission is that the shrink path is the `else` branch (i.e., it only runs when `newSize <= oldSize` and `newSize != 0`), but this is implied by the structure described.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
