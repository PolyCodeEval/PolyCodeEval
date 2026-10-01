{
  "score": 4.9,
  "reason": "The description matches the implementation very closely. It correctly states that the function checks for an `extends` token, parses the following type inside a context that disallows conditional types, and returns the parsed constraint only when conditional types are already disallowed or when no `?` follows. It also correctly notes that nothing happens when `extends` is absent. This is essentially the full behavior of the function, with only minor omission of exact helper/method names and the fact that falling through returns `undefined` implicitly.",
  "missing_functionality": [
    "It does not explicitly mention that the function returns `undefined` implicitly when `extends` is absent or when `extends` is present and a `?` follows outside the disallowed-conditional-types context."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
