{
  "score": 4.8,
  "reason": "The description matches the implementation very closely. It correctly covers formatting stored duration parts into an ISO-8601 duration string, folding weeks into days, omitting zero-valued units, handling fractional seconds from milliseconds with rounding to three decimals, adding a leading minus sign when any unit is negative, conditionally inserting `T` only for time components, and returning `P0D` when nothing is emitted. It is also detailed enough to implement the function with the main behaviors preserved. The only small gap is that the implementation relies on a helper for per-unit formatting/negative detection, so exact edge behavior for formatting individual numbers is not fully specified here.",
  "missing_functionality": [
    "The description does not explicitly mention that negativity is determined from the formatted helper results for each unit rather than from a single aggregate duration value.",
    "It does not state that days are coerced with unary `+` and defaulted to 0 before adding weeks, though this is a minor implementation detail."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
