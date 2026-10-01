{
  "score": 5.0,
  "reason": "The description matches the implementation very closely and captures all important behaviors: required finite checks for rate/nper/pmt, defaulting non-finite presentValue and type to 0, the special nper == 0 case, normalization of type to 0/1, the zero-rate shortcut, validation of the computed growth factor, and the final future-value formula including the negated sign convention. It is also specific enough to support a faithful reimplementation.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
