{
  "score": 4.9,
  "reason": "The file-level and function-level descriptions match the implementation very closely and cover the core reconstruction-critical behavior: named-parameter compilation, bind-style rewriting, argument extraction from structs/maps/slices, batch VALUES expansion, NamedStmt preparation, and dispatch logic. The prompt is detailed enough to reproduce nearly all hollowed functions with correct control flow, error behavior, and output structure. Only a few small implementation-specific details are omitted or slightly overstated.",
  "missing_functionality": [
    "The description does not explicitly mention bindMap, although it is a small helper present in the file; however it is not one of the hollowed functions.",
    "convertMapStringInterface in the real code does not guard against reflect.TypeOf(v) being nil; the prompt does not mention this edge case, though it likely is not needed for reconstruction.",
    "compileNamedQuery's implementation is byte-oriented rather than rune-oriented and inherits the known unicode limitation noted in comments; the prompt describes accepted name characters accurately enough but does not mention this implementation limitation."
  ],
  "incorrect_or_misleading_points": [
    "The description of findMatchingClosingBracketIndex says it scans 'runes left to right and track nesting depth until the matching closing parenthesis for the first opening parenthesis is found'; this is broadly correct, but it does not state that the real implementation starts count at 0 and assumes the substring begins with '(', returning 0 both for no match and for degenerate cases.",
    "The compileNamedQuery description slightly overgeneralizes final-byte handling by saying names may end on a final byte if the final byte is part of the name; in the implementation, the special final-byte inclusion path checks unicode letter/digit only, not underscore or dot."
  ],
  "complete_enough": true
}
