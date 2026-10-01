# L0 Prompt Review: robotstxt

## Summary

The robotstxt prompt covers the core parser and matcher API with good fidelity to the actual codebase. The namespace (googlebot), key types, RobotsMatcher, RobotsParsingReporter, and ParseRobotsTxt are all specified. The abseil dependency is declared. The reporting_robots layer is mentioned. However, the details of matching semantics (longest match wins, wildcard rules, allow-vs-disallow tiebreak) are not described in the prompt's behavioral section.

## Dimension Notes

- **Completeness (4.0):** Core classes are described. But the matching semantics (longest match wins, allow-wins-on-tie, wildcard * and $ support) that the blackbox tests verify are not specified as behavioral constraints. The `disallow_ignore_global()` and `ever_seen_specific_agent()` status accessors are listed in Example Usage. RobotsParsingReporter methods (valid_directives, unused_directives, last_line_seen) are listed.

- **Unambiguity (3.5):** The GetKeyType signature includes a typo-indicator parameter. But the matching rules governing AllowedByRobots/OneAgentAllowedByRobots are not spelled out (longest path wins, allow beats disallow on tie, wildcard syntax). An implementor could produce something that passes some tests but not those testing edge-case precedence.

- **Testability (3.5):** Basic matcher tests (empty robots allows all, DisallowAll, basic allow/disallow) are derivable. But tests for wildcard patterns, dollar-anchor, longest-match precedence, and allow-wins-on-tie require knowledge of RFC 9309 or the matching algorithm that isn't given in the prompt.

- **Consistency (4.5):** KeyType enum values and order match the actual header. GetKeyType signature (string_view key, bool* is_typo) matches. RobotsMatcher and RobotsParsingReporter method names match. ParseRobotsTxt(const char*, RobotsParsingReporter*) matches. No conflicts found.

## Overall: 3.88
