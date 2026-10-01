# L0 Prompt Review: cobra

## Summary
The cobra prompt is detailed and captures most of the library's surface well. The Behavioral Constraints section is especially thorough, covering identity methods, context, version, suggestions, visibility, error suppression, and flag groups.

## Completeness (4.5)
Core Command API, positional argument validators, key fields (Use, Aliases, Hidden, Deprecated, Version, SilenceErrors) are all present. Command identity methods, context inheritance, suggestion matching, and flag groups are described. Missing details: the lifecycle hooks (PersistentPreRun, PreRun, PostRun, PersistentPostRun) are mentioned as a capability category but their specific signatures and execution order are not described. Shell completion support is listed as a capability but not elaborated.

## Unambiguity (4.0)
The PositionalArgs type signature is stated precisely. Behavioral constraints use concrete examples (e.g., CommandPath "root child grandchild"). Flag group error conditions are explicitly described. The main ambiguity is the hooks section where the capability is listed but behavior and signatures are not given.

## Testability (4.5)
The blackbox tests cover all the detailed behaviors listed in the Behavioral Constraints section. The prompt provides enough detail to implement: basic execution, flag parsing, persistent flags, subcommand routing, all identity methods, context propagation, version flag, suggestions, hidden/deprecated, silence errors, and flag groups.

## Consistency (4.5)
All described behaviors match cobra's actual implementation. Module path (github.com/spf13/cobra) and pflag integration are correct.
