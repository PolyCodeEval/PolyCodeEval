{
  "score": 5.0,
  "reason": "The description matches the implementation very closely. It correctly describes argument construction, optional CHARSET handling, normalization of criteria, use of the raw untagged SEARCH command, parsing of the returned message list, and the special handling of BAD SEARCH errors by converting them into InvalidCriteriaError while re-raising other IMAP errors unchanged. It is also sufficiently complete to support implementing the function, with only very minor omissions about the exact BAD-response regex and the detail that non-list criteria are quoted in the error message.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
