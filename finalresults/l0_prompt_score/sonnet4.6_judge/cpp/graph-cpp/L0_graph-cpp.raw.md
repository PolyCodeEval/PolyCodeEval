# L0 Prompt Review: graph-cpp

## Summary

The graph-cpp prompt is thorough in specifying custom containers (Queue, Stack), graph types (adjacency list, adjacency matrix), the Arc aggregate struct, and traversal methods. Key behavioral differences like 0-based vs 1-based locateVex indexing are explicitly called out. The main gap is that error-throwing behavior is described as "reports an error" without specifying std::out_of_range, which the tests actually check.

## Dimension Notes

- **Completeness (4.5):** All key components are present. Queue, Stack with value-returning pop(), both graph classes, Arc struct, all traversal methods, disconnected component handling. CLI program is mentioned. File layout is specified.

- **Unambiguity (4.0):** Most things are clear, but "reports an error" for empty-container operations is vague about the exception type. Also, the BFS/DFS start vertex policy is not described (the actual implementation starts at index 0 and cycles through disconnected components).

- **Testability (4.0):** Most test scenarios are derivable. The exception type gap (std::out_of_range vs generic error) is a risk — an implementation using std::runtime_error would fail EXPECT_THROW tests that specify std::out_of_range.

- **Consistency (4.5):** Verified against actual al_graph.hpp. Constructor shapes, method signatures, Arc struct definition, and locateVex 0-based indexing all match the prompt. No conflicts found.

## Overall: 4.25
