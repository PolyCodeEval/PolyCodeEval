{
  "score": 5.0,
  "reason": "The description accurately captures every behavioral branch in the implementation: NaN for non-finite required inputs, zeroing of non-finite optional inputs, early return of 0 for nper==0, NaN for rate<=-1, type coercion to 0/1, the zero-rate shortcut formula, the power-term guard, and the full annuity-plus-future-value formula with negation and discounting. The order of checks matches the code, the formulas are correctly described, and no false claims are made. A developer could implement the function from this description alone without missing any important edge case.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
