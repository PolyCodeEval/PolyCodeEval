{
  "score": 4.8,
  "reason": "The description matches the implementation very closely: it correctly states the input/output parameters, the UTF-8 length thresholds, the construction of leading and continuation bytes, and the failure case for inputs >= 0x200000. It is also sufficient to reimplement the function at a practical level. The only notable omissions are low-level implementation details such as the reverse write strategy using `output += *length` and fallthrough in the switch, but those are not essential to the abstract behavior.",
  "missing_functionality": [
    "Does not mention that bytes are written from the end of the selected output span backward after advancing `output` by `*length`.",
    "Does not mention the internal use of bit shifting (`input >>= 6`) to emit continuation bytes in reverse order."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
