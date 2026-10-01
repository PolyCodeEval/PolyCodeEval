# L0 Prompt Review: redis-cache

## Summary

The redis-cache prompt is well-specified for the tested classes: RedisConfig, JDKSerializer, KryoSerializer, DummyReadWriteLock. All tested behaviors are covered.

## Completeness (4.5)
RedisConfig covers all fields and defaults (host=127.0.0.1, port=6379, database=0, ssl=false, password=null, clientName=null, serializer=JDKSerializer.INSTANCE) with guard clauses for null/empty strings. JDKSerializer and KryoSerializer cover serialize/unserialize byte-array API and null handling. DummyReadWriteLock covers same-lock-instance behavior and newCondition returning null. Public INSTANCE singletons are specified.

## Unambiguity (4.5)
Guard-clause behaviors are precisely stated: setHost(null/empty)->fallback, setPassword(null/empty)->store null, setClientName(null/empty)->store null. Default values are matched to Jedis Protocol constants. DummyReadWriteLock returning same object for both readLock/writeLock and newCondition null are explicit.

## Testability (4.5)
All blackbox tests (RedisConfig defaults, setter guard clauses, serializer round-trips for various types, unserialize(null) returns null, DummyReadWriteLock same-instance check, newCondition null) are directly derivable from the prompt specification.

## Consistency (4.5)
The DummyReadWriteLock source confirms implementation matches prompt (both locks return same DummyLock, newCondition returns null). The prompt notes DummyReadWriteLock as a public class though source is package-private — tests in the same package work fine. No functional conflicts.

## Overall: 4.50
