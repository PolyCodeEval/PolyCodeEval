# L0 Prompt Review: people_management

## Summary

The people_management prompt is thorough with detailed behavioral constraints for each method, CLI parsing utilities, status code definitions, and file layout. The SQLite-backed design is clearly communicated, and the mentorship relationship semantics (type=1 for students, type=2 for mentors, upsert behavior) are precisely specified.

## Dimension Notes

- **Completeness (4.5):** All public methods and free functions are specified. The three-table SQLite schema is named. Status codes are defined. Per-method validation rules are listed for add, search, delete_record, update, and mentor. Minor gap: the exact list of valid option keys for add/person is not fully enumerated, though -name/-age/-school/-type/-id are implied by the constraint descriptions.

- **Unambiguity (4.5):** The return-code semantics per method are enumerated. The mentor.assign upsert behavior (update existing row, not duplicate) is stated. The build_options exit behavior on invalid keys is specified. Numeric error codes (FAILURE=6, INVALID_OPTION=2) give implementors concrete values.

- **Testability (4.5):** Every test scenario in the blackbox tests is directly derivable: add success/fail, search empty options = NOT_ENOUGH_OPTIONS, delete missing id, update missing id/field, mentor type mismatch, mentor lookup with one vs both flags. SQLite3 dependency is declared.

- **Consistency (4.5):** Verified against actual people_management.h. Class signature (methods returning int, taking string + map) matches exactly. Free functions (validate_options, build_options, handle_options) are declared as described. The common.h constants are referenced correctly.

## Overall: 4.50
