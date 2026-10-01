# L0 Prompt Review: geotext

## Summary

The geotext prompt is well-written and covers all the behavioral nuances needed for implementation. The constraints section clearly specifies the three-source aggregation for country_mentions, the ISO code format, ordering, and the exclusion of country names from cities.

## Strengths
- All four public attributes described with types
- country_mentions aggregation from three sources (cities + countries + nationalities), +1 per occurrence
- ISO 3166-1 alpha-2 key format explicitly stated
- Most-to-least frequency ordering for country_mentions
- Country names excluded from cities list
- Duplicates allowed in list attributes
- Empty/whitespace input produces empty results

## Weaknesses
- How bundled data files should be structured/named is described at high level only; the concrete file format is left to the implementor

## Overall Assessment
Score 4.5/5.0 — strong specification. The behavioral constraints directly map to the blackbox test cases.
