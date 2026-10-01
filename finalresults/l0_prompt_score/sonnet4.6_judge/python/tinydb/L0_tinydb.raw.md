# L0 Prompt Review: tinydb

## Summary

The tinydb prompt has excellent coverage of the API surface and describes most key behaviors. The main gap is that several error-raising contracts (no-args raises for get/contains/remove, insert non-mapping ValueError, upsert validation) are not described in the prompt but are tested in the blackbox suite.

## Strengths
- All CRUD operations listed
- Document described as dict subclass with doc_id
- db.get() overloads (cond, doc_id, doc_ids) described
- update_multiple signature and semantics described
- Query helpers (noop, map, one_of) described
- tinydb.operations module and all mutation helpers listed
- Storage backends and CachingMiddleware mentioned

## Weaknesses
- db.get()/contains()/remove() with no arguments raising RuntimeError not described
- db.insert(Document) preserving doc_id not described
- insert(non-mapping) raising ValueError not described
- upsert() with no cond/doc_id raising ValueError not described

## Overall Assessment
Score 4.13/5.0 — strong overall specification with notable gaps in error-case contracts.
