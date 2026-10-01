{
  "score": 5.0,
  "reason": "The description matches the implementation very closely. It correctly covers the zero-to--1 default expiration normalization, creation of the sharded cache wrapper with the requested shard count, conditional startup of the janitor only when the cleanup interval is positive, and registration of a finalizer to stop the janitor when the wrapper is no longer reachable. These are the function's substantive behaviors, and the description is sufficient to implement the function.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
