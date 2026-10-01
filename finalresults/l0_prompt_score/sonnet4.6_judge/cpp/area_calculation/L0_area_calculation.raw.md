# L0 Prompt Review: area_calculation

## Summary

The area_calculation prompt is well-crafted for a small geometry project. It clearly specifies the class hierarchy (Shape -> Circle, Shape -> Rectangle -> Square), the exact PI constant to use (3.14159265), the header-only constraint for Circle and Square, and the behavioral edge cases like negative dimensions. The file layout is precisely described, matching the actual source structure.

## Dimension Notes

- **Completeness (4.5):** All core capabilities are covered. The lifecycle output (constructor/destructor printing) is listed as a capability but the exact messages are not described. Since the blackbox tests don't test this directly, it's only a minor gap.

- **Unambiguity (4.5):** The numeric constants are explicit. The negative-dimension behavior is clearly defined for all shapes. The file-based CLI is noted but file format not specified — acceptable since tests target class APIs only.

- **Testability (4.5):** All test cases (unit circles, negative radius, polymorphic dispatch, Rectangle/Square delegation) are fully derivable from the prompt. The explicit PI value makes exact EXPECT_NEAR tests straightforward to implement correctly.

- **Consistency (4.5):** Cross-checked against actual Shape.h, Circle.hpp (blackbox_tests), Rectangle.h. All structure and inheritance matches. No conflicts found.

## Overall: 4.50
