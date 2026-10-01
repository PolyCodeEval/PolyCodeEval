# L0 Prompt Review: chakin

## Summary

The chakin prompt is very detailed and well-specified. It goes beyond typical L0 descriptions by spelling out exact data constraints (23 rows, first entry, column names, Dimension type) and the urlretrieve patchability requirement critical for mocking in tests.

## Strengths
- Exact CSV row count and first entry specified
- Required column names explicitly listed
- search() return type (None) and filtering modes (empty lang = all, unknown lang = empty without error)
- download() both number and name selection modes, directory creation, returns str
- urlretrieve import path for test mocking explicitly called out

## Weaknesses
- The progress callback / reporting behavior during download is not described (minor for blackbox testing)

## Overall Assessment
Score 4.5/5.0 — excellent specification with test-critical details that are rare in L0 prompts.
