{
  "score": 5.0,
  "reason": "The description matches the implementation very closely. It correctly states that the function gets the current authenticated user from local context, verifies the old password using the current user's identity, throws `ParameterException(10032)` on verification failure, attempts to change to the new password, throws `FailedException(10011)` if that update fails, and returns the current user on success. It is also complete enough to reproduce the implemented behavior.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
