{
  "score": 3.2,
  "reason": "The description correctly identifies the core purpose — a decorator that raises `CapabilityError` when a capability is absent — and gets the error behavior right. However, it significantly undersells what is actually visible in the implementation. The description claims the 'exact wrapped return behavior is not shown' and that 'no explicit runtime parameters beyond the wrapped callable' are visible, when in fact the full implementation is present and shows: (1) `require_capability` takes a `capability` argument making it a decorator factory, not a plain decorator; (2) the wrapper passes `client` as the first positional argument and calls `client.has_capability(capability)` to perform the check; (3) on success, the original function is called and its return value is forwarded. These are implementation-critical details that the description omits or hedges on unnecessarily.",
  "missing_functionality": [
    "The function is a decorator factory that takes a `capability` string argument, not a plain decorator — this distinction is absent",
    "The wrapper explicitly passes `client` as the first argument and uses `client.has_capability(capability)` for the check",
    "On success, the wrapped function is called with the original arguments and its return value is returned — the description says this 'is not shown'"
  ],
  "incorrect_or_misleading_points": [
    "Description says 'the exact wrapped return behavior is not shown' — it is fully shown in the implementation",
    "Description says 'no explicit runtime parameters beyond the wrapped callable are visible' — the `capability` parameter is clearly present and central to the function's behavior"
  ],
  "complete_enough": false
}
