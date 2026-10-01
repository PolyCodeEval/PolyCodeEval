# L0 Prompt Review: java_heap

## Summary

The java_heap prompt is comprehensive and precise, covering FibonacciHeap, LeftistHeap, and HeapPerformanceTest with detailed behavioral contracts.

## Completeness (4.5)
FibonacciHeap covers two constructors, insert/findMin/deleteMin/delete/meld, potential formula, countersRep, totalLinks/totalCuts static counters, empty/size, and HeapNode.getKey. LeftistHeap covers isEmpty, insert, extract_min (-1 sentinel), clear, merge (empties other), and in_order (non-decreasing order). HeapPerformanceTest covers constructor and test() with exact map keys.

## Unambiguity (4.5)
Key non-obvious contracts are precisely stated: extract_min returns -1 on empty (not exception), merge empties other, in_order returns non-decreasing order, deleteMin on empty completes without error, potential = numTrees + 2*markedNodes formula, HeapPerformanceTest map keys are exact strings.

## Testability (4.5)
All major blackbox test scenarios (heap operations, sorted extraction, delete(node), meld, potential after inserts, countersRep non-negative sums, HeapPerformanceTest key names) are derivable from the prompt. The potential = count after pure inserts is testable from the formula.

## Consistency (4.5)
No conflicts. The potential formula and counters match tests. HeapPerformanceTest key strings match exactly. The -1 sentinel for empty LeftistHeap.extract_min() is consistent with tests. FibonacciHeap(int key) single-key constructor is specified and tested.

## Overall: 4.50
