# L0 Prompt Review: babel-parser

## Summary

The babel-parser prompt is detailed and covers the core parsing APIs very well. It documents all major options, plugin constraints, error cases, and output shapes needed to implement the library and pass the blackbox tests.

## Completeness (4.5)
Covers parse, parseExpression, tokTypes, getLine/getColumn (with out-of-bounds error), all key option behaviors (tokens, ranges, locations, sourceFilename, startLine, allowReturn/AwaitOutsideFunction, allowImportExportEverywhere, createParenthesizedExpressions, annexB, errorRecovery), plugin validation rules, and File node structure (errors, comments). Minor miss: allowNewTargetOutsideFunction is only indirectly referenced in the sourceType:commonjs restriction.

## Unambiguity (4.3)
Core interfaces are clearly specified. The packed location mode, tokTypes key structure, comment types, and plugin conflict errors are well described. Minor ambiguity: the exact error message for startLine>1 validation is not quoted verbatim, and strictMode on parseExpression gets only brief treatment.

## Testability (4.5)
All blackbox test scenarios are covered by the prompt: options tests, allowReturn/Await outside function, unambiguous sourceType, createParenthesizedExpressions, annexB constraints, errorRecovery, comments array, plugin conflicts. An implementer can produce a correct implementation from the prompt alone.

## Consistency (4.5)
No conflicts between prompt and tests. annexB:true throws matches tests. Comment type names (CommentLine/CommentBlock) match. errors array on File node matches. No incorrect behavioral claims found.

## Overall: 4.45
