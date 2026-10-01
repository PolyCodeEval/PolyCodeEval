{
  "score": 4.6,
  "reason": "The description accurately captures all major behaviors: building args with optional CHARSET prefix, normalizing criteria, sending via raw untagged command, parsing the result, raising InvalidCriteriaError on BAD responses with a user-friendly message including original error text and criteria, and re-raising other exceptions unchanged. One minor gap is that the description says the error message includes 'a documentation link' but doesn't mention the specific criteria formatting logic (quoting non-list criteria with double quotes vs. passing list criteria as-is). This is a secondary detail that wouldn't block a correct implementation.",
  "missing_functionality": [
    "The criteria formatting in the error message — non-list criteria are wrapped in double quotes ('\"criteria\"') while list criteria are passed as-is — is not mentioned."
  ],
  "incorrect_or_misleading_points": [
    "The description says the error message includes 'the supplied criteria' which is true but slightly understates the conditional formatting applied to the criteria value before inclusion."
  ],
  "complete_enough": true
}
