# L0 Prompt Review: script

## Summary
The script prompt covers the chainable Pipe API with sources, filters, and sinks. The behavioral constraints are well-targeted at testable edge cases.

## Completeness (4.5)
Sources (NewPipe, File, Exec, Echo, Stdin, Get, Slice) and key filters (Match, MatchRegexp, Reject, RejectRegexp, First, Last, Column, JQ, Join, Replace, ReplaceRegexp, CountLines, String, Basename, Dirname, Freq, EncodeBase64, DecodeBase64, ExitStatus) are covered. Behavioral constraints address the most-tested edge cases. Minor gaps: additional sinks (WriteFile, AppendFile, Bytes) and sources like ListFiles/FindFiles are not mentioned. The error propagation model is not explicitly described.

## Unambiguity (4.0)
Precise constraints: First(n<=0) produces empty output, First(n>total) returns all, Freq descending frequency + alphabetical tie-breaking, Column skipping short lines, Reject('') rejects all (empty string contained in every line), JQ string results include JSON quoting. The standard base64 encoding (not URL-safe) is specified for EncodeBase64.

## Testability (4.5)
Blackbox tests cover Match/Reject/MatchRegexp/RejectRegexp, First/Last, Column, CountLines, Basename, Dirname, Freq, ReplaceRegexp with capture groups, EncodeBase64/DecodeBase64, chaining multiple filters, error propagation. All are addressed by the prompt.

## Consistency (5.0)
No contradictions with actual source. Module path and API names are accurate. Filter semantics match the library's behavior.
