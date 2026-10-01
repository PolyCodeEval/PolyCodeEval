# L0 Prompt Review: marshmallow

## Summary

The marshmallow prompt is comprehensive and covers the broad API surface of the library. It names all key classes, fields, validators, decorators, and constants. The behavioral constraints focus on the less-obvious contracts (EXCLUDE/RAISE/INCLUDE semantics, missing sentinel, validates_schema timing).

## Strengths
- All major field types listed including Dict, Nested, List, Url
- All validator classes named including Equal and NoneOf, with Length.equal kwarg
- Unknown field handling constants with exact string values
- missing sentinel described as falsy
- validates_schema timing (after field validation) described
- partial=True and partial=("field",) loading forms described
- load_only and dump_only field parameters mentioned

## Weaknesses
- Error message structure (dict of field -> list of strings) not described
- Complex Nested/List behavior for many=True not spelled out
- Schema metaclass (SchemaMeta) mentioned but not described

## Overall Assessment
Score 4.25/5.0 — strong coverage of the API surface with good behavioral detail for the key contracts.
