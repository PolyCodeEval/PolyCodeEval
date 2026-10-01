{
  "score": 4.8,
  "reason": "The description matches the implementation very closely: it correctly describes the fixed prefix/suffix, the conditional left and right ranges, the spacing rule when both are present, the length calculations using removed/added plus common lines, and the newline at the end. It is also sufficiently complete to reimplement the function. The only minor issue is that it adds an explicit edge-case statement about emitting a bare header when neither side is present; while that does follow from the implementation, this case is not especially meaningful in typical use and slightly over-specifies behavior beyond the core intent.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
