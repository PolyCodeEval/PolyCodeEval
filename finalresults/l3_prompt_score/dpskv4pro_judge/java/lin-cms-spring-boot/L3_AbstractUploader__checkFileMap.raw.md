{
  "score": 3.5,
  "reason": "The description accurately covers the empty check and counting of non-empty files, but fails to mention that the validation results in a FileTooManyException with code 10121 when the count exceeds the maximum. This omission makes the description insufficient for a complete implementation.",
  "missing_functionality": [
    "Throw FileTooManyException(10121) when number of non-empty files exceeds configured maximum"
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": false
}
