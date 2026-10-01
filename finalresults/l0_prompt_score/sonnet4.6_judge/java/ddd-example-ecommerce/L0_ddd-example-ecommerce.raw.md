# L0 Prompt Review: ddd-example-ecommerce

## Summary

The ddd-example-ecommerce prompt is well-specified for the Amount and InStock classes that are the sole targets of the blackbox tests. The broader DDD application context is described but not deeply tested.

## Completeness (4.5)
Amount (constructor with non-negative validation, ZERO constant, add/subtract immutability, compareTo, equals/hashCode) and InStock (constructor, add/remove/hasEnough/needsYet/isSoldOut, immutability, null rejection) are fully covered. The needsYet edge case (returns ZERO when stock >= requested) is explicitly noted. Null rejection for add/subtract is stated.

## Unambiguity (4.5)
Key contracts are precise: Amount(negative) throws, subtract below zero throws, both are immutable and return new instances, null arguments throw NullPointerException. InStock.needsYet behavior at boundary (>= requested returns ZERO) is clearly specified.

## Testability (4.5)
All blackbox tests (Amount validation, add/subtract immutability and correctness, compareTo ordering, InStock operations, null rejection via NullPointerException, isSoldOut, chained operations) are directly derivable from the prompt.

## Consistency (4.5)
The InStock source confirms the implementation matches: delegates to Amount.subtract for remove (so rejection propagates), needsYet uses compareTo. The prompt's description aligns with actual code behavior. No conflicts.

## Overall: 4.50
