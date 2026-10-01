{
  "score": 4.8,
  "reason": "The prompt matches the implementation very closely at both file and function level. It correctly describes the in-memory ZIP loading flow, error handling, extraction ownership model, XML lookup/parsing behavior, workbook sheet traversal, and shared strings handling. It is also detailed enough to reconstruct the four hollowed functions with the same control flow and key API usage. Only a few small implementation details are omitted, such as the exact stream-reading pattern and the fact that workbook/shared-string XML traversal assumes required nodes exist without null checks.",
  "missing_functionality": [
    "The constructor description does not mention the exact file reading pattern using ifstream seekg/tellg/reserve/assign from istreambuf_iterators, though it still captures the intended behavior.",
    "The descriptions do not mention that XML traversal in get_sheet_relations and get_shared_strings performs no defensive null checks on expected elements before dereferencing them."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
