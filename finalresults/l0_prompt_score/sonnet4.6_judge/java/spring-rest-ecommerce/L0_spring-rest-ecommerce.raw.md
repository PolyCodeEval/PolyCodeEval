# L0 Prompt Review: spring-rest-ecommerce

## Summary

The spring-rest-ecommerce prompt precisely covers Cart and CartItem which are the sole targets of the blackbox tests, with two key non-obvious behavioral contracts explicitly stated.

## Completeness (4.5)
Cart (getItems/setItems, default null items) and CartItem (productId/variantId/quantity fields, no-arg constructor, equals on productId only) are fully specified. The Cart.getItems() null default and CartItem.equals() only comparing productId are both explicitly called out, which are the critical non-obvious behaviors.

## Unambiguity (4.5)
Both critical behaviors are precisely stated: Cart.getItems() returns null by default (not empty list), CartItem.equals() compares only on productId (not variantId or quantity). Field types are specified (long productId, long variantId, int quantity). No significant ambiguity.

## Testability (4.5)
All blackbox test scenarios (null default, set/get items, CartItem defaults to zero, equals with same productId different other fields, not-equal with different productId, mutable list reference) are directly derivable from the prompt specification.

## Consistency (4.5)
No conflicts. The null default for getItems() is specified and tested. CartItem.equals() on productId only is specified and the test explicitly uses same productId with different variantId/quantity to verify equality. Default Java primitive values (0L, 0) are consistent with tests.

## Overall: 4.50
