# L0 Prompt Review: xlsx2csv

## Summary

The xlsx2csv prompt is well-specified for the utility function layer that the tests primarily exercise. The string_to_idx, string_to_row_column, and strip functions have precise edge-case behaviors documented. The shared string indexing convention (index 0 = empty sentinel) is important and explicitly noted. The bundled dependency requirements (miniz, tinyxml2) are specified with exact constraints.

## Dimension Notes

- **Completeness (4.5):** Covers all public interfaces in the namespace, including the utility functions with full edge-case semantics, workbook-level (get_shared_string, write_to_csv) and the CLI entry point. File layout is precise with all required paths. The miniz.h export macro and miniz.c self-containment requirement are spelled out.

- **Unambiguity (4.5):** string_to_idx case-insensitivity, 3-character column limit, zero return for invalid inputs are all explicit. strip() whitespace character set (space, tab, newline — ASCII only) is listed. The shared string index-0 sentinel semantics are unambiguous.

- **Testability (4.5):** All blackbox utility tests (A=1, Z=26, AA=27, ZZ=702, AAA=703, AAAA=0, '1'=0, case-insensitive, cell references, strip variants) derive directly from stated constraints. The test for internal spaces preserved by strip is consistent with the "trims only from both ends" description.

- **Consistency (4.5):** Verified against test_utils.cpp: namespace, function names, return types (unsigned for string_to_idx, pair<unsigned,unsigned> for string_to_row_column, string for strip) match. Test cases (AAAA=0, '1'=0, lowercase equivalence) all match prompt constraints.

## Overall: 4.50
