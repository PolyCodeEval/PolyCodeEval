{
  "score": 3.8,
  "reason": "The description captures the core purpose correctly: this is a decorator factory that enforces a capability check and raises `CapabilityError` when the capability is missing. However, it is somewhat incomplete for implementation because it omits the key structure that the outer function takes a `capability` argument and returns a decorator, and that the wrapped function is called with `client, *args, **kwargs` only after checking `client.has_capability(capability)`. It also does not mention preservation of metadata via `functools.wraps`.",
  "missing_functionality": [
    "The outer function accepts a `capability` parameter and returns the actual decorator.",
    "The wrapper specifically expects the wrapped callable to receive `client` as its first argument.",
    "The capability test is performed by calling `client.has_capability(capability)`.",
    "If the check passes, the original function is invoked with `client, *args, **kwargs` and its result is returned.",
    "The implementation preserves wrapped function metadata using `functools.wraps(func)`.",
    "The raised error includes the message `Server does not support {} capability`.format(capability)."
  ],
  "incorrect_or_misleading_points": [
    "The statement that the visible context does not show explicit runtime parameters is misleading, because the implementation clearly takes an explicit `capability` argument and the wrapper takes `client, *args, **kwargs`."
  ],
  "complete_enough": false
}
