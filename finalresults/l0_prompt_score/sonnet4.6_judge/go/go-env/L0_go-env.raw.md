# L0 Prompt Review: go-env

## Summary
The go-env prompt is detailed and covers the core parsing functionality, struct tags, options, and behavioral constraints well. The generic API (ParseAs, Must) and utility functions (ToMap, GetFieldParams) are included.

## Completeness (4.5)
Parse, ParseWithOptions, ParseAs, Must, GetFieldParams, Options struct, and FieldParams are all listed. Tag options (notEmpty, expand, env:"-") are described. Options.Environment and Options.UseFieldNameByDefault are covered. Map support with envKeyValSeparator and envSeparator is present. Supported types (primitives, slices, maps, nested structs, custom parsers, Duration, URL) are mentioned. Minor gap: custom parser registration mechanism (how to register a parser function for an arbitrary type) is mentioned but the exact API isn't detailed.

## Unambiguity (4.0)
Key semantic contracts are explicitly stated: notEmpty error on empty value, expand using ${VAR} syntax, env:"-" skipping fields, UseFieldNameByDefault UPPER_SNAKE_CASE conversion rule, ToMap excluding entries without "=". The FieldParams struct fields are named. The custom parser API signature is left vague.

## Testability (4.5)
Blackbox tests cover: all primitive types (string, int, bool, float, uint, int8/16/32/64), ParseAs generic, Must panic, non-pointer error, non-struct-ptr error, notEmpty enforcement, expand, nested structs, prefix, required, separators. All tested behaviors are described in the prompt.

## Consistency (5.0)
Module path (github.com/caarlos0/env/v11) is correct. All described behaviors match the go-env source. UseFieldNameByDefault conversion rule example (ServerHost -> SERVER_HOST) is accurate.
