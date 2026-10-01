# L0 Prompt Review: chi

## Summary
The chi prompt is comprehensive and covers the full router surface including middleware package, Chain utility, and the Context type. It is one of the more detailed prompts in this set.

## Completeness (4.5)
All HTTP method routes, Use/With/Group/Route/Mount methods, NotFound/MethodNotAllowed handlers, and the Routes interface are covered. The middleware package exports are explicitly listed with signatures for the most important ones. Chain and Walk are described. The Context type fields are enumerated. Minor gap: URL pattern matching rules ({param}, * wildcard) are mentioned but not detailed, though implementers would infer them from context.

## Unambiguity (4.0)
Most interfaces are precisely described. The Handle(pattern, h) with space-separated method+pattern behavior is explicitly called out. The nil *Context case for RoutePattern() is stated. Some middleware constructors are listed only by name without signatures, leaving some ambiguity about their exact parameters.

## Testability (4.5)
The blackbox tests thoroughly cover routes, URL params, middleware stacking, groups, mounts, Chain().Handler/HandlerFunc, and Walk. All behaviors tested are derivable from the prompt. The Chain and Routes interface descriptions are sufficient for the chain/walk tests.

## Consistency (4.5)
All described behaviors are consistent with chi's actual implementation. The module path github.com/go-chi/chi/v5 is correct, and the middleware subpackage layout is accurate.
