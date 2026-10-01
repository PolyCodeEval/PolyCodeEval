# L0 Prompt Review: tinyexpr-plusplus

## Summary

The tinyexpr-plusplus prompt covers the te_parser API comprehensively with precise behavioral rules for all special built-in functions. The variable/function registration mechanism via te_variable is described. The error reporting APIs (success(), get_last_error_position(), npos sentinel) are specified.

## Dimension Notes

- **Completeness (4.5):** Full te_parser API including all evaluate, compile, success, result accessors, variable registration, separator configuration, and introspection methods. The behavioral constraints section is unusually thorough, covering 15+ built-in function semantics. Minor: the exact set of standard built-ins (sin/cos/tan/log/exp/etc.) is not fully enumerated, though they're implied by "common math syntax" and tested in the blackbox tests.

- **Unambiguity (4.5):** Most behavioral rules are precisely specified. Examples: round(-1) rounds left of decimal, mod(a,0) is an error, sum/average skip NaN, clamp swaps lo/hi if lo>hi, isnan/iserr/isna return 1 for non-finite. The te_variable binding forms (pointer, constant, function pointer) are described in the comment block.

- **Testability (4.5):** Blackbox tests for arithmetic, built-ins, variables, custom functions, and error handling all derive from specified behavior. The strict npos == size_t(-1) or no-error semantics are defined.

- **Consistency (4.5):** Tests use te_parser directly from tinyexpr.h, use evaluate/compile/success/is_function_used/is_variable_used — all as specified. Custom function registration uses te_variable and te_type as described.

## Overall: 4.50
