# Analysis Scripts

This directory contains scripts used to reproduce paper tables, figures,
token-accounting checks, paired comparisons, and significance tests.

## Paper reproduction

`paper/` is the canonical location for the current paper-reproduction scripts.
The directory is kept flat because several scripts share `common.py` and
`figure_common.py`.

Typical entry points:

- `paper/report_project_level_tables.py`: L0/L1 result tables.
- `paper/report_l2_l3_tables.py`: L2/L3 result tables.
- `paper/report_prompt_and_construction_stats.py`: prompt-quality,
  construction-cost, and coverage summary tables.
- `paper/figure_*.py`: paper figures.
- `paper/paired_significance_tests.py`: paired significance tests used in the
  analysis section.
- `paper/compare_l2tol3_vs_l3_direct.py`: L2-to-L3 paired comparison table.
- `paper/l2tol3_vs_l3_direct_significance.py`: significance test for the
  L2-to-L3 paired comparison.

The scripts expect generated answers and final evaluation outputs to be present
locally. Those large artifacts are intentionally ignored by Git.
