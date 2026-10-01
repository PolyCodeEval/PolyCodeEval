# L0 Prompt Review: mitt

## Summary
The mitt prompt is excellent — it is precise, concise, and covers all tested behaviors. It documents every behavioral constraint that the blackbox tests exercise, with no ambiguity.

## Completeness (4.8)
Factory function, on/off/emit, all Map, pre-existing map injection, off without handler, off with handler, emit cycle isolation, wildcard two-arg, wildcard fires without specific handlers, symbol events, all.clear(), ordering (specific before wildcard). Also specifies devDependencies (mocha/chai) and bundle script requirement. Comprehensive coverage.

## Unambiguity (4.7)
All constraints are precisely worded. off(type) -> []. off(type, handler) -> removes reference. wildcard gets (type, payload). specific handlers before wildcard. Handlers added during emit not called in same cycle. No significant ambiguities.

## Testability (4.8)
Directly maps to all three test files (on-emit, off-wildcard, advanced-edge-cases). Every tested behavior has a corresponding constraint in the prompt.

## Consistency (4.8)
No conflicts. All behavioral statements match observed test assertions exactly.

## Overall: 4.78
