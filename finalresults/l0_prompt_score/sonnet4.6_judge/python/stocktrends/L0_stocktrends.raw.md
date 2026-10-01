# L0 Prompt Review: stocktrends

## Summary

The stocktrends prompt is very detailed for an indicators library. It explicitly states all class-level integer constants, method return behaviors, and the stub/None return for PRICE_MOVEMENT chart type, making it unusually complete for an L0 specification.

## Strengths
- All four Instrument constants with explicit integer values
- Renko constants (PERIOD_CLOSE, PRICE_MOVEMENT, TREND_CHANGE_DIFF) with values
- Renko.PRICE_MOVEMENT stub returning None specified
- LineBreak default line_number=3 stated
- PnF.get_state() return values for all four branches described
- PnF.brick_size as read-only property
- Instrument._validate_df ValueError behavior described

## Weaknesses
- period_close_bricks() |close-open|=brick_size contract not explicitly stated
- The cdf attribute used by LineBreak reversal methods is not mentioned

## Overall Assessment
Score 4.5/5.0 — excellent specification for a financial indicators library with precise constant values.
