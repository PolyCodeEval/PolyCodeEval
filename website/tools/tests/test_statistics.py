from __future__ import annotations

import json
import unittest
from pathlib import Path


DATA = Path(__file__).resolve().parents[2] / "public/data/statistics/significance.json"


class SignificanceExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(DATA.read_text(encoding="utf-8"))

    def test_selected_comparisons_display_holm_adjusted_p_values(self) -> None:
        codex = next(
            row
            for row in self.result["selectedComparisons"]
            if row["name"].startswith("L2 Codex-GPT-5.4")
        )

        self.assertAlmostEqual(codex["p_value"], 3.08244489133358e-05)
        self.assertAlmostEqual(codex["raw_p_value"], 6.16488978266716e-06)
        self.assertEqual(codex["adjustment"], "Holm (9 selected tests)")

    def test_rq4_full_pass_p_values_remain_unadjusted(self) -> None:
        overall = {
            row["model"]: row
            for row in self.result["l2ToL3FullPassTests"]
            if row["scope"] == "Overall"
        }

        self.assertAlmostEqual(overall["GPT-5.4"]["p_value"], 5.311823805357055e-04)
        self.assertAlmostEqual(overall["Claude Sonnet 4.6"]["p_value"], 2.2398323455481102e-14)
        self.assertEqual(overall["GPT-5.4"]["adjustment"], "None")


if __name__ == "__main__":
    unittest.main()
