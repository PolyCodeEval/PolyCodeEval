# L0 Prompt Review: portalocker

## Summary

The portalocker prompt covers the class/function inventory and key utility behaviors well, but leaves several important behavioral contracts unspecified. In particular, open_atomic's assertion on existing files, Lock's re-acquire same-fh behavior, w-mode truncation, and RLock over-release exception handling are not described.

## Strengths
- All exported names listed including BoundedSemaphore, NamedBoundedSemaphore, PidFileLock
- LockFlags members (EXCLUSIVE, SHARED, NON_BLOCKING, UNBLOCK) and aliases described
- coalesce semantics clearly specified with test_value default
- LockException.LOCK_FAILED=1 and fh/strerror parameters stated
- PidFileLock.read_pid() and NamedBoundedSemaphore.get_filenames() described

## Weaknesses
- open_atomic: no mention of AssertionError on existing file or pathlib.Path support
- Lock: re-acquire returns same fh not described; w-mode truncation not described
- RLock: over-release raising LockException not described
- TemporaryFileLock lifecycle (file creation/deletion on acquire/release) not described

## Overall Assessment
Score 3.75/5.0 — good inventory coverage but notable behavioral gaps for advanced lock features tested in blackbox tests.
