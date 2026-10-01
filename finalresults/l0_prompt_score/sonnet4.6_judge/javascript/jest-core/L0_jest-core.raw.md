# L0 Prompt Review: jest-core

## Summary
The jest-core prompt is highly detailed for a complex orchestration library. It specifies the three core tested classes (FailedTestsCache, ReporterDispatcher, SnapshotInteractiveMode) with precise behavioral contracts, covering nearly all blackbox test scenarios.

## Completeness (4.5)
FailedTestsCache filter logic with testExecError edge case, all ReporterDispatcher methods including fallbacks and side effects, all SnapshotInteractiveMode states and key mappings — all documented. SearchSource and TestScheduler listed as modules. jest-test-utils-shim.js requirement included. Minor gap: pipe.write behavior in SnapshotInteractiveMode is mentioned but not specified.

## Unambiguity (4.2)
FailedTestsCache criteria are clearly stated. ReporterDispatcher fallback methods explicit. SnapshotInteractiveMode key-to-action mapping is listed. The abort() callback invocation with (null, false) is implied but not precisely typed.

## Testability (4.4)
All blackbox test scenarios map directly to stated behavioral constraints. The shim requirement is documented, which is essential for the test harness to work. An implementer has enough information to write all the tested behaviors.

## Consistency (4.3)
No conflicts. Minor note: abort calling onConfigChange(null, false) is correctly implied from "notifies config callback that no assertion is pending" but the exact call signature is not spelled out, requiring inference.

## Overall: 4.35
