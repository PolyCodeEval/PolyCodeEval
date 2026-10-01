{
  "score": 4.8,
  "reason": "The description matches the implementation closely: it correctly explains that the function wraps an `http.ResponseWriter`, checks supported optional interfaces, uses `protoMajor` to choose between HTTP/2 and non-HTTP/2 paths, and returns progressively more capable wrapper types based on interface support. It also correctly notes the fallback to a basic wrapper when no relevant capabilities are present. The only notable omission is that for HTTP/2 the function does not consider hijacking or `io.ReaderFrom` at all, and for non-HTTP/2 `io.ReaderFrom` only matters in combination with both flushing and hijacking. Those details are minor enough that the description is still sufficient to reimplement the function.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
