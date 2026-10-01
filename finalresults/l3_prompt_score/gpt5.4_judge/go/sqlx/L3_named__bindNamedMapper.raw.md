{
  "score": 4.9,
  "reason": "The description matches the implementation very closely. It correctly explains that the function inspects the runtime kind of `arg`, dispatches to map/array-slice/struct binding helpers, uses the supplied mapper for struct-like binding, and returns the resulting query, args, and any error. It also accurately notes the special handling for string-keyed maps and the unsupported-map-type error when conversion fails. The only notable omission is that the implementation assumes `arg` is non-nil, since it immediately calls `reflect.TypeOf(arg)` and then `Kind()` on the result.",
  "missing_functionality": [
    "The implementation does not handle a nil `arg`; it would panic because `reflect.TypeOf(arg)` can return nil and the description does not mention this assumption."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
