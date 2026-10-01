# L0 Prompt Review: zxcvbn

## Summary

The zxcvbn prompt is very well-specified. It goes beyond listing API structure to describe specific behavioral contracts like exact warning text patterns for common password types, the timedelta type for calc_time, and the guesses_log10 formula. These match the oracle-testing approach in the blackbox suite.

## Strengths
- All return dict keys listed
- All four crack-time scenario keys explicitly named
- guesses_log10 = math.log10(guesses) stated explicitly
- calc_time as datetime.timedelta specified
- feedback warning text conventions for repeat/sequence/date/recent-year described
- Strong password produces empty warning and empty suggestions
- user_inputs non-string conversion mentioned
- sequence match required keys (pattern, token, i, j) listed

## Weaknesses
- The exact warning strings (e.g., 'Repeats like "aaa" are easy to guess.') are convention-described but the exact wording tested in tests ('Repeats like "aaa" are easy to guess.') relies on a specific implementation
- Score boundary values not described

## Overall Assessment
Score 4.5/5.0 — excellent prompt with thorough behavioral specification enabling deterministic implementation.
