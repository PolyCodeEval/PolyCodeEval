{
  "score": 4.2,
  "reason": "The description accurately captures all three core behaviors: sending the IDLE command and storing the tag, waiting for the immediate server response, and raising IMAPClientError if a non-None response is received. The error message format and the exact condition (`resp is not None`) are correctly described. One notable omission is the `@require_capability('IDLE')` decorator, which means the function will raise an error if the server doesn't advertise IDLE capability — this is a meaningful precondition not mentioned in the description. Otherwise the description is complete enough to implement the function faithfully.",
  "missing_functionality": [
    "The function is decorated with @require_capability('IDLE'), meaning it checks that the server supports the IDLE extension before proceeding. This precondition is not mentioned in the description."
  ],
  "incorrect_or_misleading_points": [
    "The description says 'treats successful entry into IDLE as requiring no returned data from this call' — this is slightly awkward phrasing but not technically wrong; the function simply returns None implicitly on success."
  ],
  "complete_enough": true
}
