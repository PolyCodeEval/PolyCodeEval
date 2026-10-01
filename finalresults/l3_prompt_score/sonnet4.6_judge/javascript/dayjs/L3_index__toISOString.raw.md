{
  "score": 4.8,
  "reason": "The description accurately captures all major behaviors of the implementation: weeks-to-days conversion (×7), milliseconds converted to fractional seconds rounded to three decimal places, the negative-mode prefix logic, the conditional `T` separator, the `P` prefix, and the `P0D` fallback for empty results. The description is precise enough that a developer could implement the function correctly from it alone.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [
    "The description says 'omit it from the output when its value is zero/absent' — this is technically delegated to `getNumberUnitFormat`, whose exact behavior (returning an empty string for zero) is implied but not visible in the description. This is a minor abstraction gap, not an error."
  ],
  "complete_enough": true
}
