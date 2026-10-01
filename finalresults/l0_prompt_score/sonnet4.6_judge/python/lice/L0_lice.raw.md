# L0 Prompt Review: lice

## Summary

The lice prompt is very well-specified with detailed behavioral constraints for all six public functions plus LICENSES. It covers all edge cases tested in the blackbox tests, including the space-inside-braces requirement for extract_vars, the txt fallback for format_license, and the specific valid_year rejection criteria.

## Strengths
- All six functions described with precise behavioral constraints
- extract_vars: space-inside-braces requirement, deduplication, alphabetical sort
- generate_license: ValueError on missing key, returns StringIO
- format_license: None falls back to 'txt', supported language keys listed, returns StringIO
- get_suffix: explicit False return cases described
- valid_year: exact four ASCII digits requirement
- load_template: header=True support, IOError on unknown license
- LICENSES minimum set specified

## Weaknesses
- The exact format of comment styles (e.g., Java's /** */ vs C's /* */) is implied rather than specified

## Overall Assessment
Score 4.5/5.0 — excellent specification. Almost all blackbox test contracts are derivable from the prompt.
