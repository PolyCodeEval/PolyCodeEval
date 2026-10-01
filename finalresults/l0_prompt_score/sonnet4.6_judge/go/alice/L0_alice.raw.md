# L0 Prompt Review: alice

## Summary
The alice prompt is well-structured and covers the essential surface area of this small library accurately.

## Completeness (4.5)
All public types and methods are listed: `Constructor`, `Chain`, `New`, `Then`, `ThenFunc`, `Append`, `Extend`. The three core capabilities (Creating, Applying, Extending a Chain) are correctly named. The immutability guarantee is explicitly called out. The only minor missing detail is `Then(nil)` falling back to `http.DefaultServeMux`, but this is a secondary behavioral constraint rather than a core capability.

## Unambiguity (4.0)
The module path (`github.com/justinas/alice`), package name, and all method signatures are clear from the Required Public Entry Points section. The immutability contract is made explicit. However, the exact middleware ordering guarantee (m1 wraps m2 wraps m3) is only hinted at via the example, not spelled out in prose. The Then(nil) fallback is omitted entirely.

## Testability (4.5)
The blackbox tests exercise: empty chain creation, multiple middleware ordering, ThenFunc, Append not mutating original chain, Extend, Then(nil) defaults to DefaultServeMux, and middleware short-circuiting. All of these behaviors can be implemented from the prompt. The immutability statement is critical for the mutation tests.

## Consistency (5.0)
No contradictions between the prompt and the actual source. The source `chain.go` confirms all types, method signatures, and the immutability pattern exactly as described. Module path matches.
