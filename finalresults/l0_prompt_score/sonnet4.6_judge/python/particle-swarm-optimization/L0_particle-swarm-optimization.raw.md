# L0 Prompt Review: particle-swarm-optimization

## Summary

The PSO prompt is well-focused and covers all the key contractual details for Particle and minimize. The sentinel values for pre-evaluation state are explicitly called out, which is critical for the blackbox tests.

## Strengths
- Particle attribute names all listed
- Pre-evaluation sentinel values explicitly stated (err_i=-1, err_best_i=-1, pos_best_i=[])
- minimize signature with all parameters and return type described
- verbose=True behavior and "FINAL SOLUTION" output mentioned
- Cost function module (pso.cost_functions) and sphere function named

## Weaknesses
- Velocity initialization range [-1,1] not stated explicitly
- The personal-best update logic (only update when error improves) is implied but not stated

## Overall Assessment
Score 4.5/5.0 — excellent prompt for a small, well-scoped package.
