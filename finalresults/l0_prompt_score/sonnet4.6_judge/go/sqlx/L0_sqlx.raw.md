# L0 Prompt Review: sqlx

## Summary
The sqlx prompt focuses on bind variable rebinding, named query compilation, and In expansion — the main areas tested in the blackbox suite. The default driver mappings are exhaustively listed.

## Completeness (4.5)
Core functions (Open, Connect, NewDb, Get, Select, NamedExec), bind/rebind helpers (BindType, BindDriver, Rebind, In, Named, BindNamed), bind-type constants (UNKNOWN, DOLLAR, QUESTION, NAMED, AT), and all default driver-to-bind-type mappings are present. The :: escape and := non-parameter rules are specified. Missing: the sqlx type hierarchy (DB, Tx, Stmt, Row, Rows) and struct scanning behavior are not described in detail, but since the blackbox tests focus on bind/rebind/named/in, this is acceptable.

## Unambiguity (4.0)
The NAMED bind type Rebind output (:arg1, :arg2) is stated. UNKNOWN leaves query unchanged. In expansion error conditions (mismatch between ? count and args) are specified. :: escape to literal colon and := not treated as named param are explicitly stated. Default driver mappings are complete. Named() output uses ? placeholders (QUESTION). The struct scanning behavior (db tag, Get/Select) is mentioned but not detailed.

## Testability (4.5)
Blackbox tests cover BindType for postgres/mysql/sqlite3/oci8/sqlserver, Rebind for DOLLAR/QUESTION/AT/NAMED bind types, Named with struct/map/missing field, In with slice expansion and error cases. All these are precisely described in the prompt. The ::escape and := rules are explicitly tested (test_extended_test.go implied by sqlx extended tests).

## Consistency (5.0)
All driver-to-bind-type mappings, Rebind behavior, NAMED rebind format (:arg1), and In semantics match sqlx's actual implementation.
