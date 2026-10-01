# L0 Prompt Review: go-cache

## Summary
The go-cache prompt is one of the most thorough in the set. It enumerates every typed increment/decrement variant explicitly, which is crucial since these are tested. The behavioral constraints section is precise and covers all edge cases tested in the blackbox suite.

## Completeness (5.0)
Every public method is listed, including all 26+ typed increment/decrement variants. Serialization (Save/Load/SaveFile/LoadFile) with gob semantics is included. Key constants (NoExpiration, DefaultExpiration), the Item struct, and NewFrom are present. The janitor goroutine background behavior is mentioned. Nothing significant is missing.

## Unambiguity (4.5)
Return shapes are precisely given. The Behavioral Constraints section is exceptionally clear: Add vs Replace error conditions, Increment/Decrement error cases, ItemCount counting expired items, IncrementFloat/DecrementFloat type restrictions. The only minor ambiguity is that Load's non-overwrite semantics ("does not overwrite keys that already exist and have not expired") might not clarify what "have not expired" means in terms of time check.

## Testability (5.0)
All tested scenarios — set/get, expiration, NoExpiration, DefaultExpiration, janitor cleanup, IncrementInt/DecrementInt, Add/Replace semantics, NewFrom, GetWithExpiration — are described sufficiently to implement and verify.

## Consistency (5.0)
No contradictions with the actual source code. All method signatures, Item struct fields, and behavioral semantics match go-cache's implementation.
