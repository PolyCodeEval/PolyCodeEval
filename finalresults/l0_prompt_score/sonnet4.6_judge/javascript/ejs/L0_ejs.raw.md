# L0 Prompt Review: ejs

## Summary
The ejs prompt is detailed and covers all tested APIs. It explicitly lists behavioral constraints for escapeXML, whitespace control tags, literal tags, cache, and Template class — all of which correspond directly to the blackbox test suite.

## Completeness (4.6)
All public APIs documented. Key options covered. Whitespace slurp modes (<%_, _%>), newline slurp (-%>), literal tags (<%%/%%>), localsName, destructuredLocals, cache, Template — all present. The renderFile callback API is mentioned but lightly detailed. File include behavior is acknowledged but not specified deeply.

## Unambiguity (4.4)
escapeXML escape table is explicit. Cache method names are listed. Custom delimiter suppression is explained. Render with null data is explicitly called out. Gaps in renderFile signature and include/extends semantics.

## Testability (4.5)
All blackbox test scenarios are supported by the prompt: escapeXML edge cases, render null/custom-delimiter/whitespace, literal tags, cache, Template, compile options. An implementer can pass all tests from this prompt.

## Consistency (4.6)
No conflicts between prompt and tests. All stated behaviors match test assertions. Cache API, Template API, delimiter semantics, whitespace control — all consistent.

## Overall: 4.53
